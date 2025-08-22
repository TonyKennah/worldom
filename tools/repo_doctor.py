# tools/repo_doctor.py
from __future__ import annotations
import argparse
from pathlib import Path
import json

MANDATORY = ("pyproject.toml",)
OPTIONAL = ("LICENSE", ".editorconfig")

def check(root: Path) -> dict:
    present = {name: (root / name).exists() for name in set(MANDATORY) | set(OPTIONAL)}
    return {
        "root": str(root),
        "mandatory_ok": all(present[n] for n in MANDATORY),
        "missing_mandatory": [n for n in MANDATORY if not present[n]],
        "missing_optional": [n for n in OPTIONAL if not present[n]],
    }

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repo sanity checker")
    ap.add_argument("--cwd", type=str, default=".")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--no-fail", action="store_true", help="Never exit non-zero (for CI smoke checks)")
    args = ap.parse_args(argv)

    info = check(Path(args.cwd).resolve())

    if args.format == "json":
        print(json.dumps(info))
    else:
        print("Repo Doctor Summary")
        print("-------------------")
        print(f"Root: {info['root']}")
        print(f"Mandatory OK: {info['mandatory_ok']} | Missing: {', '.join(info['missing_mandatory']) or 'None'}")
        if info["missing_optional"]:
            print(f"Optional Missing: {', '.join(info['missing_optional'])}")

    # Honor --no-fail strictly
    if args.no_fail:
        return 0
    return 0 if info["mandatory_ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
