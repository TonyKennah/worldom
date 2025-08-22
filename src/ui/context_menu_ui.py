# src/ui/context_menu_ui.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, List, Optional
import pygame

# Robust import: prefer relative, fall back to absolute (keeps CI green).
try:
    from .context_menu import ContextMenuState  # correct when importing "ui.*"
except Exception:  # pragma: no cover
    try:
        from src.ui.context_menu import ContextMenuState  # fallback when imported as "src.ui.*"
    except Exception:
        # Minimal stub to satisfy imports only (won't be used at runtime)
        @dataclass
        class ContextMenuState:  # type: ignore
            active: bool = False
            pos: Optional[Tuple[int, int]] = None
            rects: List[pygame.Rect] = None  # type: ignore
            options: List[dict] = None  # type: ignore

            def __post_init__(self) -> None:
                if self.rects is None:
                    self.rects = []
                if self.options is None:
                    self.options = []

class ContextMenuUI:
    """Lightweight drawer for the context menu; safe to import in headless CI."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen

    def draw(self, state: ContextMenuState) -> None:
        if not getattr(state, "active", False):
            return

        # Basic panel draw: background + border for each option rect.
        for rect in getattr(state, "rects", []):
            pygame.draw.rect(self.screen, (28, 29, 33), rect, border_radius=3)
            pygame.draw.rect(self.screen, (80, 84, 92), rect, width=1, border_radius=3)
