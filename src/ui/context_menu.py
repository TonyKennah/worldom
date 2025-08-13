# c:/prj/WorldDom/src/context_menu.py
"""
Defines state classes for UI context menus.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import pygame
import src.utils.settings as settings

class SubMenuState:
    """Encapsulates the state of a context sub-menu."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.active: bool = False
        self.options: List[str] = []
        self.rects: List[pygame.Rect] = []
        self.parent_rect: Optional[pygame.Rect] = None

class ContextMenuState:
    """Encapsulates the state of the right-click context menu."""
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.active: bool = False
        self.pos: Optional[Tuple[int, int]] = None
        self.options: List[Dict[str, Any]] = [
            {"label": "Attack"},
            {"label": "Build", "sub_options": ["Shelter", "Workshop", "Farm", "Barracks"]},
            {"label": "MoveTo"},
        ]
        self.rects: List[pygame.Rect] = []
        self.target_tile: Optional[Tuple[int, int]] = None
        self.font = pygame.font.SysFont("Arial", settings.CONTEXT_MENU_FONT_SIZE)
        self.sub_menu = SubMenuState()