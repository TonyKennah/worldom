# src/worldom.py
"""
Compatibility shim for legacy `import worldom` usages.

This module lets files like `src/core/map_io.py` import successfully in
environments (e.g., CI) where a real `worldom` package is not installed.
If your production setup provides a real package on PYTHONPATH, that package
will take precedence and shadow this shim.

Keep this minimal: it’s only intended to satisfy imports at discovery time.
"""

__all__ = []
__version__ = "0.0.0-ci-shim"
