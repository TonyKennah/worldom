# assets.py
# Lightweight helpers to locate and load assets in common project layouts.
from __future__ import annotations
from typing import Iterable, List, Tuple
import os
import pygame


def _candidate_roots() -> List[str]:
    """
    Try a few likely roots:
      - directory of the running script
      - parent dirs of the script (up to 3 levels)
      - current working directory
    """
    roots = set()
    here = os.path.abspath(os.path.dirname(__file__))
    roots.add(here)
    cur = here
    for _ in range(3):
        cur = os.path.dirname(cur)
        roots.add(cur)
    roots.add(os.getcwd())
    return [r for r in roots if r]


def resolve_path(name: str, subdirs: Iterable[str] = ("assets", "image")) -> str | None:
    """
    Return the first existing path for `name` within any of the given subdirs
    below likely project roots.
    """
    for root in _candidate_roots():
        for sd in subdirs:
            p = os.path.join(root, sd, name)
            if os.path.exists(p):
                return p
    # also try name as-is (absolute or cwd-relative)
    if os.path.exists(name):
        return os.path.abspath(name)
    return None


def load_images(names: Iterable[str], subdirs: Iterable[str] = ("assets", "image")) -> List[pygame.Surface]:
    """Load a list of images; skip missing gracefully, print info once."""
    out: List[pygame.Surface] = []
    for name in names:
        p = resolve_path(name, subdirs=subdirs)
        if not p:
            print(f"[assets] Info: image '{name}' not found in {tuple(subdirs)} (searched under common roots).")
            continue
        try:
            img = pygame.image.load(p).convert_alpha()
            out.append(img)
        except pygame.error as e:
            print(f"[assets] Error loading '{p}': {e}")
    return out
