"""AI label map vs gold. Gold ``255`` (unknown) is ignored everywhere.

``lesion_dice_tol2`` also ignores pixels within 2px of the gold lesion border: two careful
humans disagree there, so it is the closest pixel metric to "would a reviewer accept this".
"""

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

TOL = 2


def _dice(a: np.ndarray, b: np.ndarray, keep: np.ndarray) -> Optional[float]:
    a, b = a & keep, b & keep
    s = int(a.sum() + b.sum())
    return round(2 * int((a & b).sum()) / s, 4) if s else None


def lesion_dice(ai: np.ndarray, gold: np.ndarray) -> Optional[float]:
    return _dice(ai == 2, gold == 2, gold != 255)


def summary(ai: np.ndarray, gold: np.ndarray) -> Dict[str, Any]:
    known = gold != 255
    g_les = (gold == 2).astype(np.uint8)
    border = cv2.morphologyEx(g_les, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    band = cv2.dilate(border.astype(np.uint8), np.ones((2 * TOL + 1,) * 2, np.uint8)).astype(bool)
    skin_ai, skin_gold = np.isin(ai, (1, 2, 255)), np.isin(gold, (1, 2))
    n = lambda m: int(m.sum())  # noqa: E731
    les_ai, les_gold = n((ai == 2) & known), n(gold == 2)
    sk_ai, sk_gold = n((ai == 1) & known) + les_ai, n(gold == 1) + les_gold
    return {
        "lesion_dice": lesion_dice(ai, gold),
        "lesion_dice_tol2": _dice(ai == 2, gold == 2, known & ~band),
        "skin_dice": _dice(skin_ai, skin_gold, known),
        "occl_dice": _dice(ai == 3, gold == 3, known),
        "ai_ratio": round(100 * les_ai / max(sk_ai, 1), 2),
        "gold_ratio": round(100 * les_gold / max(sk_gold, 1), 2),
        # class mistakes that hurt training semantics (lesson L-201-2: clothes ≠ occlusion)
        "bg_as_occl": n((ai == 3) & (gold == 0)),
        "occl_as_lesion": n((ai == 2) & (gold == 3)),
    }


def mean(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    out = {}
    for k in ("lesion_dice", "lesion_dice_tol2", "skin_dice"):
        v = [r[k] for r in rows if r.get(k) is not None]
        out[k] = round(float(np.mean(v)), 4) if v else None
    return out
