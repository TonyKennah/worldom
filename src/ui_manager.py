# c:/prj/WorldDom/src/ui_manager.py
"""
Handles the rendering and state of all UI elements in the game.
"""
from __future__ import annotations
from typing import List, Tuple, TYPE_CHECKING

import pygame
import settings

if TYPE_CHECKING:
    from game import Game

class UIManager:
    """Manages the drawing and state of all UI components."""

    def __init__(self, game: Game):
        """Initializes the UI Manager."""
        self.game = game
        self.screen = game.screen

        # --- Globe Animation State ---
        self.show_globe_popup: bool = False
        self.globe_frames: List[pygame.Surface] = []
        self.globe_frame_index: int = 0
        self.globe_animation_timer: float = 0.0

    def update(self, dt: float) -> None:
        """Updates UI components, like animations."""
        if self.show_globe_popup:
            self._update_globe_animation(dt)

    def _update_globe_animation(self, dt: float) -> None:
        """Cycles through the globe animation frames based on a timer."""
        if not self.game.globe_frames:
            return
        self.globe_animation_timer += dt
        if self.globe_animation_timer >= settings.GLOBE_FRAME_DURATION:
            self.globe_animation_timer = 0
            self.globe_frame_index = (self.globe_frame_index + 1) % len(self.game.globe_frames)

    def draw_ui(self) -> None:
        """Draws all UI elements, called once per frame."""
        # Draw selection box
        if self.game.world_state.selection_box:
            pygame.draw.rect(self.screen, settings.SELECTION_BOX_COLOR,
                             self.game.world_state.selection_box, settings.SELECTION_BOX_BORDER_WIDTH)

        # Draw globe popup if active
        if self.show_globe_popup:
            self.draw_globe_popup()

        # Draw context menu if active
        if self.game.world_state.context_menu.active:
            self.draw_context_menu()
            if self.game.world_state.context_menu.sub_menu.active:
                self.draw_sub_menu()

    def draw_globe_popup(self) -> None:
        """Draws the globe animation popup in the center of the screen."""
        if not self.game.globe_frames:
            return

        overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        current_frame = self.game.globe_frames[self.globe_frame_index]
        frame_rect = current_frame.get_rect()

        padding = 40
        popup_width = frame_rect.width + padding
        popup_height = frame_rect.height + padding
        popup_rect = pygame.Rect(0, 0, popup_width, popup_height)
        popup_rect.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)

        pygame.draw.rect(self.screen, (40, 40, 60), popup_rect, border_radius=10)
        pygame.draw.rect(self.screen, (200, 200, 220), popup_rect, width=2, border_radius=10)
        self.screen.blit(current_frame, (popup_rect.x + padding // 2, popup_rect.y + padding // 2))

    def draw_context_menu(self) -> None:
        """Renders the context menu on the screen."""
        context_menu = self.game.world_state.context_menu
        if not context_menu.rects:
            return

        for i, rect in enumerate(context_menu.rects):
            option_text = context_menu.options[i]["label"]

            pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BG_COLOR, rect)
            pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BORDER_COLOR, rect, 1)

            text_surface = context_menu.font.render(
                option_text, True, settings.CONTEXT_MENU_TEXT_COLOR)
            text_x = rect.x + settings.CONTEXT_MENU_PADDING
            text_y = rect.y + (settings.CONTEXT_MENU_PADDING / 2)
            self.screen.blit(text_surface, (text_x, text_y))

    def draw_sub_menu(self) -> None:
        """Renders the sub-menu on the screen."""
        context_menu = self.game.world_state.context_menu
        if not context_menu.sub_menu.rects:
            return

        for i, rect in enumerate(context_menu.sub_menu.rects):
            option_text = context_menu.sub_menu.options[i]

            # Draw background and border
            pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BG_COLOR, rect)
            pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BORDER_COLOR, rect, 1)

            text_surface = context_menu.font.render(
                option_text, True, settings.CONTEXT_MENU_TEXT_COLOR
            )
            text_x = rect.x + settings.CONTEXT_MENU_PADDING
            text_y = rect.y + (settings.CONTEXT_MENU_PADDING / 2)
            self.screen.blit(text_surface, (text_x, text_y))

    def handle_context_menu_hover(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles hover events for the context menu to show sub-menus."""
        context_menu = self.game.world_state.context_menu

        hovered_main_item = False
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                hovered_main_item = True
                option_data = context_menu.options[i]
                if "sub_options" in option_data:
                    # Open sub-menu if not already open for this item
                    if (not context_menu.sub_menu.active
                            or context_menu.sub_menu.parent_rect != rect):
                        self._open_sub_menu(option_data["sub_options"], rect)
                else:
                    # This item has no sub-menu, so close any active one
                    self.close_sub_menu()
                break  # Found the hovered item

        if not hovered_main_item:
            # Mouse is not over any main menu item. Check if it's over the sub-menu.
            is_mouse_on_sub_menu = False
            if context_menu.sub_menu.active:
                for sub_rect in context_menu.sub_menu.rects:
                    if sub_rect.collidepoint(mouse_pos):
                        is_mouse_on_sub_menu = True
                        break

            if not is_mouse_on_sub_menu:
                self.close_sub_menu()

    def _open_sub_menu(self, sub_options: List[str], parent_rect: pygame.Rect) -> None:
        """Opens a sub-menu next to a parent menu item."""
        context_menu = self.game.world_state.context_menu
        context_menu.sub_menu.active = True
        context_menu.sub_menu.options = sub_options.copy()
        context_menu.sub_menu.parent_rect = parent_rect
        context_menu.sub_menu.rects.clear()

        # Position sub-menu to the right of the parent
        x = parent_rect.right
        y = parent_rect.top
        padding = settings.CONTEXT_MENU_PADDING

        for i, option_text in enumerate(sub_options):
            text_surface = context_menu.font.render(option_text, True, (0, 0, 0))
            width = text_surface.get_width() + padding * 2
            height = text_surface.get_height() + padding
            rect = pygame.Rect(x, y + i * height, width, height)
            context_menu.sub_menu.rects.append(rect)

    def close_sub_menu(self) -> None:
        """Closes the sub-menu."""
        context_menu = self.game.world_state.context_menu
        if not context_menu.sub_menu.active:
            return
        context_menu.sub_menu.active = False
        context_menu.sub_menu.options.clear()
        context_menu.sub_menu.rects.clear()
        context_menu.sub_menu.parent_rect = None