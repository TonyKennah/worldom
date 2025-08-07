# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.
"""
import random
import sys
from typing import List, Optional, Tuple

import pygame

from settings import (SCREEN_WIDTH, SCREEN_HEIGHT, FPS, BG_COLOR,
                      MAP_WIDTH_TILES, MAP_HEIGHT_TILES)
from camera import Camera
from map import Map
from unit import Unit

class WorldState:
    """Encapsulates the state of all game objects and player interaction."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.units: List[Unit] = []
        self.selected_unit: Optional[Unit] = None
        self.hovered_tile: Optional[Tuple[int, int]] = None
        self.left_mouse_down_pos: Optional[Tuple[int, int]] = None

# --- Game Class ---
class Game:
    """The main game class, orchestrating all game components."""
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Strategy Game with Camera")
        self.clock = pygame.time.Clock()
        self.running: bool = True
        self.events: List[pygame.event.Event] = []

        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)

        self.map = Map(MAP_WIDTH_TILES, MAP_HEIGHT_TILES)
        self.world_state = WorldState()
        initial_unit = self._spawn_initial_units()

        # Center camera on the initial unit
        if initial_unit:
            self.camera.position = initial_unit.world_pos

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

            self._handle_mouse_events(event)

    def _handle_mouse_events(self, event: pygame.event.Event) -> None:
        """Handles all mouse-related events."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.world_state.left_mouse_down_pos = event.pos
            elif event.button == 3:  # Right-click for commands
                self._handle_right_click_command()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.world_state.left_mouse_down_pos:
                start_pos = self.world_state.left_mouse_down_pos
                end_pos = event.pos
                vec_start = pygame.math.Vector2(start_pos)
                vec_end = pygame.math.Vector2(end_pos)
                dist = vec_start.distance_to(vec_end)
                if dist < 5:  # Threshold for a click
                    self._handle_left_click_selection(event.pos)
            self.world_state.left_mouse_down_pos = None  # Reset after use

    def _handle_right_click_command(self) -> None:
        """Issues a move command to the selected unit."""
        if self.world_state.selected_unit and self.world_state.hovered_tile:
            tile_x, tile_y = self.world_state.hovered_tile
            terrain = self.map.data[tile_y][tile_x]
            if terrain != 'water':  # Allow interrupting the current path
                start_pos = self.world_state.selected_unit.tile_pos
                end_pos = self.world_state.hovered_tile
                path = self.map.find_path(start_pos, end_pos)
                if path is not None:
                    self.world_state.selected_unit.set_path(path)
            else:
                print("Unit cannot move into water.")

    def _handle_left_click_selection(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles unit selection logic for a left click."""
        world_pos = self.camera.screen_to_world(mouse_pos)

        clicked_on_unit = False
        for unit in self.world_state.units:
            if unit.get_world_rect().collidepoint(world_pos):
                if self.world_state.selected_unit:
                    self.world_state.selected_unit.selected = False
                self.world_state.selected_unit = unit
                unit.selected = True
                clicked_on_unit = True
                break

        if not clicked_on_unit and self.world_state.selected_unit:
            self.world_state.selected_unit.selected = False


    def update(self, dt: float) -> None:
        """Updates the state of all game objects."""
        self.camera.update(dt, self.events)

        # Update all units
        for unit in self.world_state.units:
            unit.update(dt)

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

        self._update_caption()
        pygame.display.flip()

    def _update_caption(self) -> None:
        """Updates the window caption with helpful information."""
        world_pos = self.camera.screen_to_world(pygame.mouse.get_pos())
        world_coords = f"({int(world_pos.x)}, {int(world_pos.y)})"
        caption = f"Strategy Game | FPS: {self.clock.get_fps():.1f} | World: {world_coords}"
        if self.world_state.hovered_tile:
            tile_x, tile_y = self.world_state.hovered_tile
            terrain = self.map.data[tile_y][tile_x]
            tile_info = f"({tile_x}, {tile_y}) ({terrain.capitalize()})"
            caption += f" | Tile: {tile_info}"
        pygame.display.set_caption(caption)
