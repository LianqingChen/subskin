"""P8 boundary-band colour refinement (unattended, no gold).

Why: on 182 the main AI-vs-gold dispute was a faint depigmented band the model kept calling normal;
colour evidence (and a human look) sided with the gold, a same-family VLM referee did not.  Here each
skin pixel within ``band`` px of the voted lesion boundary is re-assigned to whichever of this
person's *local* colour centres (lesion core vs normal core, Gaussian-weighted within ``sigma`` px,
estimated from the AI's own eroded labels) it is closer to, with a ``margin`` towards no-change.

Parameters were chosen on dev golds 182/185/263 (18 configs; worst Δdice −0.003, 263 +0.024) and
frozen 2026-11-09 BEFORE scoring the next unseen image (192) — see RESULTS.md round 9.
"""

import cv2
import numpy as np

from ml.pixel_labeling import core

BAND, SIGMA, MARGIN = 5, 25, 0.1


def refine(rgb: np.ndarray, labels: np.ndarray, band: int = BAND, sigma: float = SIGMA,
           margin: float = MARGIN) -> np.ndarray:
    lab = cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32), (0, 0), 1.5)
    les = (labels == 2).astype(np.uint8)
    nor = (labels == 1).astype(np.uint8)
    if les.sum() < 200 or nor.sum() < 200:
        return labels
    skin = np.isin(labels, (1, 2))
    zone = cv2.dilate(les, core.disk(band)).astype(bool) & ~cv2.erode(les, core.disk(band)).astype(bool) & skin
    k = np.ones((9, 9), np.uint8)

    def local_centre(m):
        m = m.astype(np.float32)
        w = cv2.GaussianBlur(m, (0, 0), sigma)
        c = np.stack([cv2.GaussianBlur(lab[..., i] * m, (0, 0), sigma) / (w + 1e-6) for i in range(3)], -1)
        return c, w

    cl, wl = local_centre(cv2.erode(les, k))
    cn, wn = local_centre(cv2.erode(nor, k))
    zone &= (wl > 0.02) & (wn > 0.02)          # both colours present nearby, else leave as is
    dl = np.linalg.norm(lab - cl, axis=2)
    dn = np.linalg.norm(lab - cn, axis=2)
    score = (dn - dl) / (dn + dl + 1e-6)      # > 0: lesion-like
    out = labels.copy()
    out[zone] = np.where(score[zone] > margin, 2, 1)
    return out
