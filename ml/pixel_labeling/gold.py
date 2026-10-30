"""Gold registry: approved human submissions, read from the shared DB (never a hand-kept list).

``group`` keeps photos of the same person together so leave-one-group-out evaluation cannot
learn a person's skin colour from one photo and be scored on another.
"""

from typing import Any, Dict, List, Tuple

import numpy as np

from ml.pixel_labeling import system_io as sio
from web.backend.database.database import SessionLocal
from web.backend.models.image_label import ImageLabel
from web.backend.models.label_submission import LabelSubmission
from web.backend.services.labeling.submissions import read_snapshot


def registry() -> List[Dict[str, Any]]:
    """Latest approved submission per task, sorted by task id."""
    db = SessionLocal()
    try:
        rows = (db.query(LabelSubmission).filter(LabelSubmission.status == "approved")
                .order_by(LabelSubmission.image_label_id, LabelSubmission.id.desc()).all())
        out: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            if r.image_label_id in out:
                continue
            label = db.get(ImageLabel, r.image_label_id)
            group = f"user{label.original_user_id}" if label.original_user_id else f"task{label.id}"
            out[r.image_label_id] = {"task_id": r.image_label_id, "submission_id": r.id,
                                     "revision": r.revision, "group": group}
        return [out[k] for k in sorted(out)]
    finally:
        db.close()


def load(entry: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """``(rgb, gold_labels)``; the label map is cached per submission in the work dir."""
    tid, sid = entry["task_id"], entry["submission_id"]
    cache = sio.work_dir(tid) / f"gold_s{sid}.npy"
    if cache.exists():
        labels = np.load(cache)
    else:
        labels = read_snapshot(tid, entry["revision"])
        np.save(cache, labels)
    return sio.load_image(tid), labels
