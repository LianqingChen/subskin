"""高清视觉粗定位：在原生分辨率上向视觉模型要候选几何。

纪律（与 docs/specs/2026-09-12-pixel-level-vitiligo-refine-design.md 一致）：
- 只产出 skin-outline-v1 候选几何（0-1 归一化多边形）。像素边界始终由
  refine_annotation_layers 里的 SAM/边缘感知决定，本模块绝不产出测量数值；
- 输入走原生分辨率（长边可配，默认 2048）。视觉 token 粒度固定 32px/个，
  相对 1024 口径的定位粒度提升约 2 倍；裁剪放大二次提问进一步收紧局部；
- 思考档位可配（默认关闭）：纯定位任务不需要长思考，长提示延迟约降一个数量级；
- 任一阶段失败都退回上一轮结果或抛 AnnotationContractError，由上层降级处理。
"""
import asyncio
import base64
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from web.backend.services.annotation_contract import (
    AnnotationContractError,
    parse_annotation,
    polygon_points,
    raster_polygons,
)
from web.backend.services.annotation_prompt import ANNOTATION_SCHEMA, annotation_prompt
from web.backend.services.rgb_segmentation.images import canonical_image

logger = logging.getLogger(__name__)

CROP_INSTRUCTION = """这是一张皮肤照片的局部裁剪图，坐标严格相对本裁剪图本身（左上(0,0)、右下(1,1)）。
只定位本裁剪图中可辨的浅色/色素减退候选区域，不推测画面之外的区域，不按模板补形状。
四个数组必须都出现：lesion_regions 给可辨候选，uncertain_regions 给不确定部分，其余无内容给空数组。
禁止输出面积、周长、VASI、分期、诊断或其他文字。只输出符合下面 JSON Schema 的实例：
"""


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        return min(high, max(low, int(os.getenv(name, str(default)))))
    except (ValueError, TypeError):
        return default


def _env_float(name: str, default: float, low: float, high: float) -> float:
    try:
        return min(high, max(low, float(os.getenv(name, str(default)))))
    except (ValueError, TypeError):
        return default


def outline_settings() -> Dict[str, Any]:
    return {
        "max_side": _env_int("VASI_OUTLINE_MAX_SIDE", 2048, 1024, 4096),
        "zoom": _env_int("VASI_OUTLINE_ZOOM", 1, 0, 1) == 1,
        "consensus": _env_int("VASI_OUTLINE_CONSENSUS", 0, 0, 1) == 1,
        "thinking": os.getenv("VASI_OUTLINE_THINKING", "off").strip().lower(),
        "max_tokens": _env_int("VASI_OUTLINE_VLM_MAX_TOKENS", 32000, 2048, 32768),
        "total_budget_s": _env_float("VASI_OUTLINE_TOTAL_BUDGET_S", 200.0, 30.0, 600.0),
        "zoom_regions": _env_int("VASI_OUTLINE_ZOOM_REGIONS", 4, 1, 8),
        "refine_budget_s": _env_float("VASI_OUTLINE_REFINE_BUDGET_S", 60.0, 10.0, 180.0),
        "refine_regions": _env_int("VASI_OUTLINE_REFINE_REGIONS", 12, 1, 24),
    }


def thinking_extra_body(thinking: str) -> Optional[Dict[str, Any]]:
    """DashScope 不允许 reasoning_effort 与 thinking_budget 同时下发。"""
    value = (thinking or "off").strip().lower()
    if value in ("default", "provider"):
        return None
    if value in ("off", "none", "false", "0"):
        return {"enable_thinking": False}
    if value == "medium":
        return {"enable_thinking": True, "reasoning_effort": "medium"}
    if value in ("xhigh", "high", "max"):
        return {"enable_thinking": True, "reasoning_effort": "xhigh"}
    return None


def encode_jpeg_base64(rgb: np.ndarray, quality: int = 95) -> str:
    stream = io.BytesIO()
    Image.fromarray(rgb).save(stream, format="JPEG", quality=quality)
    return base64.b64encode(stream.getvalue()).decode("ascii")


def polygon_area(poly: List[List[float]]) -> float:
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][0], poly[i][1]
        x2, y2 = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def crop_box_for_polygon(poly: List[List[float]], pad: float = 0.25,
                         min_side: float = 0.18) -> List[float]:
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
    x1 -= (x2 - x1) * pad
    x2 += (x2 - x1) * pad
    y1 -= (y2 - y1) * pad
    y2 += (y2 - y1) * pad
    if x2 - x1 < min_side:
        cx = (x1 + x2) / 2
        x1, x2 = cx - min_side / 2, cx + min_side / 2
    if y2 - y1 < min_side:
        cy = (y1 + y2) / 2
        y1, y2 = cy - min_side / 2, cy + min_side / 2
    return [max(0.0, min(1.0, v)) for v in (x1, y1, x2, y2)]


def pixel_box(box: List[float], w: int, h: int) -> Tuple[int, int, int, int]:
    x1 = max(0, min(w - 2, int(round(box[0] * (w - 1)))))
    y1 = max(0, min(h - 2, int(round(box[1] * (h - 1)))))
    x2 = max(x1 + 1, min(w, int(round(box[2] * (w - 1))) + 1))
    y2 = max(y1 + 1, min(h, int(round(box[3] * (h - 1))) + 1))
    return x1, y1, x2, y2


def remap_polygon(poly: List[List[float]], box: List[float]) -> List[List[float]]:
    x1, y1, x2, y2 = box
    bw, bh = max(1e-6, x2 - x1), max(1e-6, y2 - y1)
    out = []
    for p in poly:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            continue
        try:
            px, py = float(p[0]), float(p[1])
        except (TypeError, ValueError):
            continue
        out.append([round(min(1.0, max(0.0, x1 + px * bw)), 6),
                    round(min(1.0, max(0.0, y1 + py * bh)), 6)])
    return out


def safe_raster(polys: Any, w: int, h: int) -> np.ndarray:
    """Per-polygon validation: one malformed region must not void the rest."""
    mask = np.zeros((h, w), dtype=np.uint8)
    if not isinstance(polys, list):
        return mask.astype(bool)
    for poly in polys:
        try:
            points = polygon_points(poly)
        except AnnotationContractError:
            continue
        pixels = np.rint(np.asarray(points) * [w - 1, h - 1]).astype(np.int32)
        import cv2
        cv2.fillPoly(mask, [pixels], 1)
    return mask.astype(bool)


def mask_to_polygons(mask: np.ndarray, w: int, h: int, min_area_px: int = 8) -> List[Any]:
    import cv2
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out: List[Any] = []
    for contour in contours:
        if cv2.contourArea(contour) < min_area_px:
            continue
        approx = cv2.approxPolyDP(contour, 1.5, True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        out.append([[round(float(x) / max(1, w - 1), 6), round(float(y) / max(1, h - 1), 6)]
                    for x, y in approx])
    return out


def consensus_documents(doc_a: Dict[str, Any], doc_b: Dict[str, Any],
                        w: int, h: int) -> Tuple[Dict[str, Any], float]:
    """两轮独立结果的交集为病灶，异或为待核对；协议与图层语义不变。"""
    a = safe_raster(doc_a.get("lesion_regions") or [], w, h)
    b = safe_raster(doc_b.get("lesion_regions") or [], w, h)
    union, inter = a | b, a & b
    iou = float(inter.sum()) / float(union.sum()) if union.any() else 1.0
    min_area = max(8, int(0.0002 * w * h))
    merged = {
        **doc_a,
        "lesion_regions": mask_to_polygons(inter, w, h, min_area),
        "uncertain_regions": list(doc_a.get("uncertain_regions") or [])
                             + list(doc_b.get("uncertain_regions") or [])
                             + mask_to_polygons(union & ~inter, w, h, min_area),
    }
    return merged, round(iou, 3)


def crop_prompt(body_site: str) -> str:
    return (CROP_INSTRUCTION
            + json.dumps(ANNOTATION_SCHEMA, ensure_ascii=False, separators=(",", ":"))
            + "\n本次所选部位：" + body_site)


def _looks_like_param_rejection(exc: Exception) -> bool:
    text = str(exc).lower()
    return "thinking" in text or "reasoning_effort" in text


async def _call_outline(client, model: str, image_b64: str, prompt: str, *,
                        thinking: str, max_tokens: int, timeout_s: float
                        ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    extra = thinking_extra_body(thinking)
    kwargs: Dict[str, Any] = dict(
        model=model, temperature=0, max_tokens=max_tokens,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    if extra:
        kwargs["extra_body"] = extra
    started = time.monotonic()
    try:
        response = await asyncio.wait_for(client.chat.completions.create(**kwargs), timeout=timeout_s)
    except Exception as exc:
        if extra and _looks_like_param_rejection(exc):
            logger.info("outline thinking parameter rejected; retrying without it")
            kwargs.pop("extra_body", None)
            response = await asyncio.wait_for(client.chat.completions.create(**kwargs), timeout=timeout_s)
        else:
            raise
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise AnnotationContractError("定位信息未完整返回，请稍后重试")
    document = parse_annotation(choice.message.content or "")
    if document.get("status") != "candidate":
        raise AnnotationContractError("照片暂不能可靠定位，请调整光照或拍摄范围后重试")
    usage = getattr(response, "usage", None)
    info = {
        "latency_s": round(time.monotonic() - started, 2),
        "thinking": thinking,
        "tokens": ({"input": getattr(usage, "prompt_tokens", None),
                    "output": getattr(usage, "completion_tokens", None)} if usage else None),
    }
    return document, info


async def propose_geometry(image_bytes: bytes, body_site: str, *,
                           zoom: Optional[bool] = None,
                           consensus: Optional[bool] = None,
                           thinking: Optional[str] = None,
                           max_side: Optional[int] = None,
                           deadline_s: Optional[float] = None
                           ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """高清一轮 + 裁剪复问 (+ 可选举证共识) → skin-outline-v1 候选几何与元数据。"""
    from openai import AsyncOpenAI
    from web.backend.utils.llm_config import get_llm_config

    settings = outline_settings()
    zoom = settings["zoom"] if zoom is None else bool(zoom)
    consensus = settings["consensus"] if consensus is None else bool(consensus)
    thinking = (thinking or settings["thinking"])
    max_side = int(max_side or settings["max_side"])
    budget = float(deadline_s or settings["total_budget_s"])
    config = get_llm_config("vasi")
    model = config.get("vision_model")
    if not model or not config.get("api_key") or not config.get("base_url"):
        raise AnnotationContractError("当前配置没有可用的视觉模型，请先配置支持图片输入的模型")

    rgb, _ = canonical_image(image_bytes, max_side=max_side)
    h, w = rgb.shape[:2]
    started = time.monotonic()
    limit = started + budget
    passes: List[Dict[str, Any]] = []

    def remaining() -> float:
        return max(10.0, min(140.0, limit - time.monotonic()))

    async with AsyncOpenAI(api_key=config["api_key"], base_url=config["base_url"],
                           max_retries=0, timeout=remaining()) as client:
        full_b64 = encode_jpeg_base64(rgb)
        document, info = await _call_outline(
            client, model, full_b64, annotation_prompt(body_site),
            thinking=thinking, max_tokens=settings["max_tokens"], timeout_s=remaining())
        info["pass"] = "full"
        passes.append(info)

        if zoom and document.get("lesion_regions"):
            polys = [p for p in document["lesion_regions"] if isinstance(p, list)]
            ranked = sorted(range(len(polys)), key=lambda i: -polygon_area(polys[i]))
            chosen = set(ranked[: settings["zoom_regions"]])
            new_lesion: List[Any] = []
            new_uncertain = list(document.get("uncertain_regions") or [])
            for index, poly in enumerate(polys):
                if index not in chosen or time.monotonic() > limit - 5:
                    new_lesion.append(poly)
                    continue
                box = crop_box_for_polygon(poly)
                x1, y1, x2, y2 = pixel_box(box, w, h)
                if min(x2 - x1, y2 - y1) < 96:
                    new_lesion.append(poly)
                    continue
                try:
                    local, info = await _call_outline(
                        client, model, encode_jpeg_base64(rgb[y1:y2, x1:x2]), crop_prompt(body_site),
                        thinking=thinking, max_tokens=settings["max_tokens"], timeout_s=remaining())
                except Exception as exc:
                    logger.info("outline zoom pass skipped (%s)", type(exc).__name__)
                    new_lesion.append(poly)
                    continue
                info["pass"] = "zoom:%d" % index
                passes.append(info)
                remapped = [remap_polygon(p, box) for p in (local.get("lesion_regions") or [])
                            if isinstance(p, list)]
                remapped = [p for p in remapped if len(p) >= 3 and polygon_area(p) > 0]
                new_lesion.extend(remapped if remapped else [poly])
                for p in (local.get("uncertain_regions") or []):
                    if isinstance(p, list):
                        mapped = remap_polygon(p, box)
                        if len(mapped) >= 3:
                            new_uncertain.append(mapped)
            document = {**document, "lesion_regions": new_lesion,
                        "uncertain_regions": new_uncertain}

        agreement = None
        if consensus and time.monotonic() < limit - 5:
            second, info = await _call_outline(
                client, model, full_b64, annotation_prompt(body_site),
                thinking=thinking, max_tokens=settings["max_tokens"], timeout_s=remaining())
            info["pass"] = "consensus"
            passes.append(info)
            document, agreement = consensus_documents(document, second, w, h)

    skin = safe_raster(document.get("skin_regions") or [], w, h)
    if not skin.any():
        raise AnnotationContractError("未得到有效皮肤范围")
    lesion = safe_raster(document.get("lesion_regions") or [], w, h)
    uncertain = safe_raster(document.get("uncertain_regions") or [], w, h)
    meta = {
        "work_grid": [w, h],
        "max_side": max_side,
        "thinking": thinking,
        "zoom": bool(zoom),
        "consensus": bool(consensus),
        "consensus_iou": agreement,
        "passes": passes,
        "lesion_regions": len(document.get("lesion_regions") or []),
        "lesion_pixels": int(lesion.sum()),
        "uncertain_pixels": int(uncertain.sum()),
        "latency_s": round(time.monotonic() - started, 2),
        "source": "vision-outline-hires",
    }
    logger.info("vision outline: grid=%dx%d passes=%d lesion=%dpx uncertain=%dpx in %.1fs",
                w, h, len(passes), int(lesion.sum()), int(uncertain.sum()), meta["latency_s"])
    return document, meta


def propose_geometry_sync(image_bytes: bytes, body_site: str, **kwargs: Any
                          ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return asyncio.run(propose_geometry(image_bytes, body_site, **kwargs))
