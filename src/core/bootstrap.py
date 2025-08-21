"""
Runtime bootstrap helpers: safe environment detection & pygame init.

Use from your main entry (before importing pygame-heavy modules):

    from src.core.bootstrap import configure_environment, init_pygame
    configure_environment()           # auto-detect CI/headless/Linux
    screen = init_pygame((1280, 720)) # returns display Surface (or None headless)
"""
from __future__ import annotations
import os
from typing import Optional, Tuple

def configure_environment(headless: Optional[bool] = None) -> None:
    """
    Configure SDL/Pygame environment for robustness across Linux/CI/headless:
    - Uses dummy video/audio when CI is detected or DISPLAY/WAYLAND_DISPLAY is absent.
    - Hides the pygame support prompt to keep CI logs clean.
    """
    ci = os.getenv("CI", "").lower() == "true"
    no_display = not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))

    if headless is None:
        headless = ci or no_display

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    # Reduce sdl lag on some Linux distros
    os.environ.setdefault("SDL_HINT_RENDER_DRIVER", "software")

def init_pygame(size: Tuple[int, int] = (320, 180), *, caption: str = "WorldDom", try_display: bool = True):
    """
    Initialize pygame safely. Returns display Surface if created, else None.
    """
    import pygame
    pygame.init()
    pygame.font.init()

    if not try_display:
        return None

    try:
        surf = pygame.display.set_mode(size)
        pygame.display.set_caption(caption)
        return surf
    except Exception:
        # Still allow headless runs with mixer/clock/timers when display fails
        return None
