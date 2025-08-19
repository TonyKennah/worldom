# src/ui/help_overlay.py
from __future__ import annotations
from typing import List, Tuple
import pygame

import src.utils.settings as settings


class HelpOverlay:
    """
    A semi-transparent help/controls overlay.
    Toggle from anywhere: ui_manager.toggle_help_overlay().
    Drawn at the very end of UI so it sits on top of everything.
    """

    def __init__(self) -> None:
        self.visible: bool = False
        # Fonts
        self.title_font = pygame.font.SysFont("Arial", 28, bold=True)
        self.body_font = pygame.font.SysFont("Arial", 18)
        self.mono_font = pygame.font.SysFont("Consolas", 16)

        # Static help text. Adjust to taste or generate dynamically.
        self.title_text = "WorldDom — Help & Controls"
        self.sections: List[Tuple[str, List[str]]] = [
            ("General",
             [
                 "F1 or ? : Toggle this help",
                 "F11    : Toggle fullscreen",
                 "P      : Pause / Resume",
                 "Right-click: Context menu (Move / Attack, etc.)",
                 "Mouse wheel: Zoom in/out",
             ]),
            ("Selection",
             [
                 "Left-click: Select a single unit",
                 "Drag LMB : Box select multiple units",
                 "Hover tile: Debug panel shows terrain under cursor",
             ]),
            ("World / Camera",
             [
                 "Edge pan near screen edges (unless blocked by the debug panel)",
                 "Toroidal world: units & map wrap at edges",
             ]),
            ("Tips",
             [
                 "Use the Debug panel links (top-right) for 'New', 'Show Globe', 'Exit'.",
                 "Globe popup speed control is under the popup.",
             ]),
        ]

        self.footer_lines = [
            f"Theme: {settings.ACTIVE_THEME.get('name', settings.ACTIVE_THEME_NAME)}",
            f"Resolution: {settings.SCREEN_WIDTH} x {settings.SCREEN_HEIGHT}",
        ]

    def toggle(self) -> None:
        self.visible = not self.visible

    def draw(self, surface: pygame.Surface, width: int, height: int) -> None:
        if not self.visible:
            return

        # Dimmed full-screen overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))

        # Central panel
        pad = 18
        col_gap = 28
        panel_w = int(min(760, width * 0.85))
        panel_h = int(min(520, height * 0.85))
        panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
        panel_rect.center = (width // 2, height // 2)

        pygame.draw.rect(surface, (38, 42, 55), panel_rect, border_radius=12)
        pygame.draw.rect(surface, (210, 210, 220), panel_rect, width=2, border_radius=12)

        # Title
        title_surf = self.title_font.render(self.title_text, True, (240, 240, 250))
        title_rect = title_surf.get_rect(midtop=(panel_rect.centerx, panel_rect.top + pad))
        surface.blit(title_surf, title_rect)

        # Two-column layout for sections
        col_w = (panel_rect.width - pad * 2 - col_gap) // 2
        left_x = panel_rect.left + pad
        right_x = left_x + col_w + col_gap
        y = title_rect.bottom + pad

        def draw_section(start_x: int, start_y: int, title: str, lines: List[str]) -> int:
            sect_title = self.body_font.render(title, True, (255, 230, 180))
            surface.blit(sect_title, (start_x, start_y))
            y2 = start_y + sect_title.get_height() + 6
            for ln in lines:
                ln_surf = self.mono_font.render("• " + ln, True, (230, 235, 245))
                surface.blit(ln_surf, (start_x, y2))
                y2 += ln_surf.get_height() + 2
            return y2 + 8

        # Render alternating sections in columns
        col_y = [y, y]
        for idx, (sect_title, lines) in enumerate(self.sections):
            col = idx % 2
            x = left_x if col == 0 else right_x
            col_y[col] = draw_section(x, col_y[col], sect_title, lines)

        # Footer
        footer_y = panel_rect.bottom - pad - (len(self.footer_lines) * (self.mono_font.get_height() + 2))
        for i, ln in enumerate(self.footer_lines):
            fs = self.mono_font.render(ln, True, (190, 200, 210))
            surface.blit(fs, (panel_rect.left + pad, footer_y + i * (self.mono_font.get_height() + 2)))

        # Hint
        hint = self.mono_font.render("Press F1 or ? to close", True, (200, 200, 210))
        surface.blit(hint, (panel_rect.right - pad - hint.get_width(), panel_rect.bottom - pad - hint.get_height()))
