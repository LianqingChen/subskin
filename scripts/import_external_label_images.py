"""Import openly licensed vitiligo photos into the admin five-class labeling queue.

Reads a harvester manifest (``harvest_pmc_vitiligo_images.py`` or
``harvest_commons_vitiligo_images.py``), and creates one ``admin_upload`` task
per image through ``services.labeling.uploads`` (canonicalize + AI draft),
keeping full attribution in the task provenance. Photos from the same article
share a pseudonymous subject so they never straddle train/test.

Usage (production DB, run from repo root):
    .venv/bin/python -I scripts/import_external_label_images.py --source pmc \
        --dir data/external/pmc_vitiligo --actor 1 [--limit 50] [--dry-run]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def content_check(data: bytes) -> dict:
    """Cheap photo-vs-figure screen tuned on 40 hand-reviewed PMC figures (1 FP, 1 FN).

    Journal figures include diagrams, charts and microscopy that captions do not
    rule out. Wood's lamp photos are a different imaging domain from the diary's
    phone RGB photos, so they are held back rather than imported.
    """
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "reason": "unreadable"}
    h, w = img.shape[:2]
    scale = 512 / max(h, w)
    img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    skin = float(((ycc[..., 1] >= 135) & (ycc[..., 1] <= 175) & (ycc[..., 2] >= 80) & (ycc[..., 2] <= 130)
                  & (ycc[..., 0] > 50)).mean())
    white = float((img.min(axis=2) > 235).mean())
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grad = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    flat = float((grad < 2).mean())
    blue = float(((hsv[..., 0] > 100) & (hsv[..., 0] < 140) & (hsv[..., 1] > 80) & (hsv[..., 2] > 60)).mean())
    feats = {"skin": round(skin, 3), "white": round(white, 3), "flat": round(flat, 3), "blue": round(blue, 3)}
    if blue >= 0.30:
        return {"ok": False, "reason": "wood_lamp", **feats}
    if white > 0.5 or flat > 0.3 or skin < 0.12:
        return {"ok": False, "reason": "not_clinical_photo", **feats}
    return {"ok": True, **feats}


def records(source: str, folder: Path) -> list:
    if source == "pmc":
        rows = [json.loads(line) for line in (folder / "manifest.jsonl").read_text().splitlines() if line.strip()]
        return [{
            "file": r["file"],
            "subject_ref": r["pmcid"],
            "note": ("PMC开放获取 %s：%s %s" % (r["license"], r["citation"] or "", r["figure_label"] or "")).strip()[:200],
            "external": {"source": "pmc_oa", "pmcid": r["pmcid"], "doi": r["doi"], "license": r["license"],
                         "citation": r["citation"], "figure": r["figure_label"], "caption": r["caption"][:600],
                         "url": r["source_url"]},
        } for r in rows]
    rows = json.loads((folder / "manifest.json").read_text())["kept"]
    return [{
        "file": r["file"],
        "subject_ref": "COMMONS-" + r["sha256"][:16],
        "note": ("Wikimedia Commons %s：%s（%s）" % (r["license"], r["title"], r["artist"])).strip()[:200],
        "external": {"source": "wikimedia_commons", "license": r["license"], "license_url": r["license_url"],
                     "share_alike": r["share_alike"], "artist": r["artist"], "url": r["page_url"]},
    } for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["pmc", "commons"], required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--actor", type=int, required=True, help="admin user id recorded as uploader")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.path[:0] = [str(ROOT), str(ROOT / "web" / "backend")]
    from dotenv import load_dotenv

    load_dotenv(ROOT / "web" / "backend" / ".env", override=True)  # same DB/secret as the backend
    from web.backend.app import main as _app  # noqa: F401  (registers every model, runs additive migrations)
    from web.backend.database.database import SessionLocal
    from web.backend.database.models import User
    from web.backend.exceptions import RGBSegmentationError
    from web.backend.services.labeling import uploads

    folder = Path(args.dir)
    log_path = folder / "imported.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    todo = [r for r in records(args.source, folder) if r["file"] not in log]
    if args.limit:
        todo = todo[: args.limit]
    print("to import:", len(todo))
    checks = {r["file"]: content_check((folder / "images" / r["file"]).read_bytes()) for r in todo}
    (folder / "content_check.json").write_text(json.dumps(checks, indent=1))
    reasons = {}
    for c in checks.values():
        reasons[c.get("reason", "ok")] = reasons.get(c.get("reason", "ok"), 0) + 1
    print("content check:", reasons)
    excluded_path = folder / "manual_exclude.json"  # reviewer's contact-sheet decisions (file -> reason)
    excluded = json.loads(excluded_path.read_text()) if excluded_path.exists() else {}
    print("manual exclusions:", sum(1 for r in todo if r["file"] in excluded))
    todo = [r for r in todo if checks[r["file"]]["ok"] and r["file"] not in excluded]
    if args.dry_run:
        for r in todo[:5]:
            print(r["file"], r["subject_ref"], r["note"])
        return 0
    with SessionLocal() as db:
        actor = db.get(User, args.actor)
        if actor is None or not actor.is_admin:
            print("actor must be an admin user")
            return 1
        for i, r in enumerate(todo, 1):
            data = (folder / "images" / r["file"]).read_bytes()
            try:
                result = uploads.upload_photos(db, args.actor, [(r["file"], data)], r["note"], r["subject_ref"],
                                               True, external=r["external"])
                db.commit()
            except RGBSegmentationError as exc:
                db.rollback()
                result = {"created": [], "skipped": [{"reason": str(exc)}]}
            log[r["file"]] = result["created"][0] if result["created"] else {"skipped": result["skipped"][0]["reason"]}
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
            if i % 10 == 0:
                print(i, "done", flush=True)
    created = sum(isinstance(v, int) for v in log.values())
    print("created total", created, "skipped total", len(log) - created)
    return 0


if __name__ == "__main__":
    sys.exit(main())
