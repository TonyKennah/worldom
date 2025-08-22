# src/ui/ui_manager.py
"""
Handles the rendering and state of all UI elements in the game.
- Selection box
- Context menu (and sub-menu)
- Rotating globe popup with speed controls
- Help overlay hook
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING

import pygame
import src.utils.settings as settings

# Optional help overlay (created earlier in patch series)
try:
    from src.ui.help_overlay import HelpOverlay
except Exception:  # Fallback stub to avoid import errors if file not present
    class HelpOverlay:  # type: ignore
        def __init__(self) -> None:
            self.visible: bool = False

        def toggle(self) -> None:
            self.visible = not self.visible

        def draw(self, *_args, **_kwargs) -> None:
            pass

if TYPE_CHECKING:
    from src.core.game import Game


class UIManager:
    """Manages the drawing and state of all UI components."""

    def __init__(self, game: Game) -> None:
        """Initializes the UI Manager."""
        self.game = game
        self.screen = game.screen

        # --- Globe Animation State ---
        self.show_globe_popup: bool = False
        self.globe_frame_index: int = 0
        self.globe_animation_timer: float = 0.0
        self.globe_animation_speed_index: int = getattr(
            settings, "GLOBE_ANIMATION_DEFAULT_SPEED_INDEX", 1
        )
        self.globe_speed_down_rect: Optional[pygame.Rect] = None
        self.globe_speed_up_rect: Optional[pygame.Rect] = None

        # Fonts
        self.popup_title_font = pygame.font.SysFont("Arial", 24, bold=True)
        self.breakdown_font = pygame.font.SysFont("Arial", 18)
        self.speed_control_font = pygame.font.SysFont("Arial", 16, bold=True)
        self.font = pygame.font.SysFont(
            "Arial", getattr(settings, "CONTEXT_MENU_FONT_SIZE", 16)
        )

        # Help overlay
        self.help_overlay = HelpOverlay()

    # --------------------------------------------------------------------- #
    # Public API (called from Game / input handlers)
    # --------------------------------------------------------------------- #

    def toggle_help_overlay(self) -> None:
        """Toggle on-screen help overlay."""
        self.help_overlay.toggle()

    def toggle_globe_popup(self) -> None:
        """Show/hide the rotating globe popup."""
        self.show_globe_popup = not self.show_globe_popup

    def handle_mouse_move(self, mouse_pos: Tuple[int, int]) -> None:
        """Hover logic for context menu/sub-menu."""
        if self.game.world_state.context_menu.active:
            self.handle_context_menu_hover(mouse_pos)

    def handle_mouse_down(self, mouse_pos: Tuple[int, int]) -> None:
        """
        Handle clicks on globe speed controls (if globe popup is visible),
        and forward to context menu click handling when active.
        """
        if self.show_globe_popup:
            if self.globe_speed_down_rect and self.globe_speed_down_rect.collidepoint(mouse_pos):
                self.decrease_globe_speed()
                return
            if self.globe_speed_up_rect and self.globe_speed_up_rect.collidepoint(mouse_pos):
                self.increase_globe_speed()
                return

        if self.game.world_state.context_menu.active:
            self.handle_context_menu_click(mouse_pos)

    # --------------------------------------------------------------------- #
    # Update & animation
    # --------------------------------------------------------------------- #

    def update(self, dt: float) -> None:
        """Updates UI components, like animations."""
        if self.show_globe_popup:
            self._update_globe_animation(dt)

    def _update_globe_animation(self, dt: float) -> None:
        """Cycles through the globe animation frames based on a timer."""
        frames = getattr(self.game, "globe_frames", None)
        if not frames:
            return

        speeds = getattr(settings, "GLOBE_ANIMATION_SPEEDS", (0.12, 0.08, 0.04, math.inf))
        idx = max(0, min(self.globe_animation_speed_index, len(speeds) - 1))
        frame_duration = speeds[idx]

        if math.isinf(frame_duration):  # paused
            return

        self.globe_animation_timer += dt
        if self.globe_animation_timer >= frame_duration:
            self.globe_animation_timer = 0.0
            self.globe_frame_index = (self.globe_frame_index + 1) % len(frames)

    def increase_globe_speed(self) -> None:
        """Increases the globe's rotation speed."""
        speeds = getattr(settings, "GLOBE_ANIMATION_SPEEDS", (0.12, 0.08, 0.04, math.inf))
        self.globe_animation_speed_index = min(
            self.globe_animation_speed_index + 1, len(speeds) - 1
        )

    def decrease_globe_speed(self) -> None:
        """Decreases the globe's rotation speed."""
        self.globe_animation_speed_index = max(self.globe_animation_speed_index - 1, 0)

    # --------------------------------------------------------------------- #
    # Draw entry-point
    # --------------------------------------------------------------------- #

    def draw_ui(self) -> None:
        """Draws all UI elements, called once per frame."""
        # Selection box
        if self.game.world_state.selection_box:
            pygame.draw.rect(
                self.screen,
                settings.SELECTION_BOX_COLOR,
                self.game.world_state.selection_box,
                settings.SELECTION_BOX_BORDER_WIDTH,
            )

        # Globe popup
        if self.show_globe_popup:
            self.draw_globe_popup()

        # Context menu (& sub-menu)
        if self.game.world_state.context_menu.active:
            self.draw_context_menu()
            if self.game.world_state.context_menu.sub_menu.active:
                self.draw_sub_menu()

        # Help overlay (on top)
        if getattr(self.help_overlay, "visible", False):
            self.help_overlay.draw(self.screen, settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

    # --------------------------------------------------------------------- #
    # Globe popup
    # --------------------------------------------------------------------- #

    def draw_globe_popup(self) -> None:
        """Draw the globe animation popup in the center of the screen."""
        frames = getattr(self.game, "globe_frames", None)
        if not frames:
            return

        overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Title
        title_text = f"{getattr(settings, 'ACTIVE_THEME', {}).get('name', 'World')} Overview"
        title_surface = self.popup_title_font.render(
            title_text, True, settings.DEBUG_PANEL_FONT_COLOR
        )
        title_rect = title_surface.get_rect()

        # Globe image frame
        frame_idx = self.globe_frame_index % len(frames)
        current_frame: pygame.Surface = frames[frame_idx]
        frame_rect = current_frame.get_rect()

        # Terrain breakdown (safe against missing APIs)
        percentages: Dict[str, float] = {}
        try:
            if hasattr(self.game, "map") and hasattr(self.game.map, "get_terrain_percentages"):
                percentages = self.game.map.get_terrain_percentages() or {}
        except Exception:
            percentages = {}

        breakdown_items: List[Tuple[pygame.Surface, pygame.Surface]] = []
        max_text_width = 0
        if percentages:
            sorted_terrain = sorted(percentages.items(), key=lambda item: item[1], reverse=True)
            for terrain, pct in sorted_terrain:
                if pct > 0:
                    terrain_data = settings.TERRAIN_DATA.get(terrain, {})
                    terrain_name = terrain_data.get("name", terrain.capitalize())
                    terrain_color = terrain_data.get("color", (128, 128, 128))

                    text = f"{terrain_name}: {pct:.1f}%"
                    text_surface = self.breakdown_font.render(text, True, settings.DEBUG_PANEL_FONT_COLOR)
                    max_text_width = max(max_text_width, text_surface.get_width())

                    swatch_size = text_surface.get_height()
                    swatch_surface = pygame.Surface((swatch_size, swatch_size))
                    swatch_surface.fill(terrain_color)
                    breakdown_items.append((swatch_surface, text_surface))

        breakdown_height = 0
        breakdown_width = 0
        if breakdown_items:
            spacing = 8
            swatch_size = breakdown_items[0][0].get_height()
            breakdown_height = sum(item[0].get_height() for item in breakdown_items)
            breakdown_width = swatch_size + spacing + max_text_width

        # Speed controls
        speed_down_surface = self.speed_control_font.render(" << ", True, settings.DEBUG_PANEL_FONT_COLOR)
        speed_up_surface = self.speed_control_font.render(" >> ", True, settings.DEBUG_PANEL_FONT_COLOR)

        speeds = getattr(settings, "GLOBE_ANIMATION_SPEEDS", (0.12, 0.08, 0.04, math.inf))
        default_idx = getattr(settings, "GLOBE_ANIMATION_DEFAULT_SPEED_INDEX", 1)
        default_duration = speeds[default_idx]
        current_duration = speeds[self.globe_animation_speed_index]

        if math.isinf(current_duration):
            speed_text = "Speed: Paused"
        else:
            try:
                speed_multiplier = default_duration / current_duration if current_duration > 0 else 0.0
            except ZeroDivisionError:
                speed_multiplier = 0.0
            speed_text = f"Speed: {speed_multiplier:.1f}x"
        speed_display_surface = self.breakdown_font.render(speed_text, True, settings.DEBUG_PANEL_FONT_COLOR)

        speed_controls_height = max(
            speed_down_surface.get_height(),
            speed_display_surface.get_height(),
            speed_up_surface.get_height(),
        )

        # Popup container metrics
        padding = 40
        title_spacing = 20
        breakdown_spacing = 20
        speed_control_spacing = 15
        content_width = max(title_rect.width, frame_rect.width, breakdown_width)
        popup_width = content_width + padding
        popup_height = title_rect.height + title_spacing + frame_rect.height + padding
        if breakdown_items:
            popup_height += breakdown_spacing + breakdown_height
        popup_height += speed_control_spacing + speed_controls_height

        popup_rect = pygame.Rect(0, 0, popup_width, popup_height)
        popup_rect.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)

        # Background + border
        pygame.draw.rect(self.screen, (40, 40, 60), popup_rect, border_radius=10)
        pygame.draw.rect(self.screen, (200, 200, 220), popup_rect, width=2, border_radius=10)

        # Title
        title_rect.centerx = popup_rect.centerx
        title_rect.top = popup_rect.top + (padding // 2)
        self.screen.blit(title_surface, title_rect)

        # Globe frame
        frame_rect.centerx = popup_rect.centerx
        frame_rect.top = title_rect.bottom + title_spacing
        self.screen.blit(current_frame, frame_rect)

        # Breakdown
        last_y = frame_rect.bottom
        if breakdown_items:
            current_y = frame_rect.bottom + breakdown_spacing
            spacing = 8
            swatch_size = breakdown_items[0][0].get_height()
            total_width = swatch_size + spacing + max_text_width
            start_x = popup_rect.centerx - (total_width / 2)
            for swatch_surface, text_surface in breakdown_items:
                swatch_rect = swatch_surface.get_rect(left=start_x, top=current_y)
                self.screen.blit(swatch_surface, swatch_rect)
                text_rect = text_surface.get_rect(left=swatch_rect.right + spacing, centery=swatch_rect.centery)
                self.screen.blit(text_surface, text_rect)
                current_y += swatch_surface.get_height()
            last_y = current_y

        # Speed controls
        controls_y = last_y + speed_control_spacing
        spacing_between_controls = 10

        speed_display_rect = speed_display_surface.get_rect(centerx=popup_rect.centerx, top=controls_y)
        self.screen.blit(speed_display_surface, speed_display_rect)

        self.globe_speed_down_rect = speed_down_surface.get_rect(
            right=speed_display_rect.left - spacing_between_controls,
            centery=speed_display_rect.centery,
        )
        self.screen.blit(speed_down_surface, self.globe_speed_down_rect)

        self.globe_speed_up_rect = speed_up_surface.get_rect(
            left=speed_display_rect.right + spacing_between_controls,
            centery=speed_display_rect.centery,
        )
        self.screen.blit(speed_up_surface, self.globe_speed_up_rect)

    # --------------------------------------------------------------------- #
    # Context menu (+ sub-menu)
    # --------------------------------------------------------------------- #

    def draw_context_menu(self) -> None:
        """Renders the context menu on the screen as a single panel."""
        context_menu = self.game.world_state.context_menu
        if not context_menu.rects:
            return

        panel_rect = context_menu.rects[0].unionall(context_menu.rects[1:])
        pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BG_COLOR, panel_rect, border_radius=3)
        pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BORDER_COLOR, panel_rect, 1, border_radius=3)

        mouse_pos = pygame.mouse.get_pos()
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, settings.CONTEXT_MENU_HOVER_BG_COLOR, rect, border_radius=3)
            option_text = context_menu.options[i]["label"]
            text_surface = self.font.render(option_text, True, settings.CONTEXT_MENU_TEXT_COLOR)
            text_rect = text_surface.get_rect(x=rect.x + settings.CONTEXT_MENU_PADDING, centery=rect.centery)
            self.screen.blit(text_surface, text_rect)

    def draw_sub_menu(self) -> None:
        """Renders the sub-menu on the screen as a single panel."""
        sub_menu = self.game.world_state.context_menu.sub_menu
        if not sub_menu.rects:
            return

        panel_rect = sub_menu.rects[0].unionall(sub_menu.rects[1:])
        pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BG_COLOR, panel_rect, border_radius=3)
        pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BORDER_COLOR, panel_rect, 1, border_radius=3)

        mouse_pos = pygame.mouse.get_pos()
        for i, rect in enumerate(sub_menu.rects):
            if rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, settings.CONTEXT_MENU_HOVER_BG_COLOR, rect, border_radius=3)
            option_text = sub_menu.options[i]["label"]
            text_surface = self.font.render(option_text, True, settings.CONTEXT_MENU_TEXT_COLOR)
            text_rect = text_surface.get_rect(x=rect.x + settings.CONTEXT_MENU_PADDING, centery=rect.centery)
            self.screen.blit(text_surface, text_rect)

    def handle_context_menu_hover(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles hover events for the context menu to show sub-menus."""
        context_menu = self.game.world_state.context_menu

        hovered_main_item = False
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                hovered_main_item = True
                option_data = context_menu.options[i]
                if "sub_options" in option_data:
                    if (not context_menu.sub_menu.active) or (context_menu.sub_menu.parent_rect != rect):
                        self._open_sub_menu(option_data["sub_options"], rect)
                else:
                    self.close_sub_menu()
                break

        if not hovered_main_item:
            is_mouse_on_sub_menu = False
            if context_menu.sub_menu.active:
                for sub_rect in context_menu.sub_menu.rects:
                    if sub_rect.collidepoint(mouse_pos):
                        is_mouse_on_sub_menu = True
                        break
            if not is_mouse_on_sub_menu:
                self.close_sub_menu()

    def _open_sub_menu(self, sub_options: List[Dict[str, Any]], parent_rect: pygame.Rect) -> None:
        """Opens a sub-menu next to a parent menu item."""
        context_menu = self.game.world_state.context_menu
        context_menu.sub_menu.active = True
        context_menu.sub_menu.options = sub_options.copy()
        context_menu.sub_menu.parent_rect = parent_rect
        context_menu.sub_menu.rects.clear()

        padding = settings.CONTEXT_MENU_PADDING

        max_width = 0
        for option_data in sub_options:
            text_surface = self.font.render(option_data["label"], True, settings.CONTEXT_MENU_TEXT_COLOR)
            max_width = max(max_width, text_surface.get_width())
        item_width = max_width + padding * 2

        x = parent_rect.right
        y = parent_rect.top
        for i, option_data in enumerate(sub_options):
            option_text = option_data["label"]
            text_surface = self.font.render(option_text, True, settings.CONTEXT_MENU_TEXT_COLOR)
            width = item_width
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

        padding = settings.CONTEXT_MENU_PADDING

        max_width = 0
        for option_data in context_menu.options:
            text_surface = self.font.render(option_data["label"], True, settings.CONTEXT_MENU_TEXT_COLOR)
            max_width = max(max_width, text_surface.get_width())
        item_width = max_width + padding * 2

        x, y = screen_pos
        for i, option_data in enumerate(context_menu.options):
            option_text = option_data["label"]
            text_surface = self.font.render(option_text, True, settings.CONTEXT_MENU_TEXT_COLOR)
            width = item_width
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

        # Sub-menu first
        if context_menu.sub_menu.active:
            for i, rect in enumerate(context_menu.sub_menu.rects):
                if rect.collidepoint(mouse_pos):
                    option = context_menu.sub_menu.options[i]
                    # Default action on sub-option: move to target (leave as-is for feature parity)
                    getattr(self.game, "issue_move_command_to_target", lambda: None)()
                    self.close_context_menu()
                    return

        # Main menu
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                option_data = context_menu.options[i]
                if "sub_options" in option_data:
                    # Opening submenu is handled in hover; no-op on main click.
                    return
                if option_data["label"] in ["Attack", "Move"]:
                    getattr(self.game, "issue_move_command_to_target", lambda: None)()
                    self.close_context_menu()
                    return

        self.close_context_menu()
