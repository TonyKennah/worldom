# starfield.py
# Enhanced 3D “warp speed” starfield with galaxies, twinkle, warp bursts,
# resizing support, and cached scaled sprites for performance.
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import math
import random
import pygame

from src.ui.image_cache import ScaledImageCache
from src.ui.assets import load_images

Color = Tuple[int, int, int]


@dataclass
class Star:
    x: float
    y: float
    z: float
    prev_z: float
    galaxy_index: Optional[int] = None
    twinkle_phase: float = 0.0
    twinkle_speed: float = 1.0


class Starfield:
    """
    A 3D 'warp speed' starfield effect with:
      - mouse-smooth warp perspective projection
      - optional galaxy sprites with cached scaling
      - twinkling stars & motion trails
      - warp/burst speed boosts
      - deterministic seeding and resize support
    """

    def __init__(
        self,
        width: int,
        height: int,
        num_stars: int,
        speed_factor: float = 50.0,
        *,
        seed: int | None = None,
        z_min: float = 1.0,
        z_max: Optional[float] = None,
        focal_length: Optional[float] = None,
        galaxy_image_names: Optional[List[str]] = None,
        max_star_size: int = 4,
        enable_twinkle: bool = True,
        enable_trails: bool = True,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.center_x = self.width * 0.5
        self.center_y = self.height * 0.5

        self.num_stars = int(max(1, num_stars))
        self.speed_factor = float(speed_factor)

        self.z_min = float(z_min)
        self.z_max = float(z_max if z_max is not None else self.width)
        self.focal_length = float(focal_length if focal_length is not None else self.width)

        self.enable_twinkle = enable_twinkle
        self.enable_trails = enable_trails
        self.max_star_size = int(max_star_size)

        self._rng = random.Random(seed)
        self._time_accum = 0.0

        # Warp burst state
        self._warp_multiplier = 1.0
        self._warp_timer = 0.0
        self._warp_decay = 1.5  # seconds to decay back to 1.0 when timer elapses

        # Stars and galaxies
        self.stars: List[Star] = []
        self.galaxy_images: List[pygame.Surface] = []
        self._scaled_cache = ScaledImageCache()

        if galaxy_image_names is None:
            galaxy_image_names = ["galaxy.png", "galaxy1.png"]

        self._load_galaxies(galaxy_image_names)
        self._init_stars()

    # ------------------------------------------------------------------ #
    # Initialization / assets
    # ------------------------------------------------------------------ #

    def _load_galaxies(self, names: List[str]) -> None:
        """Load galaxy sprites via assets helper, warm up cache for small sizes."""
        self.galaxy_images = load_images(names, subdirs=("image",))
        # Warm-up a tiny scale to avoid first-frame stutter
        for surf in self.galaxy_images:
            _ = self._scaled_cache.get(surf, 1, smooth=True)

    def _rand_xy(self) -> Tuple[float, float]:
        """Uniform distribution across screen bounds around center."""
        return (
            self._rng.uniform(-self.center_x, self.center_x),
            self._rng.uniform(-self.center_y, self.center_y),
        )

    def _init_stars(self) -> None:
        self.stars.clear()
        for _ in range(self.num_stars):
            x, y = self._rand_xy()
            z = self._rng.uniform(self.z_min, self.z_max)
            self.stars.append(
                Star(
                    x=x,
                    y=y,
                    z=z,
                    prev_z=z,
                    galaxy_index=None,
                    twinkle_phase=self._rng.uniform(0.0, math.tau),
                    twinkle_speed=self._rng.uniform(0.6, 2.0),
                )
            )

        # Assign a subset of stars to carry galaxy sprites (one per image by default)
        if self.galaxy_images and self.stars:
            idxs = list(range(len(self.stars)))
            self._rng.shuffle(idxs)
            count = min(len(self.galaxy_images), len(idxs))
            for i in range(count):
                self.stars[idxs[i]].galaxy_index = i

    # ------------------------------------------------------------------ #
    # Public controls
    # ------------------------------------------------------------------ #

    def resize(self, width: int, height: int) -> None:
        """Update screen dimensions and projection center."""
        self.width = int(width)
        self.height = int(height)
        self.center_x = self.width * 0.5
        self.center_y = self.height * 0.5
        # Keep focal length roughly proportional to width for similar feel
        self.focal_length = max(1.0, float(self.width))

    def set_speed_factor(self, speed: float) -> None:
        """Directly set base starfield speed."""
        self.speed_factor = float(max(0.0, speed))

    def warp(self, duration: float = 1.2, multiplier: float = 3.0) -> None:
        """
        Trigger a warp-speed burst.
        During warp, stars advance faster by `multiplier`.
        """
        self._warp_timer = max(self._warp_timer, float(duration))
        self._warp_multiplier = max(self._warp_multiplier, float(multiplier))

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #

    def update(self, dt: float) -> None:
        """Advance stars along z toward the camera; handle warp decay."""
        if dt <= 0:
            return

        self._time_accum += dt

        # Warp handling
        if self._warp_timer > 0.0:
            self._warp_timer = max(0.0, self._warp_timer - dt)
        else:
            # Ease multiplier back to 1.0
            if self._warp_multiplier > 1.0:
                k = math.exp(-self._warp_decay * dt)
                self._warp_multiplier = 1.0 + (self._warp_multiplier - 1.0) * k
                if abs(self._warp_multiplier - 1.0) < 1e-3:
                    self._warp_multiplier = 1.0

        advance = self.speed_factor * max(0.0, self._warp_multiplier) * dt
        zmin, zmax = self.z_min, self.z_max

        for s in self.stars:
            s.prev_z = s.z
            s.z -= advance

            # Recycle star if it passed the camera
            if s.z <= zmin:
                s.x, s.y = self._rand_xy()
                s.z = zmax
                s.prev_z = zmax
                # keep twinkle coherent but slightly change phase
                s.twinkle_phase = (s.twinkle_phase + self._rng.uniform(0.0, math.pi)) % math.tau

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _project(self, x: float, y: float, z: float) -> Tuple[int, int]:
        """Perspective projection (x/z, y/z) scaled by focal_length."""
        invz = 1.0 / max(z, 1e-6)
        sx = int(self.center_x + x * invz * self.focal_length)
        sy = int(self.center_y + y * invz * self.focal_length)
        return sx, sy

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw stars and galaxies sorted by depth.
        Uses line trails for stars (motion blur) and cached scaled sprites for galaxies.
        """
        # Depth sort: draw far -> near
        stars = self.stars
        stars.sort(key=lambda s: s.z, reverse=True)

        W, H = self.width, self.height
        for s in stars:
            if s.z <= 0.0:
                continue

            x, y, z, pz = s.x, s.y, s.z, s.prev_z
            sx, sy = self._project(x, y, z)

            # Quick reject if current position is way off-screen
            if sx < -64 or sx > W + 64 or sy < -64 or sy > H + 64:
                continue

            # Galaxy sprite?
            if s.galaxy_index is not None and 0 <= s.galaxy_index < len(self.galaxy_images):
                img = self.galaxy_images[s.galaxy_index]
                scale = max(0.0, 1.0 - (z / self.z_max))
                size = max(1, int(scale * 128))
                if size > 1:
                    spr = self._scaled_cache.get(img, size, smooth=True)
                    rect = spr.get_rect(center=(sx, sy))
                    surface.blit(spr, rect)
                continue

            # Regular star: twinkle + trail
            base_bright = max(0.0, 1.0 - (z / self.z_max))
            bright = base_bright
            if self.enable_twinkle:
                # subtle twinkle around the base brightness
                tw = 0.35 * (0.5 + 0.5 * math.sin(self._time_accum * s.twinkle_speed + s.twinkle_phase))
                bright = max(0.0, min(1.0, base_bright * (0.85 + tw)))

            size = int(bright * self.max_star_size) + 1
            val = min(255, int(60 + 195 * bright))
            color = (val, val, val)

            if self.enable_trails and pz > 0.0:
                psx, psy = self._project(x, y, pz)
                # Avoid huge off-screen trail strokes (cheap clip)
                if not (psx < -64 or psx > W + 64 or psy < -64 or psy > H + 64):
                    pygame.draw.line(surface, color, (psx, psy), (sx, sy), size)
            else:
                if 0 <= sx < W and 0 <= sy < H:
                    pygame.draw.circle(surface, color, (sx, sy), size // 2 + 1)
