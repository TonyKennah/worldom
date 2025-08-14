# image_cache.py
# Small LRU-ish cache for scaled pygame surfaces to avoid repeated smoothscale cost.
from __future__ import annotations
from typing import Dict, Tuple
import pygame


class ScaledImageCache:
    def __init__(self, max_entries: int = 256) -> None:
        self._cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self._order: list[Tuple[int, int]] = []
        self._max = int(max_entries)

    def _touch(self, key: Tuple[int, int]) -> None:
        try:
            self._order.remove(key)
        except ValueError:
            pass
        self._order.append(key)
        if len(self._order) > self._max:
            # evict oldest
            old = self._order.pop(0)
            self._cache.pop(old, None)

    def get(self, surf: pygame.Surface, size: int, *, smooth: bool = True) -> pygame.Surface:
        size = max(1, int(size))
        key = (id(surf), size)
        if key in self._cache:
            self._touch(key)
            return self._cache[key]

        if smooth and hasattr(pygame.transform, "smoothscale"):
            scaled = pygame.transform.smoothscale(surf, (size, size))
        else:
            scaled = pygame.transform.scale(surf, (size, size))

        self._cache[key] = scaled
        self._touch(key)
        return scaled
