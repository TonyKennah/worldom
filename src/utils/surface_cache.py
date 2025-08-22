# src/utils/surface_cache.py
from __future__ import annotations
from typing import Dict, Tuple
import pygame


class SurfaceCache:
    """
    Small cache for (surface_id, scale or angle) -> transformed surface.
    Useful for repeatedly drawing rotated bullets, shuriken, etc.
    """

    def __init__(self, max_items: int = 512) -> None:
        self._max = max_items
        self._cache: Dict[Tuple[int, Tuple], pygame.Surface] = {}

    def _trim(self) -> None:
        # simple FIFO eviction
        if len(self._cache) > self._max:
            remove = len(self._cache) - self._max
            for k in list(self._cache.keys())[:remove]:
                self._cache.pop(k, None)

    def rot(self, surface: pygame.Surface, angle: float) -> pygame.Surface:
        key = (id(surface), ("rot", int(angle) % 360))
        s = self._cache.get(key)
        if s is None:
            s = pygame.transform.rotate(surface, angle)
            self._cache[key] = s
            self._trim()
        return s

    def scale(self, surface: pygame.Surface, w: int, h: int, smooth: bool = True) -> pygame.Surface:
        key = (id(surface), ("scale", int(w), int(h), 1 if smooth else 0))
        s = self._cache.get(key)
        if s is None:
            s = pygame.transform.smoothscale(surface, (w, h)) if smooth else pygame.transform.scale(surface, (w, h))
            self._cache[key] = s
            self._trim()
        return s
