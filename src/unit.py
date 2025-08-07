# c:/game/worldom/unit.py
"""
Defines the Unit class for the game.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple

import pygame

from settings import (TILE_SIZE, UNIT_RADIUS, UNIT_MOVES_PER_SECOND,
                      UNIT_COLOR, UNIT_SELECTED_COLOR, UNIT_INNER_CIRCLE_RATIO)

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

    def update(self, dt: float) -> None:
        """Moves the unit smoothly along its path by interpolating its position."""
        # If we don't have a path and we are at our destination, do nothing.
        if not self.path and self.world_pos == self.target_world_pos:
            return

        # If we are at our destination, get the next destination from the path.
        if self.world_pos == self.target_world_pos and self.path:
            next_tile = self.path.pop(0)
            self.tile_pos = pygame.math.Vector2(next_tile)
            self.target_world_pos = (self.tile_pos * TILE_SIZE) + pygame.math.Vector2(TILE_SIZE / 2)

        # Move towards the target position.
        move_vec = self.target_world_pos - self.world_pos
        dist_to_target = move_vec.length()

        if dist_to_target > 0:
            speed = UNIT_MOVES_PER_SECOND * TILE_SIZE
            distance_to_move = speed * dt

            if distance_to_move >= dist_to_target:
                # We can reach or overshoot the target this frame, so just snap to it.
                self.world_pos = self.target_world_pos.copy()
            else:
                # Move towards the target.
                move_vec.normalize_ip()
                self.world_pos += move_vec * distance_to_move

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Draws the unit on the screen."""
        screen_pos = camera.world_to_screen(self.world_pos)
        radius = int(UNIT_RADIUS * camera.zoom_state.current)

        # Draw selection circle first (underneath the unit)
        if self.selected:
            pygame.draw.circle(surface, UNIT_SELECTED_COLOR, screen_pos, radius)
            inner_radius = int(radius * UNIT_INNER_CIRCLE_RATIO)
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, inner_radius)
        else:
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, radius)
