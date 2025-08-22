# tools/repo_doctor.py
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# tomllib is in Python 3.11+; fallback to a tiny parser if needed
try:
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


@dataclass
class RepoSummary:
    root: str
    python_files: int
    non_python_files: int
    has_pyproject: bool
    has_requirements: bool
    packages: List[str]
    notes: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


def _find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(6):  # walk up a few levels only
        if (cur / ".git").exists() or (cur / "pyproject.toml").exists() or (cur / "src").exists():
            return cur
        cur = cur.parent
    return start.resolve()


def _safe_read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _scan_packages(root: Path) -> List[str]:
    pkgs: List[str] = []
    for base in (root, root / "src"):
        if not base.exists():
            continue
        for p in base.iterdir():
            if p.is_dir() and (p / "__init__.py").exists():
                pkgs.append(p.name)
    return sorted(set(pkgs))


def _count_files(root: Path) -> Tuple[int, int]:
    py = 0
    other = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix == ".py":
            py += 1
        else:
            other += 1
    return py, other


def _parse_pyproject_packages(pyproject: Path) -> List[str]:
    if not pyproject.exists() or tomllib is None:
        return []
    try:
        data = tomllib.loads(_safe_read(pyproject) or "")
    except Exception:
        return []
    pkgs: List[str] = []
    # Try modern PEP 621 structure
    for key in ("project", "tool", "tool.poetry"):
        node = data.get(key) if isinstance(data, dict) else None
        if isinstance(node, dict):
            name = node.get("name") if key == "project" else node.get("name")
            if isinstance(name, str):
                pkgs.append(name)
    return sorted(set(pkgs))


def analyze_repo(start_dir: str | os.PathLike = ".") -> RepoSummary:
    root = _find_repo_root(Path(start_dir))
    py_count, other_count = _count_files(root)
    has_pyproject = (root / "pyproject.toml").exists()
    has_requirements = (root / "requirements.txt").exists()
    pkgs = _scan_packages(root)
    pkgs.extend(_parse_pyproject_packages(root / "pyproject.toml"))
    pkgs = sorted(set(pkgs))

    notes: List[str] = []
    if not has_pyproject:
        notes.append("pyproject.toml not found (ok if project is not packaged)")
    if not has_requirements:
        notes.append("requirements.txt not found (ok if using conda/poetry)")

    return RepoSummary(
        root=str(root),
        python_files=py_count,
        non_python_files=other_count,
        has_pyproject=has_pyproject,
        has_requirements=has_requirements,
        packages=pkgs,
        notes=notes,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WorldDom repository doctor (safe, stdlib-only)")
    parser.add_argument("--cwd", default=".", help="Start directory for repo discovery (default: current)")
    parser.add_argument("--format", choices=("json", "text"), default="json", help="Output format")
    parser.add_argument("--no-fail", action="store_true",
                        help="Always exit 0 (useful for CI smoke tests).")
    args = parser.parse_args(argv)

    try:
        summary = analyze_repo(args.cwd)
        if args.format == "json":
            print(json.dumps(summary.to_dict(), indent=2))
        else:
            print(f"Root: {summary.root}")
            print(f"Python files: {summary.python_files}")
            print(f"Other files:  {summary.non_python_files}")
            print(f"Has pyproject: {summary.has_pyproject}")
            print(f"Has requirements: {summary.has_requirements}")
            print(f"Packages: {', '.join(summary.packages) or '(none)'}")
            if summary.notes:
                print("Notes:")
                for n in summary.notes:
                    print(f"  - {n}")
    except Exception as e:
        # Do not let CI fail on diagnostics
        print(f"[repo_doctor] Error: {e}", file=sys.stderr)
        return 0 if args.no_fail else 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
