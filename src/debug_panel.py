from __future__ import annotations
from typing import Optional, TYPE_CHECKING

import pygame
import settings

if TYPE_CHECKING:
    from game import Game

class DebugPanel:
    """Handles rendering and interaction for the top debug panel."""
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("Arial", settings.DEBUG_PANEL_FONT_SIZE)
        self.exit_link_rect: Optional[pygame.Rect] = None
        self.new_link_rect: Optional[pygame.Rect] = None
        self.show_globe_link_rect: Optional[pygame.Rect] = None

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """
        Handles events for the debug panel.
        Returns an action string ('exit', 'new_map') or None.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.exit_link_rect and self.exit_link_rect.collidepoint(event.pos):
                return "exit"  # Signal to exit
            if self.new_link_rect and self.new_link_rect.collidepoint(event.pos):
                return "new_map" # Signal to create a new map
            if self.show_globe_link_rect and self.show_globe_link_rect.collidepoint(event.pos):
                return "show_globe" # Signal to show the globe
        return None

    def _draw_main_info(self, game: Game) -> None:
        """Draws the main informational text (FPS, zoom, etc.)."""
        world_pos = game.camera.screen_to_world(pygame.mouse.get_pos())
        world_coords = f"({int(world_pos.x)}, {int(world_pos.y)})"
        zoom_percentage = game.camera.zoom_state.current * 100
        info_string = (
            f"FPS: {game.clock.get_fps():.1f} | "
            f"Zoom: {zoom_percentage:.0f}% | "
            f"World: {world_coords}"
        )
        if game.world_state.hovered_tile:
            tile_x, tile_y = game.world_state.hovered_tile
            terrain = game.map.data[tile_y][tile_x]
            tile_info = f"({tile_x}, {tile_y}) ({terrain.capitalize()})"
            info_string += f" | Tile: {tile_info}"

        text_surface = self.font.render(info_string, True, settings.DEBUG_PANEL_FONT_COLOR)
        text_y = (settings.DEBUG_PANEL_HEIGHT - text_surface.get_height()) // 2
        game.screen.blit(text_surface, (10, text_y))

    def _draw_exit_link(self, game: Game) -> None:
        """Draws the clickable 'Exit' link."""
        exit_text_surface = self.font.render("Exit", True, settings.DEBUG_PANEL_FONT_COLOR)
        exit_text_x = settings.SCREEN_WIDTH - exit_text_surface.get_width() - 10
        exit_text_y = (settings.DEBUG_PANEL_HEIGHT - exit_text_surface.get_height()) // 2
        self.exit_link_rect = game.screen.blit(exit_text_surface, (exit_text_x, exit_text_y))

    def _draw_new_link(self, game: Game) -> None:
        """Draws the clickable 'New' link."""
        new_text_surface = self.font.render("New", True, settings.DEBUG_PANEL_FONT_COLOR)
        # Position it to the left of the exit link, which must be drawn first.
        exit_width = self.exit_link_rect.width if self.exit_link_rect else 0
        spacing = 15
        new_text_x = settings.SCREEN_WIDTH - exit_width - 10
        new_text_x = new_text_x - new_text_surface.get_width() - spacing
        new_text_y = (settings.DEBUG_PANEL_HEIGHT - new_text_surface.get_height()) // 2
        self.new_link_rect = game.screen.blit(new_text_surface, (new_text_x, new_text_y))

    def _draw_show_globe_link(self, game: Game) -> None:
        """Draws the clickable 'Show Globe' link."""
        globe_text_surface = self.font.render("Show Globe", True, settings.DEBUG_PANEL_FONT_COLOR)
        # Position it to the left of the 'New' link, which must be drawn first.
        new_width = self.new_link_rect.width if self.new_link_rect else 0
        spacing = 15
        globe_text_x = self.new_link_rect.left - globe_text_surface.get_width() - spacing
        globe_text_y = (settings.DEBUG_PANEL_HEIGHT - globe_text_surface.get_height()) // 2
        self.show_globe_link_rect = game.screen.blit(globe_text_surface, (globe_text_x, globe_text_y))

    def draw(self, game: Game) -> None:
        """Renders the complete debug panel by calling its helper methods."""
        panel_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.DEBUG_PANEL_HEIGHT)
        pygame.draw.rect(game.screen, settings.DEBUG_PANEL_BG_COLOR, panel_rect)

        self._draw_main_info(game)
        # Draw links from right to left to position them correctly relative to each other
        self._draw_exit_link(game)
        self._draw_new_link(game)
        self._draw_show_globe_link(game)