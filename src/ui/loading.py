# src/ui/loading.py
from __future__ import annotations

import time
from typing import Optional, Iterable, Callable

import pygame

class LoadingBar:
    """
    Minimal loading overlay that keeps the window responsive.
    Use it while warming libraries or preloading assets.

    Example:
        bar = LoadingBar(screen, "Loading...")
        for i in range(n):
            heavy_step()
            bar.draw(i/(n-1), f"Step {i+1}/{n}")
    """
    def __init__(self, screen: "pygame.Surface", title: str = "Loading..."):
        self.screen = screen
        self.title = title
        self._font = pygame.font.SysFont("Arial", 18)
        self._last_flip = 0.0

    def _pump(self) -> None:
        # Keep OS happy
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                raise SystemExit

    def draw(self, progress: float, subtitle: Optional[str] = None) -> None:
        self._pump()
        W, H = self.screen.get_size()
        self.screen.fill((18, 22, 28))

        # Title
        title_surf = self._font.render(self.title, True, (220, 220, 235))
        self.screen.blit(title_surf, (20, 20))

        # Bar
        bar_w, bar_h = int(W * 0.6), 24
        bar_x, bar_y = (W - bar_w) // 2, (H - bar_h) // 2
        pygame.draw.rect(self.screen, (60, 65, 75), (bar_x, bar_y, bar_w, bar_h), border_radius=6)

        p = max(0.0, min(1.0, progress))
        fill_w = int(bar_w * p)
        pygame.draw.rect(self.screen, (88, 186, 255), (bar_x, bar_y, fill_w, bar_h), border_radius=6)

        # Percent text
        pct = self._font.render(f"{int(p*100)}%", True, (20, 20, 25))
        pct_rect = pct.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h // 2))
        self.screen.blit(pct, pct_rect)

        if subtitle:
            sub = self._font.render(subtitle, True, (220, 220, 235))
            self.screen.blit(sub, (bar_x, bar_y + bar_h + 12))

        # Throttle flips to avoid saturating the compositor
        now = time.time()
        if now - self._last_flip > 1/120:
            pygame.display.flip()
            self._last_flip = now

def run_steps_with_loading(
    screen: "pygame.Surface",
    title: str,
    steps: Iterable[Callable[[], None]],
    *,
    subtitle_format: Optional[str] = "Step {i}/{n}",
) -> None:
    """
    Utility: run a list of callables while showing progress.
    """
    bar = LoadingBar(screen, title)
    steps = list(steps)
    n = max(1, len(steps))
    for i, step in enumerate(steps, start=1):
        step()
        sub = subtitle_format.format(i=i, n=n) if subtitle_format else None
        bar.draw(i / n, sub)
