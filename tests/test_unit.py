# c:/prj/WorldDom/tests/test_unit.py
"""
Unit tests for the Unit class.

This test suite focuses on:
- Correct initialization & coordinate conversions (tile <-> world)
- Selection state semantics (method-based or direct flag)
- Path attribute presence & basic invariants
- Optional world-position sync behavior when tile changes (best-effort; skipped if API absent)

The tests are resilient to differing Unit APIs by feature-detecting methods and
skipping optional tests when a method/property is not available.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Tuple

# --- Headless-friendly pygame init (no real window needed) -------------------
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402


# --- Ensure project root on sys.path so `src.*` imports resolve --------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# pylint: disable=wrong-import-position
from src.utils.settings import TILE_SIZE  # type: ignore  # noqa: E402
from src.entities.unit import Unit        # type: ignore  # noqa: E402

# Local test helpers
try:
    from tests.util_asserts import assert_vec2_almost_equal  # type: ignore
except Exception:
    # Fallback inline if the helper module isn't present (CI environments, etc.)
    def assert_vec2_almost_equal(
        tc: unittest.TestCase, a: pygame.math.Vector2, b: pygame.math.Vector2, places: int = 4, msg: str | None = None
    ) -> None:
        tc.assertIsInstance(a, pygame.math.Vector2)
        tc.assertIsInstance(b, pygame.math.Vector2)
        tc.assertAlmostEqual(a.x, b.x, places=places, msg=msg)
        tc.assertAlmostEqual(a.y, b.y, places=places, msg=msg)


def tile_center(tile: Tuple[int, int]) -> pygame.math.Vector2:
    """World-space center of a given tile coordinate."""
    v = pygame.math.Vector2(tile)
    return v * TILE_SIZE + pygame.math.Vector2(TILE_SIZE / 2, TILE_SIZE / 2)


class TestUnit(unittest.TestCase):
    """Test suite for the Unit class."""

    @classmethod
    def setUpClass(cls):
        """Initialize Pygame once for all tests in this class."""
        pygame.init()
        # Some Unit implementations rely on Vector2 only; display is not required,
        # but initialize it in dummy mode to avoid edge cases.
        try:
            pygame.display.init()
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        """Shut down Pygame cleanly after all tests."""
        try:
            pygame.display.quit()
        except Exception:
            pass
        pygame.quit()

    # --------------------------------------------------------------------- #
    # Initialization & coordinates
    # --------------------------------------------------------------------- #

    def test_unit_initialization_defaults(self):
        """Unit initializes with correct tile/world positions and default flags."""
        tile_pos = (10, 20)
        unit = Unit(tile_pos)

        # Logical tile position
        self.assertIsInstance(unit.tile_pos, pygame.math.Vector2)
        assert_vec2_almost_equal(self, unit.tile_pos, pygame.math.Vector2(10, 20))

        # World position is at the tile center
        expected_world = tile_center(tile_pos)
        self.assertIsInstance(unit.world_pos, pygame.math.Vector2)
        assert_vec2_almost_equal(self, unit.world_pos, expected_world)

        # Initial state invariants
        self.assertFalse(getattr(unit, "selected", False))
        # Path presence (many engines keep a simple list of tiles)
        self.assertTrue(hasattr(unit, "path"), "Unit should expose a 'path' attribute")
        self.assertIsInstance(unit.path, list)
        self.assertEqual(unit.path, [])

        # __repr__ should be a string for logging/debugging
        self.assertIsInstance(repr(unit), str)

    def test_multiple_start_positions(self):
        """Validate world-center conversion across several tiles."""
        samples = [(0, 0), (1, 1), (7, 3), (25, 9), (10, 20)]
        for t in samples:
            with self.subTest(tile=t):
                u = Unit(t)
                assert_vec2_almost_equal(self, u.world_pos, tile_center(t))

    # --------------------------------------------------------------------- #
    # Selection semantics
    # --------------------------------------------------------------------- #

    def test_selection_toggle(self):
        """
        Selection may be controlled by methods (select/deselect), a setter, or direct flag.
        This test attempts the common approaches and asserts final state.
        """
        u = Unit((3, 4))

        # Select
        if hasattr(u, "select") and callable(u.select):
            u.select()
        elif hasattr(u, "set_selected") and callable(u.set_selected):
            u.set_selected(True)
        elif hasattr(u, "selected"):
            u.selected = True
        else:
            self.skipTest("Unit has no supported selection API")

        self.assertTrue(getattr(u, "selected", False), "Unit should be selected after selection call")

        # Deselect
        if hasattr(u, "deselect") and callable(u.deselect):
            u.deselect()
        elif hasattr(u, "set_selected") and callable(u.set_selected):
            u.set_selected(False)
        elif hasattr(u, "selected"):
            u.selected = False
        else:
            self.skipTest("Unit has no supported deselection API")

        self.assertFalse(getattr(u, "selected", True), "Unit should be deselected after deselection call")

    # --------------------------------------------------------------------- #
    # Position sync behavior (optional APIs)
    # --------------------------------------------------------------------- #

    def test_world_pos_sync_after_tile_change(self):
        """
        If Unit exposes a method to sync world position when tile changes (e.g., on_tile_changed,
        sync_world_from_tile, update_world_position, or update()), verify correct world center.
        If no such method exists, skip this test to avoid false failures.
        """
        u = Unit((5, 5))
        # Change logical tile position
        u.tile_pos = pygame.math.Vector2(8, 2)

        # Try common sync hooks (best-effort)
        synced = False
        for name in ("on_tile_changed", "sync_world_from_tile", "update_world_position"):
            if hasattr(u, name) and callable(getattr(u, name)):
                getattr(u, name)()
                synced = True
                break

        if not synced:
            # Some implementations recompute on generic update()
            if hasattr(u, "update") and callable(u.update):
                try:
                    u.update(0.0)
                    synced = True
                except TypeError:
                    # update might not accept dt; try calling without args
                    try:
                        u.update()  # type: ignore
                        synced = True
                    except Exception:
                        pass

        if not synced:
            self.skipTest("Unit does not expose a sync/update hook to recompute world_pos from tile_pos")

        expected_world = tile_center((8, 2))
        assert_vec2_almost_equal(self, u.world_pos, expected_world, msg="world_pos should match tile center after sync")

    # --------------------------------------------------------------------- #
    # Path attribute presence / basic mutation
    # --------------------------------------------------------------------- #

    def test_path_attribute_and_mutation(self):
        """
        Ensure Unit exposes a list-like 'path' and that setting/replacing it works.
        If a formal setter exists (set_path), use it; otherwise assign directly.
        """
        u = Unit((1, 1))
        self.assertTrue(hasattr(u, "path"), "Unit should expose a 'path' attribute")
        self.assertIsInstance(u.path, list)

        new_path = [(2, 1), (3, 1), (4, 1)]
        if hasattr(u, "set_path") and callable(getattr(u, "set_path")):
            u.set_path(new_path)  # type: ignore[attr-defined]
        else:
            u.path = list(new_path)  # type: ignore[assignment]

        self.assertEqual(len(u.path), len(new_path))
        self.assertEqual(u.path[0], new_path[0])
        self.assertEqual(u.path[-1], new_path[-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
