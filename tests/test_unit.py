# c:/prj/WorldDom/tests/test_unit.py
"""
Unit tests for the Unit class.
"""
import os
import sys
import unittest

import pygame

# This adds the 'src' directory to Python's path to allow for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# pylint: disable=wrong-import-position
from settings import TILE_SIZE
from unit import Unit

class TestUnit(unittest.TestCase):
    """Test suite for the Unit class."""

    def test_unit_initialization(self):
        """Tests that a unit is initialized with the correct default state."""
        tile_pos = (10, 20)
        unit = Unit(tile_pos)

        # Check that the logical tile position is correct
        self.assertEqual(unit.tile_pos, pygame.math.Vector2(10, 20))

        # Check that the world position is calculated correctly (center of the tile)
        expected_world_pos = (pygame.math.Vector2(tile_pos) * TILE_SIZE) + pygame.math.Vector2(TILE_SIZE / 2)
        self.assertEqual(unit.world_pos, expected_world_pos)

        # Check initial state
        self.assertFalse(unit.selected)
        self.assertEqual(unit.path, [])