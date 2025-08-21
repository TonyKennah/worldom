# c:/prj/WorldDom/src/ui/minimap.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional, Iterable
import pygame

MM_BG    = (18, 18, 22)
MM_GRID  = (34, 38, 45)
MM_BORDER= (70, 74, 82)
MM_UNIT  = (240, 240, 240)
MM_ENEMY = (255, 92, 92)
MM_CP    = (255, 215, 0)
MM_VIEW  = (100, 180, 255)


def _infer_world_bounds(game) -> Tuple[int, int]:
    """
    Try to infer world size in pixels.
    Heuristics:
      - game.map.data as grid of tiles + game.map.tile_size
      - game.map.pixel_size (w,h)
      - fall back to (4096, 4096)
    """
    try:
        data = game.map.data  # type: ignore[attr-defined]
        tsize = getattr(game.map, "tile_size", 64)
        h = len(data)
        w = len(data[0]) if h > 0 else 0
        return int(w * tsize), int(h * tsize)
    except Exception:
        try:
            w, h = game.map.pixel_size  # type: ignore[attr-defined]
            return int(w), int(h)
        except Exception:
            return 4096, 4096


@dataclass
class MiniMap:
    width: int = 180
    height: int = 180
    margin: int = 10
    anchor: str = "topright"  # "topleft"|"topright"
    rect: pygame.Rect = pygame.Rect(0, 0, 1, 1)

    def _place(self, screen_size: Tuple[int, int]) -> None:
        sw, sh = screen_size
        if self.anchor == "topright":
            x = sw - self.margin - self.width
            y = self.margin
        else:
            x = self.margin
            y = self.margin
        self.rect = pygame.Rect(x, y, self.width, self.height)

    def update(self, game) -> None:
        self._place(game.screen.get_size())

    def _world_to_mm(self, w: Tuple[float, float], world_w: int, world_h: int) -> Tuple[int, int]:
        wx, wy = w
        sx = self.rect.x + int((wx / max(1, world_w)) * self.rect.w)
        sy = self.rect.y + int((wy / max(1, world_h)) * self.rect.h)
        return sx, sy

    def _mm_to_world(self, px: int, py: int, world_w: int, world_h: int) -> Tuple[float, float]:
        fx = (px - self.rect.x) / max(1, self.rect.w)
        fy = (py - self.rect.y) / max(1, self.rect.h)
        return float(fx * world_w), float(fy * world_h)

    def draw(self, game) -> None:
        surf = game.screen
        self._place(surf.get_size())

        pygame.draw.rect(surf, MM_BG, self.rect, border_radius=6)
        pygame.draw.rect(surf, MM_BORDER, self.rect, width=1, border_radius=6)

        # optional grid
        for i in range(1, 3):
            x = self.rect.x + int(self.rect.w * (i / 3.0))
            y = self.rect.y + int(self.rect.h * (i / 3.0))
            pygame.draw.line(surf, MM_GRID, (x, self.rect.y), (x, self.rect.bottom), 1)
            pygame.draw.line(surf, MM_GRID, (self.rect.x, y), (self.rect.right, y), 1)

        world_w, world_h = _infer_world_bounds(game)

        # Draw capture points (if capture system present)
        cps = getattr(game, "capture_points", None)
        if cps is not None:
            for p in cps.points:
                sx, sy = self._world_to_mm((p.world_pos[0], p.world_pos[1]), world_w, world_h)
                pygame.draw.circle(surf, MM_CP, (sx, sy), 3)

        # Draw units
        for u in getattr(game.world_state, "units", []):
            pos = getattr(u, "world_pos", None)
            if pos is None:
                continue
            col = MM_ENEMY if getattr(u, "is_enemy", False) else MM_UNIT
            sx, sy = self._world_to_mm((float(pos.x), float(pos.y)), world_w, world_h)
            pygame.draw.rect(surf, col, (sx - 1, sy - 1, 3, 3))

        # Draw current camera viewport by sampling the four screen corners back to world
        try:
            tl = game.camera.screen_to_world((0, 0))
            br = game.camera.screen_to_world(game.screen.get_size())
            tr = game.camera.screen_to_world((game.screen.get_width(), 0))
            bl = game.camera.screen_to_world((0, game.screen.get_height()))
            tlp = self._world_to_mm((tl.x, tl.y), world_w, world_h)
            trp = self._world_to_mm((tr.x, tr.y), world_w, world_h)
            brp = self._world_to_mm((br.x, br.y), world_w, world_h)
            blp = self._world_to_mm((bl.x, bl.y), world_w, world_h)
            pygame.draw.lines(surf, MM_VIEW, True, [tlp, trp, brp, blp], 1)
        except Exception:
            pass

    # ----- Input handling -----
    def handle_event(self, event: pygame.event.Event, game) -> bool:
        """Click minimap to pan. Returns True if consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 2, 3):
            if self.rect.collidepoint(event.pos):
                world_w, world_h = _infer_world_bounds(game)
                wx, wy = self._mm_to_world(event.pos[0], event.pos[1], world_w, world_h)
                try:
                    # Center camera on selected world position
                    game.camera.look_at((wx, wy))  # if your camera has this API
                except Exception:
                    # Fallback: if camera has position attr
                    if hasattr(game.camera, "pos"):
                        game.camera.pos.x = wx
                        game.camera.pos.y = wy
                return True
        return False
