"""Admin-reviewed RGB gold → private training manifest → training run → registry.

Chain: a user's RGB observation is projected into the admin queue
(``label_sync``); an admin saves masks (immutable snapshot, ``label_review``)
and approves the snapshot as gold; export re-checks model-training consent and
writes an ``ml.rgb_segmentation`` manifest with pseudonymous subjects; a
background run trains and evaluates; only a run that clears the locked test
gate can be registered. RGB labels never enter the legacy VasiTrainingSample
pipeline (``ImageLabel.training_eligible`` stays False for them).
"""

import hashlib
import hmac
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel, ImageLabelLog
from web.backend.services.assessment_measurement import read_details
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import decode_binary, encode_mask

LABELS = ["background", "normal_skin", "depigmented_skin", "occlusion", "unreadable"]
LABEL_SOURCES = ("admin_reviewed", "clinician")


# Resolved per call so tests (and RGB_SEGMENTATION_DATA_ROOT) can relocate storage.
def datasets_dir() -> Path:
    return artifacts.ROOT / "datasets"


def runs_dir() -> Path:
    return artifacts.ROOT / "training_runs"


def registry_path() -> Path:
    return artifacts.PROJECT_ROOT / "configs" / "rgb_segmentation_registry.json"


def models_dir() -> Path:
    return artifacts.PROJECT_ROOT / "models" / "rgb"

# Registration gate on the locked test split (never used for model selection).
GATE = {"min_test_images": 20, "min_test_subjects": 5, "min_dice": 0.80, "min_skin_dice": 0.85}
BODY_SITES = {"面部": "face", "颈部": "neck", "手部": "hand", "躯干": "trunk", "上肢": "arm", "下肢": "leg", "足部": "foot"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync(label: ImageLabel) -> Dict[str, Any]:
    return read_details(label.ai_details).get("rgb_sync") or {}


def _write_sync(label: ImageLabel, sync: Dict[str, Any]) -> None:
    details = read_details(label.ai_details)
    details["rgb_sync"] = sync
    label.ai_details = json.dumps(details, ensure_ascii=False)


def latest_snapshot(db: Session, label: ImageLabel) -> Optional[Dict[str, Any]]:
    row = (
        db.query(ImageLabelLog)
        .filter_by(image_label_id=label.id, action="rgb-admin-reference")
        .order_by(ImageLabelLog.id.desc())
        .first()
    )
    return read_details(row.new_value) if row else None


def gold_state(db: Session, label: ImageLabel) -> Dict[str, Any]:
    """What the admin UI needs to show for one RGB label."""
    from web.backend.services.data_consent import label_training_decision

    snapshot = latest_snapshot(db, label)
    gold = _sync(label).get("gold")
    consent = label_training_decision(db, label)
    return {
        "is_rgb": True,
        "snapshot_revision": snapshot.get("revision") if snapshot else None,
        "snapshot_draft": snapshot.get("draft") if snapshot else None,
        "gold": gold,
        "gold_current": bool(gold and snapshot and gold.get("revision") == snapshot.get("revision")),
        "consent_allowed": consent.allowed,
        "consent_reason": consent.reason,
    }


def approve_gold(db: Session, label: ImageLabel, actor: int, label_source: str = "admin_reviewed") -> Dict[str, Any]:
    """Mark the latest submitted (non-draft) admin snapshot as gold."""
    from web.backend.services.data_consent import label_training_decision

    if label_source not in LABEL_SOURCES:
        raise RGBSegmentationError("INVALID_REQUEST", "标注来源无效", 400)
    if label.is_user_deleted:
        raise RGBSegmentationError("NOT_FOUND", "原记录已删除", 404)
    snapshot = latest_snapshot(db, label)
    if not snapshot or snapshot.get("draft"):
        raise RGBSegmentationError("REVIEW_REQUIRED", "请先正式提交管理员标注，再审核通过", 409)
    decision = label_training_decision(db, label)
    if not decision.allowed:
        raise RGBSegmentationError("CONSENT_REQUIRED", "该用户未授权「改进识别」，不能作为训练金标准", 403)
    gold = {
        "revision": snapshot["revision"],
        "label_source": label_source,
        "approved_by": actor,
        "approved_at": _now(),
        "consent_grant_id": decision.grant_id,
    }
    sync = _sync(label)
    sync["gold"] = gold
    sync["training_state"] = "gold_approved"
    _write_sync(label, sync)
    label.training_eligible = False  # legacy U-Net pipeline must never pick RGB labels up
    db.add(ImageLabelLog(image_label_id=label.id, operator_id=actor, action="rgb-gold-approved",
                         new_value=json.dumps(gold, ensure_ascii=False)))
    return gold


def revoke_gold(db: Session, label: ImageLabel, actor: int) -> None:
    sync = _sync(label)
    old = sync.pop("gold", None)
    if not old:
        return
    sync["training_state"] = "awaiting_authorized_dataset"
    _write_sync(label, sync)
    db.add(ImageLabelLog(image_label_id=label.id, operator_id=actor, action="rgb-gold-revoked",
                         old_value=json.dumps(old, ensure_ascii=False)))


def _subject(user_id: Optional[int], label_id: int) -> str:
    key = (os.getenv("SECRET_KEY") or "").encode()
    if not key:
        raise RGBSegmentationError("CONFIG_MISSING", "服务端缺少密钥，无法生成匿名编号", 500)
    value = "user:%s" % user_id if user_id is not None else "admin-upload:%s" % label_id
    return "subject_" + hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:24]


def _gold_rows(db: Session) -> List[Dict[str, Any]]:
    from web.backend.services.data_consent import label_training_decision

    rows = []
    for label in db.query(ImageLabel).filter(ImageLabel.is_user_deleted.is_(False)).all():
        sync = _sync(label)
        gold = sync.get("gold")
        if not gold or not sync.get("job_id"):
            continue
        decision = label_training_decision(db, label)
        rows.append({"label": label, "sync": sync, "gold": gold, "consent": decision})
    return rows


def dataset_status(db: Session) -> Dict[str, Any]:
    rgb_total = labeled = 0
    for label in db.query(ImageLabel).filter(ImageLabel.is_user_deleted.is_(False)).all():
        if not _sync(label).get("job_id"):
            continue
        rgb_total += 1
        labeled += label.label_status == "labeled"
    gold = _gold_rows(db)
    usable = [r for r in gold if r["consent"].allowed]
    subjects = {_subject(r["label"].original_user_id, r["label"].id) for r in usable} if usable else set()
    return {
        "rgb_labels": rgb_total,
        "admin_labeled": labeled,
        "gold": len(gold),
        "gold_consented": len(usable),
        "gold_consent_withdrawn": len(gold) - len(usable),
        "subjects": len(subjects),
        "gate": GATE,
        "datasets": list_datasets(),
        "runs": list_runs(),
        "registry": registry_state(),
    }


def _split_for(subjects: List[str]) -> Dict[str, str]:
    """Deterministic subject-level split; every split gets a subject when possible."""
    ordered = sorted(subjects, key=lambda s: hashlib.sha256(s.encode()).hexdigest())
    split = {}
    for index, subject in enumerate(ordered):
        if index == 0:
            split[subject] = "test"
        elif index == 1:
            split[subject] = "validation"
        else:
            bucket = int(hashlib.sha256(subject.encode()).hexdigest(), 16) % 20
            split[subject] = "test" if bucket < 3 else "validation" if bucket < 6 else "train"
    return split


def export_dataset(db: Session, actor: int) -> Dict[str, Any]:
    """Write a private manifest from consented gold; validate it with the trainer's checker."""
    rows = [r for r in _gold_rows(db) if r["consent"].allowed]
    if not rows:
        raise RGBSegmentationError("NO_DATA", "还没有已授权、已审核通过的金标准标注", 409)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha256("|".join(sorted(r["gold"]["revision"] for r in rows)).encode()).hexdigest()[:8]
    dataset_id = "rgbds-%s-%s" % (stamp, digest)
    folder = datasets_dir() / dataset_id
    subjects = {r["label"].id: _subject(r["label"].original_user_id, r["label"].id) for r in rows}
    split = _split_for(sorted(set(subjects.values())))
    items, skipped = [], []
    for row in rows:
        label, sync, gold = row["label"], row["sync"], row["gold"]
        try:
            snap = artifacts.ROOT / "admin_labels" / str(label.id) / gold["revision"]
            meta = json.loads((snap / "metadata.json").read_text())
            raw = {name: (snap / name).read_bytes() for name in ("normal_skin.png", "lesion.png")}
            if any(hashlib.sha256(v).hexdigest() != meta["mask_sha256"][k] for k, v in raw.items()):
                raise ValueError("snapshot hash mismatch")
            image = artifacts.read_artifact(sync["job_id"], sync["ai_revision"], "image")
            manifest = artifacts.read_manifest(sync["job_id"], sync["ai_revision"])["metadata"]["image"]
            shape = (manifest["height"], manifest["width"])
            normal = decode_binary(raw["normal_skin.png"], shape)
            lesion = decode_binary(raw["lesion.png"], shape)
        except (OSError, KeyError, ValueError, RGBSegmentationError, json.JSONDecodeError):
            skipped.append({"label_id": label.id, "reason": "artifact_unavailable"})
            continue
        labels = np.zeros(shape, np.uint8)
        labels[normal] = 1
        labels[lesion] = 2
        image_id = "image_" + hashlib.sha256(image).hexdigest()[:20]
        mask_bytes = _label_png(labels)
        artifacts.atomic_write(folder / "images" / (image_id + ".png"), image)
        artifacts.atomic_write(folder / "masks" / (image_id + ".png"), mask_bytes)
        site = label.admin_body_site or label.user_body_site or label.ai_body_site
        items.append({
            "id": image_id,
            "subject_id": subjects[label.id],
            "split": split[subjects[label.id]],
            "image": "images/%s.png" % image_id,
            "mask": "masks/%s.png" % image_id,
            "image_sha256": hashlib.sha256(image).hexdigest(),
            "mask_sha256": hashlib.sha256(mask_bytes).hexdigest(),
            "review_reference": "image_label:%s:%s:%s" % (label.id, gold["revision"][:16], gold["label_source"]),
            "groups": {"body_site": BODY_SITES.get(site or "", "unknown"), "skin_tone": "unknown",
                       "lighting": "unknown", "quality": "unknown", "device": "unknown"},
        })
    # Same photo uploaded twice must stay in one split (validator rejects leakage).
    first = {}
    for item in items:
        first.setdefault(item["image_sha256"], item["split"])
        item["split"] = first[item["image_sha256"]]
    grants = sorted({str(r["consent"].grant_id) for r in rows if r["consent"].grant_id})
    document = {
        "labels": LABELS,
        "coordinate_frame": "normalized_rgb",
        "synthetic": False,
        "authorization": {
            "training": True,
            "reference": "data_consent:model_training:" + (",".join(grants) or "not_user_contributed"),
            "expires_at": (date.today() + timedelta(days=30)).isoformat(),
        },
        "dataset_review_id": dataset_id,
        "created_by": actor,
        "created_at": _now(),
        "items": items,
    }
    artifacts.atomic_write(folder / "manifest.json", json.dumps(document, ensure_ascii=False, indent=1).encode())
    counts = {s: sum(i["split"] == s for i in items) for s in ("train", "validation", "test")}
    report = {"dataset_id": dataset_id, "items": len(items), "skipped": skipped, "counts": counts,
              "subjects": len(set(subjects.values()))}
    try:
        from ml.rgb_segmentation.dataset import validate_manifest

        validate_manifest(folder / "manifest.json")
        report["valid"], report["error"] = True, None
    except (ValueError, OSError) as exc:
        report["valid"], report["error"] = False, str(exc)
    artifacts.atomic_write(folder / "export-report.json", json.dumps(report, ensure_ascii=False).encode())
    return report


def _label_png(labels: np.ndarray) -> bytes:
    import io
    from PIL import Image

    out = io.BytesIO()
    Image.fromarray(labels, mode="L").save(out, format="PNG", optimize=True)
    return out.getvalue()


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def list_datasets() -> List[Dict[str, Any]]:
    if not datasets_dir().exists():
        return []
    reports = [_read_json(p / "export-report.json") for p in sorted(datasets_dir().iterdir(), reverse=True) if p.is_dir()]
    return [r for r in reports if r][:20]


def _alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def list_runs() -> List[Dict[str, Any]]:
    if not runs_dir().exists():
        return []
    out = []
    for folder in sorted(runs_dir().iterdir(), reverse=True)[:20]:
        status = _read_json(folder / "status.json")
        if not status:
            continue
        if status.get("state") in ("queued", "training", "evaluating") and not _alive(status.get("pid")):
            status["state"], status["error"] = "failed", status.get("error") or "进程已退出"
        status["gate"] = gate_result(folder)
        out.append(status)
    return out


def start_training(dataset_id: str, actor: int, epochs: int = 30) -> Dict[str, Any]:
    if any(r["state"] in ("queued", "training", "evaluating") for r in list_runs()):
        raise RGBSegmentationError("BUSY", "已有训练在进行中", 409)
    report = _read_json(datasets_dir() / dataset_id / "export-report.json") if "/" not in dataset_id else None
    if not report or not report.get("valid"):
        raise RGBSegmentationError("INVALID_DATASET", "数据集未通过校验，不能训练", 409)
    if not 1 <= epochs <= 200:
        raise RGBSegmentationError("INVALID_REQUEST", "训练轮数需在 1~200 之间", 400)
    run_id = "rgbrun-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    folder = runs_dir() / run_id
    status = {"run_id": run_id, "dataset_id": dataset_id, "epochs": epochs, "state": "queued",
              "created_by": actor, "created_at": _now(), "pid": None, "error": None}
    artifacts.atomic_write(folder / "status.json", json.dumps(status).encode())
    env = {**os.environ, "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
    process = subprocess.Popen(
        ["nice", "-n", "15", sys.executable, "-m", "web.backend.services.rgb_segmentation.training_job", run_id],
        cwd=str(artifacts.PROJECT_ROOT), env=env, start_new_session=True,
        stdout=open(folder / "train.log", "ab"), stderr=subprocess.STDOUT,
    )
    status["pid"] = process.pid
    artifacts.atomic_write(folder / "status.json", json.dumps(status).encode())
    return status


def cancel_training(run_id: str) -> None:
    status = _read_json(runs_dir() / run_id / "status.json") if "/" not in run_id else None
    if not status or not _alive(status.get("pid")):
        raise RGBSegmentationError("NOT_FOUND", "没有进行中的训练", 404)
    os.killpg(status["pid"], signal.SIGTERM)


def gate_result(folder: Path) -> Dict[str, Any]:
    model = _read_json(folder / "eval-model.json")
    if not model:
        return {"passed": False, "reasons": ["尚无测试集评测"]}
    summary = model.get("summary") or {}
    baseline = (_read_json(folder / "eval-baseline.json") or {}).get("summary") or {}
    dice = (summary.get("dice") or {}).get("mean")
    skin = (summary.get("skin_dice") or {}).get("mean")
    base_dice = (baseline.get("dice") or {}).get("mean")
    subjects = len({r["subject_id"] for r in model.get("rows", [])})
    reasons = []
    if model.get("synthetic"):
        reasons.append("合成数据不能登记")
    if summary.get("images", 0) < GATE["min_test_images"]:
        reasons.append("测试集图片 %s 张，少于 %s" % (summary.get("images", 0), GATE["min_test_images"]))
    if subjects < GATE["min_test_subjects"]:
        reasons.append("测试集用户 %s 位，少于 %s" % (subjects, GATE["min_test_subjects"]))
    if dice is None or dice < GATE["min_dice"]:
        reasons.append("白斑 Dice %s，低于 %s" % (None if dice is None else round(dice, 3), GATE["min_dice"]))
    if skin is None or skin < GATE["min_skin_dice"]:
        reasons.append("皮肤 Dice %s，低于 %s" % (None if skin is None else round(skin, 3), GATE["min_skin_dice"]))
    if dice is not None and base_dice is not None and dice <= base_dice:
        reasons.append("未超过当前线上初稿（Dice %s）" % round(base_dice, 3))
    return {"passed": not reasons, "reasons": reasons, "dice": dice, "skin_dice": skin,
            "baseline_dice": base_dice, "test_subjects": subjects}


def registry_state() -> Dict[str, Any]:
    entry = _read_json(registry_path()) or {}
    return {k: entry.get(k) for k in ("enabled", "model_id", "dataset_review_id", "training_source", "registered_at", "run_id")}


def register_run(run_id: str, actor: int) -> Dict[str, Any]:
    folder = runs_dir() / run_id
    if "/" in run_id or not folder.is_dir():
        raise RGBSegmentationError("NOT_FOUND", "训练记录不存在", 404)
    gate = gate_result(folder)
    if not gate["passed"]:
        raise RGBSegmentationError("GATE_FAILED", "未达到登记门槛：" + "；".join(gate["reasons"]), 409)
    report = _read_json(folder / "training-report.json") or {}
    weights = (folder / "model.pt").read_bytes()
    if hashlib.sha256(weights).hexdigest() != report.get("sha256") or report.get("training_source") != "authorized_reviewed_manifest":
        raise RGBSegmentationError("ARTIFACT_INVALID", "模型文件校验失败", 409)
    name = report["model_id"] + ".pt"
    models_dir().mkdir(parents=True, exist_ok=True)
    artifacts.atomic_write(models_dir() / name, weights)
    entry = {
        "enabled": True, "model_id": report["model_id"], "input_type": "rgb_photo", "format": "torchscript",
        "weights": name, "sha256": report["sha256"], "labels": LABELS,
        "training_source": "authorized_reviewed_manifest", "dataset_review_id": report["dataset_review_id"],
        "automatic_measurement": False, "run_id": run_id, "registered_by": actor, "registered_at": _now(),
        "test_gate": gate,
    }
    if registry_path().exists():
        shutil.copyfile(registry_path(), registry_path().with_suffix(".prev.json"))
    artifacts.atomic_write(registry_path(), json.dumps(entry, ensure_ascii=False, indent=2).encode())
    return registry_state()


def disable_registry(actor: int) -> Dict[str, Any]:
    entry = _read_json(registry_path()) or {}
    if entry.get("enabled"):
        entry.update(enabled=False, disabled_by=actor, disabled_at=_now())
        artifacts.atomic_write(registry_path(), json.dumps(entry, ensure_ascii=False, indent=2).encode())
    return registry_state()
