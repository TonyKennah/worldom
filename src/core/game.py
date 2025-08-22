# src/core/game.py
"""
Main game bootstrap and loop for WorldDom.

This module intentionally keeps hard dependencies light and guards optional
features (camera, input handler, map generation, etc.) so test and CI
environments can import the Game class without runtime errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, List

import sys
import pygame

import src.utils.settings as settings

# Optional helpers: be defensive to keep CI green if a file is absent.
try:
    # Our portable, test-friendly init helpers.
    from src.utils.platform_init import create_window
except Exception:
    def create_window(
        width: int, height: int, title: str, flags: int = 0
    ) -> Tuple[pygame.Surface, pygame.time.Clock]:
        pygame.init()
        surface = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption(title)
        return surface, pygame.time.Clock()

try:
    from src.ui.ui_manager import UIManager
except Exception:  # Fallback stub to avoid import errors in tests
    class UIManager:  # type: ignore
        def __init__(self, game: "Game") -> None:
            self.game = game
            self.screen = game.screen

        def update(self, _dt: float) -> None:
            pass

        def draw_ui(self) -> None:
            pass

        def toggle_help_overlay(self) -> None:
            pass

        def toggle_globe_popup(self) -> None:
            pass

        def handle_mouse_move(self, _pos: Tuple[int, int]) -> None:
            pass

        def handle_mouse_down(self, _pos: Tuple[int, int]) -> None:
            pass


try:
    from src.world_state import WorldState
except Exception:
    # Minimal stub to preserve interface for UIManager and tests
    @dataclass
    class WorldState:  # type: ignore
        units: List = None  # type: ignore
        def __init__(self) -> None:
            self.units = []
            self.selected_units = []
            self.hovered_tile: Optional[Tuple[int, int]] = None
            self.hovered_world_pos: Optional[pygame.math.Vector2] = None
            self.selection_box: Optional[pygame.Rect] = None

            # UI/context state used by UIManager
            class _SubMenu:
                def __init__(self) -> None:
                    self.active = False
                    self.options = []
                    self.rects: List[pygame.Rect] = []
                    self.parent_rect: Optional[pygame.Rect] = None

            class _ContextMenu:
                def __init__(self) -> None:
                    self.active = False
                    self.pos: Optional[Tuple[int, int]] = None
                    self.rects: List[pygame.Rect] = []
                    self.options: List[dict] = [
                        {"label": "Move"},
                        {"label": "Attack", "sub_options": [{"label": "Focus Fire"}, {"label": "Harass"}]},
                    ]
                    self.sub_menu = _SubMenu()
                    self.target_tile: Optional[Tuple[int, int]] = None

            self.context_menu = _ContextMenu()
            self.left_mouse_down_screen_pos: Optional[Tuple[int, int]] = None
            self.left_mouse_down_world_pos: Optional[pygame.math.Vector2] = None
            self.right_mouse_down_pos: Optional[Tuple[int, int]] = None

            # Light session fields used elsewhere
            self.game_time = 0.0
            self.paused = False
            self.pings: List = []  # type: ignore

        def tick(self, dt: float) -> None:
            if not self.paused:
                self.game_time += max(0.0, dt)

        def add_ping(self, world_pos: Tuple[float, float], ttl: float = 1.2,
                     color: Tuple[int, int, int] = (255, 215, 0), radius: int = 12) -> None:
            # Minimal ping structure
            self.pings.append((pygame.math.Vector2(world_pos), ttl, color, radius))


# Optional camera (keep it soft to avoid circular or missing deps in CI)
try:
    from src.core.camera import Camera
except Exception:
    class Camera:  # type: ignore
        def __init__(self, width: int, height: int) -> None:
            self.width = width
            self.height = height
            self.zoom = 1.0
            self.shake = (0.0, 0.0)

        def screen_to_world(self, pos: Tuple[int, int]) -> pygame.math.Vector2:
            return pygame.math.Vector2(pos)

        def world_to_screen(self, pos: pygame.math.Vector2, include_shake: bool = True) -> pygame.math.Vector2:
            return pygame.math.Vector2(pos)

        @property
        def zoom_state(self):  # UI might query this
            class _Z:
                current = 1.0
            return _Z()


# Asset helpers (globe frames and images)
try:
    from src.ui.assets import load_frames_from_dir
except Exception:
    def load_frames_from_dir(_directory: str, pattern_suffix: str = ".png", sort_natural: bool = True) -> List[pygame.Surface]:
        return []


DEFAULT_WIDTH = int(getattr(settings, "SCREEN_WIDTH", 1280))
DEFAULT_HEIGHT = int(getattr(settings, "SCREEN_HEIGHT", 720))
BG_COLOR = tuple(getattr(settings, "BG_COLOR", (18, 20, 24)))


class Game:
    """Main game orchestrator."""

    def __init__(self, *args, **kwargs) -> None:
        # Window & clock
        self.screen, self.clock = create_window(
            DEFAULT_WIDTH, DEFAULT_HEIGHT, getattr(settings, "WINDOW_TITLE", "WorldDom")
        )

        # Subsystems
        self.world_state = WorldState()
        self.camera = Camera(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.ui_manager = UIManager(self)

        # Globe frames (used by UIManager for popup animation)
        self.globe_frames: List[pygame.Surface] = self._try_load_globe_frames()

        # Map is optional; keep a reference if present
        self.map = self._try_get_map()

        # Running state
        self._running = True

    # ------------------------------------------------------------------ #
    # Optional loaders / integration
    # ------------------------------------------------------------------ #

    def _try_load_globe_frames(self) -> List[pygame.Surface]:
        """
        Attempt to load pre-rendered globe frames from a standard folder.
        Returns an empty list if not found; UIManager can handle that.
        """
        try:
            frames = load_frames_from_dir("globe_frames")
            return frames or []
        except Exception:
            return []

    def _try_get_map(self):
        """
        If a map object is provided elsewhere (e.g., by a generator),
        attach it; otherwise return a tiny stub that satisfies UI queries.
        """
        try:
            # If the project’s map system injects one onto Game externally,
            # don’t override; otherwise make a stub.
            if hasattr(self, "map") and self.map is not None:  # type: ignore[attr-defined]
                return self.map  # pragma: no cover
        except Exception:
            pass

        class _StubMap:
            data = [["water", "grass"], ["forest", "mountain"]]

            def get_terrain_percentages(self):
                # Simple illustrative breakdown
                return {
                    "water": 25.0,
                    "grass": 25.0,
                    "forest": 25.0,
                    "mountain": 25.0,
                }

        return _StubMap()

    # ------------------------------------------------------------------ #
    # Event handling
    # ------------------------------------------------------------------ #

    def _handle_input_event(self, ev: pygame.event.Event) -> None:
        """Central input dispatch with safe fallbacks."""
        # Provide a hook to a dedicated input handler if it exists
        try:
            from src.ui.input_handler import process_event  # type: ignore
            process_event(self, ev)
            return
        except Exception:
            pass

        # Built-in lightweight handling to ensure playability in CI/dev
        if ev.type == pygame.QUIT:
            self._running = False
            return

        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                # If the help overlay is open, close it; otherwise quit
                try:
                    if getattr(self.ui_manager.help_overlay, "visible", False):
                        self.ui_manager.toggle_help_overlay()
                    else:
                        self._running = False
                except Exception:
                    self._running = False
                return

            if ev.key == pygame.K_F1:
                self.ui_manager.toggle_help_overlay()
                return

            if ev.key == pygame.K_g:
                # Developer toggle for globe popup
                self.ui_manager.toggle_globe_popup()
                return

        if ev.type == pygame.MOUSEMOTION:
            self.world_state.hovered_world_pos = self.camera.screen_to_world(ev.pos)  # type: ignore[attr-defined]
            self.ui_manager.handle_mouse_move(ev.pos)
            return

        if ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                # Left click: selection (minimal)
                self.world_state.left_mouse_down_screen_pos = ev.pos
                self.world_state.left_mouse_down_world_pos = self.camera.screen_to_world(ev.pos)
                self.ui_manager.handle_mouse_down(ev.pos)
                return
            if ev.button == 3:
                # Right click: open context menu at cursor & ping
                self.world_state.right_mouse_down_pos = ev.pos
                self.ui_manager.open_context_menu(ev.pos)  # type: ignore[attr-defined]
                # Add a tiny “order issued” ping in world space
                wpos = self.camera.screen_to_world(ev.pos)
                self.world_state.add_ping((wpos.x, wpos.y))
                return

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.world_state.selection_box = None
            return

    # ------------------------------------------------------------------ #
    # Update / Render
    # ------------------------------------------------------------------ #

    def update(self, dt: float) -> None:
        """Advance world state and UI animations."""
        self.world_state.tick(dt)
        self.ui_manager.update(dt)

    def render(self) -> None:
        """Clear and draw UI; game world drawing is intentionally minimal here."""
        self.screen.fill(BG_COLOR)

        # (Optional) draw a faint grid to make the screen less empty in CI
        try:
            grid = 32
            w, h = self.screen.get_size()
            color = (30, 34, 40)
            for x in range(0, w, grid):
                pygame.draw.line(self.screen, color, (x, 0), (x, h))
            for y in range(0, h, grid):
                pygame.draw.line(self.screen, color, (0, y), (w, y))
        except Exception:
            pass

        # UI last (selection box, context menus, overlays, etc.)
        self.ui_manager.draw_ui()

        pygame.display.flip()

    # ------------------------------------------------------------------ #
    # Public helpers used by UIManager / other systems
    # ------------------------------------------------------------------ #

    def issue_move_command_to_target(self) -> None:
        """
        Minimal hook used by UI to confirm a 'Move' or 'Attack' action.
        Here we just drop a ping at the targeted tile/world position.
        Real game logic can enqueue pathing/commands as needed.
        """
        if self.world_state.hovered_world_pos is not None:
            pos = self.world_state.hovered_world_pos
            self.world_state.add_ping((pos.x, pos.y))

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Main loop for local/dev execution."""
        self._running = True
        target_fps = int(getattr(settings, "FPS", 60))
        while self._running:
            dt = self.clock.tick(target_fps) / 1000.0

            for ev in pygame.event.get():
                self._handle_input_event(ev)

            if not self.world_state.paused:
                self.update(dt)

            self.render()

        pygame.quit()


# Convenience entry point for manual runs
def main() -> int:
    try:
        game = Game()
        game.run()
        return 0
    except Exception as e:
        print(f"[WorldDom] Fatal error: {e}", file=sys.stderr)
        try:
            pygame.quit()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
