# c:/prj/WorldDom/src/world_state.py
"""
WorldState holds all interactive state: units, selection, input anchors,
spatial index, control groups, pending orders, and an event queue.

It does not render; it provides data and queries for your systems.
"""
from __future__ import annotations
from typing import List, Optional, Tuple, Dict, Deque, Iterable, Set
from collections import deque
from dataclasses import dataclass, field
import math
import time
import pygame

from context_menu import ContextMenuState
from unit import Unit                     # Expected shape: .id (int), .position (Vec2), .radius (float), .type_name (str)
from spatial_hash import SpatialHash
from commands import Command, CommandType, move_to, attack_target

Vec2 = pygame.math.Vector2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rect_from_points(a: Vec2, b: Vec2) -> pygame.Rect:
    x0, y0, x1, y1 = a.x, a.y, b.x, b.y
    l, r = (x0, x1) if x0 <= x1 else (x1, x0)
    t, btm = (y0, y1) if y0 <= y1 else (y1, y0)
    return pygame.Rect(int(l), int(t), int(r - l), int(btm - t))

def _grid_formation(n: int, center: Vec2, spacing: float = 28.0) -> List[Vec2]:
    """Return n offsets arranged in a compact grid around center."""
    if n <= 0:
        return []
    cols = max(1, int(math.sqrt(n)))
    rows = math.ceil(n / cols)
    offsets: List[Vec2] = []
    half_w = (cols - 1) * spacing * 0.5
    half_h = (rows - 1) * spacing * 0.5
    for i in range(n):
        r = i // cols
        c = i % cols
        offsets.append(Vec2(c * spacing - half_w, r * spacing - half_h))
    # Shuffle a bit for less “blocky” feel
    return [center + o for o in offsets]

# ---------------------------------------------------------------------------
# WorldState
# ---------------------------------------------------------------------------

@dataclass
class WorldState:
    """Encapsulates game objects, selection, and interaction state."""
    units: List[Unit] = field(default_factory=list)
    selected_units: List[Unit] = field(default_factory=list)

    # Hover / selection
    hovered_tile: Optional[Tuple[int, int]] = None
    hovered_unit_id: Optional[int] = None

    left_mouse_down_screen_pos: Optional[Tuple[int, int]] = None
    left_mouse_down_world_pos: Optional[Vec2] = None
    right_mouse_down_pos: Optional[Tuple[int, int]] = None
    selection_box_screen: Optional[pygame.Rect] = None
    selection_box_world: Optional[pygame.Rect] = None

    # Double-click support
    _last_click_time: float = 0.0
    _last_click_unit_type: Optional[str] = None
    _double_click_window: float = 0.28  # seconds

    # Input modifiers (set by your input system each frame)
    shift_down: bool = False
    ctrl_down: bool = False
    alt_down: bool = False

    # Spatial index and id mapping
    _spatial: SpatialHash = field(default_factory=lambda: SpatialHash(cell_size=128))
    _units_by_id: Dict[int, Unit] = field(default_factory=dict)

    # Pending orders if a given Unit has no issue_command method
    pending_orders: Dict[int, Deque[Command]] = field(default_factory=dict)

    # Control groups: 0-9 -> set(unit_id)
    control_groups: Dict[int, Set[int]] = field(default_factory=lambda: {i: set() for i in range(10)})

    # Events for UI/notifications (tuples like ("selection_changed", {...}))
    events: Deque[Tuple[str, Dict]] = field(default_factory=deque)

    # Context menu
    context_menu: ContextMenuState = field(default_factory=ContextMenuState)

    # ---------------------------------------------------------------------
    # Unit management
    # ---------------------------------------------------------------------

    def add_unit(self, unit: Unit) -> None:
        """Add a unit and index it for queries."""
        self.units.append(unit)
        self._units_by_id[unit.id] = unit
        pos = Vec2(unit.position)
        rad = float(getattr(unit, "radius", 16.0))
        self._spatial.add(unit.id, pos, rad)

    def remove_unit(self, unit_id: int) -> None:
        unit = self._units_by_id.pop(unit_id, None)
        if unit is None:
            return
        if unit in self.units:
            self.units.remove(unit)
        if unit in self.selected_units:
            self.selected_units.remove(unit)
        self._spatial.remove(unit_id)
        for g in self.control_groups.values():
            g.discard(unit_id)
        self.pending_orders.pop(unit_id, None)
        self.events.append(("unit_removed", {"id": unit_id}))

    def update_unit_position(self, unit_id: int, new_pos: Tuple[float, float]) -> None:
        """Keep spatial index in sync; call this when your Unit moves."""
        self._spatial.update(unit_id, Vec2(new_pos))

    # ---------------------------------------------------------------------
    # Queries
    # ---------------------------------------------------------------------

    def find_units_in_rect(self, rect_world: pygame.Rect) -> List[Unit]:
        ids = list(self._spatial.query_rect(rect_world))
        return [self._units_by_id[i] for i in ids if i in self._units_by_id]

    def find_units_in_radius(self, center_world: Tuple[float, float], radius: float) -> List[Unit]:
        ids = list(self._spatial.query_radius(Vec2(center_world), radius))
        return [self._units_by_id[i] for i in ids if i in self._units_by_id]

    def get_unit_at_point(self, point_world: Tuple[float, float], radius_px: float = 16.0) -> Optional[Unit]:
        """Return the closest unit under cursor within radius."""
        best: tuple[float, Optional[Unit]] = (1e9, None)
        for uid in self._spatial.query_radius(Vec2(point_world), radius_px):
            u = self._units_by_id.get(uid)
            if not u: continue
            d2 = (Vec2(u.position) - Vec2(point_world)).length_squared()
            if d2 < best[0]:
                best = (d2, u)
        return best[1]

    # ---------------------------------------------------------------------
    # Selection management
    # ---------------------------------------------------------------------

    def clear_selection(self) -> None:
        if self.selected_units:
            self.selected_units.clear()
            self.events.append(("selection_changed", {"units": []}))

    def select_units_list(self, units: Iterable[Unit], *, additive: bool = False, toggle: bool = False) -> None:
        new = list(units)
        if toggle:
            cur = set(self.selected_units)
            for u in new:
                if u in cur:
                    cur.remove(u)
                else:
                    cur.add(u)
            self.selected_units = list(cur)
        elif additive:
            cur = {u.id: u for u in self.selected_units}
            for u in new:
                cur[u.id] = u
            self.selected_units = list(cur.values())
        else:
            self.selected_units = new

        self.events.append(("selection_changed", {"units": [u.id for u in self.selected_units]}))

    def begin_marquee(self, screen_pos: Tuple[int, int], world_pos: Tuple[float, float]) -> None:
        self.left_mouse_down_screen_pos = (int(screen_pos[0]), int(screen_pos[1]))
        self.left_mouse_down_world_pos = Vec2(world_pos)
        self.selection_box_screen = None
        self.selection_box_world = None

    def update_marquee(self, screen_pos: Tuple[int, int]) -> None:
        if self.left_mouse_down_screen_pos is None:
            return
        x0, y0 = self.left_mouse_down_screen_pos
        x1, y1 = screen_pos
        l, r = (x0, x1) if x0 <= x1 else (x1, x0)
        t, btm = (y0, y1) if y0 <= y1 else (y1, y0)
        self.selection_box_screen = pygame.Rect(l, t, r - l, btm - t)

    def end_marquee(self, world_pos_end: Tuple[float, float]) -> None:
        """Finalize marquee; select by world-space rectangle."""
        if self.left_mouse_down_world_pos is None:
            return
        a = Vec2(self.left_mouse_down_world_pos)
        b = Vec2(world_pos_end)
        self.selection_box_world = _rect_from_points(a, b)

        if self.selection_box_world.width < 4 and self.selection_box_world.height < 4:
            # Treat as click
            self._handle_click_selection(world_pos_end)
        else:
            # Drag select
            units = self.find_units_in_rect(self.selection_box_world)
            self.select_units_list(units, additive=self.shift_down, toggle=False)

        self.left_mouse_down_screen_pos = None
        self.left_mouse_down_world_pos = None
        self.selection_box_screen = None
        self.selection_box_world = None

    def _handle_click_selection(self, world_pos: Tuple[float, float]) -> None:
        clicked = self.get_unit_at_point(world_pos, radius_px=20.0)
        now = time.time()

        if clicked is None:
            if not self.shift_down and not self.ctrl_down:
                self.clear_selection()
            return

        # Double-click selects all same type near the clicked unit
        if (now - self._last_click_time) <= self._double_click_window and \
           self._last_click_unit_type == getattr(clicked, "type_name", None):
            same_type = getattr(clicked, "type_name", None)
            if same_type:
                nearby = [
                    u for u in self.find_units_in_radius(clicked.position, radius=480.0)
                    if getattr(u, "type_name", None) == same_type
                ]
                self.select_units_list(nearby, additive=False)
        else:
            # Single click
            if self.ctrl_down:
                self.select_units_list([clicked], additive=False)  # ctrl = replace in many RTS
            else:
                self.select_units_list([clicked], additive=self.shift_down, toggle=False)

        self._last_click_time = now
        self._last_click_unit_type = getattr(clicked, "type_name", None)

    # ---------------------------------------------------------------------
    # Commands & control groups
    # ---------------------------------------------------------------------

    def issue_command_to_selection(
        self,
        cmd: Command,
        *,
        formation: bool = True,
        spacing: float = 28.0
    ) -> None:
        """Fan out target positions for MOVE/ATTACK across selection."""
        if not self.selected_units:
            return

        units = self.selected_units[:]
        if cmd.kind in (CommandType.MOVE, CommandType.ATTACK) and cmd.target_pos is not None and formation:
            targets = _grid_formation(len(units), Vec2(cmd.target_pos), spacing)
            for u, tpos in zip(units, targets):
                self._send_or_queue(u, Command(kind=cmd.kind, target_pos=Vec2(tpos), queue=cmd.queue, meta=cmd.meta))
        else:
            for u in units:
                self._send_or_queue(u, cmd)

        self.events.append(("orders_issued", {
            "kind": cmd.kind.value,
            "unit_ids": [u.id for u in units],
        }))

    def _send_or_queue(self, unit: Unit, cmd: Command) -> None:
        # If your Unit has its own API, dispatch to it. Otherwise, retain locally.
        if hasattr(unit, "issue_command") and callable(getattr(unit, "issue_command")):
            try:
                unit.issue_command(cmd)  # type: ignore[attr-defined]
                return
            except Exception:
                # Fallback to queue if unit rejects
                pass
        q = self.pending_orders.setdefault(unit.id, deque())
        if not cmd.queue:
            q.clear()
        q.append(cmd)

    def assign_control_group(self, group: int) -> None:
        if 0 <= group <= 9:
            self.control_groups[group] = {u.id for u in self.selected_units}
            self.events.append(("control_group_assigned", {"group": group, "unit_ids": list(self.control_groups[group])}))

    def recall_control_group(self, group: int, *, additive: bool = False) -> None:
        if 0 <= group <= 9:
            ids = self.control_groups.get(group, set())
            units = [self._units_by_id[i] for i in ids if i in self._units_by_id]
            self.select_units_list(units, additive=additive, toggle=False)

    # ---------------------------------------------------------------------
    # Hover and context menu
    # ---------------------------------------------------------------------

    def set_hovered_tile(self, tile_xy: Optional[Tuple[int, int]]) -> None:
        self.hovered_tile = tile_xy

    def update_hovered_unit(self, world_cursor: Tuple[float, float]) -> None:
        unit = self.get_unit_at_point(world_cursor, radius_px=22.0)
        self.hovered_unit_id = unit.id if unit else None

    def open_context_menu(self, screen_pos: Tuple[int, int]) -> None:
        """Populate the context menu based on selection/hover (simple example)."""
        self.context_menu.clear()
        if self.selected_units:
            self.context_menu.add_item("Move", payload={"cmd": "move"})
            self.context_menu.add_item("Stop", payload={"cmd": "stop"})
            self.context_menu.add_item("Hold Position", payload={"cmd": "hold"})
        if self.hovered_unit_id is not None:
            self.context_menu.add_item("Attack", payload={"cmd": "attack", "target_id": self.hovered_unit_id})
        self.context_menu.open_at(screen_pos)

    # ---------------------------------------------------------------------
    # Serialization (lightweight)
    # ---------------------------------------------------------------------

    def to_dict(self) -> Dict:
        """Snapshot minimal state. Units should implement a .to_dict() for full save."""
        return {
            "units": [u.to_dict() if hasattr(u, "to_dict") else {"id": u.id, "pos": tuple(Vec2(u.position))} for u in self.units],
            "selected_ids": [u.id for u in self.selected_units],
            "control_groups": {k: list(v) for k, v in self.control_groups.items()},
        }

    def from_dict(self, data: Dict) -> None:
        """Restore minimal state. You’re expected to create Unit instances externally and add via add_unit()."""
        sel_ids = set(data.get("selected_ids", []))
        self.control_groups = {int(k): set(v) for k, v in data.get("control_groups", {}).items()}
        # Units must be re-added by the caller; here we only restore selection once they exist.
        self.selected_units = [u for u in self.units if u.id in sel_ids]
        self.events.append(("selection_changed", {"units": [u.id for u in self.selected_units]}))
