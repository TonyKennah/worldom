# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.
"""
import math
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

import pygame
import settings

from settings import (FPS, BG_COLOR, MAP_WIDTH_TILES, MAP_HEIGHT_TILES, SELECTION_BOX_COLOR,
                      SELECTION_BOX_BORDER_WIDTH, DEBUG_PANEL_HEIGHT, DEBUG_PANEL_BG_COLOR,
                      DEBUG_PANEL_FONT_COLOR, DEBUG_PANEL_FONT_SIZE, CONTEXT_MENU_BG_COLOR,
                      CONTEXT_MENU_BORDER_COLOR, CONTEXT_MENU_TEXT_COLOR, CONTEXT_MENU_FONT_SIZE, CONTEXT_MENU_PADDING)
from camera import Camera
from map import Map
from unit import Unit

class ContextMenuState:
    """Encapsulates the state of the right-click context menu."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.active: bool = False
        self.pos: Optional[Tuple[int, int]] = None
        self.options: List[Dict[str, Any]] = [
            {"label": "Attack"},
            {"label": "Build", "sub_options": ["Shelter", "Workshop", "Farm", "Barracks"]},
            {"label": "MoveTo"},
        ]
        self.rects: List[pygame.Rect] = []
        self.target_tile: Optional[Tuple[int, int]] = None
        self.font = pygame.font.SysFont("Arial", CONTEXT_MENU_FONT_SIZE)
        # Sub-menu state
        self.sub_menu_active: bool = False
        self.sub_menu_options: List[str] = []
        self.sub_menu_rects: List[pygame.Rect] = []
        self.sub_menu_parent_rect: Optional[pygame.Rect] = None

class WorldState:
    """Encapsulates the state of all game objects and player interaction."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.units: List[Unit] = []
        self.selected_units: List[Unit] = []
        self.hovered_tile: Optional[Tuple[int, int]] = None
        self.left_mouse_down_pos: Optional[Tuple[int, int]] = None
        self.right_mouse_down_pos: Optional[Tuple[int, int]] = None
        self.selection_box: Optional[pygame.Rect] = None
        self.context_menu = ContextMenuState()

# --- Game Class ---
class Game:
    """The main game class, orchestrating all game components."""
    def __init__(self) -> None:
        pygame.init()

        # Start with a resizable, maximized window if possible
        flags = pygame.RESIZABLE
        try:
            # pygame.MAXIMIZED is available in Pygame 2.0.1+
            flags |= pygame.MAXIMIZED
        except AttributeError:
            # If the flag doesn't exist, we'll just get a default-sized resizable window.
            # This is a safe fallback for older Pygame versions.
            pass
        self.screen = pygame.display.set_mode((0, 0), flags)

        # Update the settings module with the actual screen size.
        # This makes the true dimensions available globally to other modules
        # that import the settings, like the camera and map.
        settings.SCREEN_WIDTH = self.screen.get_width()
        settings.SCREEN_HEIGHT = self.screen.get_height()

        pygame.display.set_caption("WorldDom")
        self.clock = pygame.time.Clock()
        self.running: bool = True
        self.events: List[pygame.event.Event] = []
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        self.debug_font = pygame.font.SysFont("Arial", DEBUG_PANEL_FONT_SIZE)
        self.exit_link_rect: Optional[pygame.Rect] = None

        self.map = Map(MAP_WIDTH_TILES, MAP_HEIGHT_TILES)
        self.world_state = WorldState()
        initial_unit = self._spawn_initial_units()

        # Center camera on the initial unit
        if initial_unit:
            # Use .copy() to prevent the camera and unit from sharing the same Vector2 object
            self.camera.position = initial_unit.world_pos.copy()

    def run(self) -> None:
        """The main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()

    def _spawn_initial_units(self) -> Unit:
        """
        Creates the starting units for the game, ensuring it's on a grass tile
        and no water is visible on screen at the start. Returns the first unit.
        """
        # Calculate how many tiles are visible from the center to the edge of the screen
        # at the initial zoom level. Add a small buffer.
        initial_zoom = self.camera.zoom_state.current
        radius_x = math.ceil(
            (settings.SCREEN_WIDTH / 2 / initial_zoom) / settings.TILE_SIZE
        ) + 1
        radius_y = math.ceil(
            (settings.SCREEN_HEIGHT / 2 / initial_zoom) / settings.TILE_SIZE
        ) + 1

        # Try to find a valid spawn point up to a max number of attempts
        for _ in range(1000):  # Max attempts to prevent infinite loop
            x = random.randint(0, self.map.width - 1)
            y = random.randint(0, self.map.height - 1)

            # Condition 1: The spawn tile must be grass
            if self.map.data[y][x] != 'grass':
                continue

            # Condition 2: No water tiles should be in the visible area
            is_ocean_visible = False
            for j in range(y - radius_y, y + radius_y + 1):
                for i in range(x - radius_x, x + radius_x + 1):
                    if 0 <= i < self.map.width and 0 <= j < self.map.height:
                        if self.map.data[j][i] == 'water':
                            is_ocean_visible = True
                            break
                if is_ocean_visible:
                    break

            if not is_ocean_visible:
                # Found a valid spawn point
                new_unit = Unit((x, y))
                self.world_state.units.append(new_unit)
                return new_unit

        # Fallback if no suitable spot is found after many tries.
        # This might happen on maps with a lot of water.
        # Just spawn on any grass tile.
        while True:
            x, y = random.randint(0, self.map.width - 1), random.randint(0, self.map.height - 1)
            if self.map.data[y][x] == 'grass':
                new_unit = Unit((x, y))
                self.world_state.units.append(new_unit)
                return new_unit

    def handle_events(self) -> None:
        """Processes all user input and events."""
        self.events = pygame.event.get()
        for event in self.events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            elif event.type == pygame.VIDEORESIZE:
                current_flags = self.screen.get_flags()
                self.screen = pygame.display.set_mode((event.w, event.h), current_flags)
                settings.SCREEN_WIDTH = event.w
                settings.SCREEN_HEIGHT = event.h
                self.camera.width = settings.SCREEN_WIDTH
                self.camera.height = settings.SCREEN_HEIGHT
                self.camera.screen_center = pygame.math.Vector2(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2)

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
        # Handle UI clicks first. We only care about left-clicks for UI.
        if event.button == 1:
            if self.exit_link_rect and self.exit_link_rect.collidepoint(event.pos):
                self.running = False
                return

        # Ignore other clicks that are inside the debug panel
        if event.pos[1] < DEBUG_PANEL_HEIGHT:
            return

        if event.button == 1:
            if self.world_state.context_menu.active:
                self._handle_context_menu_click(event.pos)
            else:
                self.world_state.left_mouse_down_pos = event.pos
        elif event.button == 3:  # Right-click
            if self.world_state.context_menu.active:
                self._close_context_menu()
            else:
                self.world_state.right_mouse_down_pos = event.pos

    def _handle_mouse_button_up(self, event: pygame.event.Event) -> None:
        """Handles mouse button up events."""
        if event.button == 1:  # Left-click up
            self._handle_left_mouse_up(event)
        elif event.button == 3:  # Right-click up
            self._handle_right_mouse_up(event)

    def _handle_left_mouse_up(self, event: pygame.event.Event) -> None:
        """Handles left mouse button up events (click vs. drag)."""
        if self._is_click(self.world_state.left_mouse_down_pos, event.pos):
            self._handle_left_click_selection(event.pos)
        elif self.world_state.selection_box:  # It's a drag
            self._handle_drag_selection(self.world_state.selection_box)

        self.world_state.left_mouse_down_pos = None  # Reset after use
        self.world_state.selection_box = None

    def _handle_right_mouse_up(self, event: pygame.event.Event) -> None:
        """Handles right mouse button up events (click vs. drag)."""
        if self._is_click(self.world_state.right_mouse_down_pos, event.pos):
            if self.world_state.selected_units:
                self._open_context_menu(event.pos)

        self.world_state.right_mouse_down_pos = None

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        """Handles mouse motion for drawing the selection box."""
        if self.world_state.left_mouse_down_pos:
            start_pos = self.world_state.left_mouse_down_pos
            current_pos = event.pos
            x = min(start_pos[0], current_pos[0])
            y = min(start_pos[1], current_pos[1])
            width = abs(start_pos[0] - current_pos[0])
            height = abs(start_pos[1] - current_pos[1])
            self.world_state.selection_box = pygame.Rect(x, y, width, height)

    def _open_context_menu(self, screen_pos: Tuple[int, int]) -> None:
        """Opens a context menu at the given screen position."""
        if not self.world_state.hovered_tile:
            return

        self.world_state.context_menu.active = True
        self.world_state.context_menu.pos = screen_pos
        self.world_state.context_menu.target_tile = self.world_state.hovered_tile
        self.world_state.context_menu.rects.clear()

        # Calculate rects for each option
        x, y = screen_pos
        padding = CONTEXT_MENU_PADDING
        for i, option_data in enumerate(self.world_state.context_menu.options):
            option_text = option_data["label"]
            text_surface = self.world_state.context_menu.font.render(option_text, True, (0, 0, 0))
            width = text_surface.get_width() + padding * 2
            height = text_surface.get_height() + padding
            rect = pygame.Rect(x, y + i * height, width, height)
            self.world_state.context_menu.rects.append(rect)

    def _close_context_menu(self) -> None:
        """Closes the context menu."""
        self._close_sub_menu()
        self.world_state.context_menu.active = False
        self.world_state.context_menu.pos = None
        self.world_state.context_menu.rects.clear()
        self.world_state.context_menu.target_tile = None

    def _handle_context_menu_click(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles a click when the context menu is active."""
        context_menu = self.world_state.context_menu

        # Check for sub-menu click first, as it's on top
        if context_menu.sub_menu_active:
            for i, rect in enumerate(context_menu.sub_menu_rects):
                if rect.collidepoint(mouse_pos):
                    option = context_menu.sub_menu_options[i]
                    print(f"Sub-menu option clicked: {option}")
                    self._issue_move_command_to_target()
                    self._close_context_menu()  # Close everything after action
                    return

        # Check for main menu click
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                option_data = context_menu.options[i]
                option_label = option_data["label"]
                if "sub_options" not in option_data and option_label in ["Attack", "MoveTo"]:
                    self._issue_move_command_to_target()
                    self._close_context_menu()
                    return

        # If we clicked, but not on an actionable item (e.g. on Build, or outside all menus)
        # just close everything.
        self._close_context_menu()

    def _issue_move_command_to_target(self) -> None:
        """Issues a move command to selected units to the stored target tile."""
        target_tile = self.world_state.context_menu.target_tile
        if not self.world_state.selected_units or not target_tile:
            return

        tile_x, tile_y = target_tile
        terrain = self.map.data[tile_y][tile_x]

        if terrain == 'water':
            print("Units cannot move into water.")
            return

        for unit in self.world_state.selected_units:
            start_pos = unit.tile_pos
            end_pos = pygame.math.Vector2(target_tile)
            path = self.map.find_path(start_pos, end_pos)
            if path is not None:
                unit.set_path(path)

    def _handle_left_click_selection(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles unit selection logic for a left click."""
        world_pos = self.camera.screen_to_world(mouse_pos)

        # Deselect all units first
        for unit in self.world_state.selected_units:
            unit.selected = False
        self.world_state.selected_units.clear()

        # Find and select the clicked unit
        for unit in self.world_state.units:
            if unit.get_world_rect().collidepoint(world_pos):
                unit.selected = True
                self.world_state.selected_units.append(unit)
                break  # Stop after selecting one unit

    def _handle_drag_selection(self, selection_rect_screen: pygame.Rect) -> None:
        """Selects units within a given rectangle in screen coordinates."""
        # Deselect all units first, unless holding shift (extension for later)
        for unit in self.world_state.selected_units:
            unit.selected = False
        self.world_state.selected_units.clear()

        # Convert screen rect to world rect to check for collisions with units
        world_topleft = self.camera.screen_to_world(selection_rect_screen.topleft)
        world_bottomright = self.camera.screen_to_world(selection_rect_screen.bottomright)
        selection_rect_world = pygame.Rect(
            world_topleft,
            (world_bottomright.x - world_topleft.x, world_bottomright.y - world_topleft.y)
        )
        selection_rect_world.normalize()

        for unit in self.world_state.units:
            if selection_rect_world.colliderect(unit.get_world_rect()):
                unit.selected = True
                self.world_state.selected_units.append(unit)


    def update(self, dt: float) -> None:
        """Updates the state of all game objects."""
        self.camera.update(dt, self.events)

        # Update all units
        for unit in self.world_state.units:
            unit.update(dt)

        if self.world_state.context_menu.active:
            self._handle_context_menu_hover(pygame.mouse.get_pos())
        else:
            self._update_hovered_tile()

    def _update_hovered_tile(self) -> None:
        """Calculates which map tile is currently under the mouse cursor."""
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(mouse_pos)
        tile_col = int(world_pos.x // self.map.tile_size)
        tile_row = int(world_pos.y // self.map.tile_size)

        if 0 <= tile_col < self.map.width and 0 <= tile_row < self.map.height:
            self.world_state.hovered_tile = (tile_col, tile_row)
        else:
            self.world_state.hovered_tile = None

    def draw(self) -> None:
        """Renders all game objects to the screen."""
        self.screen.fill(BG_COLOR)
        self.map.draw(self.screen, self.camera, self.world_state.hovered_tile)

        # Draw all units
        for unit in self.world_state.units:
            unit.draw(self.screen, self.camera)

        # Draw selection box
        if self.world_state.selection_box:
            pygame.draw.rect(self.screen, SELECTION_BOX_COLOR,
                             self.world_state.selection_box, SELECTION_BOX_BORDER_WIDTH)

        # Draw context menu if active
        if self.world_state.context_menu.active:
            self._draw_context_menu()
            if self.world_state.context_menu.sub_menu_active:
                self._draw_sub_menu()

        self._draw_debug_panel()
        pygame.display.flip()

    def _draw_context_menu(self) -> None:
        """Renders the context menu on the screen."""
        if not self.world_state.context_menu.rects:
            return

        for i, rect in enumerate(self.world_state.context_menu.rects):
            option_text = self.world_state.context_menu.options[i]["label"]

            # Draw background and border
            pygame.draw.rect(self.screen, CONTEXT_MENU_BG_COLOR, rect)
            pygame.draw.rect(self.screen, CONTEXT_MENU_BORDER_COLOR, rect, 1)

            text_surface = self.world_state.context_menu.font.render(
                option_text, True, CONTEXT_MENU_TEXT_COLOR)
            text_x = rect.x + CONTEXT_MENU_PADDING
            text_y = rect.y + (CONTEXT_MENU_PADDING / 2)
            self.screen.blit(text_surface, (text_x, text_y))

    def _draw_sub_menu(self) -> None:
        """Renders the sub-menu on the screen."""
        context_menu = self.world_state.context_menu
        if not context_menu.sub_menu_rects:
            return

        for i, rect in enumerate(context_menu.sub_menu_rects):
            option_text = context_menu.sub_menu_options[i]

            # Draw background and border
            pygame.draw.rect(self.screen, CONTEXT_MENU_BG_COLOR, rect)
            pygame.draw.rect(self.screen, CONTEXT_MENU_BORDER_COLOR, rect, 1)

            text_surface = context_menu.font.render(option_text, True, CONTEXT_MENU_TEXT_COLOR)
            text_x = rect.x + CONTEXT_MENU_PADDING
            text_y = rect.y + (CONTEXT_MENU_PADDING / 2)
            self.screen.blit(text_surface, (text_x, text_y))

    def _handle_context_menu_hover(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles hover events for the context menu to show sub-menus."""
        context_menu = self.world_state.context_menu

        hovered_main_item = False
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                hovered_main_item = True
                option_data = context_menu.options[i]
                if "sub_options" in option_data:
                    # Open sub-menu if not already open for this item
                    if not context_menu.sub_menu_active or context_menu.sub_menu_parent_rect != rect:
                        self._open_sub_menu(option_data["sub_options"], rect)
                else:
                    # This item has no sub-menu, so close any active one
                    self._close_sub_menu()
                break  # Found the hovered item

        if not hovered_main_item:
            # Mouse is not over any main menu item. Check if it's over the sub-menu.
            is_mouse_on_sub_menu = False
            if context_menu.sub_menu_active:
                for sub_rect in context_menu.sub_menu_rects:
                    if sub_rect.collidepoint(mouse_pos):
                        is_mouse_on_sub_menu = True
                        break

            if not is_mouse_on_sub_menu:
                self._close_sub_menu()

    def _open_sub_menu(self, sub_options: List[str], parent_rect: pygame.Rect) -> None:
        """Opens a sub-menu next to a parent menu item."""
        context_menu = self.world_state.context_menu
        context_menu.sub_menu_active = True
        context_menu.sub_menu_options = sub_options.copy()
        context_menu.sub_menu_parent_rect = parent_rect
        context_menu.sub_menu_rects.clear()

        # Position sub-menu to the right of the parent
        x = parent_rect.right
        y = parent_rect.top
        padding = CONTEXT_MENU_PADDING

        for i, option_text in enumerate(sub_options):
            text_surface = context_menu.font.render(option_text, True, (0, 0, 0))
            width = text_surface.get_width() + padding * 2
            height = text_surface.get_height() + padding
            rect = pygame.Rect(x, y + i * height, width, height)
            context_menu.sub_menu_rects.append(rect)

    def _close_sub_menu(self) -> None:
        """Closes the sub-menu."""
        context_menu = self.world_state.context_menu
        if not context_menu.sub_menu_active:
            return
        context_menu.sub_menu_active = False
        context_menu.sub_menu_options.clear()
        context_menu.sub_menu_rects.clear()
        context_menu.sub_menu_parent_rect = None

    def _draw_debug_panel(self) -> None:
        """Renders the debug information panel at the top of the screen."""
        panel_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, DEBUG_PANEL_HEIGHT)
        pygame.draw.rect(self.screen, DEBUG_PANEL_BG_COLOR, panel_rect)

        world_pos = self.camera.screen_to_world(pygame.mouse.get_pos())
        world_coords = f"({int(world_pos.x)}, {int(world_pos.y)})"
        zoom_percentage = self.camera.zoom_state.current * 100
        info_string = (
            f"FPS: {self.clock.get_fps():.1f} | "
            f"Zoom: {zoom_percentage:.0f}% | "
            f"World: {world_coords}"
        )
        if self.world_state.hovered_tile:
            tile_x, tile_y = self.world_state.hovered_tile
            terrain = self.map.data[tile_y][tile_x]
            tile_info = f"({tile_x}, {tile_y}) ({terrain.capitalize()})"
            info_string += f" | Tile: {tile_info}"

        text_surface = self.debug_font.render(info_string, True, DEBUG_PANEL_FONT_COLOR)
        # Vertically center the text in the panel
        text_y = (DEBUG_PANEL_HEIGHT - text_surface.get_height()) // 2
        self.screen.blit(text_surface, (10, text_y))

        # Draw the "Exit" link on the right
        exit_text_surface = self.debug_font.render("Exit", True, DEBUG_PANEL_FONT_COLOR)
        exit_text_x = settings.SCREEN_WIDTH - exit_text_surface.get_width() - 10
        exit_text_y = (DEBUG_PANEL_HEIGHT - exit_text_surface.get_height()) // 2
        # Store the rect so we can check for clicks on it
        self.exit_link_rect = self.screen.blit(exit_text_surface, (exit_text_x, exit_text_y))
