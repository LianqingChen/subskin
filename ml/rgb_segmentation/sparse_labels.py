"""Research-only sparse polygon labels: unlabeled pixels are unknown, never background."""
from typing import Iterable, Mapping
import numpy as np
from PIL import Image, ImageDraw


def rasterize_partial_polygons(width: int, height: int, annotations: Iterable[Mapping]) -> np.ndarray:
    """Map explicit class_id 0/1/2 polygons to a partial grid; conflicts become 255.

    Each annotation has class_id and points (N x 2). Class 0 means explicitly
    annotated background. Uncovered and cross-class overlapping pixels remain
    unknown. This operation does not certify source quality or training rights.
    """
    if (not isinstance(width, int) or not isinstance(height, int)
            or width <= 0 or height <= 0 or width * height > 20_000_000):
        raise ValueError("Positive bounded integer dimensions required")
    layers = np.zeros((3, height, width), dtype=bool)
    for annotation in annotations:
        label = annotation["class_id"]
        if not isinstance(label, (int, np.integer)) or label not in (0, 1, 2):
            raise ValueError("Only explicitly annotated background, skin and lesion are supported")
        points = np.asarray(annotation["points"], dtype=np.float64)
        if (points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 3
                or not np.isfinite(points).all()):
            raise ValueError("Finite polygon coordinates required")
        if ((points < 0).any() or (points[:, 0] > width).any()
                or (points[:, 1] > height).any()):
            raise ValueError("Polygon coordinates outside image")
        area = abs(np.dot(points[:, 0], np.roll(points[:, 1], -1))
                   - np.dot(points[:, 1], np.roll(points[:, 0], -1))) / 2
        if area <= 0:
            raise ValueError("Degenerate polygon")
        mask = Image.new("1", (width, height))
        ImageDraw.Draw(mask).polygon([tuple(x) for x in points], fill=1)
        layers[label] |= np.asarray(mask, dtype=bool)
    known = layers.sum(axis=0) == 1
    result = np.full((height, width), 255, dtype=np.uint8)
    for label in range(3):
        result[known & layers[label]] = label
    return result
