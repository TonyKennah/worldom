from __future__ import annotations
from typing import Iterable, List, Optional, Tuple, TYPE_CHECKING
import time
import pygame
import src.utils.settings as settings  # for TILE_SIZE

if TYPE_CHECKING:
    from src.core.game import Game
    from src.entities.unit import Unit


class SelectionManager:
    """Processes selections and delegates actions to the game."""

    # Double-click + cycling tuning
    _DOUBLE_CLICK_S = 0.30
    _CYCLE_RADIUS_PX = 8  # how close consecutive clicks must be to be considered same spot

    def __init__(self, game: Game) -> None:
        """Initializes the game."""
        self.game = game

        # Click cycle state (to cycle through stacked units)
        self._last_click_t: float = 0.0
        self._last_click_pos: Tuple[int, int] = (0, 0)
        self._last_pick_list: List[int] = []  # unit ids in deterministic order
        self._last_pick_index: int = -1
        self._last_clicked_unit_id: Optional[int] = None

    # ---------- Public selection actions (keep original signatures) ----------

    def handle_left_click_selection(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles unit selection logic for a left click."""
        # Modifiers: Shift=additive, Ctrl=toggle
        mods = pygame.key.get_mods()
        additive = bool(mods & pygame.KMOD_SHIFT)
        toggle = bool(mods & pygame.KMOD_CTRL)

        clicked_units = self._units_under_cursor(mouse_pos)

        # Double-click detection (before cycling)
        now = time.time()
        is_double = (now - self._last_click_t) <= self._DOUBLE_CLICK_S and self._near(mouse_pos, self._last_click_pos)

        # Cycling selection when multiple overlap
        picked: Optional["Unit"] = None
        if clicked_units:
            # Build deterministic order (nearest first, then id)
            ordered = self._order_units_by_cursor_distance(mouse_pos, clicked_units)
            ordered_ids = [id(u) for u in ordered]

            if self._same_pick_group(ordered_ids, mouse_pos, now):
                self._last_pick_index = (self._last_pick_index + 1) % len(ordered)
            else:
                self._last_pick_list = ordered_ids
                self._last_pick_index = 0
                self._last_click_pos = mouse_pos
                self._last_click_t = now

            picked = ordered[self._last_pick_index]
        else:
            # No unit under cursor; reset cycling
            self._reset_cycle_state(mouse_pos, now)

        if is_double and picked is not None:
            # Double click: select "similar" units on screen (same color, visible)
            self._select_similar_on_screen(picked, additive=additive, toggle=toggle)
            self._last_clicked_unit_id = id(picked)
            return

        # Apply selection according to modifiers
        if picked is not None:
            self._apply_selection([picked], additive=additive, toggle=toggle)
            self._last_clicked_unit_id = id(picked)
        else:
            # Clicked empty space: clear unless using additive/toggle (common RTS behavior)
            if not additive and not toggle:
                self.clear_selection()

    def handle_drag_selection(self, selection_rect_screen: pygame.Rect) -> None:
        """Selects units within a given rectangle in screen coordinates."""
        mods = pygame.key.get_mods()
        additive = bool(mods & pygame.KMOD_SHIFT)
        toggle = bool(mods & pygame.KMOD_CTRL)

        units_in_rect = [u for u in self.game.world_state.units if self._unit_intersects_screen_rect(u, selection_rect_screen)]
        self._apply_selection(units_in_rect, additive=additive, toggle=toggle)

    # ---------- Quality-of-life helpers (new) ----------

    def clear_selection(self) -> None:
        """Deselect all selected units and clear state."""
        for u in self.game.world_state.selected_units:
            u.selected = False
        self.game.world_state.selected_units.clear()

    def select_units(self, units: Iterable["Unit"], *, additive: bool = False, toggle: bool = False) -> None:
        """Programmatic selection entrypoint: add/toggle/replace selection with given units."""
        self._apply_selection(list(units), additive=additive, toggle=toggle)

    def select_all_visible(self) -> None:
        """Select all units with centers currently inside the screen."""
        screen_rect = pygame.Rect(0, 0, self.game.camera.width, self.game.camera.height)
        visible: List["Unit"] = []
        for u in self.game.world_state.units:
            if self._unit_intersects_screen_rect(u, screen_rect):
                visible.append(u)
        self._apply_selection(visible, additive=False, toggle=False)

    # ---------- Internals ----------

    def _apply_selection(self, picked: List["Unit"], *, additive: bool, toggle: bool) -> None:
        ws = self.game.world_state

        if not additive and not toggle:
            # Replace selection
            for u in ws.selected_units:
                u.selected = False
            ws.selected_units.clear()

        if toggle:
            # Toggle membership; don't touch others
            for u in picked:
                if u in ws.selected_units:
                    ws.selected_units.remove(u)
                    u.selected = False
                else:
                    ws.selected_units.append(u)
                    u.selected = True
        else:
            # Add all picked (or replace if additive=False and we cleared above)
            for u in picked:
                if u not in ws.selected_units:
                    ws.selected_units.append(u)
                    u.selected = True

    def _units_under_cursor(self, screen_pos: Tuple[int, int]) -> List["Unit"]:
        """Return units whose wrap-aware hit-test contains the screen point."""
        map_w_px = self.game.map.width * settings.TILE_SIZE
        map_h_px = self.game.map.height * settings.TILE_SIZE
        hits: List["Unit"] = []
        for u in self.game.world_state.units:
            try:
                if u.hit_test_screen_point(screen_pos, self.game.camera, map_w_px, map_h_px):
                    hits.append(u)
            except Exception:
                # Fallback to simple rect check (not wrap-aware) if unit lacks helper
                world_pos = self.game.camera.screen_to_world(screen_pos)
                if u.get_world_rect().collidepoint(world_pos):
                    hits.append(u)
        return hits

    def _order_units_by_cursor_distance(self, screen_pos: Tuple[int, int], units: List["Unit"]) -> List["Unit"]:
        """Sort units by distance of their screen centers to the cursor (stable by id)."""
        def _screen_center(u: "Unit") -> Tuple[float, float]:
            p = self.game.camera.world_to_screen(u.world_pos, include_shake=False)
            return (float(p.x), float(p.y))

        cx, cy = float(screen_pos[0]), float(screen_pos[1])
        return sorted(
            units,
            key=lambda u: ((cx - _screen_center(u)[0]) ** 2 + (cy - _screen_center(u)[1]) ** 2, id(u))
        )

    def _unit_intersects_screen_rect(self, unit: "Unit", screen_rect: pygame.Rect) -> bool:
        """
        Conservative test: project the unit’s 9 wrap clones, convert its world
        bounding rect to screen rect via camera, and test intersection.
        """
        cam = self.game.camera
        map_w_px = self.game.map.width * settings.TILE_SIZE
        map_h_px = self.game.map.height * settings.TILE_SIZE

        world_rect = unit.get_world_rect()
        # 9-neighborhood (wrap clones)
        for dx in (-map_w_px, 0, map_w_px):
            for dy in (-map_h_px, 0, map_h_px):
                wr = world_rect.move(dx, dy)
                try:
                    sr = cam.apply(wr)  # camera.apply(Rect) -> Rect in screen space
                except Exception:
                    # Fallback: approximate by transforming corners
                    tl = cam.world_to_screen((wr.left, wr.top), include_shake=False)
                    br = cam.world_to_screen((wr.right, wr.bottom), include_shake=False)
                    sr = pygame.Rect(int(tl.x), int(tl.y), int(br.x - tl.x), int(br.y - tl.y))
                    sr.normalize()
                if screen_rect.colliderect(sr):
                    return True
        return False

    def _select_similar_on_screen(self, ref: "Unit", *, additive: bool, toggle: bool) -> None:
        """
        Simple similarity heuristic: units with the same visual color that are
        on-screen. Extend this if you add unit classes/metadata.
        """
        screen_rect = pygame.Rect(0, 0, self.game.camera.width, self.game.camera.height)
        candidates = [u for u in self.game.world_state.units
                      if getattr(u, "color", None) == getattr(ref, "color", None)
                      and self._unit_intersects_screen_rect(u, screen_rect)]
        # Ensure the reference unit is part of the set
        if ref not in candidates:
            candidates.append(ref)
        self._apply_selection(candidates, additive=additive, toggle=toggle)

    def _same_pick_group(self, ordered_ids: List[int], mouse_pos: Tuple[int, int], now: float) -> bool:
        """Whether this click should continue cycling through the same stack of units."""
        if (now - self._last_click_t) > self._DOUBLE_CLICK_S:
            return False
        if not self._near(mouse_pos, self._last_click_pos):
            return False
        return ordered_ids == self._last_pick_list

    def _reset_cycle_state(self, mouse_pos: Tuple[int, int], now: float) -> None:
        self._last_pick_list = []
        self._last_pick_index = -1
        self._last_click_pos = mouse_pos
        self._last_click_t = now

    @staticmethod
    def _near(a: Tuple[int, int], b: Tuple[int, int], r: int = _CYCLE_RADIUS_PX) -> bool:
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 <= r * r
