"""Validate explicitly supplied, reviewed datasets; never harvest the user DB."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from PIL import Image

LABELS = ["background", "normal_skin", "depigmented_skin", "occlusion", "unreadable"]


def inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError("Dataset file missing")
    return path


def validate_manifest(path: Path, allow_synthetic: bool = False) -> Dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("labels") != LABELS
        or document.get("coordinate_frame") != "normalized_rgb"
    ):
        raise ValueError("Label dictionary or coordinate frame mismatch")
    synthetic = document.get("synthetic") is True
    if synthetic and not allow_synthetic:
        raise ValueError(
            "Synthetic dataset requires --allow-synthetic and cannot be registered"
        )
    authorization = document.get("authorization") or {}
    if authorization.get("training") is not True or not authorization.get("reference"):
        raise ValueError("Explicit dataset training authorization required")
    if (
        authorization.get("expires_at")
        and date.fromisoformat(authorization["expires_at"]) < date.today()
    ):
        raise ValueError("Dataset authorization expired")
    if not document.get("dataset_review_id"):
        raise ValueError("Dataset adjudication reference required")
    items = document.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Dataset is empty")
    subjects, hashes, ids = {}, {}, set()
    counts = {"train": 0, "validation": 0, "test": 0}
    root = path.parent
    for item in items:
        if not re.fullmatch(r"subject_[a-f0-9]{8,64}", item.get("subject_id", "")):
            raise ValueError("Use opaque, pseudonymous subject IDs")
        if (
            not re.fullmatch(r"image_[A-Za-z0-9_-]{1,80}", item.get("id", ""))
            or item["id"] in ids
        ):
            raise ValueError("Duplicate or invalid image ID")
        ids.add(item["id"])
        split = item.get("split")
        if split not in counts or not item.get("review_reference"):
            raise ValueError("Split and reviewed annotation reference required")
        if item["subject_id"] in subjects and subjects[item["subject_id"]] != split:
            raise ValueError("Subject leakage across dataset splits")
        subjects[item["subject_id"]] = split
        image_path = inside(root, item["image"])
        mask_path = inside(root, item["mask"])
        if hashlib.sha256(mask_path.read_bytes()).hexdigest() != item.get(
            "mask_sha256"
        ):
            raise ValueError("Mask hash mismatch")
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if digest != item.get("image_sha256"):
            raise ValueError("Image hash mismatch")
        if digest in hashes and hashes[digest] != split:
            raise ValueError("Duplicate image leakage across splits")
        hashes[digest] = split
        with Image.open(image_path) as image, Image.open(mask_path) as mask:
            if (
                image.getexif().get(274, 1) != 1
                or image.size != mask.size
                or mask.mode != "L"
            ):
                raise ValueError("Masks must align with already normalized photographs")
            if image.width * image.height > 20_000_000:
                raise ValueError("Image exceeds pixel limit")
            labels = np.asarray(mask)
            if (
                not np.isin(labels, [0, 1, 2, 3, 4, 255]).all()
                or int((labels != 255).sum()) < 64
            ):
                raise ValueError("Invalid or entirely unreviewed labels")
        if not isinstance(item.get("groups"), dict) or not all(
            key in item["groups"]
            for key in ["body_site", "skin_tone", "lighting", "quality", "device"]
        ):
            raise ValueError(
                "Evaluation grouping metadata required; use unknown when unavailable"
            )
        counts[split] += 1
    if not all(counts.values()):
        raise ValueError("Training, validation and locked test splits are all required")
    return {
        **document,
        "root": str(root.resolve()),
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "counts": counts,
        "subject_count": len(subjects),
    }


def load_item(root: Path, item: Dict[str, Any]):
    with Image.open(inside(root, item["image"])) as image:
        rgb = np.asarray(image.convert("RGB")).copy()
    with Image.open(inside(root, item["mask"])) as mask:
        labels = np.asarray(mask).copy()
    return rgb, labels
