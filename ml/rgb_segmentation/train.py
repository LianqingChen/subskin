"""Train only an explicitly authorized manifest; export never activates a model."""

import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any, Dict
import numpy as np
from PIL import Image
import torch
from torch.nn import functional as F
from ml.rgb_segmentation.dataset import load_item, validate_manifest
from ml.rgb_segmentation.network import RGBUNet


class ReviewedDataset(torch.utils.data.Dataset):
    def __init__(self, document: dict, split: str, side: int):
        self.root = Path(document["root"])
        self.items = [i for i in document["items"] if i["split"] == split]
        self.side = side
        self.augment = split == "train"

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        rgb, label = load_item(self.root, self.items[index])
        h, w = label.shape
        factor = self.side / max(h, w)
        size = (max(1, round(w * factor)), max(1, round(h * factor)))
        image = np.asarray(
            Image.fromarray(rgb).resize(size, Image.Resampling.BILINEAR)
        ).copy()
        mask = np.asarray(
            Image.fromarray(label).resize(size, Image.Resampling.NEAREST)
        ).copy()
        frame = np.full((self.side, self.side, 3), 128, np.uint8)
        target = np.full((self.side, self.side), 255, np.int64)
        frame[: size[1], : size[0]] = image
        target[: size[1], : size[0]] = mask
        if self.augment:
            if random.random() < 0.5:
                frame, target = np.fliplr(frame).copy(), np.fliplr(target).copy()
            frame = np.clip(
                frame.astype(np.float32) * random.uniform(0.9, 1.1), 0, 255
            ).astype(np.uint8)
        return torch.from_numpy(frame.copy()).permute(
            2, 0, 1
        ).float() / 255, torch.from_numpy(target.copy())


def loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    ce = F.cross_entropy(logits, target, ignore_index=255)
    valid = target != 255
    safe = target.clone()
    safe[~valid] = 0
    truth = F.one_hot(safe, 5).permute(0, 3, 1, 2).float() * valid.unsqueeze(1)
    probability = torch.softmax(logits, 1) * valid.unsqueeze(1)
    numerator = 2 * (probability * truth).sum((0, 2, 3)) + 1e-6
    denominator = (probability + truth).sum((0, 2, 3)) + 1e-6
    return ce + 1 - (numerator / denominator).mean()


def train(
    manifest: Path,
    output: Path,
    epochs: int = 20,
    side: int = 512,
    allow_synthetic: bool = False,
) -> Dict[str, Any]:
    document = validate_manifest(manifest, allow_synthetic)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new private output directory")
    if not 1 <= epochs <= 500 or side not in (64, 128, 256, 512, 1024):
        raise ValueError("Invalid training configuration")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    torch.set_num_threads(2)
    torch.manual_seed(7)
    np.random.seed(7)
    random.seed(7)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = RGBUNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    training = torch.utils.data.DataLoader(
        ReviewedDataset(document, "train", side),
        batch_size=2,
        shuffle=True,
        num_workers=0,
    )
    validation = torch.utils.data.DataLoader(
        ReviewedDataset(document, "validation", side), batch_size=1, num_workers=0
    )
    history = []
    best = float("inf")
    stale = 0
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for image, target in training:
            optimizer.zero_grad()
            value = loss(model(image.to(device)), target.to(device))
            value.backward()
            optimizer.step()
            train_loss += float(value.detach())
        model.eval()
        val_loss = 0.0
        with torch.inference_mode():
            for image, target in validation:
                val_loss += float(loss(model(image.to(device)), target.to(device)))
        val_loss /= len(validation)
        if not np.isfinite(val_loss):
            raise ValueError("Training produced non-finite loss")
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss / len(training),
                "validation_loss": val_loss,
            }
        )
        if val_loss < best:
            best, stale = val_loss, 0
            torch.jit.script(model.cpu()).save(str(output / "model.pt"))
            model.to(device)
        else:
            stale += 1
        if stale >= 5:
            break
    report = {
        "model_id": "rgb-unet-" + document["manifest_sha256"][:12],
        "labels": document["labels"],
        "format": "torchscript",
        "input_type": "rgb_photo",
        "weights": "model.pt",
        "sha256": hashlib.sha256((output / "model.pt").read_bytes()).hexdigest(),
        "training_source": (
            "synthetic" if document.get("synthetic") else "authorized_reviewed_manifest"
        ),
        "dataset_review_id": document["dataset_review_id"],
        "manifest_sha256": document["manifest_sha256"],
        "counts": document["counts"],
        "subject_count": document["subject_count"],
        "side": side,
        "history": history,
        "encoder_initialization": "random_baseline_no_download",
        "enabled": False,
        "automatic_measurement": False,
    }
    (output / "training-report.json").write_text(json.dumps(report, indent=2))
    for path in output.iterdir():
        path.chmod(0o600)
    return report
