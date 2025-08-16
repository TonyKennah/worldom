from __future__ import annotations
from typing import Optional, Tuple, TYPE_CHECKING, Dict

import os
import time
import pygame
import src.utils.settings as settings

if TYPE_CHECKING:
    from src.core.game import Game


def _ensure_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


class DebugPanel:
    """Handles rendering and interaction for the top debug panel."""
    def __init__(self) -> None:
        # Fonts
        self.font = pygame.font.SysFont("Arial", getattr(settings, "DEBUG_PANEL_FONT_SIZE", 16))
        self.small_font = pygame.font.SysFont("Arial", max(10, int(getattr(settings, "DEBUG_PANEL_FONT_SIZE", 16) * 0.85)))

        # Link hit-rects (legacy, preserved)
        self.exit_link_rect: Optional[pygame.Rect] = None
        self.new_link_rect: Optional[pygame.Rect] = None
        self.show_globe_link_rect: Optional[pygame.Rect] = None
        self.self_link_rect: Optional[pygame.Rect] = None

        # NEW link hit-rects
        self.pause_link_rect: Optional[pygame.Rect] = None
        self.perf_link_rect: Optional[pygame.Rect] = None
        self.screenshot_link_rect: Optional[pygame.Rect] = None
        self.copy_coords_link_rect: Optional[pygame.Rect] = None

        # Local toggles/state (draw-only; game owns real state)
        self.show_perf_details: bool = True
        self._fps_ema: float = 0.0  # smoothed FPS display

        # Tooltips
        self._hover_tooltip: Optional[str] = None
        self._tooltip_pos: Tuple[int, int] = (0, 0)

    # ------------------------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, game: Optional[Game] = None) -> Optional[str]:
        """
        Handles events for the debug panel.
        Returns an action string ('exit', 'new_map', 'show_globe', 'hide_globe', 'focus_on_player', ...)
        or None.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.exit_link_rect and self.exit_link_rect.collidepoint(event.pos):
                return "exit"  # Signal to exit
            if self.new_link_rect and self.new_link_rect.collidepoint(event.pos):
                return "new_map"  # Signal to create a new map
            if self.show_globe_link_rect and self.show_globe_link_rect.collidepoint(event.pos):
                # If we know the game, toggle; otherwise keep original behavior
                if game is not None:
                    return "hide_globe" if getattr(game.ui_manager, "show_globe_popup", False) else "show_globe"
                return "show_globe"
            if self.self_link_rect and self.self_link_rect.collidepoint(event.pos):
                return "focus_on_player"
            if self.pause_link_rect and self.pause_link_rect.collidepoint(event.pos):
                return "toggle_pause"
            if self.perf_link_rect and self.perf_link_rect.collidepoint(event.pos):
                self.show_perf_details = not self.show_perf_details
                return "toggle_perf_overlay"
            if self.screenshot_link_rect and self.screenshot_link_rect.collidepoint(event.pos):
                # Panel can handle the screenshot immediately
                if game is not None:
                    self._save_screenshot(game)
                return "screenshot"
            if self.copy_coords_link_rect and self.copy_coords_link_rect.collidepoint(event.pos):
                if game is not None:
                    self._copy_coords_to_clipboard(game)
                return "copy_coords"
        return None

    # ------------------------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------------------------
    def _draw_main_info(self, game: Game) -> None:
        """Draws the main informational text (FPS, zoom, coords, selection, etc.)."""
        world_pos = game.camera.screen_to_world(pygame.mouse.get_pos())
        world_coords = f"({int(world_pos.x)}, {int(world_pos.y)})"
        zoom_percentage = game.camera.zoom_state.current * 100

        # FPS & frame time (smoothed)
        fps = float(game.clock.get_fps() or 0.0)
        alpha = 0.15
        self._fps_ema = (1.0 - alpha) * self._fps_ema + alpha * fps
        frame_ms = 1000.0 / max(self._fps_ema, 0.0001)

        info_parts = [
            f"FPS: {self._fps_ema:4.1f} ({frame_ms:4.1f} ms)",
            f"Zoom: {zoom_percentage:.0f}%",
            f"World: {world_coords}",
        ]

        # Tile/terrain details
        if game.world_state.hovered_tile:
            tile_x, tile_y = game.world_state.hovered_tile
            terrain_key = game.map.data[tile_y % game.map.height][tile_x % game.map.width]
            terrain_name = settings.TERRAIN_DATA.get(terrain_key, {}).get("name", terrain_key.capitalize())
            info_parts.append(f"Tile: ({tile_x}, {tile_y}) {terrain_name}")

        # Extra perf/system details (optional)
        if self.show_perf_details:
            try:
                import psutil  # optional; not required
                proc = psutil.Process()
                rss_mb = proc.memory_info().rss / (1024 * 1024)
                info_parts.append(f"RAM: {rss_mb:.0f} MB")
            except Exception:
                pass

            # Unit stats (safe)
            try:
                info_parts.append(f"Units: {len(game.world_state.units)} Sel: {len(game.world_state.selected_units)}")
            except Exception:
                pass

            # Theme/seed (safe)
            theme_name = getattr(settings, "ACTIVE_THEME_NAME", None)
            if theme_name:
                info_parts.append(f"Theme: {theme_name}")

        info_string = " | ".join(info_parts)
        text_surface = self.font.render(info_string, True, getattr(settings, "DEBUG_PANEL_FONT_COLOR", (220, 220, 230)))
        text_y = (getattr(settings, "DEBUG_PANEL_HEIGHT", 28) - text_surface.get_height()) // 2
        game.screen.blit(text_surface, (10, text_y))

    def _draw_link(
        self,
        game: Game,
        text: str,
        topright: Tuple[int, int],
        *,
        tooltip: Optional[str] = None,
        disabled: bool = False,
    ) -> pygame.Rect:
        """Draws a clickable link with padding and hover effect."""
        color = getattr(settings, "DEBUG_PANEL_FONT_COLOR", (220, 220, 230))
        color_disabled = (140, 140, 145)
        text_surface = self.font.render(text, True, color_disabled if disabled else color)

        # Create a padded rect for the link to make the clickable area larger.
        padding_x = 8
        link_rect = text_surface.get_rect()
        link_rect.width += padding_x * 2
        link_rect.height = getattr(settings, "DEBUG_PANEL_HEIGHT", 28)
        link_rect.topright = topright

        # Check for hover and draw a highlight background if needed.
        mouse_pos = pygame.mouse.get_pos()
        if not disabled and link_rect.collidepoint(mouse_pos):
            hover_col = getattr(settings, "DEBUG_PANEL_LINK_HOVER_BG_COLOR", (60, 60, 72))
            pygame.draw.rect(game.screen, hover_col, link_rect, border_radius=4)
            # Record tooltip for later draw
            self._hover_tooltip = tooltip
            self._tooltip_pos = (mouse_pos[0], link_rect.bottom)

        # Draw the text centered in the link rect.
        text_rect = text_surface.get_rect(center=link_rect.center)
        game.screen.blit(text_surface, text_rect)

        return link_rect

    def _draw_tooltip(self, game: Game) -> None:
        """Draw hover tooltip if set for this frame."""
        if not self._hover_tooltip:
            return
        tip = self._hover_tooltip
        x, y = self._tooltip_pos
        surf = self.small_font.render(tip, True, (235, 235, 240))
        padding = 6
        rect = surf.get_rect()
        rect.topleft = (x + 10, y + 4)
        bg_rect = pygame.Rect(rect.left - padding, rect.top - padding, rect.width + 2 * padding, rect.height + 2 * padding)
        pygame.draw.rect(game.screen, (25, 25, 28, 220), bg_rect, border_radius=5)
        pygame.draw.rect(game.screen, (180, 180, 188), bg_rect, width=1, border_radius=5)
        game.screen.blit(surf, rect)
        # Reset after draw
        self._hover_tooltip = None

    # ---- legacy links (kept) + new links ------------------------------------------------
    def _draw_exit_link(self, game: Game) -> None:
        """Draws the clickable 'Exit' link."""
        self.exit_link_rect = self._draw_link(game, "Exit", (settings.SCREEN_WIDTH - 10, 0), tooltip="Quit the game")

    def _draw_new_link(self, game: Game) -> None:
        """Draws the clickable 'New' link."""
        if not self.exit_link_rect:
            return
        spacing = 5
        topright = (self.exit_link_rect.left - spacing, 0)
        self.new_link_rect = self._draw_link(game, "New", topright, tooltip="Generate a new world")

    def _draw_show_globe_link(self, game: Game) -> None:
        """Draws the clickable 'Show Globe' / 'Hide Globe' link."""
        if not self.new_link_rect:
            return
        spacing = 5
        topright = (self.new_link_rect.left - spacing, 0)
        # Toggle label if possible
        show = True
        try:
            show = not bool(game.ui_manager.show_globe_popup)
        except Exception:
            pass
        label = "Show Globe" if show else "Hide Globe"
        self.show_globe_link_rect = self._draw_link(game, label, topright, tooltip="View rotating planet preview")

    def _draw_self_link(self, game: Game) -> None:
        """Draws the clickable 'Self' link."""
        if not self.show_globe_link_rect:
            return
        spacing = 5
        topright = (self.show_globe_link_rect.left - spacing, 0)
        self.self_link_rect = self._draw_link(game, "Self", topright, tooltip="Center camera on player")

    # ---- NEW utility links --------------------------------------------------------------
    def _draw_pause_link(self, game: Game) -> None:
        """Draw a pause/resume toggle."""
        base_rect = self.self_link_rect or self.show_globe_link_rect or self.new_link_rect or self.exit_link_rect
        if not base_rect:
            return
        spacing = 5
        topright = (base_rect.left - spacing, 0)
        paused = getattr(game.world_state, "paused", False)
        label = "Resume" if paused else "Pause"
        self.pause_link_rect = self._draw_link(
            game, label, topright,
            tooltip="Pause/resume simulation"
        )

    def _draw_perf_link(self, game: Game) -> None:
        """Draw a toggle for extra perf info in the panel."""
        base_rect = self.pause_link_rect or self.self_link_rect
        if not base_rect:
            return
        spacing = 5
        topright = (base_rect.left - spacing, 0)
        label = "Perf: On" if self.show_perf_details else "Perf: Off"
        self.perf_link_rect = self._draw_link(
            game, label, topright, tooltip="Toggle performance overlay"
        )

    def _draw_screenshot_link(self, game: Game) -> None:
        """Draw a link to capture a screenshot."""
        base_rect = self.perf_link_rect or self.pause_link_rect
        if not base_rect:
            return
        spacing = 5
        topright = (base_rect.left - spacing, 0)
        self.screenshot_link_rect = self._draw_link(
            game, "Shot", topright, tooltip="Save a screenshot to disk"
        )

    def _draw_copy_coords_link(self, game: Game) -> None:
        """Draw a link to copy world coordinates under the mouse."""
        base_rect = self.screenshot_link_rect or self.perf_link_rect
        if not base_rect:
            return
        spacing = 5
        topright = (base_rect.left - spacing, 0)
        self.copy_coords_link_rect = self._draw_link(
            game, "CopyXY", topright, tooltip="Copy world coords under mouse"
        )

    def draw(self, game: Game) -> None:
        """Renders the complete debug panel by calling its helper methods."""
        panel_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, getattr(settings, "DEBUG_PANEL_HEIGHT", 28))
        pygame.draw.rect(game.screen, getattr(settings, "DEBUG_PANEL_BG_COLOR", (22, 22, 26)), panel_rect, border_radius=0)

        # Reset tooltip each frame
        self._hover_tooltip = None

        self._draw_main_info(game)

        # Draw links from right to left to position them correctly relative to each other
        self._draw_exit_link(game)
        self._draw_new_link(game)
        self._draw_show_globe_link(game)
        self._draw_self_link(game)

        # NEW links
        self._draw_pause_link(game)
        self._draw_perf_link(game)
        self._draw_screenshot_link(game)
        self._draw_copy_coords_link(game)

        # Tooltip last so it overlays links
        self._draw_tooltip(game)

        # Optional status badges (e.g., paused)
        self._draw_status_badges(game)

    # ------------------------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------------------------
    def _draw_status_badges(self, game: Game) -> None:
        """Draw small non-interactive badges at the far-left under the info line."""
        y = int(getattr(settings, "DEBUG_PANEL_HEIGHT", 28) / 2) + 2
        x = 10
        badges: Dict[str, Tuple[Tuple[int, int, int], bool]] = {
            "PAUSED": ((212, 160, 70), getattr(game.world_state, "paused", False)),
            "GLOBE": ((120, 180, 255), getattr(game.ui_manager, "show_globe_popup", False)),
        }
        for label, (color, enabled) in badges.items():
            if not enabled:
                continue
            surf = self.small_font.render(label, True, (0, 0, 0))
            pad = 4
            rect = surf.get_rect()
            rect.topleft = (x + pad, y)
            bg = pygame.Rect(rect.left - pad, rect.top - 2, rect.width + 2 * pad, rect.height + 4)
            pygame.draw.rect(game.screen, color, bg, border_radius=4)
            pygame.draw.rect(game.screen, (0, 0, 0), bg, width=1, border_radius=4)
            game.screen.blit(surf, rect)
            x = bg.right + 6

    def _save_screenshot(self, game: Game) -> Optional[str]:
        """Save a screenshot to ./screenshots with a timestamped filename."""
        try:
            folder = os.path.join(os.getcwd(), "screenshots")
            _ensure_dir(folder)
            ts = time.strftime("%Y%m%d_%H%M%S")
            fname = os.path.join(folder, f"WorldDom_{ts}.png")
            pygame.image.save(game.screen, fname)
            print(f"[DebugPanel] Screenshot saved to: {fname}")
            return fname
        except Exception as e:
            print(f"[DebugPanel] Screenshot failed: {e}")
            return None

    def _copy_coords_to_clipboard(self, game: Game) -> None:
        """Copy current world coords under mouse to clipboard (best-effort)."""
        try:
            world_pos = game.camera.screen_to_world(pygame.mouse.get_pos())
            txt = f"{int(world_pos.x)},{int(world_pos.y)}"
            try:
                # Prefer pygame.scrap if available
                if not pygame.scrap.get_init():
                    pygame.scrap.init()
                pygame.scrap.put(pygame.SCRAP_TEXT, txt.encode("utf-8"))
                print(f"[DebugPanel] Copied coords: {txt}")
            except Exception:
                # Fallback: print to console
                print(f"[DebugPanel] Coords: {txt}")
        except Exception as e:
            print(f"[DebugPanel] Copy coords failed: {e}")
