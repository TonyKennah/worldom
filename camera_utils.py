# camera_utils.py
from __future__ import annotations
from typing import Iterable, Iterator, Tuple
import pygame

def visible_tile_rect(
    camera,
    tile_w: int,
    tile_h: int,
    *,
    padding_tiles: int = 1,
) -> Tuple[int, int, int, int]:
    """
    Returns (tx, ty, tw, th) tile-area visible by the camera, padded by N tiles.
    Useful for culling tilemaps / chunked worlds.
    """
    vis = camera.get_visible_world_rect()
    x0 = (vis.left // tile_w) - padding_tiles
    y0 = (vis.top  // tile_h) - padding_tiles
    x1 = ((vis.right  + tile_w - 1) // tile_w) + padding_tiles
    y1 = ((vis.bottom + tile_h - 1) // tile_h) + padding_tiles
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)

def cull_world_rects(camera, world_rects: Iterable[pygame.Rect], *, margin: float = 0.0) -> Iterator[pygame.Rect]:
    """Yield only rects that intersect the camera's world-space visible rect."""
    vis = camera.get_visible_world_rect(margin)
    for r in world_rects:
        if vis.colliderect(r):
            yield r

def parallax_apply_rect(camera, rect: pygame.Rect, factor: float) -> pygame.Rect:
    """
    Transform a world rect with parallax, then to screen.
    factor < 1 => background-like motion; > 1 => foreground-like.
    """
    center = rect.center
    px = camera.position.x * (1.0 - factor) + center[0] * factor
    py = camera.position.y * (1.0 - factor) + center[1] * factor
    w, h = rect.w, rect.h
    return camera.apply(pygame.Rect(int(px - w / 2), int(py - h / 2), w, h))
