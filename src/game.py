# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.
"""
from __future__ import annotations
import os
import random
import sys
from typing import List, Optional, Tuple

import pygame
import settings

from camera import Camera
import globe_renderer
from map import Map
from unit import Unit
from world_state import WorldState
from debug_panel import DebugPanel
from input_handler import InputHandler
from selection_manager import SelectionManager
from ui_manager import UIManager

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
        self.globe_frames: List[pygame.Surface] = []

        # --- Initialize Game Components ---
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        self.debug_panel = DebugPanel()
        self.input_handler = InputHandler(self)
        self.selection_manager = SelectionManager(self)
        self.ui_manager = UIManager(self)

        # Create the initial world
        self._create_new_world()

    def _draw_splash_screen(self, message: str, progress: Optional[float] = None) -> None:
        """
        Displays a loading screen with a message and an optional progress bar.
        """
        self.screen.fill(settings.DEBUG_PANEL_BG_COLOR)

        font = pygame.font.SysFont("Arial", 48)
        text_surface = font.render(message, True, settings.DEBUG_PANEL_FONT_COLOR)
        text_rect = text_surface.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2))
        self.screen.blit(text_surface, text_rect)

        if progress is not None:
            bar_width, bar_height = 400, 30
            bar_x = (settings.SCREEN_WIDTH - bar_width) / 2
            bar_y = text_rect.bottom + 30
            # Draw the progress bar background and border
            pygame.draw.rect(self.screen, (60, 60, 80), (bar_x, bar_y, bar_width, bar_height))
            pygame.draw.rect(self.screen, (200, 200, 220), (bar_x, bar_y, bar_width, bar_height), 2)
            # Draw the progress fill
            fill_width = bar_width * progress
            pygame.draw.rect(self.screen, (100, 200, 100), (bar_x, bar_y, fill_width, bar_height))

        pygame.display.flip()

    def run(self) -> None:
        """The main game loop."""
        # Clear any events that accumulated during the slow map generation
        # process. This prevents clicks during loading from causing issues.
        pygame.event.clear()
        while self.running:
            dt = self.clock.tick(settings.FPS) / 1000.0  # Delta time in seconds
            events = pygame.event.get()
            self.input_handler.handle_events(events)
            self.update(dt, events)
            self.draw()

        pygame.quit()
        sys.exit()

    def _pump_events_during_load(self) -> None:
        """
        Processes essential events during loading to keep the window responsive.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.run() # This will trigger the exit sequence

    def _load_globe_frames(self) -> None:
        """Loads the pre-rendered globe animation frames from disk."""
        self.globe_frames.clear() # Clear frames from any previous map
        base_image_dir = "image"
        frame_dir = os.path.join(base_image_dir, "globe_frames")
        if not os.path.isdir(frame_dir):
            print(f"Warning: Globe animation directory not found at '{frame_dir}'")
            return

        try:
            # Get all .png files and sort them alphabetically to ensure correct order
            filenames = sorted([f for f in os.listdir(frame_dir) if f.endswith(".png")])
            self.globe_frames = [pygame.image.load(os.path.join(frame_dir, f)).convert_alpha() for f in filenames]
            print(f"Successfully loaded {len(self.globe_frames)} globe frames.")
        except pygame.error as e:
            print(f"Error loading globe frames: {e}")

    def _get_all_land_tiles(self) -> List[Tuple[int, int]]:
        """Returns a list of all (x, y) coordinates for walkable land tiles."""
        return [
            (x, y)
            for y in range(self.map.height)
            for x in range(self.map.width)
            if self.map.is_walkable((x, y))
        ]

    def _spawn_initial_units(self) -> Unit:
        """
        Creates the starting unit on a random land tile (grass or rock).
        """
        land_tiles = self._get_all_land_tiles()
        if not land_tiles:
            raise RuntimeError("Map generation failed: No land tiles to spawn on.")

        spawn_point = random.choice(land_tiles)
        new_unit = Unit(spawn_point)
        self.world_state.units.append(new_unit)
        return new_unit

    def _create_new_world(self) -> None:
        """Creates a new map, world state, and globe, showing progress."""
        # --- Select a random theme and update global settings ---
        theme_name = random.choice(list(settings.PLANET_THEMES.keys()))
        settings.ACTIVE_THEME_NAME = theme_name
        settings.ACTIVE_THEME = settings.PLANET_THEMES[theme_name]
        settings.TERRAIN_TYPES = list(settings.ACTIVE_THEME["terrains"].keys())
        settings.TERRAIN_DATA = settings.ACTIVE_THEME["terrains"]
        settings.TERRAIN_COLORS = {key: data["color"] for key, data in settings.TERRAIN_DATA.items()}
        settings.WALKABLE_TERRAINS = {key for key, data in settings.TERRAIN_DATA.items() if data["walkable"]}
        settings.GLOBE_TERRAIN_COLORS = [data["globe_color"] for data in settings.TERRAIN_DATA.values()]
        print(f"Selected theme: {settings.ACTIVE_THEME['name']} ({settings.ACTIVE_THEME_NAME})")

        map_seed = random.randint(0, 1_000_000)
        self.map = Map(settings.MAP_WIDTH_TILES, settings.MAP_HEIGHT_TILES, seed=map_seed)
        for progress in self.map.generate():
            self._pump_events_during_load()
            self._draw_splash_screen(message="1/2 Generating 2D Map", progress=progress)

        self.world_state = WorldState()
        initial_unit = self._spawn_initial_units()
        if initial_unit:
            self.camera.position = initial_unit.world_pos.copy()

        for progress in globe_renderer.render_map_as_globe(self.map.data, map_seed):
            self._pump_events_during_load()
            self._draw_splash_screen(message="2/2 Generating Globe", progress=progress)
        self._load_globe_frames()

    def regenerate_map(self) -> None:
        """Regenerates the map and resets the world state."""
        self._create_new_world()
        pygame.event.clear()

    def issue_move_command_to_target(self) -> None:
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

    def update(self, dt: float, events: List[pygame.event.Event]) -> None:
        """Updates the state of all game objects."""
        map_width_pixels = self.map.width * settings.TILE_SIZE
        map_height_pixels = self.map.height * settings.TILE_SIZE
        self.camera.update(dt, events, map_width_pixels, map_height_pixels)

        # Update all units
        for unit in self.world_state.units:
            unit.update(dt, self.map.width, self.map.height)

        if self.world_state.context_menu.active:
            self.ui_manager.handle_context_menu_hover(pygame.mouse.get_pos())
        else:
            self._update_hovered_tile()

        self.ui_manager.update(dt)

    def draw(self) -> None:
        """Renders all game objects to the screen."""
        self.screen.fill(settings.BG_COLOR)
        self.map.draw(self.screen, self.camera, self.world_state.hovered_tile)

        # Draw all units
        map_width_pixels = self.map.width * settings.TILE_SIZE
        map_height_pixels = self.map.height * settings.TILE_SIZE
        for unit in self.world_state.units:
            unit.draw(self.screen, self.camera, map_width_pixels, map_height_pixels)

        # Delegate all UI drawing to the UIManager
        self.ui_manager.draw_ui()

        self.debug_panel.draw(self)
        pygame.display.flip()

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
