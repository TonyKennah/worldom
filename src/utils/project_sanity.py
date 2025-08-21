# src/utils/project_sanity.py
from __future__ import annotations

"""
Lightweight runtime checks that help avoid common pitfalls:
- Warn if multiple modules share the same basename (e.g., multiple 'assets.py').
- Ensure 'src' is on sys.path (running from repo root).
- Provide an alias so 'import assets' resolves to 'src.ui.assets' if present.
"""

import sys
from pathlib import Path
from collections import defaultdict
import importlib
import importlib.util
import logging

def ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[2]  # .../src/utils/project_sanity.py -> repo root
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

def warn_duplicate_basenames() -> None:
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    buckets = defaultdict(list)
    for p in src.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        buckets[p.name].append(p.relative_to(root))

    dups = {k: v for k, v in buckets.items() if len(v) > 1}
    if dups:
        logging.getLogger("sanity").warning(
            "Duplicate module basenames detected (import ambiguity possible): %s",
            {k: [str(x) for x in v] for k, v in dups.items()},
        )

def alias_assets_if_needed() -> None:
    """
    If 'src/ui/assets.py' exists, ensure 'import assets' returns that module.
    """
    root = Path(__file__).resolve().parents[2]
    candidate = root / "src" / "ui" / "assets.py"
    if candidate.exists():
        modname = "assets"
        target = "src.ui.assets"
        try:
            mod = importlib.import_module(target)
            sys.modules.setdefault(modname, mod)
        except Exception:
            pass

def apply():
    ensure_src_on_path()
    warn_duplicate_basenames()
    alias_assets_if_needed()
