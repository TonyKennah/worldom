# --- FILE: src/redundant/__init__.py
"""
Deprecated compatibility alias for old imports under `src.redundant`.

Historically `redundant.spatial_hash` may have diverged from `utils.spatial_hash`.
To avoid versions drifting, we re-export the maintained implementation so
old imports continue to function but use the same code path.
"""
from __future__ import annotations
from importlib import import_module as _import_module

_utils_spatial_hash = _import_module("src.utils.spatial_hash")

# Re-export everything public from utils.spatial_hash
for _name in dir(_utils_spatial_hash):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_utils_spatial_hash, _name)

# Create an __all__ for static analyzers
__all__ = [n for n in globals() if not n.startswith("_")]
