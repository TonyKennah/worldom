# c:/prj/WorldDom/src/world_state.py
"""
Defines the WorldState class, a central data container for game state.
Expanded with selection groups, command history, pings, and helper methods.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Callable, Any
from collections import deque
import time

import pygame

from src.ui.context_menu import ContextMenuState
from src.entities.unit import Unit

# Type-only import to avoid circular dependencies at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.commands import Command  # noqa: F401


# ------------------------------- Small helper dataclasses -------------------------------

@dataclass
class WorldPing:
    """Transient world-space ping/marker (for right-clicks, alerts, etc.)."""
    world_pos: pygame.math.Vector2
    ttl: float = 1.5
    color: Tuple[int, int, int] = (255, 215, 0)  # gold
    radius: int = 12

    def update(self, dt: float) -> None:
        self.ttl = max(0.0, self.ttl - dt)

    @property
    def alive(self) -> bool:
        return self.ttl > 0.0


@dataclass
class CommandRecord:
    """A lightweight record of issued commands for replay/analytics/undo."""
    timestamp: float
    command_json: Dict[str, Any]  # Command serialized via Command.to_dict()
    unit_ids: List[int]           # Python id(unit) snapshot for reconciliation


# ----------------------------------------- State ---------------------------------------

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
    hovered_world_pos: Optional[pygame.math.Vector2] = None
    selection_box: Optional[pygame.Rect] = None

    # --- UI State ---
    context_menu: ContextMenuState = field(default_factory=ContextMenuState)

    # --- Raw Input State (for tracking drags, etc.) ---
    left_mouse_down_screen_pos: Optional[Tuple[int, int]] = None
    left_mouse_down_world_pos: Optional[pygame.math.Vector2] = None
    right_mouse_down_pos: Optional[Tuple[int, int]] = None

    # --- NEW: System/Session State ---
    game_time: float = 0.0
    paused: bool = False

    # Selection groups (0..9) store *references* to units (filtered on recall)
    selection_groups: Dict[int, List[Unit]] = field(default_factory=dict)

    # Rolling command history (serialized) for analytics/undo/replay
    command_history: deque[CommandRecord] = field(default_factory=lambda: deque(maxlen=200))

    # Transient world pings/markers
    pings: List[WorldPing] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Initialize empty selection groups 0..9
        if not self.selection_groups:
            self.selection_groups = {i: [] for i in range(10)}

    # -------------------------------- Time & housekeeping --------------------------------

    def tick(self, dt: float) -> None:
        """Advance world-time counters and decay transient elements (pings)."""
        if not self.paused:
            self.game_time += max(0.0, dt)
        # Update pings and cull dead
        for p in self.pings:
            p.update(dt)
        self.pings = [p for p in self.pings if p.alive]

    def add_unit(self, unit: Unit) -> None:
        self.units.append(unit)

    def remove_unit(self, unit: Unit) -> None:
        """Remove a unit and clean up selections/groups."""
        if unit in self.units:
            self.units.remove(unit)
        if unit in self.selected_units:
            self.selected_units.remove(unit)
        # Clean up in groups
        for k in self.selection_groups:
            if unit in self.selection_groups[k]:
                self.selection_groups[k] = [u for u in self.selection_groups[k] if u is not unit]

    def clear_dead_units(self, is_dead: Callable[[Unit], bool] | None = None) -> int:
        """
        Remove dead units from world and selections. By default, uses a heuristic
        (hp<=0 if present) else keep all.
        Returns the number of removed units.
        """
        def default_dead(u: Unit) -> bool:
            return hasattr(u, "hp") and getattr(u, "hp") <= 0

        dead_pred = is_dead or default_dead
        before = len(self.units)
        to_remove = [u for u in self.units if dead_pred(u)]
        for u in to_remove:
            self.remove_unit(u)
        return before - len(self.units)

    # -------------------------------- Selection helpers ---------------------------------

    def clear_selection(self) -> None:
        self.selected_units.clear()

    def has_selection(self) -> bool:
        return bool(self.selected_units)

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
            self.selected_units.extend([u for u in candidates if u not in self.selected_units])

        if max_units is not None and len(self.selected_units) > max_units:
            self.selected_units = self.selected_units[:max_units]

        # Update Unit.selected flags for convenience
        selected_set = set(self.selected_units)
        for u in self.units:
            u.selected = u in selected_set

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

    def toggle_unit(self, unit: Unit) -> None:
        if unit in self.selected_units:
            self.selected_units.remove(unit)
        else:
            self.selected_units.append(unit)
        unit.selected = unit in self.selected_units

    def center_of_selection(self) -> Optional[pygame.math.Vector2]:
        """Average world_pos of current selection (wrap-agnostic)."""
        if not self.selected_units:
            return None
        sx = sum(u.world_pos.x for u in self.selected_units)
        sy = sum(u.world_pos.y for u in self.selected_units)
        return pygame.math.Vector2(sx / len(self.selected_units), sy / len(self.selected_units))

    # ------------------------------- Selection groups (0..9) --------------------------------

    def bind_group(self, index: int) -> None:
        """Bind the current selection to a numbered group (0..9)."""
        idx = int(index) % 10
        self.selection_groups[idx] = list(self.selected_units)

    def recall_group(self, index: int, *, additive: bool = False) -> List[Unit]:
        """
        Recall a group, filtering out units that no longer exist.
        Returns current selection.
        """
        idx = int(index) % 10
        group_units = [u for u in self.selection_groups.get(idx, []) if u in self.units]
        if not additive:
            self.selected_units = group_units
        else:
            for u in group_units:
                if u not in self.selected_units:
                    self.selected_units.append(u)

        # sync flags
        selected_set = set(self.selected_units)
        for u in self.units:
            u.selected = u in selected_set
        return list(self.selected_units)

    # ------------------------------------ Commands ---------------------------------------

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
            unit_ids=[id(u) for u in units],
        )
        self.command_history.append(rec)

    def last_commands(self, n: int = 10) -> List[CommandRecord]:
        return list(self.command_history)[-max(0, n):]

    # ------------------------------------- Pings -----------------------------------------

    def add_ping(self, world_pos: Tuple[float, float] | pygame.math.Vector2, ttl: float = 1.5,
                 color: Tuple[int, int, int] = (255, 215, 0), radius: int = 12) -> None:
        """Spawn a transient ping at world_pos (used e.g. when issuing orders)."""
        pos = pygame.math.Vector2(world_pos)
        self.pings.append(WorldPing(pos, ttl=ttl, color=color, radius=radius))

    # -------------------------------- Serialization (light) ------------------------------

    def to_snapshot(self) -> Dict[str, Any]:
        """
        Minimal, UI-centric snapshot for debugging/telemetry (not a full save system).
        """
        return {
            "time": self.game_time,
            "paused": self.paused,
            "units": len(self.units),
            "selected": len(self.selected_units),
            "hovered_tile": tuple(self.hovered_tile) if self.hovered_tile else None,
            "selection_groups_sizes": {k: len(v) for k, v in self.selection_groups.items()},
            "recent_commands": [
                {"t": r.timestamp, "cmd": r.command_json, "units": len(r.unit_ids)}
                for r in list(self.command_history)[-10:]
            ],
            "pings": [asdict(p) for p in self.pings],
        }
