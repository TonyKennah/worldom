# src/utils/mixer_safe.py
from __future__ import annotations

import os
from typing import Tuple

def init_mixer_safe(
    *,
    frequency: int = 44100,
    size: int = -16,
    channels: int = 2,
    buffer: int = 512,
) -> Tuple[bool, str]:
    """
    Initialize pygame.mixer with sensible fallbacks for CI/headless/Linux.

    Returns:
        (ok, message)
    """
    import pygame

    # Avoid spam
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    # Try default device first
    try:
        if not pygame.get_init():
            pygame.init()
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=frequency, size=size, channels=channels, buffer=buffer)
        return True, "mixer initialized (default)"
    except Exception as e1:
        # Fallback to dummy driver
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=frequency, size=size, channels=channels, buffer=buffer)
            return True, "mixer initialized (dummy)"
        except Exception as e2:
            return False, f"mixer failed: {e1!r}; dummy failed: {e2!r}"
