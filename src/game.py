# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.
"""
import pygame
import sys
import random
import math
from typing import List, Optional, Tuple

from settings import (SCREEN_WIDTH, SCREEN_HEIGHT, FPS, BG_COLOR, 
                      MAP_WIDTH_TILES, MAP_HEIGHT_TILES)
from camera import Camera
from map import Map
from unit import Unit

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
        self.hovered_tile: Optional[Tuple[int, int]] = None
        
        # Game object management
        self.units: List[Unit] = []
        self.selected_unit: Optional[Unit] = None
        self.left_mouse_down_pos: Optional[Tuple[int, int]] = None # For detecting clicks vs. drags
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
                self.units.append(new_unit)
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
                self.left_mouse_down_pos = event.pos
            elif event.button == 3:  # Right-click for commands
                self._handle_right_click_command()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.left_mouse_down_pos:
                dist = pygame.math.Vector2(self.left_mouse_down_pos).distance_to(event.pos)
                if dist < 5:  # Threshold for a click
                    self._handle_left_click_selection(event.pos)
            self.left_mouse_down_pos = None  # Reset after use

    def _handle_right_click_command(self) -> None:
        """Issues a move command to the selected unit."""
        if self.selected_unit and self.hovered_tile:
            terrain = self.map.data[self.hovered_tile[1]][self.hovered_tile[0]]
            if terrain != 'water':  # Allow interrupting the current path
                path = self.map.find_path(self.selected_unit.tile_pos, self.hovered_tile)
                if path is not None:
                    self.selected_unit.set_path(path)
            else:
                print("Unit cannot move into water.")

    def _handle_left_click_selection(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles unit selection logic for a left click."""
        world_pos = self.camera.screen_to_world(mouse_pos)

        clicked_on_unit = False
        for unit in self.units:
            if unit.get_world_rect().collidepoint(world_pos):
                if self.selected_unit:
                    self.selected_unit.selected = False
                self.selected_unit = unit
                unit.selected = True
                clicked_on_unit = True
                break

        if not clicked_on_unit and self.selected_unit:
            self.selected_unit.selected = False


    def update(self, dt: float) -> None:
        self.camera.update(dt, self.events)

        # Update all units
        for unit in self.units:
            unit.update(dt)

        # Determine which tile is under the mouse for highlighting
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(mouse_pos)
        tile_col = int(world_pos.x // self.map.tile_size)
        tile_row = int(world_pos.y // self.map.tile_size)

        if 0 <= tile_col < self.map.width and 0 <= tile_row < self.map.height:
            self.hovered_tile = (tile_col, tile_row)
        else:
            self.hovered_tile = None

    def draw(self) -> None:
        self.screen.fill(BG_COLOR)
        self.map.draw(self.screen, self.camera, self.hovered_tile)

        # Draw all units
        for unit in self.units:
            unit.draw(self.screen, self.camera)

        # Update window title with helpful info
        world_pos = self.camera.screen_to_world(pygame.mouse.get_pos())
        caption = f"Strategy Game | World: ({int(world_pos.x)}, {int(world_pos.y)})"
        if self.hovered_tile:
            terrain = self.map.data[self.hovered_tile[1]][self.hovered_tile[0]]
            caption += f" | Tile: {self.hovered_tile} ({terrain.capitalize()})"
        pygame.display.set_caption(caption)
        pygame.display.flip()