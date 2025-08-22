# tests/test_imports_and_audio.py
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

def test_import_sanity_and_mixer():
    from src.utils.project_sanity import apply
    from src.utils.mixer_safe import init_mixer_safe
    apply()  # should not raise
    ok, _ = init_mixer_safe()
    assert isinstance(ok, bool)
