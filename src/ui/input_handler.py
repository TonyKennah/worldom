# c:/prj/WorldDom/src/input_handler.py
"""
Handles all user input, such as mouse and keyboard events.
"""
from __future__ import annotations
from typing import List, Optional, Tuple, TYPE_CHECKING

# src/ui/input_handler.py (inside handle_events loop)
import pygame

# ... within the event loop:
if event.type == pygame.KEYDOWN:
    if event.key == pygame.K_F1 or (event.key == pygame.K_SLASH and (pygame.key.get_mods() & pygame.KMOD_SHIFT)):
        # F1 or '?' toggles the in-game help overlay
        self.game.ui_manager.toggle_help_overlay()
        return  # consume if you want this to stop further handling

    # Optional: ESC closes help if open (without quitting)
    if event.key == pygame.K_ESCAPE and self.game.ui_manager.help_overlay.visible:
        self.game.ui_manager.toggle_help_overlay()
        return


import src.utils.settings as settings

if TYPE_CHECKING:
    from src.core.game import Game

class InputHandler:
    """Processes raw user input and delegates actions to the game."""

    def __init__(self, game: Game) -> None:
        """Initializes the InputHandler."""
        self.game = game
        # Action dispatch table for cleaner handling of UI commands
        self.actions = {
            "exit": lambda: setattr(self.game, 'running', False),
            "new_map": self.game.regenerate_map,
            "show_globe": lambda: setattr(self.game.ui_manager, 'show_globe_popup', True),
            "focus_on_player": self.game.focus_on_player_unit,
        }

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        """Processes a list of events from the main game loop."""
        # For now, we just handle the quit event to make the window closeable.
        for event in events:
            if event.type == pygame.QUIT:
                self.game.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # If the globe popup is open, Escape should close it.
                    # Otherwise, it should exit the game.
                    if self.game.ui_manager.show_globe_popup:
                        self.game.ui_manager.show_globe_popup = False
                    else:
                        self.game.running = False
            elif event.type == pygame.VIDEORESIZE:
                current_flags = self.game.screen.get_flags()
                self.game.screen = pygame.display.set_mode((event.w, event.h), current_flags)
                settings.SCREEN_WIDTH = event.w
                settings.SCREEN_HEIGHT = event.h
                self.game.camera.width = settings.SCREEN_WIDTH
                self.game.camera.height = settings.SCREEN_HEIGHT
                self.game.camera.screen_center = pygame.math.Vector2(
                    settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2
                )

            # Let the debug panel handle its events first
            action = self.game.debug_panel.handle_event(event)
            if action in self.actions:
                self.actions[action]()
                continue

            self._handle_mouse_events(event)

    def _is_click(self, start_pos: Optional[Tuple[int, int]], end_pos: Tuple[int, int]) -> bool:
        """Determines if a mouse down/up sequence is a click or a drag."""
        if not start_pos:
            return False
        vec_start = pygame.math.Vector2(start_pos)
        vec_end = pygame.math.Vector2(end_pos)
        dist = vec_start.distance_to(vec_end)
        return dist < 5  # Threshold for a click

    def _handle_mouse_events(self, event: pygame.event.Event) -> None:
        """Handles all mouse-related events by dispatching to helper methods."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_button_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_button_up(event)
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event)

    def _handle_mouse_button_down(self, event: pygame.event.Event) -> None:
        """Handles mouse button down events."""
        # Ignore other clicks that are inside the debug panel
        if event.pos[1] < settings.DEBUG_PANEL_HEIGHT:
            return

        if event.button == 1:
            if self.game.ui_manager.show_globe_popup:
                ui_manager = self.game.ui_manager
                # Check for clicks on globe popup controls first
                if ui_manager.globe_speed_down_rect and ui_manager.globe_speed_down_rect.collidepoint(event.pos):
                    ui_manager.decrease_globe_speed()
                    return  # Handled, don't close popup
                if ui_manager.globe_speed_up_rect and ui_manager.globe_speed_up_rect.collidepoint(event.pos):
                    ui_manager.increase_globe_speed()
                    return  # Handled, don't close popup

                self.game.ui_manager.show_globe_popup = False  # Close popup on any other click
                return  # Event handled
            elif self.game.world_state.context_menu.active:
                self.game.ui_manager.handle_context_menu_click(event.pos)
            else:
                self.game.world_state.left_mouse_down_screen_pos = event.pos
                self.game.world_state.left_mouse_down_world_pos = self.game.camera.screen_to_world(event.pos)
        elif event.button == 3:  # Right-click
            # On right-down, we only record the position to check for a click vs. drag later.
            self.game.world_state.right_mouse_down_pos = event.pos

    def _handle_mouse_button_up(self, event: pygame.event.Event) -> None:
        """Handles mouse button up events."""
        if event.button == 1:  # Left-click up
            self._handle_left_mouse_up(event)
        elif event.button == 3:  # Right-click up
            self._handle_right_mouse_up(event)

    def _clear_all_selections(self) -> None:
        """
        Clears the current selection. This is a helper to ensure that both the
        WorldState list and the individual unit flags are kept in sync.
        """
        for unit in self.game.world_state.selected_units:
            unit.selected = False
        self.game.world_state.selected_units.clear()

    def _handle_left_mouse_up(self, event: pygame.event.Event) -> None:
        """Handles left mouse button up events (click vs. drag)."""
        if self._is_click(self.game.world_state.left_mouse_down_screen_pos, event.pos):
            # Find if a unit was clicked by iterating in reverse draw order (top-most first)
            clicked_unit = None
            map_w_px = self.game.map.width * settings.TILE_SIZE
            map_h_px = self.game.map.height * settings.TILE_SIZE
            for unit in reversed(self.game.world_state.units):
                if unit.hit_test_screen_point(event.pos, self.game.camera, map_w_px, map_h_px):
                    clicked_unit = unit
                    break

            # If a unit was clicked, decide whether to select or deselect.
            if clicked_unit:
                if clicked_unit.selected:
                    self._clear_all_selections()
                else:
                    self.game.selection_manager.handle_left_click_selection(event.pos)
            # If empty ground was clicked...
            else:
                # ...and units are selected, it's a move command.
                if self.game.world_state.selected_units:
                    world_pos = self.game.camera.screen_to_world(event.pos)
                    map_width_pixels = self.game.map.width * self.game.map.tile_size
                    map_height_pixels = self.game.map.height * self.game.map.tile_size
                    wrapped_x = world_pos.x % map_width_pixels
                    wrapped_y = world_pos.y % map_height_pixels
                    tile_col = int(wrapped_x // self.game.map.tile_size)
                    tile_row = int(wrapped_y // self.game.map.tile_size)
                    self.game.issue_move_command_to_tile((tile_col, tile_row))
                # If no units are selected and the user clicks on empty terrain,
                # no action is taken. This is more explicit than the previous
                # no-op call to the selection manager.
        elif self.game.world_state.selection_box:  # It's a drag
            self.game.selection_manager.handle_drag_selection(self.game.world_state.selection_box)

        self.game.world_state.left_mouse_down_screen_pos = None  # Reset after use
        self.game.world_state.left_mouse_down_world_pos = None
        self.game.world_state.selection_box = None

    def _handle_right_mouse_up(self, event: pygame.event.Event) -> None:
        """Handles right mouse button up events (click vs. drag)."""
        if self._is_click(self.game.world_state.right_mouse_down_pos, event.pos):
            # If the menu is already active, a right-click should close it.
            if self.game.world_state.context_menu.active:
                self.game.ui_manager.close_context_menu()
            # Otherwise, if units are selected, open the menu.
            elif self.game.world_state.selected_units:
                self.game.ui_manager.open_context_menu(event.pos)

        self.game.world_state.right_mouse_down_pos = None

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        """Handles mouse motion for drawing the selection box."""
        if self.game.world_state.left_mouse_down_world_pos:
            # Convert the fixed world start position back to current screen coordinates
            start_pos_screen = self.game.camera.world_to_screen(self.game.world_state.left_mouse_down_world_pos)
            current_pos_screen = pygame.math.Vector2(event.pos)

            x = min(start_pos_screen.x, current_pos_screen.x)
            y = min(start_pos_screen.y, current_pos_screen.y)
            width = abs(start_pos_screen.x - current_pos_screen.x)
            height = abs(start_pos_screen.y - current_pos_screen.y)
            self.game.world_state.selection_box = pygame.Rect(x, y, width, height)
