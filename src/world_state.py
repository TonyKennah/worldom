# c:/prj/WorldDom/src/world_state.py
"""
Defines the WorldState class for encapsulating the state of all game objects.
"""
from __future__ import annotations
from typing import List, Optional, Tuple

import pygame

from context_menu import ContextMenuState
from unit import Unit

class WorldState:
    """Encapsulates the state of all game objects and player interaction."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.units: List[Unit] = []
        self.selected_units: List[Unit] = []
        self.hovered_tile: Optional[Tuple[int, int]] = None
        self.left_mouse_down_screen_pos: Optional[Tuple[int, int]] = None
        self.left_mouse_down_world_pos: Optional[pygame.math.Vector2] = None
        self.right_mouse_down_pos: Optional[Tuple[int, int]] = None
        self.selection_box: Optional[pygame.Rect] = None
        self.context_menu = ContextMenuState()