import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import os

def create_globe_animation_frames():
    """
    Generates a series of PNG images showing a rotating globe.
    These frames can then be used to create an animation in pygame.
    """
    # --- Configuration ---
    output_dir = "globe_frames"
    num_frames = 120  # The number of frames in the animation (e.g., 120 for a smooth rotation)
    image_size_pixels = 300 # The width and height of the output images

    # --- Setup ---
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Generating {num_frames} frames in '{output_dir}/'...")

    # --- Frame Generation Loop ---
    for i in range(num_frames):
        # Calculate the longitude for the center of the globe for this frame
        # We go from -180 to 180 to get a full 360-degree rotation
        longitude = -180 + (360 * i / num_frames)
        
        # Create the plot
        # The projection is what makes it look like a globe
        projection = ccrs.Orthographic(central_longitude=longitude, central_latitude=20)
        
        # dpi calculation to get the desired pixel size
        dpi = image_size_pixels / 5 
        fig = plt.figure(figsize=(5, 5), dpi=dpi)
        ax = fig.add_subplot(1, 1, 1, projection=projection)
        
        # Set the extent to be global so the globe fills the image
        ax.set_global()

        # --- Add features to the globe ---
        ax.stock_img() # A basic background image
        ax.coastlines()
        # You could also add land, ocean, borders, etc.
        # ax.add_feature(cartopy.feature.LAND, zorder=0, edgecolor='black')
        # ax.add_feature(cartopy.feature.OCEAN, zorder=0)
        
        # --- Save the frame ---
        # Use zfill to pad the filename with zeros (e.g., frame_001.png)
        # This makes it easy to load them in order later
        filename = os.path.join(output_dir, f"frame_{str(i).zfill(3)}.png")
        plt.savefig(filename, dpi=dpi, transparent=True, bbox_inches='tight', pad_inches=0)
        
        # Close the plot to free up memory
        plt.close(fig)
        
        print(f"  - Saved {filename}")

    print("\nDone! All frames have been generated.")


if __name__ == '__main__':
    # Before running, make sure you have the required libraries:
    # pip install matplotlib cartopy
    create_globe_animation_frames()

