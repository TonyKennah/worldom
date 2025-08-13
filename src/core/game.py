# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.

Upgrades:
- Robust window creation (high-DPI, optional vsync) and live resize handling
- Safer, cancellable loading loops with exception capture and progress smoothing
- Theme selection + brightness check refactored
- Deterministic seed tracking and debug info
- Smarter move orders (fallback to nearest-walkable + graceful no-path)
- Utility helpers (center camera, save screenshot, toggle pause)
- Minor rendering polish (starfield resize, optional FPS overlay)
"""
from __future__ import annotations

import os
import random
import threading
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import pygame
import src.utils.settings as settings

from src.core.camera import Camera
import src.rendering.globe_renderer as globe_renderer
from src.core.map import Map
from src.entities.unit import Unit
from src.world.world_state import WorldState
from src.core.debug_panel import DebugPanel
from src.ui.input_handler import InputHandler
from src.ui.selection_manager import SelectionManager
from src.ui.ui_manager import UIManager
from src.ui.starfield import Starfield


# --- Game Class ---
class Game:
    """The main game class, orchestrating all game components."""

    # ---------------------
    # Lifecycle / init
    # ---------------------
    def __init__(self) -> None:
        pygame.init()

        # Prefer scaled/high-DPI rendering; enable vsync if available
        flags = pygame.FULLSCREEN
        # The SCALED flag makes everything appear larger on high-DPI monitors.
        # Commenting this block out will make the game render at the native resolution,
        # making UI elements and text appear smaller (less "zoomed in").
        # try:
        #     flags |= pygame.SCALED
        # except AttributeError:
        #     pass

        # Try to request vsync (Pygame 2.0+)
        self.screen: pygame.Surface
        try:
            # For true native fullscreen (least "zoomed-in"), we pass (0, 0).
            # However, the SCALED flag is incompatible with (0,0) and requires a fixed size.
            # This logic handles both cases.
            size = (0, 0)
            if flags & pygame.SCALED:
                w = settings.SCREEN_WIDTH if settings.SCREEN_WIDTH > 0 else 1280
                h = settings.SCREEN_HEIGHT if settings.SCREEN_HEIGHT > 0 else 720
                size = (w, h)
            self.screen = pygame.display.set_mode(size, flags, vsync=1)  # type: ignore[call-arg]
            self.vsync = True
        except TypeError:
            # Older pygame; fallback without vsync kwarg
            size = (0, 0)
            if flags & pygame.SCALED:
                w = settings.SCREEN_WIDTH if settings.SCREEN_WIDTH > 0 else 1280
                h = settings.SCREEN_HEIGHT if settings.SCREEN_HEIGHT > 0 else 720
                size = (w, h)
            self.screen = pygame.display.set_mode(size, flags)
            self.vsync = False

        # Update global settings with the actual screen size (needed by modules that import settings)
        self._update_settings_from_window()

        # --- WARM UP LIBRARIES ---
        globe_renderer.warm_up_rendering_libraries()
        # --- END WARM UP ---

        pygame.display.set_caption("WorldDom")
        self.clock = pygame.time.Clock()
        self.running: bool = True
        self.paused: bool = False

        # Render helpers
        self.globe_frames: List[pygame.Surface] = []
        self.starfield = Starfield(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT, num_stars=800, speed_factor=750.0)

        # --- Initialize Game Components ---
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        self.debug_panel = DebugPanel()
        self.input_handler = InputHandler(self)
        self.selection_manager = SelectionManager(self)
        self.ui_manager = UIManager(self)

        # State/debug
        self.current_seed: Optional[int] = None
        self.current_theme_key: Optional[str] = None

        # Create the initial world
        self._create_new_world()

    # ---------------------
    # Window / UI helpers
    # ---------------------
    def _update_settings_from_window(self) -> None:
        """Refresh global screen size after window creation/resizing."""
        settings.SCREEN_WIDTH = self.screen.get_width()
        settings.SCREEN_HEIGHT = self.screen.get_height()

    def _on_window_resized(self, width: int, height: int) -> None:
        """React to OS/window resize events."""
        # Pygame auto-resizes the display Surface; just refresh cached sizes and dependent systems.
        self._update_settings_from_window()
        # Resize starfield and camera to match the new window dimensions.
        self.starfield.width = settings.SCREEN_WIDTH
        self.starfield.height = settings.SCREEN_HEIGHT
        self.camera.width = settings.SCREEN_WIDTH
        self.camera.height = settings.SCREEN_HEIGHT

    # ---------------------
    # Splash / loading
    # ---------------------
    def _draw_splash_screen(self, message: str, progress: Optional[float] = None) -> None:
        """
        Draws a loading screen. Animation updates should happen before calling this.
        """
        # A dark blue/purple background for space
        self.screen.fill((5, 0, 15))
        self.starfield.draw(self.screen)

        font = pygame.font.SysFont("Arial", 48)
        text_surface = font.render(message, True, settings.DEBUG_PANEL_FONT_COLOR)
        text_rect = text_surface.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2))
        self.screen.blit(text_surface, text_rect)

        if progress is not None:
            bar_width, bar_height = 420, 28
            bar_x = (settings.SCREEN_WIDTH - bar_width) / 2
            bar_y = text_rect.bottom + 30
            # Draw the progress bar background and border
            pygame.draw.rect(self.screen, (60, 60, 80), (bar_x, bar_y, bar_width, bar_height))
            pygame.draw.rect(self.screen, (200, 200, 220), (bar_x, bar_y, bar_width, bar_height), 2)
            # Draw the progress fill
            fill_width = bar_width * max(0.0, min(1.0, progress))
            pygame.draw.rect(self.screen, (100, 200, 100), (bar_x, bar_y, fill_width, bar_height))

    def _pump_events_during_load(self, progress_state: Dict[str, Any]) -> None:
        """
        Processes essential events during loading to keep the window responsive.
        Allows cancel via ESC or window close.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                self._on_window_resized(event.w, event.h)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                progress_state['cancel'] = True

    def _run_loading_loop(self, target_func, message: str) -> None:
        """
        Runs a smooth animation loop on the main thread while a worker
        thread performs a long-running task. Captures worker exceptions.
        """
        progress_state: Dict[str, Any] = {'progress': 0.0, 'cancel': False, 'error': None}
        exception_info: Dict[str, Any] = {}

        # Wrap the target so we can capture exceptions in the worker thread
        def worker_wrapper():
            try:
                target_func(progress_state)
            except Exception:
                exception_info['exc_info'] = sys.exc_info()
                progress_state['error'] = "Worker failed"

        worker_thread = threading.Thread(target=worker_wrapper, daemon=True)
        worker_thread.start()

        # Main thread's rendering loop
        displayed = 0.0  # smoothed progress
        while worker_thread.is_alive():
            dt = self.clock.tick(settings.FPS) / 1000.0
            self._pump_events_during_load(progress_state)
            if progress_state.get('cancel'):
                break

            # Smooth progress easing
            raw = float(progress_state.get('progress', 0.0))
            displayed = 0.9 * displayed + 0.1 * raw

            self.starfield.update(dt)  # Update animation with real delta time
            self._draw_splash_screen(message, progress=displayed)
            pygame.display.flip()

        worker_thread.join(timeout=0.1)

        # If cancel requested, just return to caller (caller may decide next step)
        if progress_state.get('cancel'):
            self._draw_splash_screen("Cancelled", progress=0.0)
            pygame.display.flip()
            return

        # Propagate any worker exceptions with a friendly notice
        if progress_state.get('error'):
            self._draw_splash_screen("Error during loading", progress=None)
            pygame.display.flip()
            if 'exc_info' in exception_info:
                traceback.print_exception(*exception_info['exc_info'])
            raise RuntimeError("Loading failed; see traceback above.")

        # Draw one final time at 100% to ensure the bar is full
        self._draw_splash_screen(message, progress=1.0)
        pygame.display.flip()

    # ---------------------
    # Globe utils
    # ---------------------
    def _load_globe_frames(self) -> None:
        """Loads the pre-rendered globe animation frames from disk."""
        self.globe_frames.clear()  # Clear frames from any previous map
        frame_dir = Path("image") / "globe_frames"
        if not frame_dir.is_dir():
            print(f"Warning: Globe animation directory not found at '{frame_dir.as_posix()}'")
            return

        try:
            # Get all .png files and sort them alphabetically to ensure correct order
            filenames = sorted([p for p in frame_dir.iterdir() if p.suffix.lower() == ".png"])
            self.globe_frames = [pygame.image.load(p.as_posix()).convert_alpha() for p in filenames]
            print(f"Successfully loaded {len(self.globe_frames)} globe frames.")
        except pygame.error as e:
            print(f"Error loading globe frames: {e}")

    # ---------------------
    # World / units
    # ---------------------
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
        Falls back to nearest-walkable if map changed post-generation.
        """
        land_tiles = self._get_all_land_tiles()
        if not land_tiles:
            raise RuntimeError("Map generation failed: No land tiles to spawn on.")

        spawn_point = random.choice(land_tiles)
        new_unit = Unit(spawn_point)
        self.world_state.units.append(new_unit)
        return new_unit

    def _select_theme_and_colors(self) -> None:
        """Randomly selects a theme and configures global terrain settings."""
        theme_key = random.choice(list(settings.PLANET_THEMES.keys()))
        theme = settings.PLANET_THEMES[theme_key]

        settings.ACTIVE_THEME_NAME = theme_key
        settings.ACTIVE_THEME = theme
        settings.TERRAIN_TYPES = list(theme["terrains"].keys())
        settings.TERRAIN_DATA = theme["terrains"]
        settings.TERRAIN_COLORS = {key: data["color"] for key, data in settings.TERRAIN_DATA.items()}
        settings.WALKABLE_TERRAINS = {key for key, data in settings.TERRAIN_DATA.items() if data["walkable"]}
        settings.GLOBE_TERRAIN_COLORS = [data["globe_color"] for data in settings.TERRAIN_DATA.values()]

        self.current_theme_key = theme_key
        print(f"Selected theme: {theme['name']} ({theme_key})")

        # Determine selection color based on walkable brightness
        has_bright_walkable_terrain = any(
            ((td["color"][0] + td["color"][1] + td["color"][2]) / 3) > settings.BRIGHT_TERRAIN_THRESHOLD
            for td in settings.TERRAIN_DATA.values() if td["walkable"]
        )
        if has_bright_walkable_terrain:
            print("Bright theme detected. Using high-contrast selection colors.")
            settings.UNIT_SELECTED_COLOR = settings.ALT_SELECTION_COLOR
            settings.SELECTION_BOX_COLOR = settings.ALT_SELECTION_COLOR
        else:
            settings.UNIT_SELECTED_COLOR = settings.DEFAULT_SELECTION_COLOR
            settings.SELECTION_BOX_COLOR = settings.DEFAULT_SELECTION_COLOR

    def _create_new_world(self) -> None:
        """Creates a new map, world state, and globe, showing progress."""
        # --- Select a random theme and update global settings ---
        self._select_theme_and_colors()

        # Seed for reproducibility; allow env override
        env_seed = os.environ.get("WORLDDOM_SEED")
        map_seed = int(env_seed) if env_seed is not None else random.randint(0, 1_000_000)
        self.current_seed = map_seed

        self.map = Map(settings.MAP_WIDTH_TILES, settings.MAP_HEIGHT_TILES, seed=map_seed)

        # --- Worker function for map generation ---
        def map_generation_worker(progress_state: Dict[str, float]) -> None:
            for progress in self.map.generate():
                if progress_state.get('cancel'):
                    return
                progress_state['progress'] = progress

        self._run_loading_loop(map_generation_worker, "Interstellar Travel")

        self.world_state = WorldState()
        initial_unit = self._spawn_initial_units()
        if initial_unit:
            self.camera.position = initial_unit.world_pos.copy()

        # --- Worker function for globe rendering ---
        def globe_rendering_worker(progress_state: Dict[str, float]) -> None:
            for progress in globe_renderer.render_map_as_globe(self.map.data, map_seed):
                if progress_state.get('cancel'):
                    return
                progress_state['progress'] = progress

        self._run_loading_loop(globe_rendering_worker, "Sourcing Planet")
        self._load_globe_frames()

        # Show the globe popup immediately upon starting a new world
        self.ui_manager.show_globe_popup = True

    def regenerate_map(self) -> None:
        """Regenerates the map and resets the world state."""
        self._create_new_world()
        pygame.event.clear()

    # ---------------------
    # Commands / gameplay
    # ---------------------
    def issue_move_command_to_target(self) -> None:
        """Issues a move command to selected units to the stored target tile."""
        target_tile = self.world_state.context_menu.target_tile
        if not self.world_state.selected_units or not target_tile:
            return

        # If the target tile isn't walkable, try to snap to nearest walkable
        end = tuple(target_tile)
        if not self.map.is_walkable(end):
            nearest = None
            if hasattr(self.map, "find_nearest_walkable"):
                nearest = self.map.find_nearest_walkable(end, max_radius=25)  # type: ignore[attr-defined]
            if nearest is None:
                print("Units cannot move there (no nearby walkable tile).")
                return
            end = nearest

        end_vec = pygame.math.Vector2(end)

        for unit in self.world_state.selected_units:
            start_pos = unit.tile_pos
            path = self.map.find_path(start_pos, end_vec)
            if path is not None and len(path) > 0:
                unit.set_path(path)
            else:
                print("No path found.")

    # ---------------------
    # Main loop
    # ---------------------
    def run(self) -> None:
        """The main game loop."""
        # Clear any events that accumulated during loading
        pygame.event.clear()
        while self.running:
            dt_ms = self.clock.tick(settings.FPS)
            dt = min(0.05, dt_ms / 1000.0)  # clamp dt to avoid huge spikes

            events = pygame.event.get()
            # Handle window-level events early
            for e in events:
                if e.type == pygame.VIDEORESIZE:
                    self._on_window_resized(e.w, e.h)

            self.input_handler.handle_events(events)

            if not self.paused:
                self.update(dt, events)

            self.draw()

        pygame.quit()
        sys.exit()

    def update(self, dt: float, events: List[pygame.event.Event]) -> None:
        """Updates the state of all game objects."""
        # Define an exclusion zone for edge scrolling based on debug panel links
        exclusion_zone = None
        if self.debug_panel.show_globe_link_rect and self.debug_panel.exit_link_rect:
            padding = 50
            left = self.debug_panel.show_globe_link_rect.left - padding
            right = self.debug_panel.exit_link_rect.right
            height = settings.DEBUG_PANEL_HEIGHT + settings.EDGE_SCROLL_BOUNDARY
            exclusion_zone = pygame.Rect(left, 0, right - left, height)

        map_width_pixels = self.map.width * settings.TILE_SIZE
        map_height_pixels = self.map.height * settings.TILE_SIZE
        self.camera.update(dt, events, map_width_pixels, map_height_pixels, edge_scroll_exclusion_zone=exclusion_zone)

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
        self.map.draw(self.screen, self.camera, self.world_state.hovered_tile, self.world_state.hovered_world_pos)

        # Draw all units
        map_width_pixels = self.map.width * settings.TILE_SIZE
        map_height_pixels = self.map.height * settings.TILE_SIZE
        for unit in self.world_state.units:
            unit.draw(self.screen, self.camera, map_width_pixels, map_height_pixels)

        # Delegate all UI drawing to the UIManager
        self.ui_manager.draw_ui()

        # Debug panel & overlays
        self.debug_panel.draw(self)

        # Optional lightweight FPS overlay (toggle in settings)
        if getattr(settings, "SHOW_FPS", False):
            fps_font = pygame.font.SysFont("Consolas", 16)
            fps_text = f"FPS: {int(self.clock.get_fps())}  Seed: {self.current_seed or '-'}  Theme: {self.current_theme_key or '-'}"
            surf = fps_font.render(fps_text, True, (200, 200, 220))
            self.screen.blit(surf, (8, settings.SCREEN_HEIGHT - 22))

        pygame.display.flip()

    def _update_hovered_tile(self) -> None:
        """Calculates which map tile is currently under the mouse cursor."""
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(mouse_pos)
        self.world_state.hovered_world_pos = world_pos

        map_width_pixels = self.map.width * self.map.tile_size
        map_height_pixels = self.map.height * self.map.tile_size

        # Wrap the world position to the map's dimensions
        wrapped_x = world_pos.x % map_width_pixels
        wrapped_y = world_pos.y % map_height_pixels

        tile_col = int(wrapped_x // self.map.tile_size)
        tile_row = int(wrapped_y // self.map.tile_size)

        self.world_state.hovered_tile = (tile_col, tile_row)

    # ---------------------
    # Extra utilities (non-breaking)
    # ---------------------
    def toggle_pause(self) -> None:
        """Toggle paused state (can be bound in InputHandler)."""
        self.paused = not self.paused

    def center_camera_on_selection(self) -> None:
        """Center camera on the first selected unit (if any)."""
        if self.world_state.selected_units:
            self.camera.position = self.world_state.selected_units[0].world_pos.copy()

    def save_screenshot(self, path: Optional[str] = None) -> str:
        """Save a screenshot of the current frame; returns path."""
        out_dir = Path("screenshots")
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = path or f"worldom_{pygame.time.get_ticks()}.png"
        p = out_dir / fname
        pygame.image.save(self.screen, p.as_posix())
        print(f"Saved screenshot: {p.as_posix()}")
        return p.as_posix()
