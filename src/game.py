# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.
"""
from __future__ import annotations
import math
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

import pygame
import settings

from camera import Camera
from map import Map
from unit import Unit

class SubMenuState:
    """Encapsulates the state of a context sub-menu."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.active: bool = False
        self.options: List[str] = []
        self.rects: List[pygame.Rect] = []
        self.parent_rect: Optional[pygame.Rect] = None

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
        self.font = pygame.font.SysFont("Arial", settings.CONTEXT_MENU_FONT_SIZE)
        self.sub_menu = SubMenuState()

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

class DebugPanel:
    """Handles rendering and interaction for the top debug panel."""
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("Arial", settings.DEBUG_PANEL_FONT_SIZE)
        self.exit_link_rect: Optional[pygame.Rect] = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handles events for the debug panel.
        Returns True if the game should exit, False otherwise.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.exit_link_rect and self.exit_link_rect.collidepoint(event.pos):
                return True  # Signal to exit
        return False

    def _draw_main_info(self, game: Game) -> None:
        """Draws the main informational text (FPS, zoom, etc.)."""
        world_pos = game.camera.screen_to_world(pygame.mouse.get_pos())
        world_coords = f"({int(world_pos.x)}, {int(world_pos.y)})"
        zoom_percentage = game.camera.zoom_state.current * 100
        info_string = (
            f"FPS: {game.clock.get_fps():.1f} | "
            f"Zoom: {zoom_percentage:.0f}% | "
            f"World: {world_coords}"
        )
        if game.world_state.hovered_tile:
            tile_x, tile_y = game.world_state.hovered_tile
            terrain = game.map.data[tile_y][tile_x]
            tile_info = f"({tile_x}, {tile_y}) ({terrain.capitalize()})"
            info_string += f" | Tile: {tile_info}"

        text_surface = self.font.render(info_string, True, settings.DEBUG_PANEL_FONT_COLOR)
        text_y = (settings.DEBUG_PANEL_HEIGHT - text_surface.get_height()) // 2
        game.screen.blit(text_surface, (10, text_y))

    def _draw_exit_link(self, game: Game) -> None:
        """Draws the clickable 'Exit' link."""
        exit_text_surface = self.font.render("Exit", True, settings.DEBUG_PANEL_FONT_COLOR)
        exit_text_x = settings.SCREEN_WIDTH - exit_text_surface.get_width() - 10
        exit_text_y = (settings.DEBUG_PANEL_HEIGHT - exit_text_surface.get_height()) // 2
        self.exit_link_rect = game.screen.blit(exit_text_surface, (exit_text_x, exit_text_y))

    def draw(self, game: Game) -> None:
        """Renders the complete debug panel by calling its helper methods."""
        panel_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.DEBUG_PANEL_HEIGHT)
        pygame.draw.rect(game.screen, settings.DEBUG_PANEL_BG_COLOR, panel_rect)

        self._draw_main_info(game)
        self._draw_exit_link(game)

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
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        self.debug_panel = DebugPanel()

        self.map = Map(settings.MAP_WIDTH_TILES, settings.MAP_HEIGHT_TILES)
        self.world_state = WorldState()
        initial_unit = self._spawn_initial_units()

        # Center camera on the initial unit
        if initial_unit:
            # Use .copy() to prevent the camera and unit from sharing the same Vector2 object
            self.camera.position = initial_unit.world_pos.copy()

    def run(self) -> None:
        """The main game loop."""
        while self.running:
            dt = self.clock.tick(settings.FPS) / 1000.0  # Delta time in seconds
            events = pygame.event.get()
            self.handle_events(events)
            self.update(dt, events)
            self.draw()

        pygame.quit()
        sys.exit()

    def _get_all_grass_tiles(self) -> List[Tuple[int, int]]:
        """Returns a list of all (x, y) coordinates for grass tiles."""
        grass_tiles = []
        for y in range(self.map.height):
            for x in range(self.map.width):
                if self.map.data[y][x] == 'grass':
                    grass_tiles.append((x, y))
        return grass_tiles

    def _is_ocean_visible_from(
        self, center_x: int, center_y: int, radius_x: int, radius_y: int
    ) -> bool:
        """Checks if any ocean tiles are visible from a central point."""
        for j in range(center_y - radius_y, center_y + radius_y + 1):
            for i in range(center_x - radius_x, center_x + radius_x + 1):
                if 0 <= i < self.map.width and 0 <= j < self.map.height:
                    if self.map.data[j][i] == 'ocean':
                        return True
        return False

    def _find_best_spawn_fallback(
        self, grass_tiles: List[Tuple[int, int]], radius_x: int, radius_y: int
    ) -> Tuple[int, int]:
        """Finds the best possible spawn point by maximizing visible land."""
        best_spawn_point = None
        max_land_tiles = -1

        for x, y in grass_tiles:
            land_tile_count = 0
            # Check a bounding box around the potential spawn point
            for j in range(y - radius_y, y + radius_y + 1):
                for i in range(x - radius_x, x + radius_x + 1):
                    if 0 <= i < self.map.width and 0 <= j < self.map.height:
                        if self.map.data[j][i] != 'ocean':
                            land_tile_count += 1

            if land_tile_count > max_land_tiles:
                max_land_tiles = land_tile_count
                best_spawn_point = (x, y)

        if best_spawn_point is None:
            return grass_tiles[0]
        return best_spawn_point

    def _spawn_initial_units(self) -> Unit:
        """
        Creates the starting units for the game, ensuring it's on a grass tile
        and no ocean is visible on screen at the start. Returns the first unit.
        """
        initial_zoom = self.camera.zoom_state.current
        # Calculate how many tiles are visible from the center to the edge of the screen
        screen_radius_x_pixels = settings.SCREEN_WIDTH / 2 / initial_zoom
        tiles_to_edge_x = screen_radius_x_pixels / settings.TILE_SIZE
        screen_radius_y_pixels = settings.SCREEN_HEIGHT / 2 / initial_zoom
        tiles_to_edge_y = screen_radius_y_pixels / settings.TILE_SIZE
        radius_x = math.ceil(tiles_to_edge_x) + 1
        radius_y = math.ceil(tiles_to_edge_y) + 1

        grass_tiles = self._get_all_grass_tiles()
        if not grass_tiles:
            raise RuntimeError("Map generation failed: No grass tiles to spawn on.")

        # 1. First, try to find "perfect" spawn points where no ocean is visible.
        perfect_spawn_points = [
            (x, y) for x, y in grass_tiles
            if not self._is_ocean_visible_from(x, y, radius_x, radius_y)
        ]

        # 2. If we found any perfect spots, pick one at random.
        if perfect_spawn_points:
            spawn_point = random.choice(perfect_spawn_points)
        else:
            # 3. If no perfect spots exist, fall back to finding the "best" spot.
            random.shuffle(grass_tiles) # Shuffle to randomize choice among equally good spots
            spawn_point = self._find_best_spawn_fallback(grass_tiles, radius_x, radius_y)

        new_unit = Unit(spawn_point)
        self.world_state.units.append(new_unit)
        return new_unit

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        """Processes all user input and events."""
        for event in events:
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
                self.camera.screen_center = pygame.math.Vector2(
                    settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2
                )

            # Let the debug panel handle its events first
            if self.debug_panel.handle_event(event):
                self.running = False
                continue # Event was handled, stop processing it

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
        padding = settings.CONTEXT_MENU_PADDING
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
        if context_menu.sub_menu.active:
            for i, rect in enumerate(context_menu.sub_menu.rects):
                if rect.collidepoint(mouse_pos):
                    option = context_menu.sub_menu.options[i]
                    print(f"Sub-menu option clicked: {option}")
                    self._issue_move_command_to_target()
                    self._close_context_menu()  # Close everything after action
                    return

        # Check for main menu click
        for i, rect in enumerate(context_menu.rects):
            if rect.collidepoint(mouse_pos):
                option_data = context_menu.options[i]
                # If the clicked item has a sub-menu, do nothing.
                # This allows the user to move their mouse to the sub-menu.
                if "sub_options" in option_data:
                    return

                # If it's a normal command, execute it.
                if option_data["label"] in ["Attack", "MoveTo"]:
                    self._issue_move_command_to_target()
                    self._close_context_menu()
                    return

        # If we clicked, but not on an actionable item (e.g., outside all menus),
        # then close the menu.
        self._close_context_menu()

    def _issue_move_command_to_target(self) -> None:
        """Issues a move command to selected units to the stored target tile."""
        target_tile = self.world_state.context_menu.target_tile
        if not self.world_state.selected_units or not target_tile:
            return

        # Check if the target tile is walkable before finding a path
        if not self.map.is_walkable(target_tile):
            print("Units cannot move there.")
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


    def update(self, dt: float, events: List[pygame.event.Event]) -> None:
        """Updates the state of all game objects."""
        map_width_pixels = self.map.width * settings.TILE_SIZE
        map_height_pixels = self.map.height * settings.TILE_SIZE
        self.camera.update(dt, events, map_width_pixels, map_height_pixels)

        # Update all units
        for unit in self.world_state.units:
            unit.update(dt, self.map.width, self.map.height)

        if self.world_state.context_menu.active:
            self._handle_context_menu_hover(pygame.mouse.get_pos())
        else:
            self._update_hovered_tile()

    def _update_hovered_tile(self) -> None:
        """Calculates which map tile is currently under the mouse cursor."""
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(mouse_pos)

        map_width_pixels = self.map.width * self.map.tile_size
        map_height_pixels = self.map.height * self.map.tile_size

        # Wrap the world position to the map's dimensions
        wrapped_x = world_pos.x % map_width_pixels
        wrapped_y = world_pos.y % map_height_pixels

        tile_col = int(wrapped_x // self.map.tile_size)
        tile_row = int(wrapped_y // self.map.tile_size)

        self.world_state.hovered_tile = (tile_col, tile_row)

    def draw(self) -> None:
        """Renders all game objects to the screen."""
        self.screen.fill(settings.BG_COLOR)
        self.map.draw(self.screen, self.camera, self.world_state.hovered_tile)

        # Draw all units
        map_width_pixels = self.map.width * settings.TILE_SIZE
        map_height_pixels = self.map.height * settings.TILE_SIZE
        for unit in self.world_state.units:
            unit.draw(self.screen, self.camera, map_width_pixels, map_height_pixels)

        # Draw selection box
        if self.world_state.selection_box:
            pygame.draw.rect(self.screen, settings.SELECTION_BOX_COLOR,
                             self.world_state.selection_box, settings.SELECTION_BOX_BORDER_WIDTH)

        # Draw context menu if active
        if self.world_state.context_menu.active:
            self._draw_context_menu()
            if self.world_state.context_menu.sub_menu.active:
                self._draw_sub_menu()

        self.debug_panel.draw(self)
        pygame.display.flip()

    def _draw_context_menu(self) -> None:
        """Renders the context menu on the screen."""
        if not self.world_state.context_menu.rects:
            return

        for i, rect in enumerate(self.world_state.context_menu.rects):
            option_text = self.world_state.context_menu.options[i]["label"]

            # Draw background and border
            pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BG_COLOR, rect)
            pygame.draw.rect(self.screen, settings.CONTEXT_MENU_BORDER_COLOR, rect, 1)

            text_surface = self.world_state.context_menu.font.render(
                option_text, True, settings.CONTEXT_MENU_TEXT_COLOR)
            text_x = rect.x + settings.CONTEXT_MENU_PADDING
            text_y = rect.y + (settings.CONTEXT_MENU_PADDING / 2)
            self.screen.blit(text_surface, (text_x, text_y))

    def _draw_sub_menu(self) -> None:
        """Renders the sub-menu on the screen."""
        context_menu = self.world_state.context_menu
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
                    if (not context_menu.sub_menu.active
                            or context_menu.sub_menu.parent_rect != rect):
                        self._open_sub_menu(option_data["sub_options"], rect)
                else:
                    # This item has no sub-menu, so close any active one
                    self._close_sub_menu()
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
                self._close_sub_menu()

    def _open_sub_menu(self, sub_options: List[str], parent_rect: pygame.Rect) -> None:
        """Opens a sub-menu next to a parent menu item."""
        context_menu = self.world_state.context_menu
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

    def _close_sub_menu(self) -> None:
        """Closes the sub-menu."""
        context_menu = self.world_state.context_menu
        if not context_menu.sub_menu.active:
            return
        context_menu.sub_menu.active = False
        context_menu.sub_menu.options.clear()
        context_menu.sub_menu.rects.clear()
        context_menu.sub_menu.parent_rect = None
