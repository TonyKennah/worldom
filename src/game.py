# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.
"""
import random
import sys
from typing import List, Optional, Tuple

import pygame
import settings

from settings import (FPS, BG_COLOR, MAP_WIDTH_TILES, MAP_HEIGHT_TILES, SELECTION_BOX_COLOR,
                      SELECTION_BOX_BORDER_WIDTH, CONTEXT_MENU_BG_COLOR, CONTEXT_MENU_BORDER_COLOR,
                      CONTEXT_MENU_TEXT_COLOR, CONTEXT_MENU_FONT_SIZE,
                      CONTEXT_MENU_PADDING)
from camera import Camera
from map import Map
from unit import Unit

class ContextMenuState:
    """Encapsulates the state of the right-click context menu."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.active: bool = False
        self.pos: Optional[Tuple[int, int]] = None
        self.options: List[str] = ["Attack", "Build", "MoveTo"]
        self.rects: List[pygame.Rect] = []
        self.target_tile: Optional[Tuple[int, int]] = None
        self.font = pygame.font.SysFont("Arial", CONTEXT_MENU_FONT_SIZE)

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

        # Get the primary display's size to create a large window
        # that leaves space for the title bar and OS taskbar.
        display_info = pygame.display.Info()
        initial_width = int(display_info.current_w * 0.9)
        initial_height = int(display_info.current_h * 0.9)
        self.screen = pygame.display.set_mode((initial_width, initial_height), pygame.RESIZABLE)

        # Update the settings module with the actual screen size.
        # This makes the true dimensions available globally to other modules
        # that import the settings, like the camera and map.
        settings.SCREEN_WIDTH = self.screen.get_width()
        settings.SCREEN_HEIGHT = self.screen.get_height()

        pygame.display.set_caption("Strategy Game with Camera")
        self.clock = pygame.time.Clock()
        self.running: bool = True
        self.events: List[pygame.event.Event] = []
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

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
        """Creates the starting units for the game and returns the first one."""
        # Find a valid starting position on a grass tile
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
        if event.button == 1:  # Left-click
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
        # Note: Left-drag is handled by the camera, so we don't need an else here.
        self.world_state.left_mouse_down_pos = None  # Reset after use

    def _handle_right_mouse_up(self, event: pygame.event.Event) -> None:
        """Handles right mouse button up events (click vs. drag)."""
        if self._is_click(self.world_state.right_mouse_down_pos, event.pos):
            if self.world_state.selected_units:
                self._open_context_menu(event.pos)
        elif self.world_state.selection_box:  # It's a drag
            self._handle_drag_selection(self.world_state.selection_box)

        self.world_state.right_mouse_down_pos = None
        self.world_state.selection_box = None

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        """Handles mouse motion for drawing the selection box."""
        if self.world_state.right_mouse_down_pos:
            start_pos = self.world_state.right_mouse_down_pos
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
        for i, option_text in enumerate(self.world_state.context_menu.options):
            text_surface = self.world_state.context_menu.font.render(option_text, True, (0,0,0))
            width = text_surface.get_width() + padding * 2
            height = text_surface.get_height() + padding
            rect = pygame.Rect(x, y + i * height, width, height)
            self.world_state.context_menu.rects.append(rect)

    def _close_context_menu(self) -> None:
        """Closes the context menu."""
        self.world_state.context_menu.active = False
        self.world_state.context_menu.pos = None
        self.world_state.context_menu.rects.clear()
        self.world_state.context_menu.target_tile = None

    def _handle_context_menu_click(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles a click when the context menu is active."""
        for i, rect in enumerate(self.world_state.context_menu.rects):
            if rect.collidepoint(mouse_pos):
                option = self.world_state.context_menu.options[i]
                print(f"Context menu option clicked: {option}")
                # For now, all options just move the unit
                if option in ["Attack", "Build", "MoveTo"]:
                    self._issue_move_command_to_target()
                break

        # Always close the menu after a click (either on an option or outside)
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

        if not self.world_state.context_menu.active:
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

        self._update_caption()
        pygame.display.flip()

    def _draw_context_menu(self) -> None:
        """Renders the context menu on the screen."""
        if not self.world_state.context_menu.rects:
            return

        for i, rect in enumerate(self.world_state.context_menu.rects):
            option_text = self.world_state.context_menu.options[i]

            # Draw background and border
            pygame.draw.rect(self.screen, CONTEXT_MENU_BG_COLOR, rect)
            pygame.draw.rect(self.screen, CONTEXT_MENU_BORDER_COLOR, rect, 1)

            text_surface = self.world_state.context_menu.font.render(
                option_text, True, CONTEXT_MENU_TEXT_COLOR)
            text_x = rect.x + CONTEXT_MENU_PADDING
            text_y = rect.y + (CONTEXT_MENU_PADDING / 2)
            self.screen.blit(text_surface, (text_x, text_y))

    def _update_caption(self) -> None:
        """Updates the window caption with helpful information."""
        world_pos = self.camera.screen_to_world(pygame.mouse.get_pos())
        world_coords = f"({int(world_pos.x)}, {int(world_pos.y)})"
        zoom_percentage = self.camera.zoom_state.current * 100
        caption = f"Strategy Game | FPS: {self.clock.get_fps():.1f} | Zoom: {zoom_percentage:.0f}% | World: {world_coords}"
        if self.world_state.hovered_tile:
            tile_x, tile_y = self.world_state.hovered_tile
            terrain = self.map.data[tile_y][tile_x]
            tile_info = f"({tile_x}, {tile_y}) ({terrain.capitalize()})"
            caption += f" | Tile: {tile_info}"
        pygame.display.set_caption(caption)
