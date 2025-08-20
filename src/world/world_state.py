# c:/prj/WorldDom/src/world_state.py
"""
Defines the WorldState class, a central data container for game state.

Enhancements:
- Selection groups (0..9) with bind/recall/append/merge/unbind and pruning
- Command history (bounded deque) with lightweight serialization helpers
- Transient world pings with normalized life for UI effects
- Rich selection helpers: select by predicate/tile-rect/world-rect/circle,
  smart single-click selection with cycling through overlapping units
- Unit lifecycle helpers: add/remove, bulk dead cleanup, replace all
- Query helpers: nearest unit, units-in-radius, find-by-id (stable if provided)
- Consistent syncing of Unit.selected flags
- Snapshot/debug string exports for overlay/telemetry
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Callable, Any, Iterable
from collections import deque
import math
import time

import pygame

from src.ui.context_menu import ContextMenuState
from src.entities.unit import Unit

# Type-only import to avoid circular dependencies at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.commands import Command  # noqa: F401

Vec2 = pygame.math.Vector2

# ----------------------------------- Small helper dataclasses -----------------------------------


@dataclass
class WorldPing:
    """Transient world-space ping/marker (for right-clicks, alerts, etc.)."""
    world_pos: Vec2
    ttl: float = 1.5
    color: Tuple[int, int, int] = (255, 215, 0)  # gold
    radius: int = 12
    _life: float = field(init=False, repr=False, default=0.0)

    def __post_init__(self) -> None:
        # Cache initial life for normalized progress
        self._life = max(1e-6, float(self.ttl))
        if not isinstance(self.world_pos, Vec2):
            self.world_pos = Vec2(self.world_pos)

    def update(self, dt: float) -> None:
        self.ttl = max(0.0, self.ttl - max(0.0, dt))

    @property
    def alive(self) -> bool:
        return self.ttl > 0.0

    @property
    def norm(self) -> float:
        """Normalized remaining life in [0,1] (1 = new, 0 = expired)."""
        return max(0.0, min(1.0, self.ttl / self._life))


@dataclass
class CommandRecord:
    """A lightweight record of issued commands for replay/analytics/undo."""
    timestamp: float
    command_json: Dict[str, Any]  # Command serialized via Command.to_dict()
    unit_ids: List[int]           # Python id(unit) snapshot for reconciliation


@dataclass
class SelectionCycleState:
    """
    State for cycling through overlapping units at a click point.
    Cycle resets if the anchor moves too far or times out.
    """
    active: bool = False
    anchor_world: Optional[Vec2] = None
    units: List[Unit] = field(default_factory=list)
    index: int = 0
    radius_px: float = 28.0
    timeout_s: float = 0.9
    expires_at_game_time: float = 0.0

    def reset(self, world_pos: Vec2, units: List[Unit], game_time: float, radius_px: float) -> None:
        self.active = True
        self.anchor_world = Vec2(world_pos)
        self.units = list(units)
        self.index = 0
        self.radius_px = float(radius_px)
        self.expires_at_game_time = float(game_time) + self.timeout_s

    def expired(self, now_game_time: float) -> bool:
        return not self.active or (now_game_time >= self.expires_at_game_time)

    def bump(self, now_game_time: float) -> None:
        """Extend cycle a bit when user continues cycling."""
        self.expires_at_game_time = float(now_game_time) + self.timeout_s

    def next_index(self) -> int:
        if not self.units:
            return 0
        self.index = (self.index + 1) % len(self.units)
        return self.index


# -------------------------------------- Module constants ----------------------------------------

DEFAULT_COMMAND_HISTORY_MAX = 300
SELECTION_CYCLE_MAX_DISTANCE_PX = 16.0  # re-use existing cycle if cursor stays near anchor


# --------------------------------------------- State --------------------------------------------

@dataclass
class WorldState:
    """
    A data class to hold the current state of all game entities, selections,
    and UI interactions. Initializing attributes here prevents runtime errors.
    """
    # --- Game Entities ---
    units: List[Unit] = field(default_factory=list)

    # --- Player Selections & Actions ---
    selected_units: List[Unit] = field(default_factory=list)
    hovered_tile: Optional[Tuple[int, int]] = None
    hovered_world_pos: Optional[Vec2] = None
    selection_box: Optional[pygame.Rect] = None

    # --- UI State ---
    context_menu: ContextMenuState = field(default_factory=ContextMenuState)

    # --- Raw Input State (for tracking drags, etc.) ---
    left_mouse_down_screen_pos: Optional[Tuple[int, int]] = None
    left_mouse_down_world_pos: Optional[Vec2] = None
    right_mouse_down_pos: Optional[Tuple[int, int]] = None

    # --- System/Session State ---
    game_time: float = 0.0
    paused: bool = False

    # Selection groups (0..9) store *references* to units (filtered on recall)
    selection_groups: Dict[int, List[Unit]] = field(default_factory=dict)

    # Rolling command history (serialized) for analytics/undo/replay
    command_history: deque[CommandRecord] = field(
        default_factory=lambda: deque(maxlen=DEFAULT_COMMAND_HISTORY_MAX)
    )

    # Transient world pings/markers
    pings: List[WorldPing] = field(default_factory=list)

    # Smart single-click cycling state
    selection_cycle: SelectionCycleState = field(default_factory=SelectionCycleState)

    def __post_init__(self) -> None:
        # Initialize empty selection groups 0..9
        if not self.selection_groups:
            self.selection_groups = {i: [] for i in range(10)}
        # Ensure Unit.selected flags match selected_units on construction
        self._sync_selection_flags()

    # ------------------------------------ Time & housekeeping ------------------------------------

    def tick(self, dt: float) -> None:
        """Advance world-time counters and decay transient elements (pings)."""
        if not self.paused:
            self.game_time += max(0.0, dt)

        # Update pings and cull dead
        for p in self.pings:
            p.update(dt)
        self.pings = [p for p in self.pings if p.alive]

        # Expire the selection cycle window if needed
        if self.selection_cycle.active and self.selection_cycle.expired(self.game_time):
            self.selection_cycle = SelectionCycleState()  # reset

    # Back-compat alias if some callers use `update`
    update = tick

    # ------------------------------------ Unit lifecycle ----------------------------------------

    def add_unit(self, unit: Unit) -> None:
        self.units.append(unit)

    def remove_unit(self, unit: Unit) -> None:
        """Remove a unit and clean up selections/groups."""
        if unit in self.units:
            self.units.remove(unit)
        if unit in self.selected_units:
            self.selected_units.remove(unit)
        # Clean up in groups
        for k in list(self.selection_groups.keys()):
            if unit in self.selection_groups[k]:
                self.selection_groups[k] = [u for u in self.selection_groups[k] if u is not unit]
        self._sync_selection_flags()

    def replace_all_units(self, new_units: Iterable[Unit]) -> None:
        """Replace current world units (e.g., after generating a new map)."""
        self.units = list(new_units)
        self.selected_units.clear()
        # Prune all groups to alive units
        self.prune_groups()
        self._sync_selection_flags()

    def clear_dead_units(self, is_dead: Callable[[Unit], bool] | None = None) -> int:
        """
        Remove dead units from world and selections. By default, uses a heuristic
        (hp <= 0 if present) else keep all. Returns number of removed units.
        """
        def default_dead(u: Unit) -> bool:
            return hasattr(u, "hp") and getattr(u, "hp") <= 0

        dead_pred = is_dead or default_dead
        before = len(self.units)
        to_remove = [u for u in self.units if dead_pred(u)]
        for u in to_remove:
            self.remove_unit(u)
        return before - len(self.units)

    # ---------------------------------------- Queries --------------------------------------------

    def units_in_world_circle(self, center: Tuple[float, float] | Vec2, radius_px: float) -> List[Unit]:
        """Return units whose world_pos is within radius from center (Euclidean)."""
        c = Vec2(center)
        r2 = float(radius_px) ** 2
        return [u for u in self.units if (u.world_pos - c).length_squared() <= r2]

    def units_in_world_rect(self, rect: pygame.Rect) -> List[Unit]:
        """Return units whose world rect intersects rect (world-space)."""
        out: List[Unit] = []
        for u in self.units:
            if u.get_world_rect().colliderect(rect):
                out.append(u)
        return out

    def nearest_unit(self, world_pos: Tuple[float, float] | Vec2) -> Optional[Unit]:
        """Return unit nearest to a world point (naive scan)."""
        p = Vec2(world_pos)
        best_u: Optional[Unit] = None
        best_d2 = math.inf
        for u in self.units:
            d2 = (u.world_pos - p).length_squared()
            if d2 < best_d2:
                best_d2, best_u = d2, u
        return best_u

    def find_unit_id(self, u: Unit) -> int:
        """Try to return a stable ID if unit exposes 'unit_id', else fallback to id()."""
        if hasattr(u, "unit_id"):
            try:
                return int(getattr(u, "unit_id"))
            except Exception:
                pass
        return id(u)

    # -------------------------------------- Selection helpers ------------------------------------

    def _sync_selection_flags(self) -> None:
        """Set Unit.selected flags to match selected_units membership."""
        selected_set = set(self.selected_units)
        for u in self.units:
            u.selected = u in selected_set

    def clear_selection(self) -> None:
        self.selected_units.clear()
        self._sync_selection_flags()

    def has_selection(self) -> bool:
        return bool(self.selected_units)

    def select_only(self, units: Iterable[Unit]) -> List[Unit]:
        self.selected_units = list(dict.fromkeys(u for u in units if u in self.units))
        self._sync_selection_flags()
        return list(self.selected_units)

    def select_units(
        self,
        predicate: Callable[[Unit], bool],
        *,
        additive: bool = False,
        toggle: bool = False,
        max_units: Optional[int] = None,
    ) -> List[Unit]:
        """
        Generic selection by predicate. Returns the final selected list.
        """
        candidates = [u for u in self.units if predicate(u)]
        if toggle:
            # Toggle membership for candidates
            for u in candidates:
                if u in self.selected_units:
                    self.selected_units.remove(u)
                else:
                    self.selected_units.append(u)
        else:
            if not additive:
                self.selected_units.clear()
            # Keep order stable and unique
            for u in candidates:
                if u not in self.selected_units:
                    self.selected_units.append(u)

        if max_units is not None and len(self.selected_units) > max_units:
            self.selected_units = self.selected_units[:max_units]

        self._sync_selection_flags()
        return list(self.selected_units)

    def select_by_tile_rect(
        self,
        top_left: Tuple[int, int],
        bottom_right: Tuple[int, int],
        *,
        additive: bool = False,
        toggle: bool = False,
    ) -> List[Unit]:
        """
        Select all units with tile_pos inside the inclusive tile-rectangle.
        """
        (x0, y0) = top_left
        (x1, y1) = bottom_right
        x_lo, x_hi = sorted((x0, x1))
        y_lo, y_hi = sorted((y0, y1))

        return self.select_units(
            lambda u: x_lo <= int(u.tile_pos.x) <= x_hi and y_lo <= int(u.tile_pos.y) <= y_hi,
            additive=additive,
            toggle=toggle,
        )

    def select_by_world_rect(self, world_rect: pygame.Rect, *, additive: bool = False, toggle: bool = False) -> List[Unit]:
        """Select all units whose world rect intersects the given world-space rect."""
        return self.select_units(
            lambda u: u.get_world_rect().colliderect(world_rect),
            additive=additive,
            toggle=toggle,
        )

    def select_by_world_circle(self, center: Tuple[float, float] | Vec2, radius_px: float, *, additive: bool = False) -> List[Unit]:
        """Select units within a world-space circle."""
        c = Vec2(center)
        r2 = float(radius_px) ** 2
        return self.select_units(lambda u: (u.world_pos - c).length_squared() <= r2, additive=additive)

    def toggle_unit(self, unit: Unit) -> None:
        if unit in self.selected_units:
            self.selected_units.remove(unit)
        else:
            if unit in self.units:
                self.selected_units.append(unit)
        self._sync_selection_flags()

    def center_of_selection(self) -> Optional[Vec2]:
        """Average world_pos of current selection (wrap-agnostic)."""
        if not self.selected_units:
            return None
        sx = sum(u.world_pos.x for u in self.selected_units)
        sy = sum(u.world_pos.y for u in self.selected_units)
        return Vec2(sx / len(self.selected_units), sy / len(self.selected_units))

    def smart_select_at_point(
        self,
        world_point: Tuple[float, float] | Vec2,
        *,
        radius_px: float = 28.0,
        cycle: bool = True,
        additive: bool = False,
    ) -> List[Unit]:
        """
        Single-click selection that cycles through overlapping units when repeatedly clicked.
        - If multiple units under cursor, cycles among them within a small timeout window.
        - If additive=True, adds the cycled unit to current selection.
        """
        p = Vec2(world_point)
        under_cursor = self.units_in_world_circle(p, radius_px)

        if not under_cursor:
            if not additive:
                self.clear_selection()
            return list(self.selected_units)

        # Decide whether to re-use the existing cycle or start a new one
        reuse = False
        sc = self.selection_cycle
        if cycle and sc.active and not sc.expired(self.game_time) and sc.anchor_world is not None:
            if (sc.anchor_world - p).length_squared() <= (SELECTION_CYCLE_MAX_DISTANCE_PX ** 2):
                # Reuse previous candidate list if it matches current units set (order may differ)
                if set(sc.units) == set(under_cursor):
                    reuse = True
                    sc.bump(self.game_time)

        # (Re)initialize cycle if needed
        if not reuse:
            # Sort candidates by distance for a consistent cycle order
            under_cursor.sort(key=lambda u: (u.world_pos - p).length_squared())
            sc.reset(p, under_cursor, self.game_time, radius_px)

        # Pick current unit, then advance index for next invocation
        unit = sc.units[sc.index]
        sc.next_index()

        if additive:
            if unit not in self.selected_units:
                self.selected_units.append(unit)
        else:
            self.selected_units = [unit]

        self._sync_selection_flags()
        return list(self.selected_units)

    # --------------------------------------- Selection groups -------------------------------------

    def bind_group(self, index: int) -> None:
        """Bind the current selection to a numbered group (0..9)."""
        idx = int(index) % 10
        self.selection_groups[idx] = list(self.selected_units)

    def bind_group_append(self, index: int) -> None:
        """Append current selection into an existing group (unique)."""
        idx = int(index) % 10
        base = list(self.selection_groups.get(idx, []))
        for u in self.selected_units:
            if u not in base:
                base.append(u)
        self.selection_groups[idx] = base

    def unbind_group(self, index: int) -> None:
        """Clear a numbered group (0..9)."""
        idx = int(index) % 10
        self.selection_groups[idx] = []

    def merge_groups(self, dst_index: int, src_index: int) -> None:
        """Union src group into dst group (unique)."""
        dst = int(dst_index) % 10
        src = int(src_index) % 10
        merged = list(self.selection_groups.get(dst, []))
        for u in self.selection_groups.get(src, []):
            if u not in merged:
                merged.append(u)
        self.selection_groups[dst] = merged

    def prune_groups(self) -> None:
        """Remove references to non-existent units from all groups."""
        alive = set(self.units)
        for k, arr in list(self.selection_groups.items()):
            self.selection_groups[k] = [u for u in arr if u in alive]

    def recall_group(self, index: int, *, additive: bool = False) -> List[Unit]:
        """
        Recall a group, filtering out units that no longer exist.
        Returns current selection.
        """
        idx = int(index) % 10
        self.prune_groups()
        group_units = list(self.selection_groups.get(idx, []))
        if not additive:
            self.selected_units = group_units
        else:
            for u in group_units:
                if u not in self.selected_units:
                    self.selected_units.append(u)

        self._sync_selection_flags()
        return list(self.selected_units)

    # ------------------------------------------ Commands ------------------------------------------

    def record_command(self, command: "Command", units: List[Unit]) -> None:
        """
        Store a serialized record of an issued command for telemetry/replay/undo.
        """
        try:
            payload = command.to_dict()
        except Exception:
            # best effort if custom object slipped in
            payload = {"kind": getattr(command, "kind", "unknown"), "meta": getattr(command, "meta", {})}
        rec = CommandRecord(
            timestamp=time.time(),
            command_json=payload,
            unit_ids=[self.find_unit_id(u) for u in units],
        )
        self.command_history.append(rec)

    def last_commands(self, n: int = 10) -> List[CommandRecord]:
        return list(self.command_history)[-max(0, n):]

    # ------------------------------------------- Pings --------------------------------------------

    def add_ping(
        self,
        world_pos: Tuple[float, float] | Vec2,
        ttl: float = 1.5,
        color: Tuple[int, int, int] = (255, 215, 0),
        radius: int = 12,
    ) -> None:
        """Spawn a transient ping at world_pos (used e.g. when issuing orders)."""
        pos = Vec2(world_pos)
        self.pings.append(WorldPing(pos, ttl=ttl, color=color, radius=radius))

    def ping_selection_center(self, ttl: float = 1.0, color: Tuple[int, int, int] = (80, 200, 255)) -> None:
        """Convenience: ping the center of current selection, if any."""
        c = self.center_of_selection()
        if c is not None:
            self.add_ping(c, ttl=ttl, color=color, radius=14)

    def clear_pings(self) -> None:
        self.pings.clear()

    # ------------------------------------ Serialization / Debug -----------------------------------

    def to_snapshot(self) -> Dict[str, Any]:
        """
        Minimal, UI-centric snapshot for debugging/telemetry (not a full save system).
        """
        self.prune_groups()  # keep snapshot clean
        return {
            "time": round(self.game_time, 3),
            "paused": self.paused,
            "units": len(self.units),
            "selected": len(self.selected_units),
            "hovered_tile": tuple(self.hovered_tile) if self.hovered_tile else None,
            "selection_groups_sizes": {k: len(v) for k, v in self.selection_groups.items()},
            "recent_commands": [
                {"t": r.timestamp, "cmd": r.command_json, "units": len(r.unit_ids)}
                for r in list(self.command_history)[-10:]
            ],
            "pings": [
                {**asdict(p), "norm": p.norm}
                for p in self.pings
            ],
        }

    def debug_string(self) -> str:
        s = self.to_snapshot()
        return (
            f"[WorldState] t={s['time']} paused={s['paused']} "
            f"units={s['units']} selected={s['selected']} "
            f"groups={s['selection_groups_sizes']} pings={len(s['pings'])}"
        )
