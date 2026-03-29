#!/usr/bin/env python3
"""
Script to add rounded corners to an image.

This script takes an input image and creates a new version with rounded corners
by applying a circular mask to clip the corners.

Usage: python round_corners.py input_image.png [output_image.png] [corner_radius]
"""

import sys
import os
import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("Pillow library not found. Installing...")
    import subprocess
    import sys

    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image, ImageDraw, ImageFilter


def create_rounded_corners(image_path, output_path=None, corner_radius=None):
    """
    Create an image with rounded corners.

    Args:
        image_path: Path to input image
        output_path: Path to save output image (default: input_image_rounded.png)
        corner_radius: Radius of corners in pixels (default: min(width, height) / 10)

    Returns:
        Path to saved output image
    """
    # Open the image
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # Set default output path
    if output_path is None:
        input_path = Path(image_path)
        output_path = str(
            input_path.parent / f"{input_path.stem}_rounded{input_path.suffix}"
        )

    # Set default corner radius
    if corner_radius is None:
        corner_radius = min(width, height) // 10

    # Create a mask for rounded corners
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    # Draw a rounded rectangle on the mask
    # We'll draw a white rounded rectangle (255) on black background (0)
    draw.rounded_rectangle([(0, 0), (width, height)], corner_radius, fill=255)

    # Apply the mask to the image
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)

    # Save the result
    result.save(output_path)
    print(f"Saved rounded image to: {output_path}")
    print(f"Original size: {width}x{height}, Corner radius: {corner_radius}px")

    return output_path


def create_circular_mask(image_path, output_path=None):
    """
    Create a circular mask that follows the image contours.
    This is more sophisticated and tries to follow the actual image edges.

    Args:
        image_path: Path to input image
        output_path: Path to save output image (default: input_image_circular.png)

    Returns:
        Path to saved output image
    """
    # Open the image
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # Set default output path
    if output_path is None:
        input_path = Path(image_path)
        output_path = str(
            input_path.parent / f"{input_path.stem}_circular{input_path.suffix}"
        )

    # Create a circular mask
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    # For a circular mask, we find the center and use the smaller dimension as radius
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 2

    # Draw a white circle on the mask
    draw.ellipse(
        [
            (center_x - radius, center_y - radius),
            (center_x + radius, center_y + radius),
        ],
        fill=255,
    )

    # Apply the mask to the image
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)

    # Save the result
    result.save(output_path)
    print(f"Saved circular image to: {output_path}")
    print(f"Original size: {width}x{height}, Circle radius: {radius}px")

    return output_path


def create_contour_following_mask(image_path, output_path=None, threshold=200):
    """
    Create a mask that follows the actual contours of the image.
    This is the most sophisticated approach that tries to detect edges.

    Args:
        image_path: Path to input image
        output_path: Path to save output image (default: input_image_contour.png)
        threshold: Alpha threshold for considering a pixel as part of the image

    Returns:
        Path to saved output image
    """
    # Open the image
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # Set default output path
    if output_path is None:
        input_path = Path(image_path)
        output_path = str(
            input_path.parent / f"{input_path.stem}_contour{input_path.suffix}"
        )

    # Get the alpha channel
    alpha = img.split()[3]

    # Create a mask from the alpha channel
    # Pixels with alpha > threshold are considered part of the image
    mask_data = alpha.point(lambda x: 255 if x > threshold else 0)

    # Convert back to Image
    mask = Image.new("L", (width, height))
    mask.putdata(list(mask_data.getdata()))

    # Optional: Smooth the mask edges
    mask = mask.filter(ImageFilter.SMOOTH_MORE)

    # Apply the mask to the image
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)

    # Save the result
    result.save(output_path)
    print(f"Saved contour-following image to: {output_path}")
    print(f"Original size: {width}x{height}, Alpha threshold: {threshold}")

    return output_path


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nExamples:")
        print("  python round_corners.py subskin2.png")
        print("  python round_corners.py subskin2.png subskin2_rounded.png 50")
        print("  python round_corners.py subskin2.png --circular")
        print("  python round_corners.py subskin2.png --contour")
        return

    input_image = sys.argv[1]

    if not os.path.exists(input_image):
        print(f"Error: Input image '{input_image}' not found.")
        return

    # Check for flags
    if "--circular" in sys.argv:
        output_image = (
            sys.argv[2]
            if len(sys.argv) > 2 and not sys.argv[2].startswith("--")
            else None
        )
        create_circular_mask(input_image, output_image)
    elif "--contour" in sys.argv:
        output_image = (
            sys.argv[2]
            if len(sys.argv) > 2 and not sys.argv[2].startswith("--")
            else None
        )
        threshold = 200
        if "--threshold" in sys.argv:
            try:
                idx = sys.argv.index("--threshold")
                threshold = int(sys.argv[idx + 1])
            except (ValueError, IndexError):
                pass
        create_contour_following_mask(input_image, output_image, threshold)
    else:
        # Regular rounded corners
        if len(sys.argv) >= 3 and not sys.argv[2].startswith("--"):
            output_image = sys.argv[2]
            corner_radius = int(sys.argv[3]) if len(sys.argv) >= 4 else None
        else:
            output_image = None
            corner_radius = (
                int(sys.argv[2])
                if len(sys.argv) >= 3 and sys.argv[2].isdigit()
                else None
            )

        create_rounded_corners(input_image, output_image, corner_radius)


if __name__ == "__main__":
    main()
