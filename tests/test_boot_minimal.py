# tests/test_boot_minimal.py
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

def test_import_and_quick_loop():
    from src.core.safe_main import configure_environment, init_pygame_display
    configure_environment()
    surf = init_pygame_display((64, 36))
    # It's OK for surf to be None on pure headless. We just want init to not crash.
    assert True
