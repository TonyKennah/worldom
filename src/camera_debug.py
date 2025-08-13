# camera_debug.py
from __future__ import annotations
import pygame

YELLOW = (245, 220, 120)
CYAN   = (120, 210, 230)
WHITE  = (255, 255, 255)

def draw_camera_debug_overlay(screen: pygame.Surface, camera) -> None:
    """Render a minimal debug overlay for the camera."""
    w, h = screen.get_width(), screen.get_height()
    # Center crosshair
    cx, cy = int(camera.screen_center.x), int(camera.screen_center.y)
    pygame.draw.line(screen, CYAN, (cx - 8, cy), (cx + 8, cy), 1)
    pygame.draw.line(screen, CYAN, (cx, cy - 8), (cx, cy + 8), 1)

    # Deadzone box
    dz_w = int(w * camera.follow_deadzone_frac.x)
    dz_h = int(h * camera.follow_deadzone_frac.y)
    dz = pygame.Rect(cx - dz_w // 2, cy - dz_h // 2, dz_w, dz_h)
    pygame.draw.rect(screen, YELLOW, dz, 1)

    # Info text
    font = pygame.font.SysFont("consolas", 14)
    txt = f"pos=({camera.position.x:.1f},{camera.position.y:.1f}) zoom={camera.zoom:.2f} vel=({camera.velocity.x:.1f},{camera.velocity.y:.1f})"
    surf = font.render(txt, True, WHITE)
    screen.blit(surf, (8, 8))
