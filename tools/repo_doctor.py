# tools/repo_doctor.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

MANDATORY: Tuple[str, ...] = ("README.md", "pyproject.toml")
OPTIONAL: Tuple[str, ...] = (".gitignore", "LICENSE", ".editorconfig")

@dataclass(frozen=True)
class CheckResult:
    ok: bool
    missing: List[str]

def _have(paths: Iterable[str], root: Path) -> List[str]:
    """Return the subset of `paths` missing under `root` (case-insensitive)."""
    missing: List[str] = []
    for name in paths:
        p = root / name
        if p.exists():
            continue
        # case-insensitive fallback (Windows/macOS-friendly)
        # e.g., 'readme.md' satisfies 'README.md'
        parent = p.parent
        if not parent.exists():
            missing.append(name)
            continue
        lname = name.lower()
        found = any(child.name.lower() == lname for child in parent.iterdir())
        if not found:
            missing.append(name)
    return missing

def check_repo(root: str | Path = ".") -> Dict[str, CheckResult]:
    """
    Run minimal hygiene checks expected by tests:
      - Mandatory: README.md, pyproject.toml
      - Optional : .gitignore, LICENSE, .editorconfig  (do not fail build)
    """
    r = Path(root).resolve()
    missing_mand = _have(MANDATORY, r)
    missing_opt = _have(OPTIONAL, r)
    return {
        "mandatory": CheckResult(ok=(len(missing_mand) == 0), missing=missing_mand),
        "optional":  CheckResult(ok=True, missing=missing_opt),  # info-only
    }

def summarize(root: str | Path = ".") -> str:
    res = check_repo(root)
    lines = []
    mand = res["mandatory"]
    opt = res["optional"]
    lines.append("Repo Doctor Summary")
    lines.append("-------------------")
    lines.append(f"Root: {Path(root).resolve()}")
    lines.append(f"Mandatory OK: {mand.ok} | Missing: {', '.join(mand.missing) if mand.missing else 'None'}")
    lines.append(f"Optional Missing: {', '.join(opt.missing) if opt.missing else 'None'}")
    return "\n".join(lines)

def main(argv: List[str] | None = None) -> int:
    """
    CLI: prints a summary and returns 0 when mandatory files exist,
    otherwise returns 1 (so tests/assertions can check behavior).
    """
    print(summarize("."))
    return 0 if check_repo(".")["mandatory"].ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
