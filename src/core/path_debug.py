# c:/game/worldom/path_debug.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import pygame

@dataclass
class PathDebug:
    start: Tuple[int, int]
    goal: Tuple[int, int]
    path: List[Tuple[int, int]]
    closed: Set[Tuple[int, int]]
    open: Set[Tuple[int, int]]
    g_cost: Dict[Tuple[int, int], float]
    came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]]

def draw_path_debug(
    surface: pygame.Surface,
    camera,
    tile_size: int,
    debug: PathDebug,
    color_closed=(200, 80, 80),
    color_open=(80, 160, 220),
    color_path=(255, 240, 60),
) -> None:
    """Overlay for debugging a path search. Call after Map.draw()."""
    def tile_rect(tx: int, ty: int) -> pygame.Rect:
        return camera.apply(pygame.Rect(tx * tile_size, ty * tile_size, tile_size, tile_size))

    for tx, ty in debug.closed:
        pygame.draw.rect(surface, color_closed, tile_rect(tx, ty), 1)
    for tx, ty in debug.open:
        pygame.draw.rect(surface, color_open, tile_rect(tx, ty), 1)

    if debug.path:
        pts = []
        for tx, ty in debug.path:
            r = tile_rect(tx, ty)
            pts.append(r.center)
        if len(pts) >= 2:
            pygame.draw.lines(surface, color_path, False, pts, 3)
