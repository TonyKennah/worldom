"""
This module defines the Unit class, which represents a single unit in the game.
"""
from __future__ import annotations
import math
from typing import TYPE_CHECKING, List, Tuple

import pygame

from settings import (TILE_SIZE, UNIT_RADIUS, UNIT_MOVES_PER_SECOND,
                      UNIT_COLOR, UNIT_SELECTED_COLOR,
                      UNIT_INNER_CIRCLE_RATIO)

if TYPE_CHECKING:
    from camera import Camera

class Unit:
    """Represents a single unit in the game."""
    def __init__(self, tile_pos: Tuple[int, int]) -> None:
        """
        Initializes a unit.
        Args:
            tile_pos (Tuple[int, int]): The (col, row) starting tile position.
        """
        # Logical position on the grid
        self.tile_pos = pygame.math.Vector2(tile_pos)
        # Pixel position in the world for smooth movement
        self.world_pos = (self.tile_pos * TILE_SIZE) + pygame.math.Vector2(TILE_SIZE / 2)
        self.target_world_pos = self.world_pos.copy()
        self.selected: bool = False
        self.path: List[Tuple[int, int]] = []

    def get_world_rect(self) -> pygame.Rect:
        """Gets the unit's bounding box in world coordinates for selection."""
        size = UNIT_RADIUS * 2
        top_left_x = self.world_pos.x - UNIT_RADIUS
        top_left_y = self.world_pos.y - UNIT_RADIUS
        return pygame.Rect(top_left_x, top_left_y, size, size)

    def set_path(self, path: List[Tuple[int, int]]) -> None:
        """Sets a new path for the unit to follow."""
        self.path = path

    def update(self, dt: float, map_width_tiles: int, map_height_tiles: int) -> None:
        """Moves the unit smoothly along its path, handling toroidal map wrapping."""
        map_width_pixels = map_width_tiles * TILE_SIZE
        map_height_pixels = map_height_tiles * TILE_SIZE

        # If we are at our destination, get the next destination from the path.
        if self.world_pos == self.target_world_pos and self.path:
            next_tile_pos = self.path.pop(0)
            self.tile_pos = pygame.math.Vector2(next_tile_pos)
            self.target_world_pos = (self.tile_pos * TILE_SIZE) + pygame.math.Vector2(TILE_SIZE / 2)

        # If we don't have a path or are already at the target, do nothing.
        if self.world_pos == self.target_world_pos:
            return

        # Calculate the shortest vector to the target on a toroidal map
        move_vec = self.target_world_pos - self.world_pos
        if abs(move_vec.x) > map_width_pixels / 2:
            move_vec.x -= math.copysign(map_width_pixels, move_vec.x)
        if abs(move_vec.y) > map_height_pixels / 2:
            move_vec.y -= math.copysign(map_height_pixels, move_vec.y)

        dist_to_target = move_vec.length()

        if dist_to_target > 0:
            speed = UNIT_MOVES_PER_SECOND * TILE_SIZE
            distance_to_move = speed * dt

            if distance_to_move >= dist_to_target:
                # Snap to target
                self.world_pos = self.target_world_pos.copy()
            else:
                # Move towards the target
                move_vec.normalize_ip()
                self.world_pos += move_vec * distance_to_move

            # Wrap the unit's world position for continuous movement
            self.world_pos.x %= map_width_pixels
            self.world_pos.y %= map_height_pixels

    def draw(
        self, surface: pygame.Surface, camera: Camera,
        map_width_pixels: int, map_height_pixels: int
    ) -> None:
        """Draws the unit on the screen, handling toroidal map wrapping."""
        for dx in [-map_width_pixels, 0, map_width_pixels]:
            for dy in [-map_height_pixels, 0, map_height_pixels]:
                offset = pygame.math.Vector2(dx, dy)
                self._draw_single_unit_instance(surface, camera, self.world_pos + offset)

    def _draw_single_unit_instance(
        self, surface: pygame.Surface, camera: Camera,
        pos: pygame.math.Vector2
    ) -> None:
        """Draws a single instance of the unit at a given position."""
        screen_pos = camera.world_to_screen(pos)
        radius = int(UNIT_RADIUS * camera.zoom_state.current)

        # Don't draw if the unit is completely off-screen
        if screen_pos.x + radius < 0 or screen_pos.x - radius > camera.width:
            return
        if screen_pos.y + radius < 0 or screen_pos.y - radius > camera.height:
            return

        # Draw selection circle first (underneath the unit)
        if self.selected:
            pygame.draw.circle(surface, UNIT_SELECTED_COLOR, screen_pos, radius)
            inner_radius = int(radius * UNIT_INNER_CIRCLE_RATIO)
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, inner_radius)
        else:
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, radius)
