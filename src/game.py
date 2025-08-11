# c:/game/worldom/game.py
"""
Defines the main Game class that orchestrates all game components.
"""
from __future__ import annotations
import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

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

        # --- Initialize Game Components ---
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        self.debug_panel = DebugPanel()
        self.input_handler = InputHandler(self)
        self.selection_manager = SelectionManager(self)

        # --- Globe Animation State ---
        self.show_globe_popup: bool = False
        self.globe_frames: List[pygame.Surface] = []
        self.globe_frame_index: int = 0
        self.globe_animation_timer: float = 0.0

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

    def _load_globe_frames(self, map_seed: int) -> None:
        """Loads the pre-rendered globe animation frames from disk."""
        self.globe_frames.clear() # Clear frames from any previous map
        base_image_dir = "image"
        frame_dir = os.path.join(base_image_dir, f"globe_frames_{map_seed}")
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
        """Returns a list of all (x, y) coordinates for land tiles (grass or rock)."""
        return [
            (x, y)
            for y in range(self.map.height)
            for x in range(self.map.width)
            if self.map.data[y][x] in {'grass', 'rock'}
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
        map_seed = random.randint(0, 1_000_000)
        self.map = Map(settings.MAP_WIDTH_TILES, settings.MAP_HEIGHT_TILES, seed=map_seed)
        for progress in self.map.generate():
            self._pump_events_during_load()
            self._draw_splash_screen(message="1/2 Generating 2D Map.", progress=progress)

        self.world_state = WorldState()
        initial_unit = self._spawn_initial_units()
        if initial_unit:
            self.camera.position = initial_unit.world_pos.copy()

        for progress in globe_renderer.render_map_as_globe(self.map.data, map_seed):
            self._pump_events_during_load()
            self._draw_splash_screen(message="2/2 Generating Globe.", progress=progress)
        self._load_globe_frames(map_seed)

    def regenerate_map(self) -> None:
        """Regenerates the map and resets the world state."""
        self._create_new_world()
        pygame.event.clear()

    def open_context_menu(self, screen_pos: Tuple[int, int]) -> None:
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

    def close_context_menu(self) -> None:
        """Closes the context menu."""
        self._close_sub_menu()
        self.world_state.context_menu.active = False
        self.world_state.context_menu.pos = None
        self.world_state.context_menu.rects.clear()
        self.world_state.context_menu.target_tile = None

    def handle_context_menu_click(self, mouse_pos: Tuple[int, int]) -> None:
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
                    self.close_context_menu()
                    return

        # If we clicked, but not on an actionable item (e.g., outside all menus),
        # then close the menu.
        self.close_context_menu()

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

        if self.show_globe_popup:
            self._update_globe_animation(dt)

    def _update_globe_animation(self, dt: float) -> None:
        """Cycles through the globe animation frames based on a timer."""
        if not self.globe_frames:
            return
        self.globe_animation_timer += dt
        if self.globe_animation_timer >= settings.GLOBE_FRAME_DURATION:
            self.globe_animation_timer = 0
            self.globe_frame_index = (self.globe_frame_index + 1) % len(self.globe_frames)

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

        # Draw globe popup if active
        if self.show_globe_popup:
            self._draw_globe_popup()

        # Draw context menu if active
        if self.world_state.context_menu.active:
            self._draw_context_menu()
            if self.world_state.context_menu.sub_menu.active:
                self._draw_sub_menu()

        self.debug_panel.draw(self)
        pygame.display.flip()

    def _draw_globe_popup(self) -> None:
        """Draws the globe animation popup in the center of the screen."""
        if not self.globe_frames:
            # Optionally, draw a "no frames found" message
            return

        # 1. Draw a semi-transparent overlay to dim the background
        overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180)) # Black with 180/255 alpha
        self.screen.blit(overlay, (0, 0))

        # 2. Get the current frame and its size
        current_frame = self.globe_frames[self.globe_frame_index]
        frame_rect = current_frame.get_rect()

        # 3. Define the popup box size (with padding)
        padding = 40
        popup_width = frame_rect.width + padding
        popup_height = frame_rect.height + padding
        popup_rect = pygame.Rect(0, 0, popup_width, popup_height)
        popup_rect.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)

        # 4. Draw the popup box and the globe frame inside it
        pygame.draw.rect(self.screen, (40, 40, 60), popup_rect, border_radius=10)
        pygame.draw.rect(self.screen, (200, 200, 220), popup_rect, width=2, border_radius=10)
        self.screen.blit(current_frame, (popup_rect.x + padding // 2, popup_rect.y + padding // 2))

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
