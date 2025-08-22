# --- FILE: src/world_state.py
# Back-compat shim to unify imports.
# Some files import from `src.world_state`, others import from
# `src.world.world_state`. This module re-exports the latter so either
# import path works without code churn.
from __future__ import annotations
from importlib import import_module as _import_module

# Try the canonical module first.
_world_mod = _import_module("src.world.world_state")

# Re-export common symbols if they exist.
# (We do not *require* optional helper dataclasses.)
WorldState = getattr(_world_mod, "WorldState")
WorldPing = getattr(_world_mod, "WorldPing", None)
CommandRecord = getattr(_world_mod, "CommandRecord", None)

# Build a clean __all__ of what we actually exported
__all__ = ["WorldState"]
if WorldPing is not None:
    __all__.append("WorldPing")
if CommandRecord is not None:
    __all__.append("CommandRecord")
