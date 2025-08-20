# c:/prj/WorldDom/src/utils/screenshot.py
from __future__ import annotations

import os
import time
import pygame


def save_screenshot(surface: pygame.Surface, base_dir: str = "image/screenshots", prefix: str = "screenshot") -> str:
    """
    Saves the given surface as a PNG (uses timestamp).
    Returns absolute file path.
    """
    os.makedirs(base_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    ms = int((time.time() % 1) * 1000)
    name = f"{prefix}-{ts}-{ms:03d}.png"
    path = os.path.join(base_dir, name)
    pygame.image.save(surface, path)
    return os.path.abspath(path)
