# c:/prj/WorldDom/src/core/safe_run.py
"""
Crash-safe runner that writes human-readable crash reports to ./crash_reports/.
Use run_with_crash_report(main_fn) in your entrypoint.
"""
from __future__ import annotations
import os
import sys
import time
import traceback
from pathlib import Path

def run_with_crash_report(main_fn) -> int:
    reports = Path("crash_reports")
    reports.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    try:
        return int(main_fn() or 0)
    except SystemExit as e:
        return int(e.code or 0)
    except Exception:
        fname = reports / f"crash-{ts}.log"
        with open(fname, "w", encoding="utf-8") as f:
            f.write("WorldDom crash report\n")
            f.write("="*72 + "\n\n")
            try:
                # Lazy import to avoid pygame requirement when called on CI
                from .bootstrap import system_summary
                f.write(system_summary() + "\n\n")
            except Exception:
                pass
            traceback.print_exc(file=f)
        print(f"\n[WorldDom] A crash report was written to {fname}\n", file=sys.stderr)
        return 1
src/utils/asset_manifest.py
python
Copy
# c:/prj/WorldDom/src/utils/asset_manifest.py
"""
Declarative asset manifest for the loading screen.
Add/rename items to match your repo; missing entries are skipped safely.
"""
from __future__ import annotations

# Relative paths will be resolved inside typical subdirs by the assets helper.
# Examples are conservative; adjust to match your actual files.
ASSET_MANIFEST = {
    "images": [
        "logo.png",
        "ui/cursor.png",
        "tileset.png",
        "units/soldier.png",
    ],
    "sounds": [
        "ui/click.wav",
        "ui/confirm.wav",
        "ambience/wind.ogg",
    ],
    # Each entry: (filename, size_px or None)
    # If using TTF in repo: put it in assets/fonts/ and reference here.
    "fonts": [
        ("fonts/JetBrainsMono-Regular.ttf", 18),
        ("fonts/JetBrainsMono-Bold.ttf", 24),
    ],
}
