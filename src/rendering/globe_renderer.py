# src/rendering/globe_renderer.py
from __future__ import annotations

"""
Thin wrapper that re-exports globe rendering helpers without importing heavy
dependencies at module import time. This keeps CI import checks green.
"""

try:
    # Import from the top-level module that contains the lazy logic
    from globe_renderer import warm_up_rendering_libraries, render_map_as_globe  # noqa: F401
except Exception:
    # Define fallbacks that keep imports working; raise if actually used.
    def warm_up_rendering_libraries() -> None:  # type: ignore
        pass

    def render_map_as_globe(*args, **kwargs):  # type: ignore
        raise RuntimeError(
            "render_map_as_globe requires optional dependencies (numpy, matplotlib, cartopy) "
            "which are not installed in this environment."
        )
