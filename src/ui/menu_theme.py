# src/ui/menu_theme.py
from __future__ import annotations
from dataclasses import dataclass, field
import pygame

@dataclass(frozen=True)
class MenuTheme:
    # Use default_factory for mutable pygame.Color instances
    bg: pygame.Color = field(default_factory=lambda: pygame.Color(25, 27, 30))
    fg: pygame.Color = field(default_factory=lambda: pygame.Color(210, 210, 215))
    hover: pygame.Color = field(default_factory=lambda: pygame.Color(42, 45, 52))
    border: pygame.Color = field(default_factory=lambda: pygame.Color(80, 84, 92))
    accent: pygame.Color = field(default_factory=lambda: pygame.Color(230, 200, 60))

    padding: int = 8
    radius: int = 3
    font_name: str = "Arial"
    font_size: int = 16

def make_font(theme: MenuTheme) -> pygame.font.Font:
    """Create a font safely even when system fonts are limited (CI)."""
    try:
        return pygame.font.SysFont(theme.font_name, theme.font_size)
    except Exception:
        return pygame.font.Font(None, theme.font_size)

