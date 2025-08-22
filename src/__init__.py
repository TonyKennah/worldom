# --- FILE: src/__init__.py
"""
Top-level package marker for WorldDom.

Having an __init__ here ensures imports like
`from src.utils.settings import ...` work consistently on all environments,
including tools and test runners that don't inject the project root to sys.path.
"""
__all__ = ["core", "ui", "entities", "world", "utils", "rendering"]
