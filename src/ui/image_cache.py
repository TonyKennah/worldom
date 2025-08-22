# c:/prj/WorldDom/src/ui/image_cache.py
from __future__ import annotations
import pygame
from typing import Dict, Tuple


class ScaledImageCache:
    """
    Cache scaled versions of a pygame.Surface keyed by (id(surface), size, smooth).
    Saves a lot of CPU when repeatedly scaling weapon or galaxy sprites.
    """
    def __init__(self) -> None:
        self._cache: Dict[Tuple[int, int, bool], pygame.Surface] = {}

    def get(self, surface: pygame.Surface, size: int, smooth: bool = True) -> pygame.Surface:
        """
        Returns a square scaled version of `surface` with edge length `size`.
        """
        key = (id(surface), int(size), bool(smooth))
        hit = self._cache.get(key)
        if hit:
            return hit

        # Create scaled sprite
        target_size = (int(size), int(size))
        if smooth:
            scaled = pygame.transform.smoothscale(surface, target_size)
        else:
            scaled = pygame.transform.scale(surface, target_size)

        self._cache[key] = scaled
        return scaled

    def clear(self) -> None:
        self._cache.clear()
