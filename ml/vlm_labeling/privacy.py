"""Gate before any pixel leaves the server (STD-03 §5.1; ml/pixel_labeling/system_io.load_image).

* ``label-source:`` tasks = admin imports of licensed public images (PMC CC BY/CC0, Commons) -> allowed.
* diary/job tasks (``/api/files/serve/vasi/...``) = L3 private photos -> blocked unless the photo
  owner authorised this specific processing; the authorisation note is written to an audit log.
"""

import datetime as dt
import json
from typing import Optional

from ml.pixel_labeling import system_io as sio
from web.backend.database.database import SessionLocal
from web.backend.models.image_label import ImageLabel

AUDIT = sio.WORK / "vlm_external_audit.jsonl"


def check(task_id: int, model: str, owner_consent: Optional[str]) -> str:
    db = SessionLocal()
    try:
        row = db.get(ImageLabel, task_id)
        if row is None:
            raise SystemExit(f"task {task_id} not found")
        url, owner = row.image_url or "", row.original_user_id
    finally:
        db.close()
    kind = "public-import" if url.startswith("label-source:") else "diary-photo"
    if kind == "diary-photo" and not owner_consent:
        raise SystemExit(
            f"task {task_id} is a diary photo of user {owner}: sending it to {model} needs the owner's "
            "authorisation for this processing (STD-03 §5.1). Re-run with --owner-consent '<who, when, scope>'.")
    sio.WORK.mkdir(parents=True, exist_ok=True)
    with open(AUDIT, "a") as f:
        f.write(json.dumps({"at": dt.datetime.now().isoformat(timespec="seconds"), "task": task_id, "kind": kind,
                            "owner_user_id": owner, "model": model, "owner_consent": owner_consent},
                           ensure_ascii=False) + "\n")
    return kind
