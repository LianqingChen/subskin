"""Provider-neutral candidate geometry. This validates masks, not medical truth."""
import base64
import io
import json
import math
from typing import Any, Dict

import cv2
import numpy as np
from PIL import Image

PROTOCOL = "skin-outline-v1"
MAX_VERTICES = 256
MAX_POLYGONS = 64


class AnnotationContractError(ValueError):
    """A model returned unusable candidate geometry."""


def parse_annotation(text: str) -> Dict[str, Any]:
    """Accept a single JSON object, optionally inside a markdown code fence."""
    if not isinstance(text, str) or len(text) > 250000:
        raise AnnotationContractError("标注内容无效")
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise AnnotationContractError("模型未返回有效的轮廓标注") from exc
    if not isinstance(result, dict) or result.get("protocol") != PROTOCOL:
        raise AnnotationContractError("模型返回的标注协议不匹配")
    return result


def polygon_points(value: Any) -> np.ndarray:
    """Reject guessed units, NaNs, degenerate and self-crossing polygons."""
    if not isinstance(value, list) or not 3 <= len(value) <= MAX_VERTICES:
        raise AnnotationContractError("轮廓点数量无效")
    if any(not isinstance(p, list) or len(p) != 2 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or
            not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in value):
        raise AnnotationContractError("轮廓坐标必须在图片范围内")
    points = np.asarray(value, dtype=np.float64)
    if np.array_equal(points[0], points[-1]):
        points = points[:-1]
    if len(points) < 3 or len(np.unique(points, axis=0)) != len(points):
        raise AnnotationContractError("轮廓包含重复或无效点")
    def cross(a, b, c):
        return float((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
    def on_segment(a, b, c):
        return min(a[0], b[0])-1e-10 <= c[0] <= max(a[0], b[0])+1e-10 and min(a[1], b[1])-1e-10 <= c[1] <= max(a[1], b[1])+1e-10
    for i in range(len(points)):
        a, b = points[i], points[(i+1) % len(points)]
        for j in range(i+2, len(points)):
            if i == 0 and j == len(points)-1:
                continue
            c, d = points[j], points[(j+1) % len(points)]
            ab_c, ab_d, cd_a, cd_b = cross(a,b,c), cross(a,b,d), cross(c,d,a), cross(c,d,b)
            if (ab_c*ab_d < 0 and cd_a*cd_b < 0) or any((abs(v) < 1e-10 and on_segment(x,y,z)) for v,x,y,z in (
                    (ab_c,a,b,c),(ab_d,a,b,d),(cd_a,c,d,a),(cd_b,c,d,b))):
                raise AnnotationContractError("轮廓交叉，请重新标注")
    if abs(cv2.contourArea(points.astype(np.float32))) < 1e-7:
        raise AnnotationContractError("轮廓面积过小")
    return points


def raster_polygons(value: Any, width: int, height: int) -> np.ndarray:
    if not isinstance(value, list) or len(value) > MAX_POLYGONS:
        raise AnnotationContractError("标注区域数量无效")
    mask = np.zeros((height, width), dtype=np.uint8)
    for item in value:
        points = polygon_points(item)
        pixels = np.rint(points * [width-1, height-1]).astype(np.int32)
        cv2.fillPoly(mask, [pixels], 1)
    return mask.astype(bool)


def encode_layer(mask: np.ndarray, color: tuple) -> str:
    pixels = np.zeros((*mask.shape, 4), dtype=np.uint8)
    pixels[mask, :3] = color
    pixels[mask, 3] = 180
    stream = io.BytesIO()
    Image.fromarray(pixels, "RGBA").save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def render_annotation(document: Dict[str, Any], width: int, height: int) -> Dict[str, Any]:
    """Keep uncertainty separate. Never expand skin to absorb a bad lesion mask."""
    if document.get("protocol") != PROTOCOL or document.get("status") not in ("candidate", "not_assessable"):
        raise AnnotationContractError("标注协议或状态无效")
    if not 1 <= width <= 4096 or not 1 <= height <= 4096 or width*height > 12000000:
        raise AnnotationContractError("标注图片尺寸无效")
    if document["status"] == "not_assessable":
        raise AnnotationContractError("照片暂不能可靠标注，请调整光照或拍摄范围后重试")
    for key in ("skin_regions", "excluded_regions", "lesion_regions", "uncertain_regions"):
        if key not in document:
            raise AnnotationContractError("缺少必要的分层标注")
    if sum(len(document[k]) if isinstance(document[k], list) else MAX_POLYGONS+1 for k in
           ("skin_regions", "excluded_regions", "lesion_regions", "uncertain_regions")) > MAX_POLYGONS:
        raise AnnotationContractError("标注区域过多")
    skin = raster_polygons(document["skin_regions"], width, height)
    excluded = raster_polygons(document["excluded_regions"], width, height)
    lesions = raster_polygons(document["lesion_regions"], width, height)
    uncertain = raster_polygons(document["uncertain_regions"], width, height)
    if not skin.any():
        raise AnnotationContractError("未得到有效皮肤范围")
    outside = int(((lesions | uncertain) & ~skin).sum())
    # A 1px raster edge tolerance is permitted, substantive leakage is rejected.
    envelope_count = int((lesions | uncertain).sum())
    if outside > max(4, int(envelope_count * .02)):
        raise AnnotationContractError("候选白斑超出皮肤范围，请重新标注")
    skin &= ~excluded
    if not skin.any():
        raise AnnotationContractError("排除遮挡后没有有效皮肤范围")
    uncertain &= skin
    lesions &= skin & ~uncertain
    count, _ = cv2.connectedComponents(lesions.astype(np.uint8), connectivity=8)
    return {
        "skin_layer_data_url": encode_layer(skin, (96, 165, 250)),
        "lesion_layer_data_url": encode_layer(lesions, (0, 170, 100)),
        "annotation": {
            "protocol": PROTOCOL, "review_state": "pending", "width": width, "height": height,
            "uncertain_layer_data_url": encode_layer(uncertain, (240, 143, 0)),
            "excluded_layer_data_url": encode_layer(excluded, (100, 116, 139)),
            "uncertain_pixels": int(uncertain.sum()), "skin_pixels": int(skin.sum()),
            "candidate_pixels": int(lesions.sum()), "region_count": max(0, count-1),
            "uncertain_percentage": round(float(uncertain.sum()/skin.sum()*100), 2),
            "uncertainty_kind": "model_marked_review_region_not_statistical_ci",
        },
    }
