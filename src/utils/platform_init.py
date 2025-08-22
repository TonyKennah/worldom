# src/utils/platform_init.py
from __future__ import annotations

import os
import sys
import platform
import pygame
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import pygame

def some_function(..., flags: int = 0) -> Tuple["pygame.Surface", "pygame.time.Clock"]:
    ...

def apply_platform_tweaks(*, headless: bool = False) -> None:
    """
    Set conservative SDL/Pygame environment knobs before importing pygame.
    Safe to call multiple times.
    """
    # Hide the noisy pygame greeting
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    # Better scaling for blits
    os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "1")

    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        return

    sysname = platform.system().lower()

    # Audio: prefer 'pipewire'/'pulseaudio' on Linux, 'coreaudio' on macOS, WASAPI on Windows
    if sysname == "linux":
        # Wayland/X11 dance (prefer X11 for pygame’s stability unless Wayland works)
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if "wayland" in session:
            # Let SDL decide; only override if we detect trouble later
            os.environ.setdefault("SDL_VIDEODRIVER", "wayland")
        else:
            os.environ.setdefault("SDL_VIDEODRIVER", "x11")
        # Audio fallback priority
        os.environ.setdefault("SDL_AUDIODRIVER", "pipewire")
        # If PipeWire is unavailable, SDL will fall back to Pulse/ALSA automatically.

    elif sysname == "darwin":
        os.environ.setdefault("SDL_VIDEODRIVER", "cocoa")
        os.environ.setdefault("SDL_AUDIODRIVER", "coreaudio")
    elif sysname == "windows":
        # WASAPI is generally best on modern Windows
        os.environ.setdefault("SDL_AUDIODRIVER", "wasapi")

def safe_pygame_init(width: int, height: int, *, caption: str = "WorldDom",
                     flags: int = 0) -> Tuple["pygame.Surface", "pygame.time.Clock"]:
    """
    Initialize pygame with robust defaults and return (screen, clock).
    """
    import pygame  # local import after env is set

    # Try hardware double buffer; fall back gracefully if window creation fails.
    default_flags = pygame.DOUBLEBUF
    try:
        pygame.init()
        screen = pygame.display.set_mode((width, height), flags or default_flags)
    except Exception:
        # Fallback for headless/CI environments
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.display.quit()
        pygame.display.init()
        screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(caption)
    clock = pygame.time.Clock()
    return screen, clock

def clamp_dt(dt: float, *, min_dt: float = 1/400, max_dt: float = 1/30) -> float:
    """
    Clamp a delta-time to avoid instability from spikes or tiny steps.
    Defaults are conservative and engine-agnostic.
    """
    return max(min_dt, min(max_dt, dt))

def some_function(..., flags: int = 0) -> Tuple[pygame.Surface, pygame.time.Clock]:
