# c:/prj/WorldDom/src/gameplay/resources.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional
import pygame

BAR_BG   = (24, 26, 30)
BAR_FG   = (74, 199, 120)
BAR_TEXT = (235, 235, 240)
BAR_BAD  = (230, 90, 90)


@dataclass
class ResourcePool:
    credits: float = 0.0
    income_ui_smoothing: float = 0.92  # 0..1, higher = smoother
    _smoothed_income: float = 0.0

    def add_credits(self, amount: float) -> None:
        self.credits = max(0.0, float(self.credits) + float(amount))
        # Track income as short pulses; the UI will smooth
        self._smoothed_income = self._smoothed_income * self.income_ui_smoothing + amount * (1.0 - self.income_ui_smoothing)

    def spend(self, amount: float) -> bool:
        amt = float(amount)
        if self.credits >= amt:
            self.credits -= amt
            return True
        return False

    # Optional integration point if you ever want time‑based drains
    def update(self, dt: float) -> None:
        # nothing to do now; hook drains here
        pass

    # ---------------- UI ---------------
    def draw(self, surface: pygame.Surface, topleft: Tuple[int, int] = (12, 8)) -> None:
        """Draw a compact bar in the top-left. No images needed."""
        x, y = topleft
        w, h = 240, 24

        pygame.draw.rect(surface, BAR_BG, (x, y, w, h), border_radius=6)
        # Fill portion shows 0..(credits/target). Here we clamp at 2k for display niceness
        show_cap = 2000.0
        frac = max(0.0, min(1.0, self.credits / show_cap))
        if frac > 0:
            pygame.draw.rect(surface, BAR_FG, (x+2, y+2, int((w-4) * frac), h-4), border_radius=5)

        font = pygame.font.SysFont("Consolas,Arial", 16)
        txt = f"Credits: {int(self.credits):>5}   Δ {self._format_income(self._smoothed_income)}"
        surf = font.render(txt, True, BAR_TEXT)
        surface.blit(surf, (x + 8, y + 3))

    @staticmethod
    def _format_income(v: float) -> str:
        # Show +x.x/s or -x.x/s
        sgn = "+" if v >= 0 else "-"
        return f"{sgn}{abs(v):.1f}/s"
