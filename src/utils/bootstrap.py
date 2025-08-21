# src/utils/bootstrap.py
from __future__ import annotations

"""
Safe, cross-platform Pygame bootstrap:
 - Applies Linux/Wayland/X11 tweaks (XDG_RUNTIME_DIR, SDL_* drivers, DPI)
 - Initializes display & mixer robustly (with fallbacks)
 - Exposes a BootConfig and BootContext you can use from any entrypoint
 - No hard dependency on your settings module (falls back to sane defaults)
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import os
import sys
import platform
import time

import pygame


@dataclass
class BootConfig:
    width: int = 1280
    height: int = 720
    caption: str = "WorldDom"
    icon_path: Optional[str] = None
    resizable: bool = True
    vsync: bool = True
    use_hardware: bool = True
    doublebuf: bool = True
    allow_highdpi: bool = True
    target_fps: int = 60
    init_mixer: bool = True
    mixer_freq: int = 44100
    mixer_size: int = -16
    mixer_channels: int = 2
    mixer_buffer: int = 512
    headless: bool = False  # When True, uses SDL_VIDEODRIVER=dummy


@dataclass
class BootContext:
    screen: pygame.Surface
    clock: pygame.time.Clock
    config: BootConfig


def _apply_env_tweaks(cfg: BootConfig) -> None:
    # Silence pygame banner
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    # Headless option for CI / servers
    if cfg.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    # Linux: fix Wayland/X11 & missing runtime dir edge cases
    if sys.platform.startswith("linux"):
        # Ensure XDG_RUNTIME_DIR exists for some SDL backends
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if not xdg:
            tmp = f"/tmp/xdg-runtime-{os.getuid()}"
            os.makedirs(tmp, exist_ok=True)
            os.environ["XDG_RUNTIME_DIR"] = tmp

        # Prefer Wayland if available; fallback to x11 (some drivers misreport)
        sdl_driver = os.environ.get("SDL_VIDEODRIVER", "")
        if not sdl_driver:
            if os.environ.get("WAYLAND_DISPLAY"):
                os.environ["SDL_VIDEODRIVER"] = "wayland"
            else:
                os.environ["SDL_VIDEODRIVER"] = "x11"

        # Audio fallback ordering
        if not os.environ.get("SDL_AUDIODRIVER"):
            for drv in ("pulseaudio", "alsa", "jack", "pipewire", "dsp", "dummy"):
                os.environ.setdefault("SDL_AUDIODRIVER", drv)

    # HiDPI hint (macOS + some Linux DEs)
    if cfg.allow_highdpi:
        os.environ.setdefault("SDL_VIDEO_ALLOW_SCREENSAVER", "1")

    # Safer threading/SDL events on Windows in some terminals
    if os.name == "nt":
        os.environ.setdefault("SDL_AUDIODRIVER", "directsound")


def _flags_from_config(cfg: BootConfig) -> int:
    flags = 0
    if cfg.resizable:
        flags |= pygame.RESIZABLE
    if cfg.doublebuf:
        flags |= pygame.DOUBLEBUF
    if cfg.use_hardware:
        flags |= pygame.HWSURFACE
    # VSYNC on modern SDL2 requires DOUBLEBUF and an OpenGL/accelerated backend;
    # for plain 2D surfaces, pygame 2 still forwards vsync where possible.
    return flags


def _init_pygame_display(cfg: BootConfig) -> pygame.Surface:
    flags = _flags_from_config(cfg)
    # If vsync is True but unsupported, pygame will ignore it harmlessly
    screen = pygame.display.set_mode((cfg.width, cfg.height), flags, vsync=1 if cfg.vsync else 0)
    pygame.display.set_caption(cfg.caption)
    return screen


def _init_mixer_safe(cfg: BootConfig) -> None:
    if not cfg.init_mixer:
        return
    try:
        pygame.mixer.pre_init(cfg.mixer_freq, cfg.mixer_size, cfg.mixer_channels, cfg.mixer_buffer)
        pygame.mixer.init()
    except Exception:
        # Fallback: disable audio but keep running
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        try:
            pygame.mixer.init()
        except Exception:
            pass


def bootstrap(config: Optional[BootConfig] = None) -> BootContext:
    cfg = config or BootConfig()

    # Merge defaults with settings if present (no hard dependency)
    try:
        from src.utils import settings  # type: ignore

        cfg.width = int(getattr(settings, "SCREEN_WIDTH", cfg.width))
        cfg.height = int(getattr(settings, "SCREEN_HEIGHT", cfg.height))
        cfg.caption = str(getattr(settings, "WINDOW_TITLE", cfg.caption))
        cfg.vsync = bool(getattr(settings, "VSYNC", cfg.vsync))
        cfg.target_fps = int(getattr(settings, "TARGET_FPS", cfg.target_fps))
    except Exception:
        pass

    _apply_env_tweaks(cfg)
    pygame.init()
    _init_mixer_safe(cfg)

    screen = _init_pygame_display(cfg)
    clock = pygame.time.Clock()
    try:
        pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN,
                                  pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.VIDEORESIZE])
    except Exception:
        pass

    return BootContext(screen=screen, clock=clock, config=cfg)
