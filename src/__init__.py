"""
WorldDom src package marker.

Having this file ensures `src` is treated as a package by Python,
so imports like `import src.ui.starfield` work consistently in CI and locally.
"""
__all__: list[str] = []
