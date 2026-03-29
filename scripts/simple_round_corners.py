#!/usr/bin/env python3
"""
Simple script to create rounded corners for subskin2.png
This script will install Pillow if needed and process the image.
"""

import subprocess
import sys
import os
from pathlib import Path


def install_pillow():
    """Install Pillow library if not already installed."""
    try:
        from PIL import Image, ImageDraw

        print("Pillow is already installed.")
        return True
    except ImportError:
        print("Installing Pillow...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pillow", "--quiet"]
            )
            print("Pillow installed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Pillow: {e}")
            return False


def create_rounded_image():
    """Create rounded corners for subskin2.png."""
    # Install Pillow first
    if not install_pillow():
        return False

    from PIL import Image, ImageDraw

    # Define paths
    input_path = Path("assets/subskin2.png")
    output_path = Path("assets/subskin2_rounded.png")

    if not input_path.exists():
        print(f"Error: Input image not found at {input_path}")
        return False

    # Open the image
    try:
        img = Image.open(input_path).convert("RGBA")
        width, height = img.size
        print(f"Processing image: {width}x{height} pixels")

        # Create a mask for rounded corners
        # Use 15% of the smaller dimension as corner radius
        corner_radius = min(width, height) // 7

        # Create mask
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)

        # Draw rounded rectangle
        draw.rounded_rectangle([(0, 0), (width, height)], corner_radius, fill=255)

        # Apply mask
        result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        result.paste(img, (0, 0), mask)

        # Save result
        result.save(output_path)
        print(f"✓ Saved rounded image to: {output_path}")
        print(f"✓ Corner radius: {corner_radius}px")

        # Also create a circular version
        circular_path = Path("assets/subskin2_circular.png")
        mask_circle = Image.new("L", (width, height), 0)
        draw_circle = ImageDraw.Draw(mask_circle)

        # Draw circle (inset by 5% to keep some margin)
        inset = min(width, height) // 20
        draw_circle.ellipse([(inset, inset), (width - inset, height - inset)], fill=255)

        result_circle = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        result_circle.paste(img, (0, 0), mask_circle)
        result_circle.save(circular_path)
        print(f"✓ Saved circular image to: {circular_path}")

        return True

    except Exception as e:
        print(f"Error processing image: {e}")
        return False


def main():
    """Main function."""
    print("=" * 60)
    print("SubSkin Logo Rounded Corners Generator")
    print("=" * 60)

    success = create_rounded_image()

    if success:
        print("\n" + "=" * 60)
        print("SUCCESS! Generated images:")
        print(f"  • assets/subskin2_rounded.png (rounded corners)")
        print(f"  • assets/subskin2_circular.png (circular)")
        print("\nYou can use these new images in your project.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("FAILED to generate images.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
