# c:/game/worldom/camera.py
"""
Defines the Camera class for managing the game's viewport.
"""
from typing import List, Tuple

import pygame

from settings import CAMERA_SPEED

class ZoomState:
    """Encapsulates the state and logic for camera zooming."""
    def __init__(self) -> None:
        self.levels = [0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
        self.index = self.levels.index(1.0)
        self.current = self.levels[self.index]

class PanningState:
    """Encapsulates the state for mouse panning."""
    def __init__(self) -> None:
        self.dragging = False
        self.drag_pos: Optional[pygame.math.Vector2] = None

class Camera:
    """Manages the game's viewport, handling zoom and panning."""
    def __init__(self, width: int, height: int) -> None:
        """Initializes the camera."""
        self.width = width
        self.height = height
        self.position = pygame.math.Vector2(0, 0)
        self.screen_center = pygame.math.Vector2(width / 2, height / 2)

        self.zoom_state = ZoomState()
        self.panning_state = PanningState()

    def screen_to_world(self, screen_pos: Tuple[int, int]) -> pygame.math.Vector2:
        """Converts screen coordinates to world coordinates."""
        return (pygame.math.Vector2(screen_pos) - self.screen_center) / self.zoom_state.current + self.position

    def world_to_screen(self, world_pos: pygame.math.Vector2) -> pygame.math.Vector2:
        """Converts world coordinates to screen coordinates."""
        return (pygame.math.Vector2(world_pos) - self.position) * self.zoom_state.current + self.screen_center

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        """Applies camera transformation to a pygame.Rect."""
        top_left = self.world_to_screen(rect.topleft)
        w = rect.width * self.zoom_state.current
        h = rect.height * self.zoom_state.current
        # Rounding all values to prevent gaps/jitter from float truncation.
        return pygame.Rect(round(top_left.x), round(top_left.y), round(w), round(h))

    def update(self, dt: float, events: List[pygame.event.Event]) -> None:
        """Updates camera position based on user input."""
        self._handle_keyboard_movement(dt)
        self._handle_mouse_input(events)

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
        """Handles mouse zooming and panning."""
        for event in events:
            if event.type == pygame.MOUSEWHEEL:
                self._handle_zoom(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.panning_state.dragging = True
                self.panning_state.drag_pos = pygame.math.Vector2(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.panning_state.dragging = False
                self.panning_state.drag_pos = None
            elif event.type == pygame.MOUSEMOTION and self.panning_state.dragging:
                drag_vec = pygame.math.Vector2(event.pos) - self.panning_state.drag_pos
                self.position -= drag_vec / self.zoom_state.current
                self.panning_state.drag_pos = pygame.math.Vector2(event.pos)

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
