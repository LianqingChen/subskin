#!/bin/bash
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
convert "$INPUT" -alpha set -background none -vignette 0x0 -sigmoidal-contrast 15x50% \
    \( +clone -alpha extract -draw 'fill black polygon 0,0 0,20 20,0 fill white circle 20,20 20,0' \
    \( +clone -flip \) -compose Multiply -composite \
    \( +clone -flop \) -compose Multiply -composite \) \
    -alpha off -compose CopyOpacity -composite "$ROUNDED"

# Create circular version
convert "$INPUT" -alpha set -background none \( +clone -threshold -1 \) \
    -channel A -morphology Distance Euclidean:5,50 -threshold 50% +channel \
    "$CIRCULAR"

echo "Done! Check: $ROUNDED and $CIRCULAR"
