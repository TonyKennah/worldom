# c:/prj/WorldDom/src/gameplay/capture_points.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Tuple, Dict, Optional
import math
import pygame


Color = Tuple[int, int, int]
Vec2 = pygame.math.Vector2


# ------------------------------- Factions & helpers -------------------------------

FACTION_PLAYER = "player"
FACTION_AI     = "ai"
FACTION_NEUT   = "neutral"

OWNER_COLORS: Dict[str, Color] = {
    FACTION_PLAYER: (72, 196, 255),
    FACTION_AI:     (255, 88, 88),
    FACTION_NEUT:   (180, 180, 180),
}

RING_BG = (30, 30, 36)
NAME_COL = (240, 240, 240)


def _dist(a: Vec2 | Tuple[float, float], b: Vec2 | Tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = ax - bx, ay - by
    return math.hypot(dx, dy)


def _classify_unit(u) -> str:
    """
    Try to determine unit faction. Falls back to 'player' if unknown.
    Expected optional attributes on Unit:
      - u.faction -> "player"/"ai"
      - u.is_enemy -> bool  (true means 'ai')
      - u.team or u.owner (ignored by default; extend as needed)
    """
    if getattr(u, "is_enemy", False):
        return FACTION_AI
    f = getattr(u, "faction", None)
    if f in (FACTION_PLAYER, FACTION_AI, FACTION_NEUT):
        return f
    return FACTION_PLAYER


def _unit_world_pos(u) -> Vec2:
    """
    Resolve a unit's position as Vec2.
    Expected attributes:
      - u.world_pos: pygame.Vector2
      - else u.pos or u.position as tuple
    """
    if hasattr(u, "world_pos"):
        return Vec2(u.world_pos.x, u.world_pos.y)  # noqa: UP015
    if hasattr(u, "pos"):
        px, py = getattr(u, "pos")
        return Vec2(px, py)
    if hasattr(u, "position"):
        px, py = getattr(u, "position")
        return Vec2(px, py)
    # Last resort – don't break, just pretend they are off-screen
    return Vec2(-10_000, -10_000)


# ------------------------------- Capture Point model -------------------------------

@dataclass
class CapturePoint:
    name: str
    world_pos: Vec2 | Tuple[float, float]
    radius: float = 140.0
    income_per_sec: float = 6.0
    # capture meter: -1.0 (AI) .. 0.0 (neutral) .. 1.0 (Player)
    meter: float = 0.0
    owner: str = FACTION_NEUT
    # Tuning
    cap_speed_per_unit: float = 0.18  # per second per net unit
    decay_when_empty: float = 0.08    # per second toward 0 when nobody nearby

    # Internal draw cache
    _label_surf: Optional[pygame.Surface] = field(default=None, repr=False, compare=False)

    def update(
        self,
        units: Iterable[object],
        dt: float,
        *,
        influence_scale: float = 1.0
    ) -> None:
        """Update capture logic based on nearby units."""
        if dt <= 0.0:
            return

        pos = Vec2(self.world_pos)
        # Count presence by faction in the circle
        p_count = 0
        a_count = 0
        r = float(self.radius)

        for u in units:
            # skip dead units if possible
            if getattr(u, "dead", False) or getattr(u, "hp", 1) <= 0:
                continue
            upos = _unit_world_pos(u)
            if _dist(upos, pos) <= r:
                fac = _classify_unit(u)
                if fac == FACTION_PLAYER:
                    p_count += 1
                elif fac == FACTION_AI:
                    a_count += 1

        net = p_count - a_count
        if net == 0:
            # Nobody dominating: decay toward neutral (0)
            if self.meter > 0.0:
                self.meter = max(0.0, self.meter - self.decay_when_empty * dt)
            elif self.meter < 0.0:
                self.meter = min(0.0, self.meter + self.decay_when_empty * dt)
        else:
            # push meter toward side with advantage
            self.meter += (self.cap_speed_per_unit * influence_scale) * float(net) * dt
            self.meter = max(-1.0, min(1.0, self.meter))

        # Determine owner from meter with hysteresis
        prev_owner = self.owner
        if self.meter >= 0.9:
            self.owner = FACTION_PLAYER
        elif self.meter <= -0.9:
            self.owner = FACTION_AI
        elif -0.3 < self.meter < 0.3:
            self.owner = FACTION_NEUT

        # Invalidate cached name surface if color changed
        if self.owner != prev_owner:
            self._label_surf = None

    def income(self) -> float:
        return self.income_per_sec if self.owner == FACTION_PLAYER else 0.0


# ------------------------------- Manager -------------------------------

class CapturePointManager:
    def __init__(
        self,
        points: List[CapturePoint],
        resource_pool,  # object with add_credits(float)
        *,
        font: Optional[pygame.font.Font] = None
    ) -> None:
        self.points: List[CapturePoint] = points
        self.res = resource_pool
        self.font = font or pygame.font.SysFont("Arial", 16)
        self._ring_thickness = 4

    # ---- Simulation ----
    def update(self, dt: float, units: Iterable[object]) -> None:
        total_income = 0.0
        for p in self.points:
            p.update(units, dt)
            total_income += p.income()
        if total_income > 0:
            self.res.add_credits(total_income * dt)

    # ---- Rendering ----
    def _world_to_screen(self, camera, wpos: Vec2 | Tuple[float, float]) -> Tuple[int, int]:
        try:
            v = camera.world_to_screen((float(wpos[0]), float(wpos[1])))
            return int(v[0]), int(v[1])
        except Exception:
            # Best effort: assume 1:1 projection (debug)
            return int(wpos[0]), int(wpos[1])

    def draw(self, surface: pygame.Surface, camera) -> None:
        for p in self.points:
            sx, sy = self._world_to_screen(camera, p.world_pos)
            # Outer ring (control radius)
            pygame.draw.circle(surface, RING_BG, (sx, sy), int(p.radius), width=1)

            # Control progress ring (from -1..1)
            prog = (p.meter + 1.0) * 0.5  # 0..1
            # Draw a 360° arc as several short arcs to avoid heavy trigs
            steps = 48
            fill_steps = int(prog * steps)
            col = OWNER_COLORS.get(p.owner, (200, 200, 200))
            for i in range(fill_steps):
                a0 = (i / steps) * math.tau
                a1 = ((i + 1) / steps) * math.tau
                x0 = sx + int(math.cos(a0) * (p.radius + 4))
                y0 = sy + int(math.sin(a0) * (p.radius + 4))
                x1 = sx + int(math.cos(a1) * (p.radius + 4))
                y1 = sy + int(math.sin(a1) * (p.radius + 4))
                pygame.draw.line(surface, col, (x0, y0), (x1, y1), self._ring_thickness)

            # Center flag / dot
            pygame.draw.circle(surface, col, (sx, sy), 6)

            # Name label (cached per color)
            if p._label_surf is None:
                txt = f"{p.name} (+{int(p.income_per_sec)}/s)" if p.income_per_sec > 0 else p.name
                p._label_surf = self.font.render(txt, True, NAME_COL)
            rect = p._label_surf.get_rect(midbottom=(sx, sy - int(p.radius) - 8))
            surface.blit(p._label_surf, rect)
