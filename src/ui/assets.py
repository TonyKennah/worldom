# src/ui/assets.py
# Lightweight helpers to locate and load assets in common project layouts.

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Dict
import os
import re

import pygame

# --------------------------------------------------------------------------------------
# Configuration / search strategy
# --------------------------------------------------------------------------------------

# Allow the game to push extra search roots at runtime (e.g., mod folders)
_EXTRA_ROOTS: List[Path] = []

# Environment variables that, if set, are used as additional roots
_ENV_VARS: Tuple[str, ...] = ("WORLDDOM_ASSETS", "WORLD_DOM_ASSETS", "ASSETS_DIR")

# Common subdir names used by many repos
_DEFAULT_IMAGE_SUBDIRS: Tuple[str, ...] = ("assets", "image", "images", "img", "gfx")
_DEFAULT_AUDIO_SUBDIRS: Tuple[str, ...] = ("assets/audio", "assets/sound", "audio", "sound", "sfx")
_DEFAULT_FONT_SUBDIRS: Tuple[str, ...] = ("assets/fonts", "assets/font", "fonts")


# --------------------------------------------------------------------------------------
# Public API: search roots control
# --------------------------------------------------------------------------------------

def add_search_root(path: str | os.PathLike) -> None:
    """Register an additional root directory to scan for assets."""
    p = Path(path).expanduser().resolve()
    if p.exists() and p.is_dir() and p not in _EXTRA_ROOTS:
        _EXTRA_ROOTS.append(p)


def set_search_roots(paths: Iterable[str | os.PathLike]) -> None:
    """Replace the extra roots list with a specific set of paths."""
    _EXTRA_ROOTS.clear()
    for p in paths:
        add_search_root(p)


# --------------------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------------------

def _natural_key(s: str):
    """Natural sort key: frame_2 before frame_10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def _candidate_roots() -> List[Path]:
    """
    Try a few likely roots:
      - directory of this file
      - parent dirs (up to 3 levels)
      - current working directory
      - env vars (WORLDDOM_ASSETS, WORLD_DOM_ASSETS, ASSETS_DIR)
      - any extra roots registered via add_search_root()
    """
    roots: List[Path] = []

    here = Path(__file__).expanduser().resolve().parent
    roots.append(here)

    cur = here
    for _ in range(3):
        cur = cur.parent
        roots.append(cur)

    roots.append(Path(os.getcwd()).expanduser().resolve())

    for var in _ENV_VARS:
        val = os.getenv(var)
        if val:
            p = Path(val).expanduser().resolve()
            if p.exists():
                roots.append(p)

    # Allow runtime-injected roots (mods, DLC, etc.)
    roots.extend(_EXTRA_ROOTS)

    # Deduplicate while preserving order
    seen: set[Path] = set()
    out: List[Path] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _split_subdirs(subdirs: Iterable[str]) -> List[Path]:
    """Allow subdirs like 'assets/audio' as well as simple names."""
    return [Path(sd) for sd in subdirs]


def _case_insensitive_match(dirpath: Path, target: str) -> Optional[Path]:
    """
    If exact path doesn't exist, try to match filename case-insensitively
    within dirpath (works for common Windows/macOS dev setups).
    """
    if not dirpath.exists() or not dirpath.is_dir():
        return None
    lower = target.lower()
    parent = dirpath
    for entry in parent.iterdir():
        if entry.name.lower() == lower:
            return entry
    return None


def _can_convert_alpha() -> bool:
    """Only call convert/convert_alpha if a display surface exists."""
    try:
        return pygame.get_init() and pygame.display.get_surface() is not None
    except Exception:
        return False


# --------------------------------------------------------------------------------------
# Path resolution
# --------------------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def resolve_path(
    name: str,
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS,
    *,
    extensions: Optional[Sequence[str]] = None,
    allow_case_insensitive: bool = True,
) -> Optional[str]:
    """
    Return the first existing absolute path for `name` within any of the given
    `subdirs` under likely project roots. If `name` has no extension and
    `extensions` are provided, try those as fallbacks.

    Args:
        name: file name or relative path (e.g., "ui/cursor.png")
        subdirs: tuples of subdirectories to search under each root
        extensions: e.g., (".png", ".jpg") if you want automatic suffix tries
        allow_case_insensitive: also try case-insensitive filename match

    Returns:
        Absolute path as string, or None if not found.
    """
    target = Path(name)
    if target.is_absolute() and target.exists():
        return str(target)

    # Try CWD-relative directly
    if target.exists():
        return str(target.resolve())

    # Try configured roots/subdirs
    subpaths = _split_subdirs(subdirs)
    for root in _candidate_roots():
        for sd in subpaths:
            candidate_dir = (root / sd).resolve()
            candidate = candidate_dir / target

            # direct hit
            if candidate.exists():
                return str(candidate)

            # case-insensitive fallback
            if allow_case_insensitive:
                alt = _case_insensitive_match(candidate_dir / target.parent, target.name)
                if alt and alt.exists():
                    return str(alt.resolve())

            # try with extensions if none provided in name
            if extensions and not target.suffix:
                for ext in extensions:
                    c2 = candidate.with_suffix(ext)
                    if c2.exists():
                        return str(c2.resolve())

    return None


def find_all_paths(
    name: str,
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS,
    *,
    extensions: Optional[Sequence[str]] = None,
    allow_case_insensitive: bool = True,
) -> List[str]:
    """Return every matching absolute path across all candidate roots."""
    found: List[str] = []
    target = Path(name)
    subpaths = _split_subdirs(subdirs)

    for root in _candidate_roots():
        for sd in subpaths:
            candidate_dir = (root / sd).resolve()
            candidate = candidate_dir / target

            if candidate.exists():
                found.append(str(candidate))
                continue

            if allow_case_insensitive:
                alt = _case_insensitive_match(candidate_dir / target.parent, target.name)
                if alt and alt.exists():
                    found.append(str(alt.resolve()))
                    continue

            if extensions and not target.suffix:
                for ext in extensions:
                    c2 = candidate.with_suffix(ext)
                    if c2.exists():
                        found.append(str(c2.resolve()))

    # Deduplicate
    seen: set[str] = set()
    out: List[str] = []
    for p in found:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# --------------------------------------------------------------------------------------
# Image loading
# --------------------------------------------------------------------------------------

def _placeholder_surface(size: Tuple[int, int] = (64, 64), text: str = "?") -> pygame.Surface:
    """Generate a simple magenta placeholder for missing images."""
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((200, 0, 200))
    pygame.draw.line(surf, (0, 0, 0), (0, 0), (size[0], size[1]), 3)
    pygame.draw.line(surf, (0, 0, 0), (0, size[1]), (size[0], 0), 3)
    try:
        fnt = pygame.font.SysFont("Arial", max(10, size[0] // 4))
        txt = fnt.render(text, True, (255, 255, 255))
        rect = txt.get_rect(center=(size[0] // 2, size[1] // 2))
        surf.blit(txt, rect)
    except Exception:
        pass
    return surf


def load_image(
    name: str,
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS,
    *,
    fallback: Optional[pygame.Surface] = None,
    scale: Optional[Tuple[int, int]] = None,
    colorkey: Optional[Tuple[int, int, int]] = None,
) -> Optional[pygame.Surface]:
    """
    Load a single image with common conveniences:

    - Searches typical project roots and subdirs.
    - Returns a magenta placeholder if not found (unless fallback=None).
    - Optional scaling and colorkey.
    - Uses convert_alpha() if a display is available (fast blits).
    """
    p = resolve_path(name, subdirs, extensions=(".png", ".jpg", ".jpeg", ".bmp", ".gif"))
    if not p:
        print(f"[assets] Info: image '{name}' not found in {subdirs}.")
        if fallback is None:
            return _placeholder_surface()
        return fallback

    try:
        surf = pygame.image.load(p)
        # Apply convert/convert_alpha only if the display is set up
        if _can_convert_alpha():
            surf = surf.convert_alpha()
        if colorkey is not None:
            surf.set_colorkey(colorkey)
        if scale:
            surf = pygame.transform.smoothscale(surf, scale)
        return surf
    except pygame.error as e:
        print(f"[assets] Error loading '{p}': {e}")
        return _placeholder_surface()


def load_images(
    names: Iterable[str],
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS,
) -> List[pygame.Surface]:
    """Load a list of images; skip missing gracefully, returning placeholders."""
    out: List[pygame.Surface] = []
    for name in names:
        img = load_image(name, subdirs=subdirs)
        if img is not None:
            out.append(img)
    return out


def load_images_dict(
    names: Iterable[str],
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS,
) -> Dict[str, pygame.Surface]:
    """Load a mapping of name->Surface (useful for atlases)."""
    return {name: (load_image(name, subdirs=subdirs) or _placeholder_surface()) for name in names}


def load_frames_from_dir(
    directory: str,
    pattern_suffix: str = ".png",
    *,
    sort_natural: bool = True,
) -> List[pygame.Surface]:
    """
    Load all frames in a folder inside common image subdirs.
    Example: load_frames_from_dir("globe_frames") -> [frame_000.png, ...]
    """
    # Try resolving a directory (with typical subdirs)
    dir_path = resolve_path(directory, subdirs=_DEFAULT_IMAGE_SUBDIRS)
    if not dir_path:
        print(f"[assets] Info: directory '{directory}' not found in {_DEFAULT_IMAGE_SUBDIRS}.")
        return []

    path = Path(dir_path)
    if not path.is_dir():
        # Perhaps a nested path? Try parent dir
        path = Path(dir_path).parent

    files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() == pattern_suffix.lower()]
    files.sort(key=_natural_key if sort_natural else None)

    frames: List[pygame.Surface] = []
    for f in files:
        try:
            img = pygame.image.load(str(f))
            if _can_convert_alpha():
                img = img.convert_alpha()
            frames.append(img)
        except pygame.error as e:
            print(f"[assets] Error loading frame '{f}': {e}")
    return frames


def load_spritesheet(
    name: str,
    frame_w: int,
    frame_h: int,
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS,
) -> List[pygame.Surface]:
    """
    Load a spritesheet and slice into frames of (frame_w, frame_h).
    """
    sheet = load_image(name, subdirs=subdirs)
    if sheet is None:
        return []
    sw, sh = sheet.get_width(), sheet.get_height()
    frames: List[pygame.Surface] = []
    for y in range(0, sh, frame_h):
        for x in range(0, sw, frame_w):
            rect = pygame.Rect(x, y, frame_w, frame_h)
            frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            frames.append(frame)
    return frames


# --------------------------------------------------------------------------------------
# Sound & font loading (optional conveniences)
# --------------------------------------------------------------------------------------

def load_sound(
    name: str,
    subdirs: Tuple[str, ...] = _DEFAULT_AUDIO_SUBDIRS,
) -> Optional[pygame.mixer.Sound]:
    """
    Load a sound if mixer is initialized; otherwise return None and log info.
    """
    if not pygame.mixer.get_init():
        print("[assets] Info: mixer not initialized; skipping sound load.")
        return None

    p = resolve_path(name, subdirs=subdirs, extensions=(".ogg", ".wav", ".mp3"))
    if not p:
        print(f"[assets] Info: sound '{name}' not found in {subdirs}.")
        return None
    try:
        return pygame.mixer.Sound(p)
    except pygame.error as e:
        print(f"[assets] Error loading sound '{p}': {e}")
        return None


def load_font(
    name_or_sysfont: str,
    size: int,
    subdirs: Tuple[str, ...] = _DEFAULT_FONT_SUBDIRS,
    *,
    bold: bool = False,
    italic: bool = False,
) -> pygame.font.Font:
    """
    Load a TTF/OTF font from assets if available; otherwise use SysFont.
    """
    p = resolve_path(name_or_sysfont, subdirs=subdirs, extensions=(".ttf", ".otf"))
    if p:
        try:
            return pygame.font.Font(p, size)
        except Exception as e:
            print(f"[assets] Error loading font '{p}': {e}")

    # Fallback: system font
    return pygame.font.SysFont(name_or_sysfont, size, bold=bold, italic=italic)
