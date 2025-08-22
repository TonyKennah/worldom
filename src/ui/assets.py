# assets.py
# Lightweight, robust helpers to locate and load assets in common project layouts.
# Improved with: better search roots, optional caching, placeholders, headless safety
# hooks, post-display reconversion, and extra utilities — while preserving the
# original public API and behavior.

from __future__ import annotations
"""
Compatibility shim for projects that import assets helpers from `src.ui.assets`
while the real implementation lives at top-level `assets.py`.

This re-exports the public API so both import styles work:
    from assets import load_image
    from src.ui.assets import load_image
"""

from typing import Iterable, List, Optional, Sequence, Tuple, Dict

# Import the real implementation
try:
    # Prefer the top-level file you've already got in the repo.
    from assets import (                     # type: ignore
        add_search_root,
        set_search_roots,
        resolve_path,
        find_all_paths,
        load_image,
        load_images,
        load_images_dict,
        load_frames_from_dir,
        load_spritesheet,
        load_sound,
        load_font,
    )
except Exception as _e:  # Last-resort fallback: provide minimal stubs
    import pygame

    def _missing(*_args, **_kwargs):
        raise RuntimeError(
            "assets shim couldn't import the top-level 'assets.py'. "
            "Ensure it exists or adjust your import path."
        )

    add_search_root = _missing
    set_search_roots = _missing
    resolve_path = _missing
    find_all_paths = _missing
    load_image = _missing
    load_images = _missing
    load_images_dict = _missing
    load_frames_from_dir = _missing
    load_spritesheet = _missing
    load_sound = _missing
    load_font = _missing

__all__ = [
    "add_search_root", "set_search_roots", "resolve_path", "find_all_paths",
    "load_image", "load_images", "load_images_dict", "load_frames_from_dir",
    "load_spritesheet", "load_sound", "load_font",
]

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Dict, Any
import os
import re
import fnmatch
import threading

import pygame


# ======================================================================================
# Configuration / search strategy
# ======================================================================================

# Allow the game to push extra search roots at runtime (e.g., mod folders)
_EXTRA_ROOTS: List[Path] = []

# Environment variables that, if set, are used as additional roots
_ENV_VARS: Tuple[str, ...] = ("WORLDDOM_ASSETS", "WORLD_DOM_ASSETS", "ASSETS_DIR")

# Common subdir names used by many repos
_DEFAULT_IMAGE_SUBDIRS: Tuple[str, ...] = ("assets", "image", "images", "img", "gfx")
_DEFAULT_AUDIO_SUBDIRS: Tuple[str, ...] = ("assets/audio", "assets/sound", "audio", "sound", "sfx")
_DEFAULT_FONT_SUBDIRS: Tuple[str, ...] = ("assets/fonts", "assets/font", "fonts")

# Logging verbosity (set WORLDDOM_ASSETS_VERBOSE=1 to enable)
_ASSETS_VERBOSE = os.environ.get("WORLDDOM_ASSETS_VERBOSE", "0") not in ("", "0", "false", "False")

# Thread-safety for caches
_LOCK = threading.RLock()


# ======================================================================================
# Public API: search roots control (unchanged and extended)
# ======================================================================================

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


def get_search_roots() -> List[str]:
    """Return the current list of candidate roots (for diagnostics/UI)."""
    return [str(p) for p in _candidate_roots()]


class temporary_search_root:
    """
    Context manager to temporarily add a root (e.g., for a mod or test).
    Example:
        with temporary_search_root("mods/awesome_pack"):
            surf = load_image("ui/icon.png")
    """
    def __init__(self, path: str | os.PathLike) -> None:
        self._p = Path(path).expanduser().resolve()
        self._added = False

    def __enter__(self):
        if self._p.exists() and self._p.is_dir() and self._p not in _EXTRA_ROOTS:
            _EXTRA_ROOTS.append(self._p)
            self._added = True
        return self

    def __exit__(self, *exc):
        if self._added and self._p in _EXTRA_ROOTS:
            _EXTRA_ROOTS.remove(self._p)


# ======================================================================================
# Internal helpers
# ======================================================================================

def _log(msg: str) -> None:
    if _ASSETS_VERBOSE:
        print(f"[assets] {msg}")


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
    for entry in dirpath.iterdir():
        if entry.name.lower() == lower:
            return entry
    return None


def _can_convert_alpha() -> bool:
    """Only call convert/convert_alpha if a display surface exists."""
    try:
        return pygame.display.get_init() and pygame.display.get_surface() is not None
    except Exception:
        return False


# ======================================================================================
# Path resolution (unchanged public signatures)
# ======================================================================================

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
                alt_parent = candidate_dir / target.parent if target.parent != Path(".") else candidate_dir
                alt = _case_insensitive_match(alt_parent, target.name)
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
                alt_parent = candidate_dir / target.parent if target.parent != Path(".") else candidate_dir
                alt = _case_insensitive_match(alt_parent, target.name)
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


# ======================================================================================
# Caching / stats (NEW but transparent to existing users)
# ======================================================================================

@dataclass
class CacheStats:
    images: int = 0
    sounds: int = 0
    fonts: int = 0


# Keyed by (resolved_path, scale, colorkey)
_IMAGE_CACHE: Dict[Tuple[str, Optional[Tuple[int, int]], Optional[Tuple[int, int, int]]], pygame.Surface] = {}
# Simple caches keyed by resolved path or tuple(path, size, bold, italic)
_SOUND_CACHE: Dict[str, pygame.mixer.Sound] = {}
_FONT_CACHE: Dict[Tuple[Optional[str], int, bool, bool], pygame.font.Font] = {}
_CACHE_STATS = CacheStats()


def clear_caches() -> None:
    """Clear all in-memory asset caches."""
    with _LOCK:
        _IMAGE_CACHE.clear()
        _SOUND_CACHE.clear()
        _FONT_CACHE.clear()
        _CACHE_STATS.images = _CACHE_STATS.sounds = _CACHE_STATS.fonts = 0


def reconvert_cached_surfaces() -> int:
    """
    After you create a real display surface, call this once to convert any
    already-cached images to the display format for faster blitting.
    Returns the count of surfaces reconverted.
    """
    if not _can_convert_alpha():
        return 0
    count = 0
    with _LOCK:
        for key, surf in list(_IMAGE_CACHE.items()):
            # Recreate via load path to ensure correct convert_alpha
            path, scale, colorkey = key
            try:
                original = pygame.image.load(path)
                if _can_convert_alpha():
                    original = original.convert_alpha()
                if colorkey is not None:
                    original.set_colorkey(colorkey)
                if scale:
                    original = pygame.transform.smoothscale(original, scale)
                _IMAGE_CACHE[key] = original
                count += 1
            except Exception:
                pass
    return count


# ======================================================================================
# Image loading (unchanged public signatures, improved internals)
# ======================================================================================

def _ensure_font_module() -> None:
    try:
        if not pygame.font.get_init():
            pygame.font.init()
    except Exception:
        pass


def _placeholder_surface(size: Tuple[int, int] = (64, 64), text: str = "?") -> pygame.Surface:
    """Generate a simple magenta placeholder for missing images."""
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((200, 0, 200))
    pygame.draw.line(surf, (0, 0, 0), (0, 0), (size[0], size[1]), 3)
    pygame.draw.line(surf, (0, 0, 0), (0, size[1]), (size[0], 0), 3)
    try:
        _ensure_font_module()
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
        _log(f"Info: image '{name}' not found in {subdirs}.")
        if fallback is None:
            return _placeholder_surface()
        return fallback

    cache_key = (p, scale, colorkey)
    with _LOCK:
        cached = _IMAGE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        surf = pygame.image.load(p)
        # Apply convert/convert_alpha only if the display is set up
        if _can_convert_alpha():
            surf = surf.convert_alpha() if surf.get_alpha() is not None else surf.convert()
        if colorkey is not None:
            surf.set_colorkey(colorkey)
        if scale:
            surf = pygame.transform.smoothscale(surf, scale)
        with _LOCK:
            _IMAGE_CACHE[cache_key] = surf
            _CACHE_STATS.images = len(_IMAGE_CACHE)
        return surf
    except pygame.error as e:
        print(f"[assets] Error loading '{p}': {e}")
        return _placeholder_surface()


def load_images(
    names: Iterable[str],
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS
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
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS
) -> Dict[str, pygame.Surface]:
    """Load a mapping of name->Surface (useful for atlases)."""
    return {name: (load_image(name, subdirs=subdirs) or _placeholder_surface()) for name in names}


def load_frames_from_dir(
    directory: str,
    pattern_suffix: str = ".png",
    *,
    sort_natural: bool = True,
    recursive: bool = False,
    glob: Optional[str] = None,
) -> List[pygame.Surface]:
    """
    Load all frames in a folder inside common image subdirs.

    Args:
        directory: Directory to scan (looked up via resolve_path with image subdirs).
        pattern_suffix: Only files with this suffix are loaded if `glob` is None.
        sort_natural: Use natural sorting ("frame_2" before "frame_10").
        recursive: Recurse into subdirectories.
        glob: Optional fnmatch pattern (e.g. "frame_*.png"). Overrides suffix filter.

    Example:
        load_frames_from_dir("globe_frames") -> [frame_000.png, ...]
    """
    # Try resolving a directory (with typical subdirs)
    dir_path = resolve_path(directory, subdirs=_DEFAULT_IMAGE_SUBDIRS)
    if not dir_path:
        _log(f"Info: directory '{directory}' not found in {_DEFAULT_IMAGE_SUBDIRS}.")
        return []

    root = Path(dir_path)
    if not root.is_dir():
        # Perhaps a nested path? Try parent dir
        root = Path(dir_path).parent

    def matches(p: Path) -> bool:
        if glob:
            return fnmatch.fnmatch(p.name, glob)
        return p.suffix.lower() == pattern_suffix.lower()

    files: List[Path] = []
    if recursive:
        for p in root.rglob("*"):
            if p.is_file() and matches(p):
                files.append(p)
    else:
        for p in root.iterdir():
            if p.is_file() and matches(p):
                files.append(p)

    files.sort(key=(lambda p: _natural_key(p.name)) if sort_natural else None)

    frames: List[pygame.Surface] = []
    for f in files:
        try:
            img = pygame.image.load(str(f))
            if _can_convert_alpha():
                img = img.convert_alpha() if img.get_alpha() is not None else img.convert()
            frames.append(img)
        except pygame.error as e:
            print(f"[assets] Error loading frame '{f}': {e}")
    return frames


def load_spritesheet(
    name: str,
    frame_w: int,
    frame_h: int,
    subdirs: Tuple[str, ...] = _DEFAULT_IMAGE_SUBDIRS
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


# ======================================================================================
# Sound & font loading (optional conveniences, unchanged signatures, cached)
# ======================================================================================

def load_sound(
    name: str,
    subdirs: Tuple[str, ...] = _DEFAULT_AUDIO_SUBDIRS
) -> Optional[pygame.mixer.Sound]:
    """
    Load a sound if mixer is initialized; otherwise return None and log info.
    """
    if not pygame.mixer.get_init():
        _log("Info: mixer not initialized; skipping sound load.")
        return None

    p = resolve_path(name, subdirs=subdirs, extensions=(".ogg", ".wav", ".mp3"))
    if not p:
        _log(f"Info: sound '{name}' not found in {subdirs}.")
        return None

    with _LOCK:
        snd = _SOUND_CACHE.get(p)
    if snd is not None:
        return snd

    try:
        snd = pygame.mixer.Sound(p)
        with _LOCK:
            _SOUND_CACHE[p] = snd
            _CACHE_STATS.sounds = len(_SOUND_CACHE)
        return snd
    except pygame.error as e:
        print(f"[assets] Error loading sound '{p}': {e}")
        return None


def load_font(
    name_or_sysfont: str,
    size: int,
    subdirs: Tuple[str, ...] = _DEFAULT_FONT_SUBDIRS,
    *,
    bold: bool = False,
    italic: bool = False
) -> pygame.font.Font:
    """
    Load a TTF/OTF font from assets if available; otherwise use SysFont.
    Fonts are cached by (resolved_path or None, size, bold, italic) to avoid
    recreating handles repeatedly.
    """
    _ensure_font_module()

    resolved = resolve_path(name_or_sysfont, subdirs=subdirs, extensions=(".ttf", ".otf"))
    cache_key = (resolved if resolved else None, size, bold, italic)

    with _LOCK:
        cached = _FONT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        if resolved:
            font = pygame.font.Font(resolved, size)
        else:
            # Fallback: system font
            font = pygame.font.SysFont(name_or_sysfont, size, bold=bold, italic=italic)
    except Exception as e:
        print(f"[assets] Error loading font '{resolved or name_or_sysfont}': {e}")
        # Last-ditch fallback
        font = pygame.font.SysFont("Arial", size, bold=bold, italic=italic)

    with _LOCK:
        _FONT_CACHE[cache_key] = font
        _CACHE_STATS.fonts = len(_FONT_CACHE)
    return font


# ======================================================================================
# Small general-purpose helpers (NEW, non-breaking)
# ======================================================================================

def warmup_headless_for_assets() -> None:
    """
    Useful in CI/tests: if no display is active, set SDL_VIDEODRIVER=dummy and
    create a tiny surface so convert_alpha() is safe during imports.
    """
    try:
        if not pygame.display.get_init():
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
            pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((2, 2))
    except Exception:
        pass


def list_assets_in_subdir(
    subdir: str,
    *,
    glob: str = "*",
    include_dirs: bool = False
) -> List[str]:
    """
    Enumerate assets that exist under the first matching root/subdir.
    This is handy for debug UIs or editor pickers.
    """
    path = resolve_path(subdir, subdirs=("",))  # interpret subdir as path-like
    if not path:
        # Try common roots + subdir directly
        for root in _candidate_roots():
            p = (root / subdir).resolve()
            if p.exists() and p.is_dir():
                path = str(p)
                break
    if not path:
        return []

    base = Path(path)
    items: List[str] = []
    for entry in base.iterdir():
        if not include_dirs and entry.is_dir():
            continue
        if fnmatch.fnmatch(entry.name, glob):
            items.append(str(entry.resolve()))
    return items


def cache_stats() -> CacheStats:
    """Shallow copy of current cache counters."""
    return CacheStats(images=_CACHE_STATS.images, sounds=_CACHE_STATS.sounds, fonts=_CACHE_STATS.fonts)


# ======================================================================================
# End of module
# ======================================================================================
