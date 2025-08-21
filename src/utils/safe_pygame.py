"""
Small helpers to interact with pygame safely (headless-aware).
"""
from __future__ import annotations
import pygame

def display_ready() -> bool:
    try:
        return pygame.get_init() and pygame.display.get_surface() is not None
    except Exception:
        return False

def ensure_display(min_size=(4, 4)) -> None:
    """
    Create a tiny display if none exists (so convert_alpha() works in loaders).
    No-op if display is already present.
    """
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        try:
            pygame.display.set_mode(min_size)
        except Exception:
            # Headless or not permitted; ignore
            pass
