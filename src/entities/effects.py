from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from .unit import Unit


class Effect:
    """Base time-limited effect."""
    remaining: float

    def update(self, unit: "Unit", dt: float) -> bool:
        self.remaining = max(0.0, self.remaining - dt)
        return self.remaining <= 0.0  # True -> remove


@dataclass
class SpeedBoost(Effect):
    multiplier: float = 1.0

    def update(self, unit: "Unit", dt: float) -> bool:
        super().update(unit, dt)
        return self.remaining <= 0.0


@dataclass
class Slow(Effect):
    multiplier: float = 1.0  # e.g. 0.7 = 30% slower

    def update(self, unit: "Unit", dt: float) -> bool:
        super().update(unit, dt)
        return self.remaining <= 0.0


@dataclass
class Stun(Effect):
    """Disables movement for duration."""
    def update(self, unit: "Unit", dt: float) -> bool:
        super().update(unit, dt)
        return self.remaining <= 0.0


@dataclass
class DamageOverTime(Effect):
    dps: float = 0.0
    show_bar: bool = True
    flash_color: Tuple[int, int, int] = (255, 120, 120)

    def update(self, unit: "Unit", dt: float) -> bool:
        if self.remaining > 0.0 and self.dps > 0.0:
            unit.apply_damage(int(self.dps * dt), show_bar=self.show_bar)
            unit.flash(self.flash_color, duration=0.06)
        return super().update(unit, dt)


@dataclass
class FlashPulse(Effect):
    color: Tuple[int, int, int] = (255, 255, 255)
    def update(self, unit: "Unit", dt: float) -> bool:
        unit.flash(self.color, duration=min(0.12, self.remaining))
        return super().update(unit, dt)


class EffectManager:
    """Holds transient effects and computes combined modifiers."""
    __slots__ = ("_effects", "_show_health_timeout", "_flash_time", "_flash_color")

    def __init__(self) -> None:
        self._effects: List[Effect] = []
        self._show_health_timeout: float = 0.0
        self._flash_time: float = 0.0
        self._flash_color: Tuple[int, int, int] = (255, 255, 255)

    # --- public API ---

    def add(self, effect: Effect) -> None:
        self._effects.append(effect)

    def add_speed_boost(self, multiplier: float, duration: float) -> None:
        self.add(SpeedBoost(remaining=max(0.0, duration), multiplier=max(0.0, multiplier)))

    def add_slow(self, multiplier: float, duration: float) -> None:
        self.add(Slow(remaining=max(0.0, duration), multiplier=max(0.0, multiplier)))

    def add_stun(self, duration: float) -> None:
        self.add(Stun(remaining=max(0.0, duration)))

    def add_dot(self, dps: float, duration: float) -> None:
        self.add(DamageOverTime(remaining=max(0.0, duration), dps=max(0.0, dps)))

    def flash(self, color: Tuple[int, int, int], duration: float) -> None:
        self._flash_color = color
        self._flash_time = max(self._flash_time, duration)

    def show_health_for(self, seconds: float) -> None:
        self._show_health_timeout = max(self._show_health_timeout, seconds)

    # --- per-frame ---

    def update(self, unit: "Unit", dt: float) -> None:
        # Status effects
        alive: List[Effect] = []
        for e in self._effects:
            if not e.update(unit, dt):
                alive.append(e)
        self._effects = alive

        # Flash decay
        if self._flash_time > 0.0:
            self._flash_time = max(0.0, self._flash_time - dt)

        # Health-bar autohide
        if self._show_health_timeout > 0.0:
            self._show_health_timeout = max(0.0, self._show_health_timeout - dt)

    # --- queries for renderer / movement ---

    def flash_ring(self) -> Optional[Tuple[Tuple[int, int, int], float]]:
        """Return (color, time_remaining) if a flash ring should be drawn."""
        if self._flash_time > 0.0:
            return (self._flash_color, self._flash_time)
        return None

    def healthbar_visible(self) -> bool:
        return self._show_health_timeout > 0.0

    def speed_multiplier(self) -> float:
        mult = 1.0
        # Stun overrides movement (handled in Unit.update())
        for e in self._effects:
            if isinstance(e, SpeedBoost):
                mult *= max(0.0, e.multiplier)
            elif isinstance(e, Slow):
                mult *= max(0.0, e.multiplier)
        return mult

    def is_stunned(self) -> bool:
        return any(isinstance(e, Stun) and e.remaining > 0.0 for e in self._effects)
