# c:/prj/WorldDom/src/ui/menu_theme.py
from __future__ import annotations
from dataclasses import dataclass

import pygame

@dataclass
class MenuTheme:
    bg: pygame.Color = pygame.Color(25, 25, 28, 230)
    border: pygame.Color = pygame.Color(60, 60, 65)
    text: pygame.Color = pygame.Color(230, 230, 235)
    text_disabled: pygame.Color = pygame.Color(140, 140, 145)
    hover_bg: pygame.Color = pygame.Color(58, 90, 170, 220)
    hover_text: pygame.Color = pygame.Color(255, 255, 255)
    separator: pygame.Color = pygame.Color(80, 80, 85)
    shadow: pygame.Color = pygame.Color(0, 0, 0, 140)
    submenu_arrow: pygame.Color = pygame.Color(210, 210, 215)

    padding_x: int = 14
    padding_y: int = 8
    item_height: int = 26
    border_radius: int = 6
    shadow_offset: int = 4
    icon_size: int = 18
    check_width: int = 16
    shortcut_gap: int = 16
