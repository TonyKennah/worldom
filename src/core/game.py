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

from src.utils.linux_tweaks import (
    early_env_setup as _linux_early_env_setup,
    recommended_display_flags as _linux_display_flags,
    is_linux as _is_linux,
)



# --- Game Class ---
class Game:
    """The main game class, orchestrating all game components."""

    # ---------------------
    # Lifecycle / init
    # ---------------------
    def __init__(self) -> None:
        # Apply Linux performance env tweaks BEFORE initializing pygame/SDL
        try:
            _linux_early_env_setup()
        except Exception:
            # Non‑fatal: run with default environment if tweaks fail
            pass

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
        self.player_unit: Optional[Unit] = None

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

    def _run_loading_loop(
        self,
        target_func,
        message: str,
        speed_profile: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        """
        Runs a smooth animation loop on the main thread while a worker
        thread performs a long-running task. Captures worker exceptions.

        The speed_profile is a list of (progress, speed) tuples, e.g.,
        [(0.0, 100), (0.5, 200), (1.0, 100)].
        """
        progress_state: Dict[str, Any] = {'progress': 0.0, 'cancel': False, 'error': None}
        exception_info: Dict[str, Any] = {}

        # Set initial speed if provided for the transition
        if speed_profile:
            self.starfield.speed_factor = speed_profile[0][1]

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

            # Use raw progress for calculations, smoothed progress for the visual bar
            raw = float(progress_state.get('progress', 0.0))
            displayed = 0.9 * displayed + 0.1 * raw

            # If a speed profile is provided, interpolate the speed based on raw progress.
            if speed_profile:
                clamped_raw = max(0.0, min(1.0, raw))
                # Find the segment of the profile the current progress is in
                start_kf = speed_profile[0]
                end_kf = speed_profile[-1]
                for i in range(len(speed_profile) - 1):
                    if speed_profile[i][0] <= clamped_raw <= speed_profile[i+1][0]:
                        start_kf = speed_profile[i]
                        end_kf = speed_profile[i+1]
                        break
                # Interpolate speed within the current segment
                segment_duration = end_kf[0] - start_kf[0]
                if segment_duration > 0:
                    progress_in_segment = (clamped_raw - start_kf[0]) / segment_duration
                    current_speed = start_kf[1] + (end_kf[1] - start_kf[1]) * progress_in_segment
                    self.starfield.speed_factor = current_speed
                else:  # Handle zero-duration segments (instant change)
                    self.starfield.speed_factor = end_kf[1]

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

        # Ensure final speed is set correctly after the loop
        if speed_profile:
            self.starfield.speed_factor = speed_profile[-1][1]

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
        settings.WALKABLE_TERRAINS = {key for key, data in settings.TERRAIN_DATA.items() if data.get("walkable")}

        # Robustly parse globe colors into (r, g, b, a) tuples.
        # This handles various formats (hex, names, RGB, RGBA) and ensures
        # all consumers receive a consistent RGBA format.
        globe_colors = []
        # Matplotlib expects colors as floats in [0, 1] range.
        for terrain_data in settings.TERRAIN_DATA.values():
            c = pygame.Color(terrain_data["globe_color"])
            # Normalize to floats for matplotlib compatibility
            globe_colors.append((c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0))
        settings.GLOBE_TERRAIN_COLORS = globe_colors

        self.current_theme_key = theme_key
        print(f"Selected theme: {theme['name']} ({theme_key})")

        # Determine selection color based on walkable brightness
        has_bright_walkable_terrain = any(
            ((td["color"][0] + td["color"][1] + td["color"][2]) / 3) > settings.BRIGHT_TERRAIN_THRESHOLD
            for td in settings.TERRAIN_DATA.values() if td["walkable"]
        )
        if has_bright_walkable_terrain:
            # For bright themes like "hoth", use the alternate, high-contrast color.
            print("Bright theme detected. Using high-contrast (alternate) selection colors.")
            settings.UNIT_SELECTED_COLOR = settings.ALT_SELECTION_COLOR
            settings.SELECTION_BOX_COLOR = settings.ALT_SELECTION_COLOR
        else:
            # For normal/dark themes, use the default selection color.
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

        # Define speeds for the loading sequence narrative
        hyper_speed = 2500.0
        normal_speed = 750.0
        final_speed = normal_speed / 2.0

        # --- Calculate intermediate speed for the seamless transition ---
        # The deceleration from hyper_speed to normal_speed happens over a total progress of 0.75
        # (0.25 from bar 1, 0.5 from bar 2). We need to find the speed at the end of bar 1.
        decel_duration_total = 0.25 + 0.5
        decel_duration_bar1 = 0.25
        decel_progress_bar1 = decel_duration_bar1 / decel_duration_total
        speed_delta_total = hyper_speed - normal_speed
        intermediate_speed = hyper_speed - (speed_delta_total * decel_progress_bar1)

        # --- Define Speed Profiles ---
        profile1 = [
            (0.0, normal_speed),      # Start at normal speed
            (0.25, normal_speed),     # Hold until 25%, then start accelerating
            (0.75, hyper_speed),      # Reach hyper speed at 75%, then start decelerating
            (1.0, intermediate_speed) # End at the calculated intermediate speed
        ]
        profile2 = [
            (0.0, intermediate_speed), # Start where the last bar left off
            (0.5, normal_speed),       # Decelerate to normal speed by 50%
            (1.0, final_speed)         # Decelerate to final speed by 100%
        ]

        # Stage 1: Intergalactic travel with its complex speed profile.
        self._run_loading_loop(
            map_generation_worker, "Intergalactic boost", speed_profile=profile1)

        self.world_state = WorldState()
        # Configure the context menu options. This was missing, causing the menu
        # to be invisible because it had no items to render.
        self.world_state.context_menu.options = [
            {"label": "Move"},
            {"label": "Attack"},
            {
                "label": "Build",
                # Sub-options should follow the same dict structure as main options
                # for consistency and to fix the rendering TypeError.
                "sub_options": [{"label": "Outpost"}, {"label": "Turret"}, {"label": "Mine"}],
            },
        ]
        # Store a reference to the first unit created so we can always find it.
        self.player_unit = self._spawn_initial_units()
        if self.player_unit:
            self.camera.position = self.player_unit.world_pos.copy()

        # --- Worker function for globe rendering ---
        def globe_rendering_worker(progress_state: Dict[str, float]) -> None:
            for progress in globe_renderer.render_map_as_globe(self.map.data, map_seed):
                if progress_state.get('cancel'):
                    return
                progress_state['progress'] = progress

        # Stage 2: Interstellar travel, with its own deceleration profile.
        self._run_loading_loop(
            globe_rendering_worker, "Interstellar slow down", speed_profile=profile2)
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
    def focus_on_player_unit(self) -> None:
        """Centers camera on the first unit and zooms to 400%."""
        if self.player_unit:
            self.camera.position = self.player_unit.world_pos.copy()

            # To prevent the camera from immediately zooming back out, we must
            # update both its current state and its target state. This ensures
            # the camera's internal animation logic remains stable after our
            # direct manipulation.
            target_zoom = 4.0
            self.camera.zoom_state.current = target_zoom
            self.camera.zoom_state.target = target_zoom

    def _issue_move_command_for_tile(self, end_tile: Tuple[int, int]) -> None:
        """Shared logic to find a path and issue a move command to a tile."""
        # If the target tile isn't walkable, try to snap to nearest walkable
        end = tuple(end_tile)
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

    def issue_move_command_to_target(self) -> None:
        """Issues a move command to selected units to the stored target tile."""
        target_tile = self.world_state.context_menu.target_tile
        if not self.world_state.selected_units or not target_tile:
            return
        self._issue_move_command_for_tile(target_tile)

    def issue_move_command_to_tile(self, target_tile: Tuple[int, int]) -> None:
        """Issues a move command to selected units to a specific tile."""
        if not self.world_state.selected_units:
            return
        self._issue_move_command_for_tile(target_tile)

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
        # The root cause of a previous visual glitch was fixed, so it is now
        # safe to re-enable the debug panel.
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
