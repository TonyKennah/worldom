# tests/test_assets_basic.py
"""
Ultra-light tests so CI doesn't fail with 'no tests collected'.

We only touch the assets helper in a safe way that works headless.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
pygame.init()

from assets import resolve_path, load_image, load_frames_from_dir, load_sound  # noqa: E402


def test_resolve_path_missing_returns_none():
    assert resolve_path("this_file_should_not_exist.png") is None


def test_load_image_missing_returns_surface_placeholder():
    surf = load_image("also_not_here.png")
    assert isinstance(surf, pygame.Surface)
    assert surf.get_width() > 0 and surf.get_height() > 0


def test_load_frames_from_dir_missing_returns_empty_list():
    frames = load_frames_from_dir("folder_that_is_absent")
    assert isinstance(frames, list)
    assert frames == []


def test_load_sound_without_mixer_returns_none():
    # mixer not initialized in CI, function should gracefully return None
    snd = load_sound("nonexistent.wav")
    assert snd is None
