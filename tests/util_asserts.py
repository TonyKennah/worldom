# c:/prj/WorldDom/tests/util_asserts.py
"""
Small assertion helpers for tests.
"""
from __future__ import annotations

import unittest
import pygame


def assert_vec2_almost_equal(
    tc: unittest.TestCase,
    a: pygame.math.Vector2,
    b: pygame.math.Vector2,
    places: int = 4,
    msg: str | None = None,
) -> None:
    """Assert two pygame Vector2 are almost equal component-wise."""
    tc.assertIsInstance(a, pygame.math.Vector2, msg or "Left value is not a pygame.math.Vector2")
    tc.assertIsInstance(b, pygame.math.Vector2, msg or "Right value is not a pygame.math.Vector2")
    tc.assertAlmostEqual(a.x, b.x, places=places, msg=msg)
    tc.assertAlmostEqual(a.y, b.y, places=places, msg=msg)
