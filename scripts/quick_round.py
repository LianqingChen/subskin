#!/usr/bin/env python3
"""
Quick script to create rounded corners without installing Pillow.
Uses basic Python if possible, otherwise provides instructions.
"""

import os
import sys
from pathlib import Path


def check_image():
    """Check if the image exists."""
    input_path = Path("assets/subskin2.png")
    if not input_path.exists():
        print(f"Error: Image not found at {input_path}")
        return False
    return True


def provide_instructions():
    """Provide manual instructions for creating rounded corners."""
    print("\n" + "=" * 60)
    print("MANUAL INSTRUCTIONS for creating rounded corners:")
    print("=" * 60)
    print("\nSince automatic Pillow installation failed, here are options:")
    print("\nOption 1: Install Pillow manually")
    print(
        "  Run: pip install pillow --trusted-host pypi.org --trusted-host files.pythonhosted.org"
    )
    print("  Then run: python scripts/round_corners.py assets/subskin2.png")

    print("\nOption 2: Use online tools")
    print("  1. Go to: https://www.online-image-editor.com/")
    print("  2. Upload assets/subskin2.png")
    print("  3. Find 'Rounded Corners' or 'Crop Circle' tool")
    print("  4. Save as subskin2_rounded.png")

    print("\nOption 3: Use other image editors")
    print("  - Photoshop: Layer Style > Rounded Rectangle")
    print("  - GIMP: Filters > Decor > Round Corners")
    print("  - Preview (macOS): Tools > Adjust Size > add rounded corners")

    print("\nOption 4: Alternative Python approach (no Pillow):")
    print("  Use wand (ImageMagick wrapper) or opencv if available")

    print("\n" + "=" * 60)
    print("The image is at: assets/subskin2.png (704x682 pixels)")
    print("=" * 60)


def try_simple_approach():
    """Try a very simple approach if possible."""
    # Check if we can use tkinter (built-in) for basic operations
    try:
        import tkinter as tk
        from tkinter import filedialog

        print("tkinter is available, but limited for image processing.")
        return False
    except ImportError:
        return False


def main():
    """Main function."""
    print("SubSkin Logo Rounded Corners Helper")
    print("-" * 40)

    if not check_image():
        return

    # Try simple approach first
    if try_simple_approach():
        print("Simple approach available.")
    else:
        print("Advanced image processing required.")

    provide_instructions()

    # Create a simple bash script as alternative
    bash_script = """#!/bin/bash
# Quick image processing script
# Requires: ImageMagick (install via: brew install imagemagick)

INPUT="assets/subskin2.png"
ROUNDED="assets/subskin2_rounded.png"
CIRCULAR="assets/subskin2_circular.png"

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "Installing ImageMagick..."
    brew install imagemagick
fi

# Create rounded corners (20px radius)
convert "$INPUT" -alpha set -background none -vignette 0x0 -sigmoidal-contrast 15x50% \\
    \( +clone -alpha extract -draw 'fill black polygon 0,0 0,20 20,0 fill white circle 20,20 20,0' \\
    \( +clone -flip \) -compose Multiply -composite \\
    \( +clone -flop \) -compose Multiply -composite \) \\
    -alpha off -compose CopyOpacity -composite "$ROUNDED"

# Create circular version
convert "$INPUT" -alpha set -background none \\( +clone -threshold -1 \\) \\
    -channel A -morphology Distance Euclidean:5,50 -threshold 50% +channel \\
    "$CIRCULAR"

echo "Done! Check: $ROUNDED and $CIRCULAR"
"""

    script_path = Path("scripts/process_image.sh")
    script_path.parent.mkdir(exist_ok=True)
    script_path.write_text(bash_script)
    script_path.chmod(0o755)

    print(f"\nAlso created bash script: {script_path}")
    print("Run: bash scripts/process_image.sh (requires ImageMagick)")


if __name__ == "__main__":
    main()
