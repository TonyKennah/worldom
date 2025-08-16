"""
Toroidal (wrap-around) helpers used by multiple systems.
"""
from __future__ import annotations

import math
from typing import Tuple

import pygame
import src.utils.settings as settings

TILE_SIZE = settings.TILE_SIZE
_EPS = 1e-6


def tile_to_world_center(tile_xy: pygame.Vector2 | Tuple[int, int]) -> pygame.Vector2:
    """Convert (col,row) tile into world-space center point."""
    v = pygame.Vector2(tile_xy)
    return (v * TILE_SIZE) + pygame.Vector2(TILE_SIZE * 0.5, TILE_SIZE * 0.5)


def world_center_to_tile(world_center: pygame.Vector2, map_w_tiles: int, map_h_tiles: int) -> pygame.Vector2:
    """Convert a world-space center point to (col,row) tile indices under wrap."""
    total_w = max(1, map_w_tiles * TILE_SIZE)
    total_h = max(1, map_h_tiles * TILE_SIZE)
    x = int((world_center.x % total_w) // TILE_SIZE)
    y = int((world_center.y % total_h) // TILE_SIZE)
    return pygame.Vector2(x, y)


def shortest_delta(a: pygame.Vector2, b: pygame.Vector2, w_px: int, h_px: int) -> pygame.Vector2:
    """Vector from a -> b on a toroidal map (shortest wrapped delta)."""
    dx = b.x - a.x
    dy = b.y - a.y
    if abs(dx) > w_px * 0.5:
        dx -= math.copysign(w_px, dx)
    if abs(dy) > h_px * 0.5:
        dy -= math.copysign(h_px, dy)
    return pygame.Vector2(dx, dy)


def shortest_distance(a: pygame.Vector2, b: pygame.Vector2, w_px: int, h_px: int) -> float:
    """Scalar distance using shortest_delta()."""
    return shortest_delta(a, b, w_px, h_px).length()


def wrap_pos_inplace(p: pygame.Vector2, w_px: int, h_px: int) -> None:
    """Wrap a world position in-place into [0, size) range (handles negatives)."""
    if w_px > 0:
        p.x = p.x % w_px
    if h_px > 0:
        p.y = p.y % h_px
