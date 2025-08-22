# src/utils/pygame_bootstrap.py
from __future__ import annotations

import os
import pygame


def _maybe_set_linux_env() -> None:
    """
    Small Linux stability tweaks that are safe elsewhere:
    - keep compositor active (prevents tearing/flicker on some WMs)
    - prefer X11 if both Wayland & X are present (SDL behaves better in CI)
    """
    if os.name != "posix":
        return
    os.environ.setdefault("SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR", "0")
    # If Wayland is present but CI/headless is requested, force dummy instead.
    if os.environ.get("WORLDDOM_HEADLESS") == "1" or os.environ.get("CI") == "true":
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def init_pygame_display(size: tuple[int, int] = (1, 1), *, headless: bool | None = None) -> pygame.Surface:
    """
    Robust pygame bootstrap:
      - Configures 'dummy' drivers in CI/headless runs (no window/audio device required).
      - Ensures display is initialized before any convert_alpha / font usage.
      - Creates a tiny surface if no window was created yet.

    Returns:
        A pygame display surface (even in headless mode).
    """
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    _maybe_set_linux_env()

    if headless is None:
        headless = (
            os.environ.get("WORLDDOM_HEADLESS") == "1"
            or os.environ.get("CI") == "true"
            or os.environ.get("SDL_VIDEODRIVER") == "dummy"
        )

    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    # Pygame init (idempotent)
    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()

    # Ensure at least a tiny surface exists so convert()/convert_alpha() is safe
    surf = pygame.display.get_surface()
    if surf is None:
        try:
            surf = pygame.display.set_mode(size)
        except pygame.error:
            # Fallback hard to dummy in case a system driver fails
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            pygame.display.quit()
            pygame.display.init()
            surf = pygame.display.set_mode(size)

    # Fonts are frequently used during imports; make sure they're up
    if not pygame.font.get_init():
        pygame.font.init()

    return surf
