"""
Smoke test for the new skin-aware vitiligo segmentation algorithm.
Generates synthetic test images that simulate the original bugs and verifies
that the new logic correctly rejects backgrounds while still detecting real
vitiligo patches within skin regions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import numpy as np
from PIL import Image

from web.backend.services.vasi_segmentation import segment_vitiligo


def make_image(spec: dict) -> bytes:
    """Build a synthetic RGB image. `spec` example:
        {'size': (400, 400),
         'background': (240, 240, 240),
         'skin_rect': (100, 100, 300, 350, (200, 160, 130)),
         'white_patch_rects': [(150, 150, 200, 200, (235, 220, 200))]}
    """
    w, h = spec["size"]
    img = np.full((h, w, 3), spec["background"], dtype=np.uint8)
    if "skin_rect" in spec:
        x1, y1, x2, y2, color = spec["skin_rect"]
        img[y1:y2, x1:x2] = color
    for patch in spec.get("white_patch_rects", []):
        x1, y1, x2, y2, color = patch
        img[y1:y2, x1:x2] = color

    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def run_case(name: str, img_bytes: bytes, expect_detection: bool, expect_area_in_skin_gt: float = 0):
    result = segment_vitiligo(img_bytes, precision="quick")
    detected = bool(result.get("success") and result.get("contours"))
    status = "PASS" if (detected == expect_detection) else "FAIL"

    if detected and expect_detection and expect_area_in_skin_gt > 0:
        actual_area = result.get("total_area_percent", 0)
        if actual_area < expect_area_in_skin_gt:
            status = "FAIL"
            print(
                f"  [denominator check] expected area_in_skin >= {expect_area_in_skin_gt}, "
                f"got {actual_area}"
            )

    print(f"[{status}] {name}")
    print(
        f"  detected={detected}, contours={len(result.get('contours', []))},"
        f" total_area_in_skin={result.get('total_area_percent')}%,"
        f" denominator={result.get('denominator', 'unknown')},"
        f" source={result.get('source')},"
        f" error={result.get('error')!r}"
    )
    if "skin_region_ratio" in result:
        print(f"  skin_region_ratio={result['skin_region_ratio']}% of image")
    if result.get("contours"):
        for c in result["contours"][:3]:
            print(
                f"  - {c['label']}: {c['area_percent']}% of skin, "
                f"{c.get('area_percent_in_image', 'N/A')}% of image"
            )
    return status == "PASS"


def main():
    cases = [
        (
            "Pure white background (should NOT detect vitiligo)",
            make_image({"size": (400, 400), "background": (250, 250, 250)}),
            False,
        ),
        (
            "White shirt no skin (should NOT detect vitiligo)",
            make_image({
                "size": (400, 400),
                "background": (60, 80, 100),
                "skin_rect": (50, 50, 350, 350, (245, 245, 245)),
            }),
            False,
        ),
        (
            "Skin with NO vitiligo (should NOT detect)",
            make_image({
                "size": (400, 400),
                "background": (60, 80, 100),
                "skin_rect": (50, 50, 350, 350, (200, 160, 130)),
            }),
            False,
        ),
        (
            "Skin with clear vitiligo patch (should detect ~11% of skin)",
            make_image({
                "size": (400, 400),
                "background": (60, 80, 100),
                "skin_rect": (50, 50, 350, 350, (200, 160, 130)),
                "white_patch_rects": [(150, 150, 250, 250, (235, 220, 205))],
            }),
            True,
            8.0,
        ),
        (
            "Skin with two vitiligo patches (should detect 8-15% of skin)",
            make_image({
                "size": (400, 400),
                "background": (60, 80, 100),
                "skin_rect": (50, 50, 350, 350, (200, 160, 130)),
                "white_patch_rects": [
                    (100, 100, 170, 170, (235, 220, 205)),
                    (220, 220, 300, 300, (240, 225, 210)),
                ],
            }),
            True,
            8.0,
        ),
        (
            "Skin + white background object (should detect skin patches only)",
            make_image({
                "size": (400, 400),
                "background": (250, 250, 250),
                "skin_rect": (50, 50, 350, 350, (200, 160, 130)),
                "white_patch_rects": [(180, 180, 250, 250, (235, 220, 205))],
            }),
            True,
            5.0,
        ),
    ]

    passed = 0
    for case in cases:
        if len(case) == 3:
            name, img, expect = case
            area_min = 0
        else:
            name, img, expect, area_min = case
        if run_case(name, img, expect, area_min):
            passed += 1
        print()

    print(f"=== {passed}/{len(cases)} cases passed ===")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
