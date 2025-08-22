# src/worldom.py
"""
A lightweight compatibility module that lets code import `worldom.*`
even though the codebase lives under `src/`.

- Turns this module into a *virtual package* so that imports like
  `from worldom.utils import settings` resolve to `src/utils/settings.py`.
- Exposes a few tiny, dependency-free helpers (paths + text/json IO)
  that older modules may rely on when importing `worldom`.

This keeps legacy imports working in CI and during local development
without changing existing source files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

# Absolute path to the project's `src/` directory (this file lives in it).
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent

__all__ = [
    "SRC_DIR",
    "PROJECT_ROOT",
    "ensure_virtual_package",
    "asset_path",
    "data_path",
    "project_path",
    "read_text",
    "write_text",
    "read_json",
    "write_json",
]


def ensure_virtual_package() -> None:
    """
    Make this *module* behave like a *package* so submodule imports work:

      from worldom.utils import settings  ->  src/utils/settings.py

    We do this by:
      - adding `src/` to sys.path (idempotent)
      - setting this module's __path__ to [src/]
      - updating the import spec to advertise submodule search locations
    """
    if str(SRC_DIR) not in sys.path:
        # Ensure `import worldom.something` can be found by the importer
        sys.path.insert(0, str(SRC_DIR))

    # Mark this module as a package by providing a __path__
    mod = sys.modules.get(__name__)
    if mod is not None:
        pkg_paths = [str(SRC_DIR)]
        try:
            setattr(mod, "__path__", pkg_paths)  # type: ignore[attr-defined]
        except Exception:
            pass

        spec = getattr(mod, "__spec__", None)
        if spec is not None:
            try:
                spec.submodule_search_locations = pkg_paths  # type: ignore[attr-defined]
            except Exception:
                # Some importers may not allow changing this; it's best-effort.
                pass


# Call immediately on import
ensure_virtual_package()


# ------------------------------ Tiny path helpers ------------------------------

def project_path(*parts: Iterable[str]) -> Path:
    """
    Build a path relative to the project root (one level above `src/`).
    """
    return PROJECT_ROOT.joinpath(*parts)


def asset_path(*parts: Iterable[str]) -> Path:
    """
    Conventional assets root helper. Adjust if your project uses a different layout.
    """
    return project_path("assets", *parts)


def data_path(*parts: Iterable[str]) -> Path:
    """
    Conventional data root helper (maps/saves/etc.). Change as needed.
    """
    # Try a few common folders; default to 'data'
    for cand in ("data", "assets/data", "assets"):
        p = project_path(cand, *parts)
        if p.parent.exists() or p.exists():
            return p
    return project_path("data", *parts)


# ------------------------------ Minimal IO helpers -----------------------------

def read_text(path: Path | str, encoding: str = "utf-8") -> str:
    p = Path(path)
    return p.read_text(encoding=encoding)


def write_text(path: Path | str, text: str, encoding: str = "utf-8") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding=encoding)


def read_json(path: Path | str, encoding: str = "utf-8") -> Any:
    p = Path(path)
    with p.open("r", encoding=encoding) as f:
        return json.load(f)


def write_json(path: Path | str, data: Any, *, indent: int = 2, encoding: str = "utf-8") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding=encoding) as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
