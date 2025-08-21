#!/usr/bin/env python3
"""
Create missing __init__.py files under src/ to make packages importable.
Safe to run repeatedly.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

def main() -> int:
    created = 0
    for d in SRC.rglob("*"):
        if d.is_dir():
            py_in_dir = any((d / f).suffix == ".py" for f in d.iterdir() if f.is_file())
            if py_in_dir:
                init = d / "__init__.py"
                if not init.exists():
                    init.write_text("# package marker\n", encoding="utf-8")
                    created += 1
    print(f"Created {created} __init__.py files.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
