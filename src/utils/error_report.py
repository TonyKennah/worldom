# src/utils/error_report.py
from __future__ import annotations

"""
Minimal crash capture:
- write logs/crash_YYYYMMDD_HHMMSS.txt
- optional in-game overlay if pygame display exists
Safe to import early in your entrypoint (before starting game loop).
"""

import os
import sys
import time
import traceback
from typing import Optional


def _log_dir() -> str:
    d = os.path.join(os.getcwd(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def _write_crash_file(tb: str) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_log_dir(), f"crash_{stamp}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(tb)
    return path


def install_excepthook(show_overlay: bool = True) -> None:
    def _hook(exc_type, exc, tb):
        full = "".join(traceback.format_exception(exc_type, exc, tb))
        path = _write_crash_file(full)
        print(f"\n[Crash] Unhandled exception written to {path}\n", file=sys.stderr)
        if show_overlay:
            try:
                import pygame
                if pygame.get_init() and pygame.display.get_surface() is not None:
                    _show_overlay(full)
            except Exception:
                pass
        # Re-raise so debuggers/CI still fail properly
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def _show_overlay(text: str) -> None:
    import pygame

    screen = pygame.display.get_surface()
    if not screen:
        return
    w, h = screen.get_size()
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill((10, 10, 10, 220))

    font = pygame.font.SysFont("Consolas", 16)
    lines = text.splitlines()[-24:]
    y = 20
    for ln in lines:
        s = font.render(ln[:120], True, (255, 160, 160))
        screen.blit(s, (20, y))
        y += 18

    pygame.display.flip()
    # wait briefly so users can see the overlay
    start = time.time()
    while time.time() - start < 4.0:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return
        pygame.time.delay(25)
