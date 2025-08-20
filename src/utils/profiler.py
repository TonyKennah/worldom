# c:/prj/WorldDom/src/utils/profiler.py
from __future__ import annotations

import time
from contextlib import contextmanager
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

import pygame

try:
    import src.utils.settings as settings
except Exception:
    # Fallback colors if settings module isn't available at import time
    class _Fallback:
        DEBUG_PANEL_FONT_COLOR = (235, 235, 245)
        DEBUG_PANEL_BG_COLOR = (32, 32, 48)
    settings = _Fallback()  # type: ignore


class Profiler:
    """
    Minimal in-game profiler overlay. Use:

        self.profiler = Profiler()
        self.profiler.frame_start()
        with self.profiler.section("update"): ...
        with self.profiler.section("draw"): ...
        self.profiler.frame_end()
        self.profiler.draw(self.screen)

    - Tracks per-section recent timings (rolling average)
    - Smooth FPS readout
    - Zero dependencies beyond pygame
    """

    def __init__(self, history: int = 180, font_name: str = "Consolas", font_size: int = 16) -> None:
        self.history = max(30, int(history))
        self.sections: Dict[str, Deque[float]] = {}
        self.current_stack: List[Tuple[str, float]] = []

        self._frame_start_t: float = 0.0
        self._last_frame_dt: float = 0.0
        self._fps_samples: Deque[float] = deque(maxlen=self.history)

        # Draw config
        self._font = pygame.font.SysFont(font_name, font_size) if pygame.get_init() else None
        self._pad_x = 8
        self._pad_y = 6
        self._line_h = font_size + 3
        self._alpha = 170  # semi-transparent background

        # Toggle
        self.enabled: bool = True

    # ------------------------------------------------------------------ #
    # Frame boundaries & sections
    # ------------------------------------------------------------------ #
    def frame_start(self) -> None:
        self._frame_start_t = time.perf_counter()

    def frame_end(self) -> None:
        now = time.perf_counter()
        self._last_frame_dt = max(1e-8, now - self._frame_start_t)
        self._fps_samples.append(1.0 / self._last_frame_dt)

    @contextmanager
    def section(self, name: str):
        t0 = time.perf_counter()
        self.current_stack.append((name, t0))
        try:
            yield
        finally:
            _, start = self.current_stack.pop()
            dt = max(0.0, time.perf_counter() - start)
            buf = self.sections.get(name)
            if buf is None:
                buf = deque(maxlen=self.history)
                self.sections[name] = buf
            buf.append(dt)

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def draw(self, surface: pygame.Surface, *, topleft: Tuple[int, int] = (10, 10)) -> None:
        if not self.enabled:
            return

        # Lazy font init if created before pygame.init()
        if self._font is None:
            self._font = pygame.font.SysFont("Consolas", 16)

        # Compose lines
        lines: List[str] = []
        fps_avg = sum(self._fps_samples) / len(self._fps_samples) if self._fps_samples else 0.0
        ms = self._last_frame_dt * 1000.0
        lines.append(f"FPS: {fps_avg:5.1f}   Frame: {ms:5.1f} ms")

        # Show per-section averages (sorted by time desc)
        sec_stats: List[Tuple[str, float, float]] = []
        for k, v in self.sections.items():
            if not v:
                continue
            avg = (sum(v) / len(v)) * 1000.0
            last = (v[-1]) * 1000.0
            sec_stats.append((k, avg, last))
        sec_stats.sort(key=lambda t: t[1], reverse=True)
        for name, avg, last in sec_stats:
            lines.append(f"{name:>10}:  avg {avg:5.1f} ms   last {last:5.1f} ms")

        # Measure panel rect
        if not lines:
            return
        surf = surface
        font = self._font
        assert font is not None

        text_surfs = [font.render(L, True, getattr(settings, "DEBUG_PANEL_FONT_COLOR", (235, 235, 245))) for L in lines]
        w = max(ts.get_width() for ts in text_surfs) + self._pad_x * 2
        h = len(text_surfs) * self._line_h + self._pad_y * 2

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        bg_col = getattr(settings, "DEBUG_PANEL_BG_COLOR", (32, 32, 48))
        panel.fill((*bg_col[:3], self._alpha))

        # Blit lines
        x = self._pad_x
        y = self._pad_y
        for ts in text_surfs:
            panel.blit(ts, (x, y))
            y += self._line_h

        surf.blit(panel, topleft)
