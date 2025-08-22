# c:/prj/WorldDom/src/core/bootstrap.py
from __future__ import annotations

import os
import sys
import platform
import ctypes
import time
from typing import Optional

# pygame is imported lazily so this module can be used by tools
_PYGAME_INITED = False


def _set_windows_dpi_awareness() -> None:
    if platform.system() != "Windows":
        return
    try:
        # Per-monitor V2 when available, else system DPI awareness
        PROCESS_PER_MONITOR_DPI_AWARE = 2
        PROCESS_SYSTEM_DPI_AWARE = 1
        shcore = ctypes.windll.shcore
        user32 = ctypes.windll.user32
        # Try the best first; fall back if needed
        try:
            shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
        except Exception:
            shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)
        user32.SetProcessDPIAware()
    except Exception:
        # Non-fatal: just run with default DPI scaling
        pass


def _choose_video_driver(headless: bool) -> None:
    """
    Avoid common Linux CI / headless crashes and macOS Big Sur+ quirks by
    explicitly selecting a driver when feasible.
    """
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        return

    if platform.system() == "Linux":
        # Prefer wayland if available, else x11; let SDL fall back as needed
        # Do not override if user already set it.
        os.environ.setdefault("SDL_VIDEODRIVER", "wayland,x11")
    elif platform.system() == "Darwin":
        # macOS: leave default; SDL picks Cocoa
        pass
    else:
        # Windows: default is fine
        pass


def _choose_audio_driver() -> None:
    """
    Pick an audio backend that tends to work on CI and desktop. If mixer init
    fails at runtime, we gracefully continue without sound.
    """
    if "SDL_AUDIODRIVER" in os.environ:
        return
    if platform.system() == "Linux":
        # pulseaudio preferred, then alsa, then dsp
        os.environ.setdefault("SDL_AUDIODRIVER", "pulseaudio,alsa,dsp")
    # macOS / Windows: default backend is fine


def configure_env(*, headless: bool = False, want_high_fps_timer: bool = True) -> None:
    """
    Set environment variables and process flags that improve stability and latency.
    Call this **before** importing pygame.
    """
    # Hide the noisy "Hello from the pygame community" line in CI
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    if want_high_fps_timer and platform.system() == "Windows":
        # Reduce timer coalescing on Win10+ (helps steady frame pacing)
        os.environ.setdefault("SDL_HINT_TIMER_RESOLUTION", "1")

    _choose_video_driver(headless=headless)
    _choose_audio_driver()

    if platform.system() == "Linux":
        # Reduce tearing on some drivers when using GL + vsync
        os.environ.setdefault("SDL_RENDER_DRIVER", "opengl")
        # Avoid slow software fallbacks on some distros
        os.environ.setdefault("SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR", "0")

    _set_windows_dpi_awareness()


def init_pygame(
    *,
    width: int = 1280,
    height: int = 720,
    title: str = "WorldDom",
    headless: bool = False,
    vsync: bool = True,
    allow_resize: bool = True,
) -> "tuple[object, object, object]":
    """
    Robust pygame initialization.
    Returns: (pygame, screen_surface, clock)
    """
    global _PYGAME_INITED

    # Must configure env before importing pygame
    configure_env(headless=headless)

    import pygame  # local import after env is set

    if _PYGAME_INITED:
        return pygame, pygame.display.get_surface(), pygame.time.Clock()

    flags = 0
    if allow_resize and not headless:
        flags |= pygame.RESIZABLE
    if vsync and not headless:
        flags |= pygame.SCALED  # gives a vsync-like swap with scaling

    pygame.init()

    if headless:
        screen = pygame.display.set_mode((width, height))
    else:
        screen = pygame.display.set_mode((width, height), flags)
        try:
            pygame.display.set_caption(title)
        except Exception:
            pass

    # Audio is optional; do not hard fail
    _safe_init_audio()

    clock = pygame.time.Clock()
    _PYGAME_INITED = True
    return pygame, screen, clock


def _safe_init_audio() -> None:
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    except Exception:
        # No audio device / headless CI is fine
        pass


def pump_events(pygame_mod, *, quit_keys: Optional[set[int]] = None) -> bool:
    """
    Process events once; return False if the user requested exit.
    """
    quit_keys = quit_keys or set()
    for ev in pygame_mod.event.get():
        if ev.type == pygame_mod.QUIT:
            return False
        if ev.type == pygame_mod.KEYDOWN and ev.key in quit_keys:
            return False
    return True


def sleep_ms(ms: float) -> None:
    # Small, portable sleep with sub-ms tolerance for smoother loaders
    time.sleep(max(0.0, ms / 1000.0))
