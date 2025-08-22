# tests/test_repo_doctor.py
"""
Smoke-run the tiny repo_doctor in headless mode to mirror the CI step.
Runs very quickly (< 0.3s) and never opens a real window.
"""
import os  # needed for os.environ.setdefault in this test module
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import json
import subprocess
import sys
from pathlib import Path

def test_repo_doctor_cli_json_ok():
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "tools.repo_doctor", "--cwd", str(root), "--format", "json", "--no-fail"]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    assert "python_files" in data and "non_python_files" in data and "root" in data

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
