# tests/test_repo_doctor.py
"""
Smoke-run the tiny repo_doctor in headless mode to mirror the CI step.
Runs very quickly (< 0.3s) and never opens a real window.
"""
import os
import sys
import subprocess
from pathlib import Path

def test_repo_doctor_headless_smoke_runs():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    script = Path("tools") / "repo_doctor.py"
    assert script.exists(), "tools/repo_doctor.py must exist for CI workflow"

    # run a very short smoke (0.2s)
    cp = subprocess.run([sys.executable, str(script), "--headless", "--smoke", "0.2"],
                        capture_output=True, text=True)
    # Print stdout on failure for easier diagnosis in CI
    if cp.returncode != 0:
        print("STDOUT:\n", cp.stdout)
        print("STDERR:\n", cp.stderr)
    assert cp.returncode == 0
