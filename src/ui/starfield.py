import random
import pygame

class Starfield:
    """A class to manage a 3D 'warp speed' starfield effect."""

    def __init__(self, width: int, height: int, num_stars: int, speed_factor: float = 50.0):
        """
        Initialize the starfield.

        Args:
            width: The width of the screen.
            height: The height of the screen.
            num_stars: The number of stars to generate.
            speed_factor: How fast the stars move towards the camera.
        """
        self.width = width
        self.height = height
        self.center_x = width / 2
        self.center_y = height / 2
        self.speed_factor = speed_factor
        self.stars = []

        for _ in range(num_stars):
            # Start stars with a random 3D position.
            # x and y are spread across the screen, z is depth.
            x = random.uniform(-self.center_x, self.center_x)
            y = random.uniform(-self.center_y, self.center_y)
            z = random.uniform(1, self.width)  # Start at a random depth
            self.stars.append({'x': x, 'y': y, 'z': z, 'prev_z': z})

    def update(self, dt: float) -> None:
        """Update the position of each star, moving it towards the camera."""
        for star in self.stars:
            # Store the previous depth before updating
            star['prev_z'] = star['z']
            # Move star closer to the viewer by decreasing its z-coordinate
            star['z'] -= self.speed_factor * dt

            # If star has passed the camera (z <= 0), reset it to a new
            # position at the furthest depth.
            if star['z'] <= 0.0:
                star['x'] = random.uniform(-self.center_x, self.center_x)
                star['y'] = random.uniform(-self.center_y, self.center_y)
                star['z'] = self.width  # Reset to the back
                star['prev_z'] = self.width # Also reset previous z to avoid streaks

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the stars on the given surface, projecting them from 3D to 2D.

        Args:
            surface: The pygame.Surface to draw on.
        """
        # Sort stars by depth so closer stars are drawn on top of farther ones.
        self.stars.sort(key=lambda s: s['z'], reverse=True)

        for star in self.stars:
            # Project 3D coordinates to 2D screen space
            if star['z'] > 0.0:
                # Perspective projection: screen_coord = (world_coord / z)
                screen_x = int((star['x'] / star['z']) * self.width + self.center_x)
                screen_y = int((star['y'] / star['z']) * self.height + self.center_y)

                # Project the previous position to create a motion blur trail
                prev_screen_x = int((star['x'] / star['prev_z']) * self.width + self.center_x)
                prev_screen_y = int((star['y'] / star['prev_z']) * self.height + self.center_y)

                # Determine size and brightness based on depth (closer = bigger/brighter)
                size = int((1 - star['z'] / self.width) * 4) + 1
                brightness = min(255, int((1 - star['z'] / self.width) * 255))
                color = (brightness, brightness, brightness)

                # Draw the star if it's within the screen bounds
                if 0 <= screen_x < self.width and 0 <= screen_y < self.height:
                    # Draw a line for the motion blur effect
                    pygame.draw.line(surface, color, (prev_screen_x, prev_screen_y), (screen_x, screen_y), size)