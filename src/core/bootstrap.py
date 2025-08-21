# c:/prj/WorldDom/src/core/bootstrap.py
"""
Safe pygame/bootstrap helpers for WorldDom.
- Initializes pygame with graceful fallbacks (audio/video)
- Creates a robust window surface
- Provides a simple long-frame watchdog
"""
from __future__ import annotations
import os
import sys
import time
import platform
import pygame

DEFAULT_CAPTION = "WorldDom"
DEFAULT_SIZE = (1280, 720)

def safe_pygame_init(*, headless: bool | None = None) -> None:
    """
    Initialize pygame defensively.
    - headless=True uses SDL_VIDEODRIVER=dummy (CI / servers)
    - audio fallback if mixer init fails
    """
    # Headless if explicitly requested or typical CI env
    if headless is None:
        headless = os.environ.get("CI") == "true" or os.environ.get("SDL_VIDEODRIVER") == "dummy"
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    # Some Linux boxes prefer this for scaling without tearing
    os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "1")  # linear
    # Less CPU usage for idle windows
    os.environ.setdefault("SDL_HINT_VIDEO_ALLOW_SCREENSAVER", "1")

    # Try audio early but tolerate failures (no hard crash)
    try:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    except Exception:
        pass

    pygame.init()

    # Attempt mixer; if it fails, disable sound usage gracefully
    _mixer_ok = True
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
    except Exception:
        _mixer_ok = False
    # Expose a flag apps can read
    os.environ["WORLDDOM_AUDIO_AVAILABLE"] = "1" if _mixer_ok else "0"

def create_window(
    size: tuple[int, int] = DEFAULT_SIZE,
    caption: str = DEFAULT_CAPTION,
    *,
    fullscreen: bool = False,
) -> tuple[pygame.Surface, pygame.time.Clock]:
    """
    Create a window surface with sensible flags and a clock.
    - DOUBLEBUF + SCALED reduces tearing
    - RESIZABLE to play nice with multi‑window setups
    """
    flags = pygame.DOUBLEBUF | pygame.SCALED | pygame.RESIZABLE
    if fullscreen:
        flags |= pygame.FULLSCREEN

    try:
        screen = pygame.display.set_mode(size, flags)
    except pygame.error as e:
        # Fallback if driver can’t create a scaled/resizable window
        screen = pygame.display.set_mode(size)
        print("[bootstrap] Warning: scaled/resizable window creation failed:", e)

    pygame.display.set_caption(caption)
    clock = pygame.time.Clock()
    return screen, clock

class LongFrameWatchdog:
    """
    Logs warnings if frames exceed a threshold (helps diagnose slowdowns/hangs).
    """
    def __init__(self, warn_ms: float = 120.0, severe_ms: float = 400.0) -> None:
        self.warn_ms = float(warn_ms)
        self.severe_ms = float(severe_ms)
        self._last = time.perf_counter()

    def tick(self) -> float:
        now = time.perf_counter()
        dt = (now - self._last) * 1000.0
        self._last = now
        if dt > self.severe_ms:
            print(f"[watchdog] SEVERE frame time: {dt:.1f} ms")
        elif dt > self.warn_ms:
            print(f"[watchdog] Slow frame: {dt:.1f} ms")
        return dt

def system_summary() -> str:
    """Human‑friendly environment line for crash logs."""
    pieces = [
        f"Python {sys.version.split()[0]}",
        f"Platform {platform.platform()}",
        f"Pygame {getattr(pygame, 'version', getattr(pygame, '__version__', 'unknown'))}",
        f"Audio={'on' if os.environ.get('WORLDDOM_AUDIO_AVAILABLE')=='1' else 'off'}",
        f"SDL_VIDEODRIVER={os.environ.get('SDL_VIDEODRIVER','(default)')}",
    ]
    return " | ".join(pieces)
