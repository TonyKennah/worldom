# camera_utils.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Tuple

import math
import pygame

try:
    # Optional: typed protocol for better hints; falls back if not present.
    from camera_types import CameraLike
except Exception:  # pragma: no cover
    CameraLike = object  # type: ignore[assignment]


TileRect = Tuple[int, int, int, int]  # (tx, ty, tw, th)


# ---------------------------------------------------------------------------
# Core culling / tile helpers
# ---------------------------------------------------------------------------

def visible_tile_rect(
    camera: CameraLike,
    tile_w: int,
    tile_h: int,
    *,
    padding_tiles: int = 1,
    world_tiles: Optional[Tuple[int, int]] = None,
) -> TileRect:
    """
    Returns the tile-area visible by the camera as (tx, ty, tw, th), padded by N tiles.

    Args:
        camera: A camera implementing CameraLike protocol.
        tile_w, tile_h: Tile pixel dimensions (> 0).
        padding_tiles: Extra tiles added around all edges to avoid pop-in.
        world_tiles: Optional (world_w_tiles, world_h_tiles) to clamp indices.

    Notes:
        - The result is clamped to non-negative width/height.
        - If world_tiles is provided, the region is clamped into [0, world-1].
    """
    if tile_w <= 0 or tile_h <= 0:
        raise ValueError("tile_w and tile_h must be > 0")

    vis = camera.get_visible_world_rect()
    # Convert visible world rect to tile indices (floor for start, ceil for end).
    x0 = math.floor(vis.left / tile_w) - padding_tiles
    y0 = math.floor(vis.top / tile_h) - padding_tiles
    x1 = math.ceil(vis.right / tile_w) + padding_tiles
    y1 = math.ceil(vis.bottom / tile_h) + padding_tiles

    if world_tiles is not None:
        max_tx, max_ty = world_tiles
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(max_tx, x1)
        y1 = min(max_ty, y1)

    tw = max(0, x1 - x0)
    th = max(0, y1 - y0)
    return int(x0), int(y0), int(tw), int(th)


def iter_visible_tiles(
    camera: CameraLike,
    tile_w: int,
    tile_h: int,
    *,
    padding_tiles: int = 1,
    world_tiles: Optional[Tuple[int, int]] = None,
) -> Iterator[Tuple[int, int]]:
    """
    Iterate all tile coordinates (tx, ty) within the visible (padded) tile rect.
    This is handy for drawing only what's on-screen.

    Example:
        for tx, ty in iter_visible_tiles(cam, 32, 32, padding_tiles=2, world_tiles=(map_w, map_h)):
            draw_tile(tx, ty)
    """
    tx, ty, tw, th = visible_tile_rect(
        camera, tile_w, tile_h, padding_tiles=padding_tiles, world_tiles=world_tiles
    )
    for y in range(ty, ty + th):
        for x in range(tx, tx + tw):
            yield x, y


def visible_chunk_rect(
    tile_rect: TileRect,
    chunk_w_tiles: int,
    chunk_h_tiles: int,
    *,
    world_chunks: Optional[Tuple[int, int]] = None,
) -> TileRect:
    """
    Given a visible tile rect (tx, ty, tw, th), compute the covered CHUNK region
    as (cx, cy, cw, ch) where each chunk is chunk_w_tiles x chunk_h_tiles tiles.

    Useful for chunk-streaming or batched draw calls.
    """
    if chunk_w_tiles <= 0 or chunk_h_tiles <= 0:
        raise ValueError("chunk_w_tiles and chunk_h_tiles must be > 0")

    tx, ty, tw, th = tile_rect
    # Convert tile range to chunk indices, rounding outward.
    cx0 = math.floor(tx / chunk_w_tiles)
    cy0 = math.floor(ty / chunk_h_tiles)
    cx1 = math.ceil((tx + tw) / chunk_w_tiles)
    cy1 = math.ceil((ty + th) / chunk_h_tiles)

    if world_chunks is not None:
        max_cx, max_cy = world_chunks
        cx0 = max(0, cx0)
        cy0 = max(0, cy0)
        cx1 = min(max_cx, cx1)
        cy1 = min(max_cy, cy1)

    cw = max(0, cx1 - cx0)
    ch = max(0, cy1 - cy0)
    return int(cx0), int(cy0), int(cw), int(ch)


def cull_world_rects(
    camera: CameraLike,
    world_rects: Iterable[pygame.Rect],
    *,
    margin: float = 0.0
) -> Iterator[pygame.Rect]:
    """Yield only world rects intersecting the camera's visible world rect."""
    vis = camera.get_visible_world_rect(margin)
    for r in world_rects:
        if vis.colliderect(r):
            yield r


def cull_world_points(
    camera: CameraLike,
    points: Iterable[Tuple[float, float]],
    *,
    margin: float = 0.0
) -> Iterator[Tuple[float, float]]:
    """Yield only points that fall within the camera's visible world rect."""
    vis = camera.get_visible_world_rect(margin)
    for p in points:
        if vis.collidepoint(p):
            yield p


# ---------------------------------------------------------------------------
# Parallax helpers
# ---------------------------------------------------------------------------

def parallax_apply_rect(camera: CameraLike, rect: pygame.Rect, factor: float) -> pygame.Rect:
    """
    Parallax-transform a world-space rect and map it to screen space via camera.apply.
    factor < 1 => background-like (moves slower); factor > 1 => foreground-like (moves faster).
    """
    cx, cy = rect.center
    px = camera.position.x * (1.0 - factor) + cx * factor
    py = camera.position.y * (1.0 - factor) + cy * factor
    w, h = rect.w, rect.h
    return camera.apply(pygame.Rect(int(px - w / 2), int(py - h / 2), w, h))


def parallax_apply_point(camera: CameraLike, pos: Tuple[float, float], factor: float) -> Tuple[int, int]:
    """
    Parallax-transform a world-space point and return its screen-space coordinates.
    """
    wx, wy = pos
    px = camera.position.x * (1.0 - factor) + wx * factor
    py = camera.position.y * (1.0 - factor) + wy * factor
    sp = camera.world_to_screen((px, py))
    return int(round(sp.x)), int(round(sp.y))


# ---------------------------------------------------------------------------
# Screen scissor helper
# ---------------------------------------------------------------------------

def screen_scissor_for_world_rect(camera: CameraLike, rect: pygame.Rect) -> pygame.Rect:
    """
    Convert a world rect to screen rect and intersect with the screen bounds
    (0..camera.width, 0..camera.height). If width/height are not present, returns
    the applied rect without clipping.
    """
    sr = camera.apply(rect)
    if hasattr(camera, "width") and hasattr(camera, "height"):
        screen_bounds = pygame.Rect(0, 0, int(camera.width), int(camera.height))
        return sr.clip(screen_bounds)
    return sr


# ---------------------------------------------------------------------------
# Small caching utility (optional)
# ---------------------------------------------------------------------------

@dataclass
class ViewCache:
    """
    Lightweight memoization of the camera's visible world rect and its derived
    tile/ chunk rectangles. Useful if you compute these multiple times per frame.
    """
    last_world_rect: Optional[pygame.Rect] = None
    last_tile_args: Optional[Tuple[int, int, int, Optional[Tuple[int, int]]]] = None
    last_tile_rect: Optional[TileRect] = None

    def tile_rect(
        self,
        camera: CameraLike,
        tile_w: int,
        tile_h: int,
        *,
        padding_tiles: int = 1,
        world_tiles: Optional[Tuple[int, int]] = None,
    ) -> TileRect:
        vis = camera.get_visible_world_rect()
        args = (tile_w, tile_h, padding_tiles, world_tiles)
        if (
            self.last_world_rect is not None
            and self.last_tile_args == args
            and vis == self.last_world_rect
            and self.last_tile_rect is not None
        ):
            return self.last_tile_rect

        tr = visible_tile_rect(
            camera, tile_w, tile_h, padding_tiles=padding_tiles, world_tiles=world_tiles
        )
        self.last_world_rect = vis.copy()
        self.last_tile_args = args
        self.last_tile_rect = tr
        return tr
