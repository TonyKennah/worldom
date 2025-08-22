# src/utils/dt.py
from __future__ import annotations
from collections import deque

class DtSmoother:
    """
    Smooth & clamp delta‑time to reduce simulation jitter and avoid spiral-of-death.

    Example:
        smoother = DtSmoother(max_dt=1/15, window=8)
        while running:
            dt = clock.tick(240) / 1000.0  # raw dt
            sdt = smoother(dt)
            update(sdt)
    """
    def __init__(self, *, max_dt: float = 1/15.0, window: int = 8):
        self.max_dt = float(max_dt)
        self._win = max(1, int(window))
        self._buf: deque[float] = deque(maxlen=self._win)

    def __call__(self, dt: float) -> float:
        dt = max(0.0, min(self.max_dt, float(dt)))  # clamp
        self._buf.append(dt)
        return sum(self._buf) / len(self._buf)
