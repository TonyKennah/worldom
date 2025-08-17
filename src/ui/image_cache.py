# image_cache.py
# Tiny LRU cache for scaled (thumbnail) versions of pygame surfaces.
from __future__ import annotations
from collections import OrderedDict
from typing import Tuple
import pygame


class ScaledImageCache:
    """
    Cache scaled versions of pygame surfaces to avoid repeated transform cost.
    Keyed by (id(surface), size, smooth_flag).
    """

    def __init__(self, capacity: int = 256) -> None:
        self.capacity = int(max(16, capacity))
        self._store: "OrderedDict[Tuple[int, int, bool], pygame.Surface]" = OrderedDict()

    def _make_key(self, surf: pygame.Surface, size: int, smooth: bool) -> Tuple[int, int, bool]:
        return (id(surf), size, bool(smooth))

    def get(self, surf: pygame.Surface, size: int, *, smooth: bool = True) -> pygame.Surface:
        size = max(1, int(size))
        key = self._make_key(surf, size, smooth)

        if key in self._store:
            s = self._store.pop(key)
            self._store[key] = s  # move to end (MRU)
            return s

        # create
        w, h = surf.get_width(), surf.get_height()
        scale = size / max(w, h)
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        scaled = pygame.transform.smoothscale(surf, new_size) if smooth else pygame.transform.scale(surf, new_size)

        # evict if needed
        if len(self._store) >= self.capacity:
            self._store.popitem(last=False)
        self._store[key] = scaled
        return scaled

    def clear(self) -> None:
        self._store.clear()
