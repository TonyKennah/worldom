# --- FILE: src/utils/__init__.py
"""
Utilities package marker.

We opportunistically import platform_init so helpful SDL/OS fixes are
applied early when the utilities package is touched.
"""
try:
    # Optional; ignore if the module doesn't exist
    from . import platform_init  # noqa: F401
except Exception:
    pass

__all__ = []
