# tests/conftest.py
from __future__ import annotations
import os
import sys
from pathlib import Path
import pytest

# Ensure repo root is importable as a package root (so `import src...` works on CI)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Headless Pygame setup (safe if pygame isn't used in a given test)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

@pytest.fixture(scope="session", autouse=True)
def _init_pygame():
    try:
        import pygame
        pygame.init()
        # create a tiny, hidden surface to allow convert_alpha() paths to succeed
        pygame.display.set_mode((1, 1))
        yield
    finally:
        try:
            import pygame
            pygame.quit()
        except Exception:
            pass
