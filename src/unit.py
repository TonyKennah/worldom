# c:/game/worldom/unit.py
"""
Defines the Unit class for the game.
"""
from __future__ import annotations
import pygame

from typing import List, Tuple, TYPE_CHECKING
from settings import (TILE_SIZE, UNIT_RADIUS, UNIT_MOVES_PER_SECOND, 
                      UNIT_COLOR, UNIT_SELECTED_COLOR)

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
        self.selected: bool = False
        self.path: List[Tuple[int, int]] = []
        self.move_timer: float = 0.0

    def get_world_rect(self) -> pygame.Rect:
        """Gets the unit's bounding box in world coordinates for selection."""
        return pygame.Rect(self.world_pos.x - UNIT_RADIUS, self.world_pos.y - UNIT_RADIUS, UNIT_RADIUS * 2, UNIT_RADIUS * 2)

    def set_path(self, path: List[Tuple[int, int]]) -> None:
        """Sets a new path for the unit to follow."""
        self.path = path

    def update(self, dt: float) -> None:
        """Moves the unit along its path one tile at a time based on a timer."""
        if not self.path:
            return

        self.move_timer += dt
        move_delay = 1.0 / UNIT_MOVES_PER_SECOND

        # If enough time has passed, move to the next tile
        if self.move_timer >= move_delay:
            self.move_timer -= move_delay

            # Instantly move to the next tile in the path
            next_tile = self.path.pop(0)
            self.tile_pos = pygame.math.Vector2(next_tile)
            self.world_pos = (self.tile_pos * TILE_SIZE) + pygame.math.Vector2(TILE_SIZE / 2)

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Draws the unit on the screen."""
        screen_pos: pygame.math.Vector2 = camera.world_to_screen(self.world_pos)
        radius = int(UNIT_RADIUS * camera.zoom)
        
        # Draw selection circle first (underneath the unit)
        if self.selected:
            pygame.draw.circle(surface, UNIT_SELECTED_COLOR, screen_pos, radius)
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, int(radius * 0.8)) # Inner circle
        else:
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, radius)