# src/ui/debug_overlay.py
from __future__ import annotations

import time
from typing import Optional, Tuple

try:
    import psutil  # optional, for memory stats
except Exception:
    psutil = None

import pygame


class DebugOverlay:
    """
    Lightweight, opt‑in overlay:
      - FPS (smoothed)
      - dt (ms)
      - memory (if psutil installed)
    Toggle by controlling `enabled` from your debug key or config.
    """

    def __init__(self, *, font_name: str = "Consolas", font_size: int = 16) -> None:
        self.enabled: bool = True
        self._font = pygame.font.SysFont(font_name, font_size)
        self._samples = []
        self._last = time.perf_counter()

    def update(self) -> None:
        now = time.perf_counter()
        dt = now - self._last
        self._last = now
        self._samples.append(dt)
        if len(self._samples) > 60:
            self._samples.pop(0)

    def _smoothed_fps(self) -> float:
        if not self._samples:
            return 0.0
        avg = sum(self._samples) / len(self._samples)
        return 1.0 / avg if avg > 0 else 0.0

    def _proc_mem(self) -> Optional[str]:
        if not psutil:
            return None
        try:
            p = psutil.Process()
            rss = p.memory_info().rss / (1024 * 1024)
            return f"{rss:.1f} MiB"
        except Exception:
            return None

    def draw(self, surface: pygame.Surface, *, pos: Tuple[int, int] = (10, 10)) -> None:
        if not self.enabled:
            return
        fps = self._smoothed_fps()
        mem = self._proc_mem()
        dt_ms = (self._samples[-1] * 1000.0) if self._samples else 0.0
        lines = [f"FPS: {fps:5.1f}", f"dt: {dt_ms:4.1f} ms"]
        if mem:
            lines.append(f"mem: {mem}")
        text = " | ".join(lines)

        txt = self._font.render(text, True, (255, 255, 255))
        bg = pygame.Surface((txt.get_width() + 8, txt.get_height() + 6), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        surface.blit(bg, pos)
        surface.blit(txt, (pos[0] + 4, pos[1] + 3))
