"""Read/write the shared labeling system (shared backend DB = production; writes are logged)."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

from web.backend.database.database import SessionLocal
from web.backend.models.image_label import ImageLabel
from web.backend.models.label_submission import LabelSubmission
from web.backend.services.labeling import class_map, sources, workflow
from web.backend.services.labeling.submissions import read_snapshot
from web.backend.services.rgb_segmentation import artifacts

REPO = Path(__file__).resolve().parents[2]
WORK = REPO / "data" / "labeling_work"
DECISIONS = Path(__file__).resolve().parent / "decisions"
REVIEWS = Path(__file__).resolve().parent / "reviews"


def work_dir(task_id: int) -> Path:
    d = WORK / str(task_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_decisions(task_id: int) -> Dict[str, Any]:
    f = DECISIONS / f"{task_id}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def load_image(task_id: int) -> np.ndarray:
    """RGB of the canonical task image, cached in the work dir. Never send job (diary) images to external models."""
    cache = work_dir(task_id) / "image.png"
    if not cache.exists():
        db = SessionLocal()
        try:
            raw, _ = sources.canonical(db.get(ImageLabel, task_id))
        finally:
            db.close()
        cache.write_bytes(raw)
    return np.array(Image.open(cache).convert("RGB"))


def ai_draft(task_id: int) -> Optional[np.ndarray]:
    db = SessionLocal()
    try:
        return sources.ai_draft(db.get(ImageLabel, task_id))
    finally:
        db.close()


def latest_submission(task_id: int, submission_id: Optional[int] = None) -> Tuple[Dict[str, Any], np.ndarray]:
    """Latest non-rejected human submission (or a specific one) and its class map."""
    db = SessionLocal()
    try:
        q = db.query(LabelSubmission).filter(LabelSubmission.image_label_id == task_id)
        row = (q.filter(LabelSubmission.id == submission_id) if submission_id
               else q.filter(LabelSubmission.status != "rejected").order_by(LabelSubmission.id.desc())).first()
        if row is None:
            raise SystemExit(f"task {task_id}: no human submission yet")
        info = {"submission_id": row.id, "author_id": row.author_id, "status": row.status,
                "prefill_source": row.prefill_source, "created_at": str(row.created_at), "revision": row.revision}
        return info, read_snapshot(task_id, row.revision)
    finally:
        db.close()


def apply_draft(task_id: int, labels: np.ndarray, model_id: str, source: str, actor_id: int) -> None:
    """Replace the AI draft for a ``pending`` task.

    - ``upload``: rewrite ``ai.png`` (keeps ``ai.v1.png`` backup on first replace).
    - ``job`` (diary, L3): write a new job revision (skin/lesion/uncertain) and point
      ``rgb_sync.ai_revision`` at it. Never send these images to external models.
    """
    db = SessionLocal()
    try:
        label = db.get(ImageLabel, task_id)
        kind = sources.kind(label)
        if label.label_status != "pending" or kind not in ("upload", "job"):
            raise SystemExit(f"task {task_id}: status={label.label_status} kind={kind} — refusing")
        if kind == "upload":
            _apply_upload(db, label, labels, model_id, source, actor_id)
        else:
            _apply_job(db, label, labels, model_id, source, actor_id)
        db.commit()
    finally:
        db.close()


def _apply_upload(db, label, labels, model_id, source, actor_id):
    folder = sources._source_dir(sources.sync_of(label)["source_id"])
    meta = json.loads((folder / "metadata.json").read_text())
    if labels.shape != (meta["height"], meta["width"]):
        raise SystemExit(f"shape {labels.shape} != image {(meta['height'], meta['width'])}")
    png = class_map.to_png(labels)
    if not (folder / "ai.v1.png").exists():
        artifacts.atomic_write(folder / "ai.v1.png", (folder / "ai.png").read_bytes())
        artifacts.atomic_write(folder / "metadata.v1.json", (folder / "metadata.json").read_bytes())
    old = meta["ai_sha256"]
    meta["ai_sha256"] = hashlib.sha256(png).hexdigest()
    meta["model"] = {"model_id": model_id, "source": source, "lesion_method": "pixel_reviewed"}
    artifacts.atomic_write(folder / "ai.png", png)
    artifacts.atomic_write(folder / "metadata.json", json.dumps(meta, ensure_ascii=False).encode())
    workflow._log(db, label, actor_id, "ai-draft-replaced",
                  {"model_id": model_id, "old_ai_sha256": old, "new_ai_sha256": meta["ai_sha256"],
                   "stats": class_map.stats(labels)})
    if not np.array_equal(sources.ai_draft(label), labels):
        raise SystemExit("verification failed: stored draft differs")


def _resolve_job_revision(job_id: str, sync: Dict[str, Any]) -> str:
    """Pick a readable revision; current pointer may be a dangling hash (→ 标注版本暂不可用)."""
    candidates = [sync.get("ai_revision"), sync.get("previous_ai_revision")]
    for rev in candidates:
        if not rev:
            continue
        try:
            artifacts.read_manifest(job_id, rev)
            return rev
        except Exception:
            continue
    raise SystemExit(f"job {job_id}: no readable ai_revision (tried {candidates})")


def _apply_job(db, label, labels, model_id, source, actor_id):
    """Diary job: five-class → skin/lesion/uncertain. Class 3 becomes excluded (not skin)."""
    import shutil
    from web.backend.services.rgb_segmentation.dataset_pipeline import write_sync
    from web.backend.services.rgb_segmentation.images import encode_mask

    sync = sources.sync_of(label)
    job_id = sync["job_id"]
    base_rev = _resolve_job_revision(job_id, sync)
    image = artifacts.read_artifact(job_id, base_rev, "image")
    old_manifest = artifacts.read_manifest(job_id, base_rev)
    h, w = labels.shape
    if (h, w) != (old_manifest["metadata"]["image"]["height"], old_manifest["metadata"]["image"]["width"]):
        raise SystemExit("label shape != job image shape")
    skin = np.isin(labels, (1, 2, 255)).astype(bool)
    lesion = (labels == 2).astype(bool)
    uncertain = (labels == 255).astype(bool)
    excluded = (labels == 3).astype(bool)
    model = {"model_id": model_id, "source": source, "lesion_method": "pixel_reviewed",
             "note": "pixel-reviewed draft; please verify before submit"}
    # Keep metadata.image.sha256 aligned with the image bytes we write (read_manifest checks this).
    image_meta = dict(old_manifest["metadata"]["image"])
    image_meta["sha256"] = hashlib.sha256(image).hexdigest()
    new_manifest = artifacts.write_revision(
        job_id, image,
        {"skin": encode_mask(skin), "lesion": encode_mask(lesion),
         "uncertain": encode_mask(uncertain), "excluded": encode_mask(excluded)},
        {"image": image_meta, "model": model,
         "quality": old_manifest["metadata"].get("quality"),
         "calibration": old_manifest["metadata"].get("calibration"),
         "pixel_review": {"previous_ai_revision": base_rev, "actor_id": actor_id}},
    )
    new_rev = new_manifest["revision"]
    folder = artifacts.job_directory(job_id) / new_rev
    if not folder.is_dir() or not (folder / "metadata.json").exists():
        raise SystemExit(f"write_revision returned {new_rev} but folder missing on disk")
    # Durable local backup — job revisions have gone missing once already.
    backup = work_dir(label.id) / "job_revision_backup" / new_rev
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(folder, backup)
    artifacts.read_manifest(job_id, new_rev)  # same check the API uses
    new_sync = {**sync, "ai_revision": new_rev, "model": model, "previous_ai_revision": base_rev}
    write_sync(label, new_sync)
    workflow._log(db, label, actor_id, "ai-draft-replaced",
                  {"model_id": model_id, "old_ai_revision": sync.get("ai_revision"),
                   "base_ai_revision": base_rev, "new_ai_revision": new_rev,
                   "stats": class_map.stats(labels), "backup": str(backup)})
    expected = class_map.from_masks(skin, lesion, uncertain)
    got = sources.ai_draft(label)
    if got is None or not np.array_equal(got, expected):
        raise SystemExit("verification failed: job draft mismatch")
