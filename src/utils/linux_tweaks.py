# src/utils/linux_tweaks.py
"""
Linux‑specific performance tweaks for Pygame + scientific stack.

Call `early_env_setup()` **before** `pygame.init()` to:
  * Hint SDL to use accelerated renderer with vsync & compositor bypass
  * Prefer X11 driver on Wayland sessions if SDL is slow
  * Limit BLAS/OMP thread counts to avoid CPU thrash
  * Force matplotlib Agg backend + local config dir

Use `recommended_display_flags()` when creating the window to add
SCALED + DOUBLEBUF on Linux (nice performance win with SDL2 paths).
"""
from __future__ import annotations
import os
import sys
import tempfile
from typing import Final

_LINUX: Final[bool] = sys.platform.startswith("linux")


def is_linux() -> bool:
    """Return True if current platform is Linux."""
    return _LINUX


def early_env_setup(prefer_x11: bool = True) -> None:
    """
    Set environment hints; safe no‑op on non‑Linux.
    Must be called before importing/initializing pygame.display.
    """
    if not _LINUX:
        return

    # SDL renderer/vsync hints
    os.environ.setdefault("SDL_HINT_FRAMEBUFFER_ACCELERATION", "1")
    os.environ.setdefault("SDL_HINT_RENDER_DRIVER", "opengl")  # often fastest on Linux
    os.environ.setdefault("SDL_RENDER_VSYNC", "1")
    os.environ.setdefault("SDL_HINT_RENDER_VSYNC", "1")
    os.environ.setdefault("SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR", "1")

    # Avoid Wayland driver if it performs poorly on some desktops
    if prefer_x11 and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        os.environ.setdefault("SDL_VIDEODRIVER", "x11")

    # Limit threaded math libs to reduce CPU oversubscription when using numpy/matplotlib
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(var, "1")

    # Matplotlib config in a fast, writable location + Agg backend
    os.environ.setdefault("MPLBACKEND", "Agg")
    mpl_cfg = os.path.join(tempfile.gettempdir(), "worlddom-mpl")
    try:
        os.makedirs(mpl_cfg, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", mpl_cfg)
    except Exception:
        # Non‑fatal
        pass


def recommended_display_flags(base_flags: int = 0) -> int:
    """
    Return extra flags that tend to perform well on Linux:
      * SCALED (hardware scaling path in SDL2)
      * DOUBLEBUF (reduce tearing with SW surfaces)
    """
    extra = 0
    if _LINUX:
        # Import pygame locally so early_env_setup can be called before pygame import
        import pygame
        extra |= pygame.SCALED
        extra |= pygame.DOUBLEBUF
    return base_flags | extra
