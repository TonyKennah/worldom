# starfield.py
# Enhanced 3D “warp speed” starfield with galaxies, twinkle, warp bursts,
# resizing support, cached scaled sprites, mouse parallax, nebula overlay,
# shooting stars (meteors), stats, and temperature-colored stars.
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
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
    temp_k: int = 6500              # new: approximate blackbody temperature
    base_rgb: Tuple[int, int, int] = (200, 200, 200)  # new: color cache


@dataclass
class Meteor:
    """Transient ‘shooting star’ rendered over the field."""
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: int
    color: Color


class Starfield:
    """
    A 3D 'warp speed' starfield effect with:
      - mouse-smooth warp perspective projection + optional mouse parallax
      - optional galaxy sprites with cached scaling
      - twinkling stars & motion trails
      - warp/burst speed boosts w/ exponential decay
      - deterministic seeding and resize support
      - temperature-colored stars (toggleable)
      - optional ‘nebula’ overlay surface
      - optional shooting stars (meteors)
      - draw statistics for quick debugging
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
        self._seed = seed
        self._time_accum = 0.0

        # Warp burst state
        self._warp_multiplier = 1.0
        self._warp_timer = 0.0
        self._warp_decay = 1.5  # seconds to decay back to 1.0 when timer elapses

        # Mouse parallax (subtle screen tilt based on mouse)
        self._mouse_parallax_strength = 0.0  # 0..1 (0 disabled)
        self._mouse_pos = (self.center_x, self.center_y)

        # Stars, galaxies, meteors
        self.stars: List[Star] = []
        self.meteors: List[Meteor] = []
        self.galaxy_images: List[pygame.Surface] = []
        self._scaled_cache = ScaledImageCache()

        if galaxy_image_names is None:
            galaxy_image_names = ["galaxy.png", "galaxy1.png"]

        self._load_galaxies(galaxy_image_names)
        self._init_stars()

        # Nebula control
        self.enable_nebula: bool = False
        self.nebula_intensity: int = 70      # 0..255 alpha
        self._nebula_surface: Optional[pygame.Surface] = None
        self._nebula_seed = self._rng.randint(0, 1_000_000)

        # Star coloring
        self.color_mode: str = "temperature"  # "white" or "temperature"

        # Meteor control
        self.meteor_rate: float = 0.0  # meteors/sec (0 disabled)
        self._meteor_accum: float = 0.0

        # Last draw stats
        self.last_stats: Dict[str, int | float] = {}

    # ------------------------------------------------------------------ #
    # Initialization / assets
    # ------------------------------------------------------------------ #

    def _load_galaxies(self, names: List[str]) -> None:
        """Load galaxy sprites via assets helper, warm up cache for small sizes."""
        self.galaxy_images = load_images(names, subdirs=("image",))
        for surf in self.galaxy_images:
            _ = self._scaled_cache.get(surf, 1, smooth=True)

    def _rand_xy(self) -> Tuple[float, float]:
        """Uniform distribution across screen bounds around center."""
        return (
            self._rng.uniform(-self.center_x, self.center_x),
            self._rng.uniform(-self.center_y, self.center_y),
        )

    @staticmethod
    def _kelvin_to_rgb(temp_k: int) -> Tuple[int, int, int]:
        """
        Approximate color from temperature (Tanner Helland model).
        Valid-ish for 1000K..40000K, we clamp to a friendly window.
        """
        t = max(1000, min(40000, temp_k)) / 100.0
        # Red
        if t <= 66:
            r = 255
        else:
            r = 329.698727446 * ((t - 60) ** -0.1332047592)
            r = max(0, min(255, r))
        # Green
        if t <= 66:
            g = 99.4708025861 * math.log(t) - 161.1195681661
            g = max(0, min(255, g))
        else:
            g = 288.1221695283 * ((t - 60) ** -0.0755148492)
            g = max(0, min(255, g))
        # Blue
        if t >= 66:
            b = 255
        elif t <= 19:
            b = 0
        else:
            b = 138.5177312231 * math.log(t - 10) - 305.0447927307
            b = max(0, min(255, b))
        return int(r), int(g), int(b)

    def _init_stars(self) -> None:
        self.stars.clear()
        for _ in range(self.num_stars):
            x, y = self._rand_xy()
            z = self._rng.uniform(self.z_min, self.z_max)
            temp_k = self._rng.randint(2500, 9500)
            base_rgb = self._kelvin_to_rgb(temp_k)
            self.stars.append(
                Star(
                    x=x,
                    y=y,
                    z=z,
                    prev_z=z,
                    galaxy_index=None,
                    twinkle_phase=self._rng.uniform(0.0, math.tau),
                    twinkle_speed=self._rng.uniform(0.6, 2.0),
                    temp_k=temp_k,
                    base_rgb=base_rgb,
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
        self.focal_length = max(1.0, float(self.width))
        self._nebula_surface = None  # force rebuild if enabled

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

    def set_mouse_parallax(self, strength: float) -> None:
        """
        Enable/adjust mouse parallax; range 0..1 (0 disables).
        Small values like 0.08–0.15 look nice.
        """
        self._mouse_parallax_strength = max(0.0, min(1.0, float(strength)))

    def set_color_mode(self, mode: str) -> None:
        """'white' or 'temperature'."""
        if mode in ("white", "temperature"):
            self.color_mode = mode

    def set_nebula(self, enabled: bool, *, intensity: int = 70) -> None:
        """Toggle nebula overlay and optional alpha intensity (0..255)."""
        self.enable_nebula = bool(enabled)
        self.nebula_intensity = max(0, min(255, int(intensity)))
        if enabled and self._nebula_surface is None:
            self._ensure_nebula_surface()

    def set_meteor_rate(self, meteors_per_second: float) -> None:
        """Set shooting star spawn rate; 0 disables."""
        self.meteor_rate = max(0.0, float(meteors_per_second))

    def reseed(self, seed: Optional[int]) -> None:
        """Reinitialize RNG and stars with a new seed (None for random)."""
        self._seed = seed
        self._rng = random.Random(seed)
        self._nebula_seed = self._rng.randint(0, 1_000_000)
        self._nebula_surface = None
        self._init_stars()

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #

    def update(self, dt: float) -> None:
        """Advance stars along z toward the camera; handle warp decay; spawn meteors."""
        if dt <= 0:
            return

        self._time_accum += dt

        # Mouse parallax: cache current mouse if available
        if pygame.get_init():
            try:
                self._mouse_pos = pygame.mouse.get_pos()
            except Exception:
                pass

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

        # Meteors
        if self.meteor_rate > 0.0:
            self._meteor_accum += dt * self.meteor_rate
            while self._meteor_accum >= 1.0:
                self._meteor_accum -= 1.0
                self._spawn_meteor()

        for m in self.meteors:
            m.life += dt
            m.x += m.vx * dt
            m.y += m.vy * dt
        self.meteors = [m for m in self.meteors if m.life < m.max_life]

        # Nebula
        if self.enable_nebula and self._nebula_surface is None:
            self._ensure_nebula_surface()

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _project(self, x: float, y: float, z: float) -> Tuple[int, int]:
        """Perspective projection (x/z, y/z) scaled by focal_length."""
        invz = 1.0 / max(z, 1e-6)
        # Parallax: shift center based on mouse
        if self._mouse_parallax_strength > 0.0:
            mx, my = self._mouse_pos
            dx = (mx - self.center_x) / max(self.center_x, 1.0)
            dy = (my - self.center_y) / max(self.center_y, 1.0)
            px = self.center_x + dx * self._mouse_parallax_strength * 40.0
            py = self.center_y + dy * self._mouse_parallax_strength * 40.0
        else:
            px, py = self.center_x, self.center_y
        sx = int(px + x * invz * self.focal_length)
        sy = int(py + y * invz * self.focal_length)
        return sx, sy

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw stars, galaxies, nebula (optional), and meteors sorted by depth.
        Uses line trails for stars (motion blur) and cached scaled sprites for galaxies.
        """
        drawn_stars = 0
        clipped = 0
        drawn_lines = 0
        drawn_gal = 0
        drawn_meteors = 0

        W, H = self.width, self.height

        # Nebula (background)
        if self.enable_nebula and self._nebula_surface is not None:
            neb = self._nebula_surface
            if self.nebula_intensity < 255:
                neb = neb.copy()
                neb.set_alpha(self.nebula_intensity)
            surface.blit(neb, (0, 0))

        # Depth sort: draw far -> near
        stars = self.stars
        stars.sort(key=lambda s: s.z, reverse=True)

        for s in stars:
            if s.z <= 0.0:
                continue

            x, y, z, pz = s.x, s.y, s.z, s.prev_z
            sx, sy = self._project(x, y, z)

            # Quick reject if current position is way off-screen
            if sx < -64 or sx > W + 64 or sy < -64 or sy > H + 64:
                clipped += 1
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
                    drawn_gal += 1
                continue

            # Regular star: color + twinkle + trail
            base_bright = max(0.0, 1.0 - (z / self.z_max))
            bright = base_bright
            if self.enable_twinkle:
                tw = 0.35 * (0.5 + 0.5 * math.sin(self._time_accum * s.twinkle_speed + s.twinkle_phase))
                bright = max(0.0, min(1.0, base_bright * (0.85 + tw)))

            if self.color_mode == "temperature":
                r, g, b = s.base_rgb
                color = (
                    min(255, int(r * (0.24 + 0.76 * bright))),
                    min(255, int(g * (0.24 + 0.76 * bright))),
                    min(255, int(b * (0.24 + 0.76 * bright))),
                )
            else:
                val = min(255, int(60 + 195 * bright))
                color = (val, val, val)

            size = int(bright * self.max_star_size) + 1

            if self.enable_trails and pz > 0.0:
                psx, psy = self._project(x, y, pz)
                if not (psx < -64 or psx > W + 64 or psy < -64 or psy > H + 64):
                    pygame.draw.line(surface, color, (psx, psy), (sx, sy), size)
                    drawn_lines += 1
            else:
                if 0 <= sx < W and 0 <= sy < H:
                    pygame.draw.circle(surface, color, (sx, sy), size // 2 + 1)

            drawn_stars += 1

        # Meteors over starfield
        for m in self.meteors:
            alpha = max(0, 1.0 - (m.life / m.max_life))
            col = (int(m.color[0] * alpha + 30), int(m.color[1] * alpha + 30), int(m.color[2] * alpha + 30))
            tail_len = max(12, int(80 * (m.life / m.max_life)))
            tail_dx = -m.vx * 0.06
            tail_dy = -m.vy * 0.06
            x2 = m.x + tail_dx
            y2 = m.y + tail_dy
            pygame.draw.line(surface, col, (m.x, m.y), (x2, y2), m.size)
            pygame.draw.circle(surface, col, (int(m.x), int(m.y)), max(1, m.size - 1))
            drawn_meteors += 1

        # Capture last-draw stats
        self.last_stats = {
            "stars_drawn": drawn_stars,
            "stars_clipped": clipped,
            "trail_lines": drawn_lines,
            "galaxies_drawn": drawn_gal,
            "meteors_drawn": drawn_meteors,
        }

    # ------------------------------------------------------------------ #
    # Internals: nebula + meteors
    # ------------------------------------------------------------------ #

    def _ensure_nebula_surface(self) -> None:
        """Create a soft, additive-looking nebula surface from random blobs."""
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        rng = random.Random(self._nebula_seed)

        # 8–14 blobs, large soft circles with low alpha
        blob_count = rng.randint(8, 14)
        for _ in range(blob_count):
            cx = rng.randint(0, self.width)
            cy = rng.randint(0, self.height)
            r = rng.randint(int(self.width * 0.12), int(self.width * 0.28))
            base = rng.choice([(90, 140, 255), (120, 80, 180), (40, 120, 160), (160, 50, 100)])
            # radial alpha falloff
            tmp = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            for ri in range(r, 0, -2):
                a = max(0, int(20 * (ri / r) ** 2))
                pygame.draw.circle(tmp, base + (a,), (r, r), ri)
            surf.blit(tmp, (cx - r, cy - r), special_flags=pygame.BLEND_PREMULTIPLIED)

        self._nebula_surface = surf

    def _spawn_meteor(self) -> None:
        """Create a fast, short-lived meteor crossing the screen."""
        side = self._rng.choice(("left", "right", "top"))
        if side == "left":
            x, y = -20.0, self._rng.uniform(0, self.height * 0.7)
            vx, vy = self._rng.uniform(380, 560), self._rng.uniform(40, 120)
        elif side == "right":
            x, y = self.width + 20.0, self._rng.uniform(0, self.height * 0.7)
            vx, vy = -self._rng.uniform(380, 560), self._rng.uniform(40, 120)
        else:
            x, y = self._rng.uniform(0, self.width), -20.0
            vx, vy = self._rng.uniform(-160, 160), self._rng.uniform(300, 500)

        life = 0.0
        max_life = self._rng.uniform(0.7, 1.4)
        size = self._rng.randint(2, 4)
        color = (255, self._rng.randint(150, 230), self._rng.randint(80, 160))
        self.meteors.append(Meteor(x=x, y=y, vx=vx, vy=vy, life=life, max_life=max_life, size=size, color=color))

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def get_stats(self) -> Dict[str, int | float]:
        """Return draw statistics from the most recent frame."""
        return dict(self.last_stats)
