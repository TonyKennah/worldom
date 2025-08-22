# src/utils/project_sanity.py
from __future__ import annotations

"""
Runtime sanity helpers:
- Ensure 'src' is on sys.path (so 'from src.foo import bar' works everywhere).
- Warn when the same module basename appears in multiple folders (import ambiguity).
- Provide friendly import aliases so both 'import assets' and 'from src.ui.assets import ...'
  resolve to a single canonical module if present.
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict
from typing import Iterable

_LOG = logging.getLogger("sanity")


def _repo_root() -> Path:
    # .../src/utils/project_sanity.py -> repo root
    return Path(__file__).resolve().parents[2]


def ensure_src_on_path() -> None:
    root = _repo_root()
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
        _LOG.debug("Inserted '%s' to sys.path[0]", src)


def warn_duplicate_basenames(exclude: Iterable[str] = ("__init__.py",)) -> None:
    root = _repo_root()
    src = root / "src"
    buckets = defaultdict(list)
    for p in src.rglob("*.py"):
        if p.name in exclude:
            continue
        buckets[p.name].append(p.relative_to(root))

    dups = {k: v for k, v in buckets.items() if len(v) > 1}
    if dups:
        _LOG.warning(
            "Duplicate module basenames detected (import ambiguity possible): %s",
            {k: [str(x) for x in v] for k, v in dups.items()},
        )


def _try_alias(modname: str, canonical: str) -> bool:
    """Map 'modname' -> already-importable 'canonical' if available."""
    try:
        import importlib
        mod = importlib.import_module(canonical)
        sys.modules.setdefault(modname, mod)
        _LOG.debug("Aliased '%s' -> '%s'", modname, canonical)
        return True
    except Exception:
        return False


def alias_common_modules() -> None:
    """
    Provide stable import points for common module names that often collide
    (case sensitivity or multiple copies in different folders).
    """
    # Try most canonical paths first
    candidates = [
        ("assets", "src.ui.assets"),
        ("assets", "src.assets"),
        ("settings", "src.utils.settings"),
        ("keymap", "src.utils.keymap"),
    ]
    for name, canonical in candidates:
        if name not in sys.modules:
            _try_alias(name, canonical)


def apply() -> None:
    ensure_src_on_path()
    warn_duplicate_basenames()
    alias_common_modules()
