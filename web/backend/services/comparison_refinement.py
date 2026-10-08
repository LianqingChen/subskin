"""Refine approximate positioning with stable landmarks, never lesion shape fitting."""
import math
from typing import Optional

import cv2
import numpy as np


def distributed(points: np.ndarray, shape: tuple) -> bool:
    """Reject fits supported by a single small patch or a straight edge."""
    h, w = shape[:2]
    spread = np.ptp(points, axis=0)
    area = cv2.contourArea(cv2.convexHull(points.astype(np.float32)))
    return bool(spread[0] >= w * .12 and spread[1] >= h * .12 and area >= h * w * .015)


def refine_transform(a: np.ndarray, b: np.ndarray, initial: np.ndarray,
                     mask_a: Optional[np.ndarray] = None,
                     mask_b: Optional[np.ndarray] = None) -> np.ndarray:
    """Keep the user's pose unless a bounded, well-supported correction is found.

    Track surrounding texture from the initially warped image to the reference.
    Forward/backward agreement rejects ambiguous matches. Only translation,
    rotation and uniform scale are permitted, so shape changes remain visible.
    """
    h, w = a.shape[:2]
    warped = cv2.warpAffine(b, initial, (w, h))
    source_mask = np.full(b.shape[:2], 255, np.uint8) if mask_b is None else mask_b
    mask = cv2.warpAffine(source_mask, initial, (w, h), flags=cv2.INTER_NEAREST)
    if mask_a is not None:
        mask = cv2.bitwise_and(mask, mask_a)
    mask = cv2.erode(mask, np.ones((25, 25), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    gray_b = cv2.cvtColor(warped, cv2.COLOR_RGB2GRAY)
    gray_a = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    points = cv2.goodFeaturesToTrack(gray_b, maxCorners=600, qualityLevel=.02, minDistance=8, mask=mask)
    if points is None or len(points) < 12:
        return initial
    options = dict(winSize=(25, 25), maxLevel=3,
                   criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, .01))
    forward, ok, error = cv2.calcOpticalFlowPyrLK(gray_b, gray_a, points, None, **options)
    if forward is None or ok is None or error is None or not np.isfinite(forward).all():
        return initial
    backward, back_ok, _ = cv2.calcOpticalFlowPyrLK(gray_a, gray_b, forward, None, **options)
    if backward is None or back_ok is None:
        return initial
    src, dst = points.reshape(-1, 2), forward.reshape(-1, 2)
    valid = (ok.ravel() > 0) & (back_ok.ravel() > 0) & (error.ravel() < 30)
    valid &= np.linalg.norm(backward.reshape(-1, 2) - src, axis=1) <= 1.5
    valid &= (dst[:, 0] >= 0) & (dst[:, 0] < w) & (dst[:, 1] >= 0) & (dst[:, 1] < h)
    if int(valid.sum()) < 12:
        return initial
    src, dst = src[valid], dst[valid]
    correction, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3)
    if correction is None or inliers is None or not np.isfinite(correction).all():
        return initial
    keep = inliers.ravel().astype(bool)
    if int(keep.sum()) < 10 or float(keep.mean()) < .6 or not distributed(dst[keep], a.shape):
        return initial
    scale = float(np.linalg.norm(correction[:, 0]))
    angle = abs(math.degrees(math.atan2(correction[1, 0], correction[0, 0])))
    center = np.array([w / 2., h / 2.])
    shift = np.linalg.norm(correction[:, :2] @ center + correction[:, 2] - center)
    if not .85 <= scale <= 1.18 or angle > 15 or shift > math.hypot(w, h) * .08:
        return initial
    before = float(np.median(np.linalg.norm(src[keep] - dst[keep], axis=1)))
    after = float(np.median(np.linalg.norm(src[keep] @ correction[:, :2].T + correction[:, 2] - dst[keep], axis=1)))
    if after > 2.5 or before - after < .5:
        return initial
    return (np.vstack((correction, [0, 0, 1])) @ np.vstack((initial, [0, 0, 1])))[:2]
