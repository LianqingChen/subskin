"""Local-only semantic relevance evidence; not a calibrated admission policy."""
import hashlib
import math
from pathlib import Path
from typing import Dict
import numpy as np

MODEL_ID = "google/siglip-base-patch16-224"
REVISION = "7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed"  # pragma: allowlist secret (public model fingerprint)
WEIGHTS_SHA256 = "2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8"  # pragma: allowlist secret (public model fingerprint)
PROMPTS = {
    "skin_closeup": "This is a photograph of a close-up of human skin.",
    "hand_photo": "This is a photograph of a real human hand or foot.",
    "face_photo": "This is a photograph of a real human face or body.",
    "document": "This is a document page with printed text.",
    "graphic": "This is a computer generated graphic with flat colored shapes.",
    "checkerboard": "This is a checkerboard pattern.",
    "surface": "This is a plain wall, fabric, wood, or painted surface.",
    "object": "This is a photograph of an object, not a human body.",
}
MODALITY_PROMPTS = {
    "visible_light": "This is a photograph of human skin under normal visible light.",
    "wood_lamp": "This is a photograph of human skin under a blue ultraviolet Wood's lamp.",
}
SKIN = frozenset({"skin_closeup", "hand_photo", "face_photo"})


def summarize_scores(scores: Dict[str, float]) -> dict:
    if set(scores) != set(PROMPTS) or not all(math.isfinite(v) for v in scores.values()):
        raise ValueError("Complete finite prompt scores required")
    margin = max(scores[k] for k in SKIN) - max(v for k, v in scores.items() if k not in SKIN)
    return {"scores": dict(scores), "top_prompt": max(scores, key=scores.get),
            "skin_minus_other_margin": margin,
            "ranked_domain": "skin" if margin > 0 else "nonmedical" if margin < 0 else "ambiguous",
            "calibrated": False, "measurement_eligible": False,
            "modality_validated": False, "clinical_accuracy": None}


class LocalRelevanceEncoder:
    """Pinned, hash-verified encoder; no API calls, downloads or remote Python."""
    def __init__(self, model_dir: Path):
        import torch
        from transformers import AutoModel, AutoProcessor
        with (model_dir / "model.safetensors").open("rb") as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != WEIGHTS_SHA256:
            raise ValueError("Unexpected relevance model weights")
        self.processor = AutoProcessor.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False, use_fast=False)
        self.model = AutoModel.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False,
            use_safetensors=True).eval()
        tokens = self.processor(text=list(PROMPTS.values()), padding="max_length", return_tensors="pt")
        with torch.inference_mode():
            self.text = torch.nn.functional.normalize(self.model.get_text_features(**tokens), dim=-1)
            modality_tokens = self.processor(text=list(MODALITY_PROMPTS.values()), padding="max_length", return_tensors="pt")
            self.modality_text = torch.nn.functional.normalize(self.model.get_text_features(**modality_tokens), dim=-1)

    def score(self, rgb: np.ndarray) -> dict:
        import torch
        from PIL import Image
        if (rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3
                or min(rgb.shape[:2]) < 1 or rgb.shape[0] * rgb.shape[1] > 20_000_000):
            raise ValueError("Expected bounded uint8 RGB image")
        inputs = self.processor(images=Image.fromarray(rgb), return_tensors="pt")
        with torch.inference_mode():
            image = torch.nn.functional.normalize(self.model.get_image_features(**inputs), dim=-1)
            logits = (image @ self.text.T) * self.model.logit_scale.exp() + self.model.logit_bias
            modality_logits = (image @ self.modality_text.T) * self.model.logit_scale.exp() + self.model.logit_bias
        result = summarize_scores(dict(zip(PROMPTS, logits[0].tolist())))
        modality_scores = dict(zip(MODALITY_PROMPTS, modality_logits[0].tolist()))
        result["acquisition_probe"] = {
            "scores": modality_scores, "top_prompt": max(modality_scores, key=modality_scores.get),
            "visible_minus_wood_margin": modality_scores["visible_light"] - modality_scores["wood_lamp"],
            "calibrated": False,
        }
        return {**result, "model_id": MODEL_ID, "revision": REVISION, "weights_sha256": WEIGHTS_SHA256}
