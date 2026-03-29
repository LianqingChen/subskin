#!/usr/bin/env python3
"""
Final solution for creating rounded corners.
Since Pillow installation is failing, this script provides exact commands.
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    print("=" * 70)
    print("SUBSKIN LOGO ROUNDED CORNERS - FINAL SOLUTION")
    print("=" * 70)

    input_path = Path("assets/subskin2.png")
    if not input_path.exists():
        print(f"❌ ERROR: Image not found at {input_path}")
        return 1

    print(f"✅ Found image: {input_path} (704x682 pixels)")
    print()

    # Option 1: Try system Python (might have Pillow)
    print("Option 1: Try system Python (may already have Pillow):")
    print("-" * 50)
    system_cmd = f"""python3 -c "
try:
    from PIL import Image, ImageDraw
    img = Image.open('{input_path}').convert('RGBA')
    w, h = img.size
    r = min(w, h) // 10
    mask = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w, h)], r, fill=255)
    result = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    result.save('assets/subskin2_rounded.png')
    print('✓ Created: assets/subskin2_rounded.png')
except ImportError:
    print('Pillow not installed. Try Option 2.')
except Exception as e:
    print(f'Error: {{e}}')
"
"""
    print(system_cmd)
    print()

    # Option 2: Use wand (ImageMagick Python wrapper)
    print("Option 2: Install wand (ImageMagick Python wrapper):")
    print("-" * 50)
    print("pip install wand")
    print("""
from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color

with Image(filename='assets/subskin2.png') as img:
    img.format = 'png'
    img.alpha_channel = True
    with Drawing() as draw:
        draw.fill_color = Color('transparent')
        draw.rectangle(left=0, top=0, width=img.width, height=img.height)
        draw.fill_color = Color('white')
        draw.roundrectangle(left=0, top=0, width=img.width, height=img.height, 
                           xradius=70, yradius=70)
        draw(img.alpha_channel)
    img.save(filename='assets/subskin2_rounded.png')
""")
    print()

    # Option 3: Direct ImageMagick command
    print("Option 3: Direct ImageMagick command (install via brew):")
    print("-" * 50)
    print("brew install imagemagick")
    print("""
# Simple rounded corners
convert assets/subskin2.png -alpha set -background none \\
  \( +clone -alpha extract -draw 'fill black polygon 0,0 0,70 70,0 fill white circle 70,70 70,0' \\
    \( +clone -flip \) -compose Multiply -composite \\
    \( +clone -flop \) -compose Multiply -composite \) \\
  -alpha off -compose CopyOpacity -composite assets/subskin2_rounded.png

# Circular version  
convert assets/subskin2.png \\( +clone -threshold -1 \\) \\
  -alpha set -channel A -morphology Distance Euclidean:5,50 -threshold 50% +channel \\
  assets/subskin2_circular.png
""")
    print()

    # Option 4: Simple workaround - create CSS/HTML preview
    print("Option 4: Web/CSS workaround (for web usage):")
    print("-" * 50)
    css_content = """
/* Add rounded corners via CSS */
.rounded-logo {
    border-radius: 70px; /* Adjust as needed */
    overflow: hidden;
    display: inline-block;
}

.rounded-logo img {
    display: block;
    width: 100%;
    height: auto;
}

/* Circular version */
.circular-logo {
    border-radius: 50%;
    overflow: hidden;
    display: inline-block;
}
"""
    print(css_content)

    # Create HTML preview
    html_path = Path("assets/logo_preview.html")
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>SubSkin Logo Preview</title>
    <style>
        {css_content}
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .preview {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; }}
        h2 {{ color: #333; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>SubSkin Logo Preview</h1>
        
        <div class="preview">
            <h2>Original</h2>
            <img src="subskin2.png" width="352" height="341">
        </div>
        
        <div class="preview">
            <h2>Rounded Corners (CSS)</h2>
            <div class="rounded-logo">
                <img src="subskin2.png" width="352" height="341">
            </div>
            <p>CSS: <code>border-radius: 70px;</code></p>
        </div>
        
        <div class="preview">
            <h2>Circular (CSS)</h2>
            <div class="circular-logo">
                <img src="subskin2.png" width="352" height="341">
            </div>
            <p>CSS: <code>border-radius: 50%;</code></p>
        </div>
    </div>
</body>
</html>
"""
    html_path.write_text(html_content)
    print(f"✅ Created HTML preview: {html_path}")
    print("  Open this file in a browser to see rounded corner effects.")

    print()
    print("=" * 70)
    print("RECOMMENDATION: Use Option 4 (CSS) for web projects.")
    print("For actual image files, try Option 3 (ImageMagick).")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
