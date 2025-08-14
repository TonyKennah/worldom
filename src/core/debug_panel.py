from __future__ import annotations
from typing import Optional, Tuple, TYPE_CHECKING

import pygame
import src.utils.settings as settings

if TYPE_CHECKING:
    from src.core.game import Game

class DebugPanel:
    """Handles rendering and interaction for the top debug panel."""
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("Arial", settings.DEBUG_PANEL_FONT_SIZE)
        self.exit_link_rect: Optional[pygame.Rect] = None
        self.new_link_rect: Optional[pygame.Rect] = None
        self.show_globe_link_rect: Optional[pygame.Rect] = None
        self.self_link_rect: Optional[pygame.Rect] = None

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
            if self.self_link_rect and self.self_link_rect.collidepoint(event.pos):
                return "focus_on_player"
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
            terrain_key = game.map.data[tile_y][tile_x]
            terrain_name = settings.TERRAIN_DATA.get(terrain_key, {}).get("name", terrain_key.capitalize())
            tile_info = f"({tile_x}, {tile_y}) ({terrain_name})"
            info_string += f" | Tile: {tile_info}"

        text_surface = self.font.render(info_string, True, settings.DEBUG_PANEL_FONT_COLOR)
        text_y = (settings.DEBUG_PANEL_HEIGHT - text_surface.get_height()) // 2
        game.screen.blit(text_surface, (10, text_y))

    def _draw_link(
        self,
        game: Game,
        text: str,
        topright: Tuple[int, int]
    ) -> pygame.Rect:
        """Draws a clickable link with padding and hover effect."""
        text_surface = self.font.render(text, True, settings.DEBUG_PANEL_FONT_COLOR)

        # Create a padded rect for the link to make the clickable area larger.
        padding_x = 8
        link_rect = text_surface.get_rect()
        link_rect.width += padding_x * 2
        link_rect.height = settings.DEBUG_PANEL_HEIGHT
        link_rect.topright = topright

        # Check for hover and draw a highlight background if needed.
        mouse_pos = pygame.mouse.get_pos()
        if link_rect.collidepoint(mouse_pos):
            pygame.draw.rect(game.screen, settings.DEBUG_PANEL_LINK_HOVER_BG_COLOR, link_rect, border_radius=3)

        # Draw the text centered in the link rect.
        text_rect = text_surface.get_rect(center=link_rect.center)
        game.screen.blit(text_surface, text_rect)

        return link_rect

    def _draw_exit_link(self, game: Game) -> None:
        """Draws the clickable 'Exit' link."""
        self.exit_link_rect = self._draw_link(game, "Exit", (settings.SCREEN_WIDTH - 10, 0))

    def _draw_new_link(self, game: Game) -> None:
        """Draws the clickable 'New' link."""
        if not self.exit_link_rect:
            return
        spacing = 5
        topright = (self.exit_link_rect.left - spacing, 0)
        self.new_link_rect = self._draw_link(game, "New", topright)

    def _draw_show_globe_link(self, game: Game) -> None:
        """Draws the clickable 'Show Globe' link."""
        if not self.new_link_rect:
            return
        spacing = 5
        topright = (self.new_link_rect.left - spacing, 0)
        self.show_globe_link_rect = self._draw_link(game, "Show Globe", topright)

    def _draw_self_link(self, game: Game) -> None:
        """Draws the clickable 'Self' link."""
        if not self.show_globe_link_rect:
            return
        spacing = 5
        topright = (self.show_globe_link_rect.left - spacing, 0)
        self.self_link_rect = self._draw_link(game, "Self", topright)

    def draw(self, game: Game) -> None:
        """Renders the complete debug panel by calling its helper methods."""
        panel_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.DEBUG_PANEL_HEIGHT)
        pygame.draw.rect(game.screen, settings.DEBUG_PANEL_BG_COLOR, panel_rect)

        self._draw_main_info(game)
        # Draw links from right to left to position them correctly relative to each other
        self._draw_exit_link(game)
        self._draw_new_link(game)
        self._draw_show_globe_link(game)
        self._draw_self_link(game)