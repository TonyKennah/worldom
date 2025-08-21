"""
Compatibility forwarder.

Some code imports 'assets' from project root, others use 'src.ui.assets'.
This shim ensures both imports resolve to the same module without breaking
existing code paths.
"""
from __future__ import annotations
# Re-export everything from the canonical assets module:
from src.ui.assets import *  # noqa: F401,F403
