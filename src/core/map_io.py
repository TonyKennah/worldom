# c:/game/worldom/map_io.py
"""
Simple (de)serialization helpers for Map (seed + grid).

This module is resilient in CI and local environments:
- It does NOT import heavy/optional libs at module import time.
- It tolerates the absence of the `worldom` package (uses a lightweight stub).
- It keeps the same public API: save_map(Map, path) and load_map(path) -> Map-like.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
import json
import sys


__all__ = ["save_map", "load_map"]


# -----------------------------------------------------------------------------
# Optional wiring for legacy imports (best effort; no hard failure)
# -----------------------------------------------------------------------------

def _try_enable_worldom_virtual_package() -> None:
    """
    If a `worldom` compatibility shim exists (see src/worldom.py), call its
    ensure_virtual_package() to allow 'worldom.*' submodule imports.
    """
    try:
        import worldom  # type: ignore
        ensure = getattr(worldom, "ensure_virtual_package", None)
        if callable(ensure):
            ensure()
    except Exception:
        # Best effort only—do not crash on import
        pass


_try_enable_worldom_virtual_package()


# -----------------------------------------------------------------------------
# Map protocol + optional concrete Map import
# -----------------------------------------------------------------------------

@runtime_checkable
class MapLike(Protocol):
    width: int
    height: int
    seed: int
    data: List[List[str]]

    def _create_lod_surface(self) -> None: ...  # optional; no-op in stub


def _import_real_map_class() -> Optional[type]:
    """
    Attempt to import a concrete Map class from likely locations.
    Returns the class or None if not available.
    """
    # Try the intended legacy location first
    try:
        from worldom.map import Map  # type: ignore
        return Map  # type: ignore[return-value]
    except Exception:
        pass

    # Fallbacks (adjust if your real Map lives elsewhere)
    for cand in (
        "src.core.map:Map",
        "src.map:Map",
        "core.map:Map",
        "map:Map",
    ):
        mod_name, _, attr = cand.partition(":")
        try:
            mod = __import__(mod_name, fromlist=[attr])
            return getattr(mod, attr)  # type: ignore[no-any-return]
        except Exception:
            continue

    return None


_RealMap = _import_real_map_class()


# -----------------------------------------------------------------------------
# Minimal stub if no real Map class is importable
# -----------------------------------------------------------------------------

@dataclass
class _LoadedMapStub:
    width: int
    height: int
    seed: int
    data: List[List[str]]

    def _create_lod_surface(self) -> None:
        # Keep behavior-compatible, but do nothing if pygame/surfaces aren't available.
        return


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def save_map(map_obj: MapLike, path: str | Path) -> None:
    """
    Serialize a Map-like object (expects .width, .height, .seed, .data).
    """
    # Normalize tiles to JSON-serializable types (strings are safest)
    tiles = [[str(t) for t in row] for row in map_obj.data]

    payload: Dict[str, Any] = {
        "width": int(map_obj.width),
        "height": int(map_obj.height),
        "seed": int(map_obj.seed),
        "tiles": tiles,
    }

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f)


def load_map(path: str | Path) -> MapLike:
    """
    Deserialize a Map-like object from JSON. If the real Map class can be
    imported, it will be used; otherwise a lightweight stub is returned.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    width = int(payload["width"])
    height = int(payload["height"])
    seed = int(payload["seed"])
    tiles = [[str(t) for t in row] for row in payload["tiles"]]

    if _RealMap is not None:
        try:
            m = _RealMap(width, height, seed)  # type: ignore[call-arg]
            # Expect it to have a .data we can assign (as per previous code)
            setattr(m, "data", tiles)
            # Create LOD/preview surface if the engine supports it
            try:
                m._create_lod_surface()  # type: ignore[attr-defined]
            except Exception:
                # If pygame/display is not initialized in CI, just skip
                pass
            return m  # type: ignore[return-value]
        except Exception:
            # Fall back to stub if the real Map couldn't be constructed
            pass

    # Fallback stub keeps the same fields so other code can continue to work.
    stub = _LoadedMapStub(width=width, height=height, seed=seed, data=tiles)
    # No-op in CI/headless
    try:
        stub._create_lod_surface()
    except Exception:
        pass
    return stub
