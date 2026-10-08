"""Owner-only per-photo measurements, distinct from registered change evidence."""
import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from web.backend.services.spot_compare import load_photo_ref


def finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def photo_measurement(info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    measurement = (info or {}).get("measurement") or {}
    annotation = measurement.get("annotation") or {}
    allowed = (measurement.get("version") in ("photo-mask-v1", "rgb-mask-v1")
               and measurement.get("status") in ("measured", "partial")
               and (not annotation or annotation.get("review_state") == "user_reviewed"))
    result = {"status": measurement.get("status", "unavailable"),
              "scope": "individual_photo", "version": measurement.get("version"),
              "source_ref": (info or {}).get("ref"),
              "area_percentage": None, "lesion_pixels": None, "skin_pixels": None,
              "area_cm2": None, "relative_lightness": None,
              "reasons": list(measurement.get("reasons") or [])}
    if allowed:
        for key in ("area_percentage", "lesion_pixels", "skin_pixels", "area_cm2"):
            result[key] = finite_number(measurement.get(key))
        result["relative_lightness"] = finite_number((measurement.get("color") or {}).get("relative_lightness"))
    else:
        result["status"] = "unavailable"
        result["reasons"] = result["reasons"] or ["缺少已核对的皮肤与白斑范围，请先完成照片标注"]
    return result


def pair_photo_measurements(db: Any, user_id: int, ref_a: str, ref_b: str) -> Dict[str, Any]:
    infos = [load_photo_ref(db, ref) for ref in (ref_a, ref_b)]
    if any(not info or info["user_id"] != user_id for info in infos):
        return {}
    a, b = sorted(infos, key=lambda info: info["date"])
    return {"before": photo_measurement(a), "after": photo_measurement(b)}


def supplement_report_quantification(db: Any, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich old owner views without modifying saved reports or pretending old data was computed."""
    if payload.get("report_type") != "comparison" or payload.get("status") != "completed":
        return payload
    metrics = payload.get("metrics") or {}
    pair = metrics.get("pair_metrics") or {}
    refs = metrics.get("refs") or []
    if pair.get("photo_measurements") or len(refs) < 2:
        return payload
    measurements = pair_photo_measurements(db, user_id, refs[0], refs[-1])
    if measurements:
        pair["photo_measurements"] = measurements
        pair["photo_measurement_source"] = "latest_source_records"
        pair["photo_measurements_as_of"] = datetime.now(timezone.utc).isoformat()
        metrics["pair_metrics"] = pair
        payload["metrics"] = metrics
    return payload
