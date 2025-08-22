# tests/conftest.py
import os
import sys

# Ensure project root is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Be explicit (also set here in case sitecustomize is bypassed)
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
