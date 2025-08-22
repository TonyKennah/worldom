# tools/repo_doctor.py
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Set

# What we consider "mandatory" and "optional" for a healthy repo
MANDATORY = ("pyproject.toml",)
OPTIONAL = ("LICENSE", ".editorconfig")

# Directories to skip when walking the tree for file stats
EXCLUDE_DIRS: Set[str] = {
    ".git",
    ".github",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "build",
    "dist",
    ".idea",
    ".vscode",
}

def _is_excluded(path: Path) -> bool:
    """
    Return True if any path part matches one of our excluded directory names.
    """
    return any(part in EXCLUDE_DIRS for part in path.parts)

def _scan_files(root: Path) -> Dict[str, List[str]]:
    """
    Walk the repo and return a split of python vs non-python files (relative, POSIX paths).
    """
    py: List[str] = []
    nonpy: List[str] = []
    for p in root.rglob("*"):
        # only files
        if not p.is_file():
            continue
        # skip excluded directories
        if _is_excluded(p.relative_to(root).parent):
            continue

        rel = p.relative_to(root).as_posix()
        if p.suffix.lower() == ".py":
            py.append(rel)
        else:
            nonpy.append(rel)

    py.sort()
    nonpy.sort()
    return {"python_files": py, "non_python_files": nonpy}

def _check_presence(root: Path) -> Dict[str, object]:
    """
    Check mandatory/optional repository files at the root.
    """
    present = {name: (root / name).exists() for name in set(MANDATORY) | set(OPTIONAL)}
    return {
        "root": str(root),
        "mandatory_ok": all(present[n] for n in MANDATORY),
        "missing_mandatory": [n for n in MANDATORY if not present[n]],
        "missing_optional": [n for n in OPTIONAL if not present[n]],
    }

def check(root: Path) -> Dict[str, object]:
    """
    Combined repository summary used by CLI and tests.
    """
    presence = _check_presence(root)
    files = _scan_files(root)
    summary: Dict[str, object] = {}
    summary.update(presence)
    summary.update(files)
    return summary

def _print_text(info: Dict[str, object]) -> None:
    """
    Human-readable output.
    """
    print("Repo Doctor Summary")
    print("-------------------")
    print(f"Root: {info['root']}")
    print(f"Mandatory OK: {info['mandatory_ok']} | Missing: {', '.join(info['missing_mandatory']) or 'None'}")
    if info["missing_optional"]:
        print(f"Optional Missing: {', '.join(info['missing_optional'])}")
    # Show counts (don’t flood CI logs with full lists)
    py_count = len(info.get("python_files", []))  # type: ignore[arg-type]
    nonpy_count = len(info.get("non_python_files", []))  # type: ignore[arg-type]
    print(f"Python files: {py_count} | Non-Python files: {nonpy_count}")

def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repo sanity checker")
    ap.add_argument("--cwd", type=str, default=".", help="Repository root to check")
    ap.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    ap.add_argument("--no-fail", action="store_true", help="Always return code 0 (for CI smoke checks)")
    args = ap.parse_args(argv)

    root = Path(args.cwd).resolve()
    info = check(root)

    if args.format == "json":
        print(json.dumps(info))
    else:
        _print_text(info)

    # Honor --no-fail strictly
    if args.no_fail:
        return 0
    return 0 if info["mandatory_ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
