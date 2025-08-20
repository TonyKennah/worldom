# c:/prj/WorldDom/src/ui/toast.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Deque, List, Tuple
from collections import deque

import pygame

try:
    import src.utils.settings as settings
except Exception:
    class _Fallback:
        DEBUG_PANEL_FONT_COLOR = (240, 240, 240)
    settings = _Fallback()  # type: ignore


@dataclass
class Toast:
    text: str
    created: float
    duration: float


class ToastManager:
    """
    Ephemeral notifications:
        toasts.add("Saved screenshot", 2.5)
        ...
        toasts.draw(screen)   # call every frame

    - No explicit update loop required (uses monotonic time)
    - Stacks at bottom-right by default
    """
    def __init__(self, font_name: str = "Consolas", font_size: int = 18) -> None:
        self._toasts: Deque[Toast] = deque(maxlen=16)
        self._font = pygame.font.SysFont(font_name, font_size) if pygame.get_init() else None
        self._pad = 8
        self._line = font_size + 8
        self._alpha = 185

    def add(self, text: str, duration: float = 2.25) -> None:
        self._toasts.append(Toast(text=text, created=time.monotonic(), duration=max(0.3, duration)))

    def draw(self, surface: pygame.Surface, *, bottomright: Tuple[int, int] | None = None) -> None:
        if not self._toasts:
            return
        if self._font is None:
            self._font = pygame.font.SysFont("Consolas", 18)

        now = time.monotonic()
        # Drop expired
        while self._toasts and now - self._toasts[0].created > self._toasts[0].duration:
            self._toasts.popleft()
        if not self._toasts:
            return

        W, H = surface.get_width(), surface.get_height()
        anchor = bottomright or (W - 10, H - 10)
        x_right, y = anchor

        # Draw from newest to oldest bottom-up
        items = list(self._toasts)[-5:][::-1]  # show last up to 5
        for t in items:
            age = now - t.created
            pct = max(0.0, min(1.0, 1.0 - (age / t.duration)))
            # slight fade out on the last 25%
            fade = 1.0 if pct > 0.25 else pct / 0.25

            text_surf = self._font.render(t.text, True, getattr(settings, "DEBUG_PANEL_FONT_COLOR", (240, 240, 240)))
            w = text_surf.get_width() + self._pad * 2
            h = text_surf.get_height() + self._pad * 2

            panel = pygame.Surface((w, h), pygame.SRCALPHA)
            panel.fill((20, 20, 20, int(self._alpha * fade)))
            panel.blit(text_surf, (self._pad, self._pad))

            rect = panel.get_rect()
            rect.bottomright = (x_right, y)
            surface.blit(panel, rect)
            y -= (h + 6)
