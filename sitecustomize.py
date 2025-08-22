# sitecustomize.py
"""
Global site customizations for CI and local runs.

- Prevent 3rd-party pytest plugins from auto-loading on GitHub runners,
  which often causes collection-time crashes (exit code 2).
- You can still enable plugins explicitly via -p or PYTEST_PLUGINS if needed.
"""
import os

# Do not override if already set by developer/CI
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
