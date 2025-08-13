import random
import pygame
import os

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
        self.galaxy_images = []

        # --- Load Galaxy Images ---
        galaxy_filenames = ["galaxy.png", "galaxy1.png"]
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))  # Navigates up from src/ui to the root

            for filename in galaxy_filenames:
                galaxy_path = os.path.join(project_root, "image", filename)
                if os.path.exists(galaxy_path):
                    print(f"Loading galaxy image from: {galaxy_path}")
                    image = pygame.image.load(galaxy_path).convert_alpha()
                    # "Warm up" the scaling for this image to prevent a stutter on the first draw.
                    pygame.transform.scale(image, (1, 1))
                    self.galaxy_images.append(image)
                else:
                    print(f"Info: Galaxy image not found at '{galaxy_path}'.")
        except pygame.error as e:
            print(f"Error loading galaxy image: {e}")

        for _ in range(num_stars):
            # Start stars with a random 3D position.
            # x and y are spread across the screen, z is depth.
            x = random.uniform(-self.center_x, self.center_x)
            y = random.uniform(-self.center_y, self.center_y)
            z = random.uniform(1, self.width)  # Start at a random depth
            self.stars.append({'x': x, 'y': y, 'z': z, 'prev_z': z})

        # Designate some stars to be galaxies, one for each loaded image.
        if self.galaxy_images and self.stars:
            # Get a list of star indices and shuffle it to pick unique stars randomly.
            available_star_indices = list(range(len(self.stars)))
            random.shuffle(available_star_indices)

            for i, _ in enumerate(self.galaxy_images):
                if not available_star_indices:
                    print("Warning: Not enough stars to assign all loaded galaxies.")
                    break
                star_index = available_star_indices.pop()
                self.stars[star_index]['galaxy_image_index'] = i
                print(f"A star has been replaced by galaxy image {i + 1}.")

    def update(self, dt: float) -> None:
        """Update the position of each star and galaxy, moving it towards the camera."""
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

                # Check if this star is a designated galaxy
                galaxy_index = star.get('galaxy_image_index')
                if galaxy_index is not None and galaxy_index < len(self.galaxy_images):
                    # Draw the galaxy image
                    image_to_draw = self.galaxy_images[galaxy_index]
                    # Scale is based on how close the object is.
                    scale = (1 - star['z'] / self.width)
                    # Let's give it a max size of 128px when it's closest.
                    size = int(scale * 128)

                    if size > 1 and 0 <= screen_x < self.width and 0 <= screen_y < self.height:
                        # Scale the original image to the new size
                        scaled_galaxy = pygame.transform.scale(image_to_draw, (size, size))
                        # Center the scaled image on its projected position
                        rect = scaled_galaxy.get_rect(center=(screen_x, screen_y))
                        surface.blit(scaled_galaxy, rect)
                else:
                    # Draw a regular star with motion blur
                    prev_screen_x = int((star['x'] / star['prev_z']) * self.width + self.center_x)
                    prev_screen_y = int((star['y'] / star['prev_z']) * self.height + self.center_y)

                    size = int((1 - star['z'] / self.width) * 4) + 1
                    brightness = min(255, int((1 - star['z'] / self.width) * 255))
                    color = (brightness, brightness, brightness)

                    if 0 <= screen_x < self.width and 0 <= screen_y < self.height:
                        pygame.draw.line(surface, color, (prev_screen_x, prev_screen_y), (screen_x, screen_y), size)