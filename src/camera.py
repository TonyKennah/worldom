# c:/game/worldom/camera.py
"""
Defines the Camera class for managing the game's viewport.
"""
from typing import List, Tuple

import pygame

from settings import (CAMERA_SPEED, EDGE_SCROLL_SPEED, EDGE_SCROLL_BOUNDARY,
                      DEBUG_PANEL_HEIGHT)

class ZoomState:
    """Encapsulates the state and logic for camera zooming."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.levels = [0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
        self.index = self.levels.index(2.0)
        self.current = self.levels[self.index]

class Camera:
    """Manages the game's viewport, handling zoom and panning."""

    def __init__(self, width: int, height: int) -> None:
        """Initializes the camera."""
        self.width = width
        self.height = height
        self.position = pygame.math.Vector2(0, 0)
        self.screen_center = pygame.math.Vector2(width / 2, height / 2)

        self.zoom_state = ZoomState()

    def screen_to_world(self, screen_pos: Tuple[int, int]) -> pygame.math.Vector2:
        """Converts screen coordinates to world coordinates."""
        world_offset = pygame.math.Vector2(screen_pos) - self.screen_center
        world_offset /= self.zoom_state.current
        return world_offset + self.position

    def world_to_screen(self, world_pos: pygame.math.Vector2) -> pygame.math.Vector2:
        """Converts world coordinates to screen coordinates."""
        screen_offset = pygame.math.Vector2(world_pos) - self.position
        screen_offset *= self.zoom_state.current
        return screen_offset + self.screen_center

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        """Applies camera transformation to a pygame.Rect."""
        top_left = self.world_to_screen(rect.topleft)
        w = rect.width * self.zoom_state.current
        h = rect.height * self.zoom_state.current
        # Rounding all values to prevent gaps/jitter from float truncation.
        return pygame.Rect(round(top_left.x), round(top_left.y), round(w), round(h))

    def update(self, dt: float, events: List[pygame.event.Event], map_width_pixels: int, map_height_pixels: int) -> None:
        """Updates camera position based on user input."""
        self._handle_keyboard_movement(dt)
        self._handle_mouse_input(events)
        self._handle_edge_scrolling(dt)
        self._wrap_camera_position(map_width_pixels, map_height_pixels)

    def _wrap_camera_position(self, map_width_pixels: int, map_height_pixels: int) -> None:
        """Wraps the camera's position to create a toroidal (looping) map effect."""
        if self.position.x < 0:
            self.position.x += map_width_pixels
        elif self.position.x >= map_width_pixels:
            self.position.x -= map_width_pixels

        if self.position.y < 0:
            self.position.y += map_height_pixels
        elif self.position.y >= map_height_pixels:
            self.position.y -= map_height_pixels

    def _handle_keyboard_movement(self, dt: float) -> None:
        """Moves the camera based on WASD key presses."""
        keys = pygame.key.get_pressed()
        move_vec = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w]:
            move_vec.y -= 1
        if keys[pygame.K_s]:
            move_vec.y += 1
        if keys[pygame.K_a]:
            move_vec.x -= 1
        if keys[pygame.K_d]:
            move_vec.x += 1

        if move_vec.length_squared() > 0:
            move_vec.normalize_ip()
            # Scale movement by zoom level to feel consistent
            self.position += move_vec * CAMERA_SPEED / self.zoom_state.current * dt

    def _handle_mouse_input(self, events: List[pygame.event.Event]) -> None:
        """Handles mouse zooming."""
        for event in events:
            if event.type == pygame.MOUSEWHEEL:
                self._handle_zoom(event)

    def _handle_zoom(self, event: pygame.event.Event) -> None:
        """Adjusts camera zoom based on mouse wheel events."""
        mouse_pos_before_zoom = self.screen_to_world(pygame.mouse.get_pos())

        if event.y > 0:  # Zoom in
            self.zoom_state.index = min(len(self.zoom_state.levels) - 1, self.zoom_state.index + 1)
        elif event.y < 0:  # Zoom out
            self.zoom_state.index = max(0, self.zoom_state.index - 1)

        self.zoom_state.current = self.zoom_state.levels[self.zoom_state.index]

        mouse_pos_after_zoom = self.screen_to_world(pygame.mouse.get_pos())
        self.position += mouse_pos_before_zoom - mouse_pos_after_zoom

    def _handle_edge_scrolling(self, dt: float) -> None:
        """Moves the camera if the mouse is near the screen edges."""
        # Only scroll if the mouse is inside the game window.
        if not pygame.mouse.get_focused():
            return

        mouse_pos = pygame.mouse.get_pos()
        move_vec = pygame.math.Vector2(0, 0)

        # Only check for horizontal scrolling if the mouse is outside the debug panel.
        if mouse_pos[1] >= DEBUG_PANEL_HEIGHT:
            if mouse_pos[0] < EDGE_SCROLL_BOUNDARY:
                move_vec.x -= 1
            elif mouse_pos[0] > self.width - EDGE_SCROLL_BOUNDARY:
                move_vec.x += 1

        # The scrollable area at the top starts just below the debug panel.
        if DEBUG_PANEL_HEIGHT <= mouse_pos[1] < DEBUG_PANEL_HEIGHT + EDGE_SCROLL_BOUNDARY:
            move_vec.y -= 1
        elif mouse_pos[1] > self.height - EDGE_SCROLL_BOUNDARY:
            move_vec.y += 1

        if move_vec.length_squared() > 0:
            move_vec.normalize_ip()
            # Scale movement by zoom level to feel consistent
            self.position += move_vec * EDGE_SCROLL_SPEED / self.zoom_state.current * dt
