# c:/prj/WorldDom/src/world_state.py
"""
Defines the WorldState class, a central data container for game state.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pygame

from context_menu import ContextMenuState
from unit import Unit

@dataclass
class WorldState:
    """
    A data class to hold the current state of all game entities, selections,
    and UI interactions. Initializing attributes here prevents runtime errors.
    """
    # --- Game Entities ---
    units: List[Unit] = field(default_factory=list)

    # --- Player Selections & Actions ---
    selected_units: List[Unit] = field(default_factory=list)
    hovered_tile: Optional[Tuple[int, int]] = None
    hovered_world_pos: Optional[pygame.math.Vector2] = None
    selection_box: Optional[pygame.Rect] = None

    # --- UI State ---
    context_menu: ContextMenuState = field(default_factory=ContextMenuState)

    # --- Raw Input State (for tracking drags, etc.) ---
    left_mouse_down_screen_pos: Optional[Tuple[int, int]] = None
    left_mouse_down_world_pos: Optional[pygame.math.Vector2] = None
    right_mouse_down_pos: Optional[Tuple[int, int]] = None