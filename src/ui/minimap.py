# src/ui/minimap.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple
import pygame

@dataclass
class MiniMapConfig:
    # Use default_factory for mutable pygame.Rect
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(10, 10, 160, 120))
    border_color: Tuple[int, int, int] = (80, 84, 92)
    bg_color: Tuple[int, int, int] = (20, 22, 26)
    alpha: int = 210

class MiniMap:
    """Import-safe minimap scaffold (draw/update are no-ops for CI)."""

    def __init__(self, surface: pygame.Surface, config: Optional[MiniMapConfig] = None) -> None:
        self.surface = surface
        self.config = config or MiniMapConfig()
        self._buffer = pygame.Surface((self.config.rect.width, self.config.rect.height), pygame.SRCALPHA)

    def update(self, _dt: float) -> None:
        # Hook for future world-to-minimap projection
        pass

    def draw(self) -> None:
        cfg = self.config
        self._buffer.fill((*cfg.bg_color, cfg.alpha))
        pygame.draw.rect(self._buffer, cfg.border_color, self._buffer.get_rect(), 1, border_radius=3)
        self.surface.blit(self._buffer, cfg.rect.topleft)
