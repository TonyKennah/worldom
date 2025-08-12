# c:/prj/WorldDom/src/ui_manager.py
"""
Handles the rendering and state of all UI elements in the game.
"""
from __future__ import annotations
import math
from typing import List, Optional, Tuple, TYPE_CHECKING, Any

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
        self.globe_frame_index: int = 0
        self.globe_animation_timer: float = 0.0
        self.globe_animation_speed_index: int = settings.GLOBE_ANIMATION_DEFAULT_SPEED_INDEX
        self.globe_speed_down_rect: Optional[pygame.Rect] = None
        self.globe_speed_up_rect: Optional[pygame.Rect] = None
        self.popup_title_font = pygame.font.SysFont("Arial", 24, bold=True)
        self.breakdown_font = pygame.font.SysFont("Arial", 18)
        self.speed_control_font = pygame.font.SysFont("Arial", 16, bold=True)

    def update(self, dt: float) -> None:
        """Updates UI components, like animations."""
        if self.show_globe_popup:
            self._update_globe_animation(dt)

    def _update_globe_animation(self, dt: float) -> None:
        """Cycles through the globe animation frames based on a timer."""
        if not self.game.globe_frames:
            return
        
        frame_duration = settings.GLOBE_ANIMATION_SPEEDS[self.globe_animation_speed_index]
        if math.isinf(frame_duration):
            return  # Animation is paused

        self.globe_animation_timer += dt
        if self.globe_animation_timer >= frame_duration:
            self.globe_animation_timer = 0
            self.globe_frame_index = (self.globe_frame_index + 1) % len(self.game.globe_frames)

    def increase_globe_speed(self) -> None:
        """Increases the globe's rotation speed."""
        num_speeds = len(settings.GLOBE_ANIMATION_SPEEDS)
        self.globe_animation_speed_index = min(self.globe_animation_speed_index + 1, num_speeds - 1)

    def decrease_globe_speed(self) -> None:
        """Decreases the globe's rotation speed."""
        self.globe_animation_speed_index = max(self.globe_animation_speed_index - 1, 0)

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

        # --- Title ---
        title_surface = self.popup_title_font.render(
            "World Overview", True, settings.DEBUG_PANEL_FONT_COLOR
        )
        title_rect = title_surface.get_rect()

        # --- Globe Image ---
        current_frame = self.game.globe_frames[self.globe_frame_index]
        frame_rect = current_frame.get_rect()

        # --- Terrain Breakdown ---
        percentages = self.game.map.get_terrain_percentages()
        breakdown_surfaces = []
        if percentages:
            # Sort by percentage (desc) and filter out empty ones
            sorted_terrain = sorted(percentages.items(), key=lambda item: item[1], reverse=True)
            for terrain, pct in sorted_terrain:
                if pct > 0:
                    text = f"{terrain.capitalize()}: {pct:.1f}%"
                    surface = self.breakdown_font.render(text, True, settings.DEBUG_PANEL_FONT_COLOR)
                    breakdown_surfaces.append(surface)

        breakdown_height = sum(s.get_height() for s in breakdown_surfaces)
        breakdown_width = max(s.get_width() for s in breakdown_surfaces) if breakdown_surfaces else 0

        # --- Speed Controls ---
        speed_down_surface = self.speed_control_font.render(" << ", True, settings.DEBUG_PANEL_FONT_COLOR)
        speed_up_surface = self.speed_control_font.render(" >> ", True, settings.DEBUG_PANEL_FONT_COLOR)

        default_duration = settings.GLOBE_ANIMATION_SPEEDS[settings.GLOBE_ANIMATION_DEFAULT_SPEED_INDEX]
        current_duration = settings.GLOBE_ANIMATION_SPEEDS[self.globe_animation_speed_index]
        if math.isinf(current_duration):
            speed_text = "Speed: Paused"
        else:
            speed_multiplier = default_duration / current_duration if current_duration > 0 else 0.0
            speed_text = f"Speed: {speed_multiplier:.1f}x"
        speed_display_surface = self.breakdown_font.render(speed_text, True, settings.DEBUG_PANEL_FONT_COLOR)

        speed_controls_height = max(
            speed_down_surface.get_height(),
            speed_display_surface.get_height(),
            speed_up_surface.get_height()
        )

        # --- Popup container ---
        padding = 40
        title_spacing = 20  # Space between title and globe
        breakdown_spacing = 20 # Space between globe and breakdown
        speed_control_spacing = 15 # Space between breakdown and speed controls
        content_width = max(title_rect.width, frame_rect.width, breakdown_width)
        popup_width = content_width + padding
        popup_height = title_rect.height + title_spacing + frame_rect.height + padding
        if breakdown_surfaces:
            popup_height += breakdown_spacing + breakdown_height
        popup_height += speed_control_spacing + speed_controls_height

        popup_rect = pygame.Rect(0, 0, popup_width, popup_height)
        popup_rect.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)

        # Draw popup background and border
        pygame.draw.rect(self.screen, (40, 40, 60), popup_rect, border_radius=10)
        pygame.draw.rect(self.screen, (200, 200, 220), popup_rect, width=2, border_radius=10)

        # --- Draw Content ---
        # Title
        title_rect.centerx = popup_rect.centerx
        title_rect.top = popup_rect.top + (padding // 2)
        self.screen.blit(title_surface, title_rect)

        # Globe
        frame_rect.centerx = popup_rect.centerx
        frame_rect.top = title_rect.bottom + title_spacing
        self.screen.blit(current_frame, frame_rect)

        # Breakdown
        last_y = frame_rect.bottom
        if breakdown_surfaces:
            current_y = frame_rect.bottom + breakdown_spacing
            for surface in breakdown_surfaces:
                breakdown_rect = surface.get_rect(centerx=popup_rect.centerx, top=current_y)
                self.screen.blit(surface, breakdown_rect)
                current_y += surface.get_height()
            last_y = current_y
        
        # Speed Controls
        controls_y = last_y + speed_control_spacing
        spacing_between_controls = 10

        # Position speed display text in the center
        speed_display_rect = speed_display_surface.get_rect(
            centerx=popup_rect.centerx,
            top=controls_y
        )
        self.screen.blit(speed_display_surface, speed_display_rect)

        # Position speed down button to the left and store its rect for input handling
        self.globe_speed_down_rect = speed_down_surface.get_rect(
            right=speed_display_rect.left - spacing_between_controls,
            centery=speed_display_rect.centery
        )
        self.screen.blit(speed_down_surface, self.globe_speed_down_rect)

        # Position speed up button to the right and store its rect for input handling
        self.globe_speed_up_rect = speed_up_surface.get_rect(
            left=speed_display_rect.right + spacing_between_controls,
            centery=speed_display_rect.centery
        )
        self.screen.blit(speed_up_surface, self.globe_speed_up_rect)

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

    def open_context_menu(self, screen_pos: Tuple[int, int]) -> None:
        """Opens a context menu at the given screen position."""
        world_state = self.game.world_state
        if not world_state.hovered_tile:
            return

        context_menu = world_state.context_menu
        context_menu.active = True
        context_menu.pos = screen_pos
        context_menu.target_tile = world_state.hovered_tile
        context_menu.rects.clear()

        # Calculate rects for each option
        x, y = screen_pos
        padding = settings.CONTEXT_MENU_PADDING
        for i, option_data in enumerate(context_menu.options):
            option_text = option_data["label"]
            text_surface = context_menu.font.render(option_text, True, (0, 0, 0))
            width = text_surface.get_width() + padding * 2
            height = text_surface.get_height() + padding
            rect = pygame.Rect(x, y + i * height, width, height)
            context_menu.rects.append(rect)

    def close_context_menu(self) -> None:
        """Closes the context menu."""
        self.close_sub_menu()
        context_menu = self.game.world_state.context_menu
        context_menu.active = False
        context_menu.pos = None
        context_menu.rects.clear()
        context_menu.target_tile = None

    def handle_context_menu_click(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles a click when the context menu is active."""
        context_menu = self.game.world_state.context_menu

        # Check for sub-menu click first, as it's on top
        if context_menu.sub_menu.active:
            for i, rect in enumerate(context_menu.sub_menu.rects):
                if rect.collidepoint(mouse_pos):
                    option = context_menu.sub_menu.options[i]
                    print(f"Sub-menu option clicked: {option}")
                    self.game.issue_move_command_to_target()
                    self.close_context_menu()  # Close everything after action
                    return

        # Check for main menu click
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                option_data = context_menu.options[i]
                if "sub_options" in option_data:
                    return
                if option_data["label"] in ["Attack", "MoveTo"]:
                    self.game.issue_move_command_to_target()
                    self.close_context_menu()
                    return

        self.close_context_menu()