# c:/prj/WorldDom/src/ui/context_menu_ui.py
"""
Renderer + interaction logic for ContextMenuState.

Usage:
    cm_state = default_context_menu()           # from src.context_menu
    cm_ui = ContextMenuUI()                     # renderer/controller
    cm_ui.open(cm_state, pos=(mx, my), screen_size=screen.get_size())

In your loop:
    result = cm_ui.handle_event(cm_state, event, pygame.Rect(0,0,*screen.get_size()))
    if result is not None:
        # MenuItem was chosen
        print("Selected:", result.id or result.label)

    cm_ui.draw(screen, cm_state)
"""

from __future__ import annotations
from typing import Optional, Tuple

import pygame

from src.context_menu import ContextMenuState, MenuItem
from src.ui.menu_theme import MenuTheme

# Optional font size from settings; fall back gracefully.
try:
    from src.utils.settings import CONTEXT_MENU_FONT_SIZE as _FONT_SIZE
except Exception:  # noqa: BLE001 - dev fallback
    _FONT_SIZE = 16


class ContextMenuUI:
    def __init__(self, theme: Optional[MenuTheme] = None, font_name: str = "Arial", font_size: Optional[int] = None) -> None:
        self.theme = theme or MenuTheme()
        self.font = pygame.font.SysFont(font_name, font_size or _FONT_SIZE)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def open(
        self,
        state: ContextMenuState,
        pos: Tuple[int, int],
        screen_size: Tuple[int, int],
        target_tile: Optional[Tuple[int, int]] = None,
    ) -> None:
        state.active = True
        state.pos = pos
        state.target_tile = target_tile
        state.hover_index = None
        state.sub_menu = state.sub_menu.__class__()  # reset submenu
        self._layout_main(state, screen_size)

    def close(self, state: ContextMenuState) -> None:
        state.active = False
        state.hover_index = None
        state.sub_menu.active = False

    def handle_event(
        self, state: ContextMenuState, ev: pygame.event.Event, screen_rect: pygame.Rect
    ) -> Optional[MenuItem]:
        if not state.active:
            return None

        # Mouse motion: update hovers; spawn submenu if applicable
        if ev.type == pygame.MOUSEMOTION:
            self._update_hover_from_mouse(state, ev.pos, screen_rect)
            return None

        # Mouse clicks
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):  # left/right
            # Clicking outside closes
            if not self._point_in_any_menu(state, ev.pos):
                self.close(state)
                return None

            # Left-click: select item / open submenu
            if ev.button == 1:
                # Check submenu first (if open)
                if state.sub_menu.active and state.sub_menu.rects:
                    idx = self._index_at_pos(ev.pos, state.sub_menu.rects)
                    if idx is not None:
                        item = self._submenu_items(state)[idx]
                        if not item.enabled or item.is_separator:
                            return None
                        state.last_selected = item
                        self.close(state)
                        return item

                # Then main
                idx = self._index_at_pos(ev.pos, state.rects)
                if idx is not None:
                    item = state.items[idx]
                    if not item.enabled or item.is_separator:
                        return None
                    # Open submenu if present
                    if item.sub_items:
                        self._open_submenu(state, idx, screen_rect)
                        return None
                    state.last_selected = item
                    self.close(state)
                    return item

                return None

            # Right click inside menus => close
            if ev.button == 3:
                self.close(state)
                return None

        # Keyboard navigation
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.close(state)
                return None

            # Move hover in main or submenu
            if ev.key in (pygame.K_UP, pygame.K_DOWN):
                if state.sub_menu.active:
                    self._move_hover_sub(state, -1 if ev.key == pygame.K_UP else +1)
                else:
                    self._move_hover_main(state, -1 if ev.key == pygame.K_UP else +1)
                return None

            # Open/close submenu
            if ev.key == pygame.K_RIGHT:
                if not state.sub_menu.active and state.hover_index is not None:
                    self._open_submenu(state, state.hover_index, screen_rect)
                return None
            if ev.key == pygame.K_LEFT:
                if state.sub_menu.active:
                    state.sub_menu.active = False
                return None

            # Activate current item
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if state.sub_menu.active and state.sub_menu.hover_index is not None:
                    item = self._submenu_items(state)[state.sub_menu.hover_index]
                elif state.hover_index is not None:
                    item = state.items[state.hover_index]
                else:
                    item = None

                if item and item.enabled and not item.is_separator:
                    if item.sub_items:
                        self._open_submenu(state, state.hover_index or 0, screen_rect)
                        return None
                    state.last_selected = item
                    self.close(state)
                    return item

        return None

    def draw(self, s: pygame.Surface, state: ContextMenuState) -> None:
        if not state.active or state.pos is None:
            return

        # Draw shadow + main panel
        self._draw_panel(s, state.rects, state.items, state.hover_index)

        # Draw submenu if open
        if state.sub_menu.active and state.sub_menu.rects:
            self._draw_panel(s, state.sub_menu.rects, self._submenu_items(state), state.sub_menu.hover_index)

    # ------------------------------------------------------------------ #
    # Layout & helpers
    # ------------------------------------------------------------------ #

    def _layout_main(self, state: ContextMenuState, screen_size: Tuple[int, int]) -> None:
        w, h = self._measure_menu(state.items)
        x, y = state.pos or (0, 0)
        rect = pygame.Rect(x, y, w, h)
        rect = self._clamp_to_screen(rect, screen_size)
        state.pos = (rect.x, rect.y)
        state.rects = self._row_rects(rect, len(state.items))

    def _open_submenu(self, state: ContextMenuState, main_index: int, screen_rect: pygame.Rect) -> None:
        item = state.items[main_index]
        if not item.sub_items:
            return

        parent = state.rects[main_index]
        sm_w, sm_h = self._measure_menu(item.sub_items)
        # Prefer opening to the right; flip if overflowing
        open_right = parent.right + sm_w <= screen_rect.right
        x = parent.right if open_right else parent.left - sm_w
        y = parent.top
        rect = pygame.Rect(x, y, sm_w, sm_h)
        rect = rect.clamp(screen_rect)

        state.sub_menu.active = True
        state.sub_menu.parent_rect = parent
        state.sub_menu.pos = (rect.x, rect.y)
        state.sub_menu.open_side = "right" if open_right else "left"
        state.sub_menu.rects = self._row_rects(rect, len(item.sub_items))
        state.sub_menu.hover_index = None

    def _row_rects(self, outer: pygame.Rect, count: int) -> list[pygame.Rect]:
        th = self.theme
        rects: list[pygame.Rect] = []
        y = outer.y
        for _ in range(count):
            rects.append(pygame.Rect(outer.x, y, outer.width, th.item_height))
            y += th.item_height
        return rects

    def _measure_menu(self, items: list[MenuItem]) -> tuple[int, int]:
        th = self.theme
        w = 0
        for mi in items:
            if mi.is_separator:
                width = 32  # minimal width
            else:
                label_w, _ = self.font.size(mi.label or "")
                icon_w = th.icon_size + 8 if mi.icon else 0
                check_w = th.check_width
                shortcut_w = self.font.size(mi.shortcut or "")[0] + (th.shortcut_gap if mi.shortcut else 0)
                arrow_w = th.icon_size if mi.sub_items else 0
                width = th.padding_x + check_w + icon_w + label_w + shortcut_w + arrow_w + th.padding_x
            w = max(w, width)

        h = max(1, len(items)) * th.item_height
        return int(w), int(h)

    def _clamp_to_screen(self, rect: pygame.Rect, screen_size: tuple[int, int]) -> pygame.Rect:
        sw, sh = screen_size
        return pygame.Rect(
            max(0, min(rect.x, sw - rect.width)),
            max(0, min(rect.y, sh - rect.height)),
            rect.width,
            rect.height,
        )

    def _update_hover_from_mouse(self, state: ContextMenuState, pos: tuple[int, int], screen_rect: pygame.Rect) -> None:
        # Submenu hover first (on top)
        if state.sub_menu.active and state.sub_menu.rects:
            idx = self._index_at_pos(pos, state.sub_menu.rects)
            state.sub_menu.hover_index = idx

        # Main hover if mouse is in main list
        idx = self._index_at_pos(pos, state.rects)
        state.hover_index = idx

        # Auto-open submenu when hovering main items with children
        if idx is not None and 0 <= idx < len(state.items) and state.items[idx].sub_items:
            self._open_submenu(state, idx, screen_rect)

    @staticmethod
    def _index_at_pos(pos: tuple[int, int], rects: list[pygame.Rect]) -> Optional[int]:
        for i, r in enumerate(rects):
            if r.collidepoint(*pos):
                return i
        return None

    def _move_hover_main(self, state: ContextMenuState, delta: int) -> None:
        if not state.items:
            state.hover_index = None
            return
        idx = 0 if state.hover_index is None else state.hover_index
        for _ in range(len(state.items) * 2):
            idx = (idx + delta) % len(state.items)
            mi = state.items[idx]
            if mi.enabled and not mi.is_separator:
                state.hover_index = idx
                break

    def _move_hover_sub(self, state: ContextMenuState, delta: int) -> None:
        sub = self._submenu_items(state)
        if not sub:
            state.sub_menu.hover_index = None
            return
        idx = 0 if state.sub_menu.hover_index is None else state.sub_menu.hover_index
        for _ in range(len(sub) * 2):
            idx = (idx + delta) % len(sub)
            mi = sub[idx]
            if mi.enabled and not mi.is_separator:
                state.sub_menu.hover_index = idx
                break

    def _submenu_items(self, state: ContextMenuState) -> list[MenuItem]:
        if state.sub_menu.parent_rect is None or state.hover_index is None:
            # Try to find a current parent by looking up which rect matches parent_rect
            # Fallback to last opened index (hover_index).
            pass
        if state.hover_index is not None and 0 <= state.hover_index < len(state.items):
            return state.items[state.hover_index].sub_items
        return []

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #

    def _draw_panel(self, s: pygame.Surface, rects: list[pygame.Rect], items: list[MenuItem], hover_idx: Optional[int]) -> None:
        if not rects:
            return
        th = self.theme
        outer = rects[0].unionall(rects[1:]) if len(rects) > 1 else rects[0]

        # Shadow
        shadow_rect = outer.move(th.shadow_offset, th.shadow_offset)
        pygame.draw.rect(s, th.shadow, shadow_rect, border_radius=th.border_radius)

        # Background
        pygame.draw.rect(s, th.bg, outer, border_radius=th.border_radius)
        pygame.draw.rect(s, th.border, outer, width=1, border_radius=th.border_radius)

        # Items
        for i, (mi, r) in enumerate(zip(items, rects)):
            # Hover BG
            if hover_idx == i and mi.enabled and not mi.is_separator:
                pygame.draw.rect(s, th.hover_bg, r)

            # Separator
            if mi.is_separator:
                y = r.centery
                pygame.draw.line(s, th.separator, (r.left + th.padding_x, y), (r.right - th.padding_x, y), 1)
                continue

            x = r.left + th.padding_x
            y_center = r.centery

            # Checkmark
            if mi.checked:
                ch_rect = pygame.Rect(x, y_center - 6, 12, 12)
                pygame.draw.rect(s, th.text, ch_rect, width=2, border_radius=2)
            x += th.check_width

            # Icon
            if mi.icon:
                icon_surf = pygame.transform.smoothscale(mi.icon, (th.icon_size, th.icon_size))
                icon_rect = icon_surf.get_rect(midleft=(x, y_center))
                s.blit(icon_surf, icon_rect)
                x = icon_rect.right + 8

            # Label
            col = th.hover_text if (hover_idx == i and mi.enabled and not mi.is_separator) else (th.text if mi.enabled else th.text_disabled)
            label_surf = self.font.render(mi.label, True, col)
            s.blit(label_surf, (x, y_center - label_surf.get_height() // 2))

            # Shortcut (right aligned)
            if mi.shortcut:
                sc_surf = self.font.render(mi.shortcut, True, col)
                sc_rect = sc_surf.get_rect()
                sc_rect.midright = (r.right - th.padding_x - (th.icon_size if mi.sub_items else 0) - th.shortcut_gap, y_center)
                s.blit(sc_surf, sc_rect)

            # Submenu arrow
            if mi.sub_items:
                pts = self._triangle_points_right((r.right - th.padding_x - th.icon_size // 2, y_center), 6)
                pygame.draw.polygon(s, th.submenu_arrow, pts)

    @staticmethod
    def _triangle_points_right(center: tuple[int, int], size: int) -> list[tuple[int, int]]:
        cx, cy = center
        return [(cx - size // 2, cy - size), (cx - size // 2, cy + size), (cx + size // 2, cy)]
    
    def _point_in_any_menu(self, state: ContextMenuState, pos: tuple[int, int]) -> bool:
        if any(r.collidepoint(*pos) for r in state.rects):
            return True
        if state.sub_menu.active and any(r.collidepoint(*pos) for r in state.sub_menu.rects):
            return True
        return False
