# c:/game/worldom/noise_adapter.py
"""
Noise4 adapter:
- Prefer OpenSimplex (opensimplex.OpenSimplex.noise4)
- Fallback to python-noise (noise.snoise4) with seed via base & axis offsets
- Final fallback: deterministic value noise hash
All return values are ~[-1, 1].
"""
from __future__ import annotations
import math
import random
from typing import Callable

class Noise4:
    def __init__(self, seed: int) -> None:
        self.seed = int(seed)
        self._impl = self._make_impl(seed)

    def _make_impl(self, seed: int) -> Callable[[float, float, float, float], float]:
        # Try opensimplex
        try:
            from opensimplex import OpenSimplex  # type: ignore
            gen = OpenSimplex(seed=seed)
            return lambda x, y, z, w: float(gen.noise4(x, y, z, w))
        except Exception:
            pass

        # Try python-noise (simplex)
        try:
            import noise  # type: ignore
            base = seed & 0x7fffffff
            # Slightly decorrelate axes with seed-based offsets
            ox = (seed * 0x9E3779B1) % 97
            oy = (seed * 0x85EBCA77) % 101
            oz = (seed * 0xC2B2AE3D) % 103
            ow = (seed * 0x27D4EB2F) % 107
            return lambda x, y, z, w: float(noise.snoise4(x + ox, y + oy, z + oz, w + ow, base=base))
        except Exception:
            pass

        # Fallback: deterministic value noise hash (fast)
        def hash2(i: int, j: int, k: int, l: int) -> int:
            h = (i * 0x9E3779B1) ^ (j * 0x85EBCA77) ^ (k * 0xC2B2AE3D) ^ (l * 0x27D4EB2F) ^ (seed * 0x165667B1)
            h ^= (h >> 16)
            h *= 0x7feb352d
            h ^= (h >> 15)
            h *= 0x846ca68b
            h ^= (h >> 16)
            return h & 0xffffffff

        def value_noise4(x: float, y: float, z: float, w: float) -> float:
            xi, yi, zi, wi = int(math.floor(x)), int(math.floor(y)), int(math.floor(z)), int(math.floor(w))
            xf, yf, zf, wf = x - xi, y - yi, z - zi, w - wi
            def lerp(a, b, t): return a + (b - a) * t
            def fade(t): return t * t * (3.0 - 2.0 * t)
            def rnd(i, j, k, l):
                return (hash2(i, j, k, l) / 4294967295.0) * 2.0 - 1.0
            u, v, s, t = fade(xf), fade(yf), fade(zf), fade(wf)
            # 16-corner interpolation (4D hypercube)
            acc = 0.0
            for dw in (0, 1):
                fw = t if dw else (1 - t)
                wi2 = wi + dw
                for dz in (0, 1):
                    fz = s if dz else (1 - s)
                    zi2 = zi + dz
                    for dy in (0, 1):
                        fy = v if dy else (1 - v)
                        yi2 = yi + dy
                        for dx in (0, 1):
                            fx = u if dx else (1 - u)
                            xi2 = xi + dx
                            acc += rnd(xi2, yi2, zi2, wi2) * fx * fy * fz * fw
            return acc
        return value_noise4

    def noise4(self, x: float, y: float, z: float, w: float) -> float:
        return self._impl(x, y, z, w)
