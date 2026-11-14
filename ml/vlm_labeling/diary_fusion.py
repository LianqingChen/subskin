"""Small-spot and boundary candidates for the diary's owner review."""

import numpy as np

from ml.vlm_labeling.refine import refine

# These are experimental drafts, with their own comparison against the helper.
SPARSE_SHARE = 0.10
WHITE_SUPPORT = 0.90
MAX_SMALLSPOTS = 96
SMALLSPOT_BATCH = 16
SMALLSPOT_ROUNDS = 3


def boundary_candidate(rgb, aided):
    return refine(rgb, aided) == 2


def sparse_candidates(rgb, base):
    """Use the branch's local contrast thresholds on the pre-helper ballot map."""
    from ml.pixel_labeling.core import depigmentation_score
    import cv2

    seed = refine(rgb, base)
    skin = np.isin(seed, (1, 2, 255))
    if not skin.any() or np.count_nonzero(seed == 2) >= SPARSE_SHARE * skin.sum():
        return seed, None
    scores = depigmentation_score(rgb, skin, 25, mode="local")
    allowed = (scores > 3.0) & skin & (seed != 2)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(
        allowed.astype(np.uint8), connectivity=8
    )
    high = np.unique(labels[(scores > 7.0) & allowed])
    rows = []
    for ident in map(int, high):
        if ident == 0:
            continue
        x, y, w, h, area = map(int, stats[ident])
        if area >= 8:
            pixels = labels[y : y + h, x : x + w] == ident
            score = float(scores[y : y + h, x : x + w][pixels].mean())
            rows.append((score, ident, (x, y, x + w, y + h)))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return seed, (labels, rows[:MAX_SMALLSPOTS], len(rows))


def confirm_smallspots(base, seed, aided, labels, accepted, probabilities):
    p, skin = probabilities
    conditional = np.divide(p, skin, out=np.full_like(p, 0.5), where=skin >= 0.5)
    add = (seed == 1) & (base == 1) & (aided == 1) & np.isin(labels, accepted)
    return (aided == 2) | (add & (conditional >= WHITE_SUPPORT))


def apply_fixed_helper(base, ballots, probabilities):
    if probabilities.shape != (2, *base.shape) or ballots.shape[1:] != base.shape:
        raise ValueError(
            "Auxiliary probabilities and ballots must share the source grid"
        )
    p, skin = probabilities
    if not (
        np.isfinite(probabilities).all()
        and (p >= 0).all()
        and (p <= skin + 1e-6).all()
        and (skin <= 1).all()
    ):
        raise ValueError("Invalid auxiliary probabilities")
    conditional = np.divide(p, skin, out=np.full_like(p, 0.5), where=skin >= 0.5)
    add = (base == 1) & (ballots == 2).any(axis=0) & (conditional >= WHITE_SUPPORT)
    remove = (base == 2) & (ballots == 1).any(axis=0) & (conditional <= 0.01)
    return np.where(add, 2, np.where(remove, 1, base)).astype(np.uint8)
