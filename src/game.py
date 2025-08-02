# c:/game/worldom/game.py
import pygame
import sys
import random
import math

from settings import (SCREEN_WIDTH, SCREEN_HEIGHT, FPS, BG_COLOR, 
                      MAP_WIDTH_TILES, MAP_HEIGHT_TILES)
from camera import Camera
from map import Map
from unit import Unit

# --- Game Class ---
class Game:
    """The main game class, orchestrating all game components."""
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Strategy Game with Camera")
        self.clock = pygame.time.Clock()
        self.running = True
        self.events = []

        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)

        self.map = Map(MAP_WIDTH_TILES, MAP_HEIGHT_TILES)
        self.hovered_tile = None
        
        # Game object management
        self.units = []
        self.selected_unit = None
        self.left_mouse_down_pos = None # For detecting clicks vs. drags
        initial_unit = self._spawn_initial_units()

        # Center camera on the initial unit
        if initial_unit:
            self.camera.position = initial_unit.world_pos

    def run(self):
        """The main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()

    def _spawn_initial_units(self):
        """Creates the starting units for the game and returns the first one."""
        # Find a valid starting position on a grass tile
        while True:
            x, y = random.randint(0, self.map.width - 1), random.randint(0, self.map.height - 1)
            if self.map.data[y][x] == 'grass':
                new_unit = Unit((x, y))
                self.units.append(new_unit)
                return new_unit

    def handle_events(self):
        """Processes all user input and events."""
        self.events = pygame.event.get()
        for event in self.events:
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.left_mouse_down_pos = event.pos
                elif event.button == 3: # Right-click for commands
                    if self.selected_unit and self.hovered_tile:
                        terrain = self.map.data[self.hovered_tile[1]][self.hovered_tile[0]]
                        if terrain != 'water': # Allow interrupting the current path
                            path = self.map.find_path(self.selected_unit.tile_pos, self.hovered_tile)
                            if path is not None:
                                self.selected_unit.set_path(path)
                        else:
                            print("Unit cannot move into water.") # Added feedback

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.left_mouse_down_pos:
                    # Check if it was a click or a drag
                    dist = pygame.math.Vector2(self.left_mouse_down_pos).distance_to(event.pos)
                    if dist < 5: # Threshold for a click
                        # --- This is a click, handle selection ---
                        world_pos = self.camera.screen_to_world(event.pos)
                        
                        clicked_on_unit = False
                        for unit in self.units:
                            if unit.get_world_rect().collidepoint(world_pos):
                                if self.selected_unit:
                                    self.selected_unit.selected = False
                                self.selected_unit = unit
                                unit.selected = True
                                clicked_on_unit = True
                                break
                        
                        # If we didn't click a unit, deselect any active one
                        if not clicked_on_unit and self.selected_unit:
                            self.selected_unit.selected = False
                self.left_mouse_down_pos = None # Reset after use


    def update(self, dt):
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

    def draw(self):
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

if __name__ == '__main__':
    game = Game()
    game.run()