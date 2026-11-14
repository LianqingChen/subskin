"""Export a frozen visual-model coating in SubSkin's local review formats."""

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional, Sequence

import numpy as np
from PIL import Image

from ml.vlm_labeling import protocol
from web.backend.services.labeling import class_map
from web.backend.services.rgb_segmentation.images import decode_binary, encode_mask
from web.backend.utils.body_sites import normalize, site_labels


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _review_tags(value: Dict[str, Any]) -> Dict[str, Any]:
    normalized = protocol._triage_tags(value)
    observations = normalized["body_site_observations"]
    appearance = value.get("appearance_tags")
    return {
        "body_site_codes": normalized["body_site_codes"],
        "body_sites": normalized["body_sites"],
        "affected_body_site_codes": normalized["affected_body_site_codes"],
        "affected_body_sites": normalized["affected_body_sites"],
        "body_site_observations": [item for item in observations if normalize(item) is None],
        "skin_tone_description": normalized["skin_tone_description"],
        "appearance_tags": appearance if isinstance(appearance, dict) else {},
        "structured_appearance_tags": normalized["appearance_tags"],
        "clinical_assessment": normalized["clinical_assessment"],
    }


def summarize_tag_candidates(candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Count observations from normalized passes without deciding reviewed labels."""
    raw_fields = Counter(key for row in candidates for key, value in row["appearance_tags"].items() if value)
    structured = {}
    for row in candidates:
        for key, value in row["structured_appearance_tags"].items():
            values = value if isinstance(value, list) else [value]
            structured.setdefault(key, Counter()).update(v for v in values if v != "不确定")
    types = Counter(value for row in candidates for value in row["clinical_assessment"]["candidate_types"])
    labels = site_labels()

    def site_candidates(field):
        counts = Counter(code for row in candidates for code in row[field])
        return [{"code": code, "label": labels[code], "supporting_passes": count}
                for code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]

    return {
        "pass_count": len(candidates),
        "body_site_candidates": site_candidates("body_site_codes"),
        "affected_body_site_candidates": site_candidates("affected_body_site_codes"),
        "raw_appearance_field_coverage": dict(sorted(raw_fields.items())),
        "structured_appearance_value_counts": {k: dict(sorted(v.items())) for k, v in sorted(structured.items())},
        "clinical_candidates": {
            "candidate_type_counts": dict(sorted(types.items())),
            "status": "unconfirmed", "evidence_scope": "image_only", "review_required": True,
        },
    }


def export_packet(labels_file: Path, labels_sha256: str, source_rgb_sha256: str,
                  model: str, triages: Sequence[Dict[str, Any]], destination: Path, *,
                  triage_sources: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{64}", source_rgb_sha256):
        raise ValueError("A frozen source RGB SHA-256 is required")
    frozen = labels_file.read_bytes()
    if _sha(frozen) != labels_sha256:
        raise ValueError("Coating does not match its frozen fingerprint")
    labels = np.load(io.BytesIO(frozen), allow_pickle=False)
    if labels.ndim != 2 or labels.dtype != np.uint8 or not np.isin(labels, class_map.VALUES).all():
        raise ValueError("Coating must be a two-dimensional SubSkin class map")
    normal = labels == class_map.NORMAL
    lesion = labels == class_map.LESION
    layers = {"normal_skin.png": normal, "lesion.png": lesion, "total_skin.png": normal | lesion}
    raw = class_map.to_png(labels)
    assert np.array_equal(class_map.from_png(raw, labels.shape), labels)
    files = {"labels.png": raw}
    for name, mask in layers.items():
        encoded = encode_mask(mask)
        assert np.array_equal(decode_binary(encoded, labels.shape), mask)
        files[name] = encoded
    candidates = [_review_tags(row) for row in triages]
    if triage_sources is not None and len(triage_sources) != len(candidates):
        raise ValueError("Every tag candidate must have one source record")
    result = {
        "model": model, "review_state": "unreviewed_ai_candidate",
        "source_rgb_sha256": source_rgb_sha256, "frozen_coating_sha256": labels_sha256,
        "shape": list(labels.shape), "class_names": class_map.NAMES, "class_stats": class_map.stats(labels),
        "mask_sha256": {name: _sha(content) for name, content in files.items()},
        "triage_candidates": candidates, "tag_summary": summarize_tag_candidates(candidates),
    }
    if triage_sources is not None:
        result["triage_sources"] = list(triage_sources)
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    with TemporaryDirectory(prefix=".review-packet-", dir=destination.parent) as folder:
        packet = Path(folder) / "packet"
        packet.mkdir(mode=0o700)
        for name, content in files.items():
            (packet / name).write_bytes(content)
        (packet / "metadata.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        packet.rename(destination)
    return result


def _canonical_run_source(task):
    from ml.pixel_labeling import system_io
    from web.backend.database.database import SessionLocal
    from web.backend.services.labeling import sources, tasks

    with SessionLocal() as db:
        rgb, shape = sources.canonical(tasks.get_visible(db, task))
    with Image.open(io.BytesIO(rgb)) as image:
        canonical = np.asarray(image.convert("RGB"))
    if not np.array_equal(canonical, system_io.load_image(task)):
        raise ValueError("Run image cache differs from the canonical task image")
    return rgb, shape, canonical


def _run_decision(run, task=None, model=None):
    raw = (run / "decision.json").read_bytes()
    decision = json.loads(raw)
    if decision["model"].startswith("sim:") or decision.get("provider") == "simulated":
        raise ValueError("A simulated run cannot be exported as an AI review candidate")
    if task is not None and (decision["task_id"], decision["model"]) != (task, model):
        raise ValueError("Voting inputs must belong to the same task and model")
    return decision, {"run": run.name, "density": decision.get("regions", {}).get("n_skin"),
                      "decision_sha256": _sha(raw)}


def _verified_labels(path, reconstructed, shape):
    payload = path.read_bytes()
    labels = np.load(io.BytesIO(payload), allow_pickle=False)
    if labels.shape != shape or not np.array_equal(labels, reconstructed):
        raise ValueError(f"{path.name} differs from the reconstructed coating")
    return _sha(payload)


def export_run(run: Path, destination: Path) -> Dict[str, Any]:
    """Export a completed real-model run with verified source and coating identity."""
    decision, source = _run_decision(run)
    task, model = decision["task_id"], decision["model"]
    rgb, shape, _ = _canonical_run_source(task)
    labels_file = run / "labels.npy"
    digest = _verified_labels(labels_file, protocol.replay(run), shape)
    triage = decision.get("triage")
    triages = [triage] if isinstance(triage, dict) else []
    return export_packet(labels_file, digest, _sha(rgb), model, triages, destination,
                         triage_sources=[source] if triages else [])


def export_auto(run: Path, destination: Path) -> Dict[str, Any]:
    """Export a complete same-model density vote and its original triage passes."""
    from ml.vlm_labeling.__main__ import vote_labels
    from ml.vlm_labeling.refine import refine

    meta = json.loads((run / "auto.json").read_text(encoding="utf-8"))
    task, model = meta["task_id"], meta["model"]
    if model.startswith("sim:") or meta["protocol"] not in ("v4", "v5"):
        raise ValueError("Expected a real-model v4 or v5 automatic labeling run")
    if (run / "incomplete.json").exists():
        raise ValueError("Automatic labeling run is incomplete")
    base_runs = [Path(path).resolve() for path in meta["runs"]]
    anchors = [Path(path).resolve() for path in meta["anchors"]]
    voters = base_runs + anchors
    if not base_runs or len(set(voters)) != len(voters) or meta["n_votes"] != len(voters):
        raise ValueError("Automatic labeling vote inventory is incomplete or duplicated")
    anchor_paths = {base.with_name(base.name + "+anchor") for base in base_runs}
    if not set(anchors) <= anchor_paths:
        raise ValueError("Automatic labeling anchor lacks its base run")
    decisions, sources = zip(*(_run_decision(path, task, model) for path in voters))
    densities = meta.get("regions_list")
    if densities is not None and sorted(densities) != sorted(row["regions"]["n_skin"] for row in decisions[:len(base_runs)]):
        raise ValueError("Automatic labeling densities differ from the planned run")
    rgb, shape, canonical = _canonical_run_source(task)
    source = meta.get("rgb_pixels_sha256")
    if source is not None and source != protocol._sha256_array(canonical):
        raise ValueError("Automatic labeling source RGB differs from its frozen fingerprint")
    rule = meta.get("rubric_sha256")
    if rule is not None and _sha((run / "rubric.snapshot.md").read_bytes()) != rule:
        raise ValueError("Automatic labeling rubric differs from its frozen snapshot")
    for path in voters:
        if rule is not None and _sha((path / "rubric.snapshot.md").read_bytes()) != rule:
            raise ValueError("Automatic labeling voter uses a different rubric")
    voted, task_id = vote_labels(voters)
    if task_id != task:
        raise ValueError("Automatic labeling vote belongs to a different task")
    labels_file = run / "labels.npy"
    if meta["protocol"] == "v5":
        _verified_labels(run / "labels_vote.npy", voted, shape)
        digest = _verified_labels(labels_file, refine(canonical, voted), shape)
    else:
        payload = labels_file.read_bytes()
        labels = np.load(io.BytesIO(payload), allow_pickle=False)
        if labels.shape != shape:
            raise ValueError("Automatic labeling coating has the wrong image grid")
        # Archived v4 metadata predates the v5 name. Some runs used P8
        # while still writing v4. Accept only a pixel-exact reconstruction.
        if not np.array_equal(labels, voted) and not np.array_equal(labels, refine(canonical, voted)):
            raise ValueError("labels.npy differs from the reconstructed v4 vote and boundary refinement")
        digest = _sha(payload)
    passes = [(row["triage"], source) for row, source in zip(decisions[:len(base_runs)], sources)
              if isinstance(row.get("triage"), dict)]
    return export_packet(labels_file, digest, _sha(rgb), model, [row for row, _ in passes], destination,
                         triage_sources=[source for _, source in passes])


def check_task_packet(task_id: int, packet: Path) -> Dict[str, Any]:
    """Check image identity and draft compatibility through the admin task's read path."""
    from web.backend.database.database import SessionLocal
    from web.backend.services.labeling import sources, tasks

    metadata = json.loads((packet / "metadata.json").read_text())
    with SessionLocal() as db:
        label = tasks.get_visible(db, task_id)
        rgb, shape = sources.canonical(label)
        kind, status, benchmark = sources.kind(label), label.label_status, bool(label.benchmark)
    if metadata.get("source_rgb_sha256") != _sha(rgb) or metadata.get("shape") != list(shape):
        raise ValueError("Review packet does not match this task's canonical image")

    names = ("labels.png", "normal_skin.png", "lesion.png", "total_skin.png")
    mask_hashes = metadata.get("mask_sha256", {})
    payloads = {name: (packet / name).read_bytes() for name in names}
    if any(_sha(payloads[name]) != mask_hashes.get(name) for name in names):
        raise ValueError("Review packet mask checksum mismatch")
    labels = class_map.from_png(payloads["labels.png"], shape)
    normal, lesion = labels == class_map.NORMAL, labels == class_map.LESION
    layers = {"normal_skin.png": normal, "lesion.png": lesion, "total_skin.png": normal | lesion}
    for name, expected in layers.items():
        if not np.array_equal(decode_binary(payloads[name], shape), expected):
            raise ValueError(f"{name} differs from the review packet's class map")

    restored = labels
    if kind == "job":
        unknown = labels == class_map.UNKNOWN
        restored = class_map.from_masks(normal | lesion | unknown, lesion, unknown)
    changed = restored != labels
    return {
        "task": task_id, "source_kind": kind, "task_status": status,
        "packet_matches_canonical_image": True, "binary_layers_match_class_map": True,
        "draft_readback_pixel_exact": not bool(changed.any()),
        "draft_readback_changed_pixels_by_class": {
            class_map.NAMES[code]: int(np.count_nonzero(changed & (labels == code)))
            for code in np.unique(labels[changed])
        },
        "task_accepts_pending_draft": status == "pending",
        "admin_hides_ai_for_blind_benchmark": benchmark and status in tasks.OPEN,
        "packet_tag_candidates": len(metadata.get("triage_candidates", [])),
    }


if __name__ == "__main__":
    if sys.argv[1:2] in (["from-run"], ["from-auto"]):
        automatic = sys.argv[1] == "from-auto"
        parser = argparse.ArgumentParser(description="Export a completed visual-model run")
        parser.add_argument("run", type=Path)
        parser.add_argument("out", type=Path)
        args = parser.parse_args(sys.argv[2:])
        exporter = export_auto if automatic else export_run
        exporter(args.run, args.out)
        print(args.out.resolve())
        sys.exit(0)
    if sys.argv[1:2] == ["check"]:
        parser = argparse.ArgumentParser(description="Check a review packet against an admin task")
        parser.add_argument("task", type=int)
        parser.add_argument("packet", type=Path)
        args = parser.parse_args(sys.argv[2:])
        print(json.dumps(check_task_packet(args.task, args.packet), ensure_ascii=False, indent=2))
        sys.exit(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--labels-sha256", required=True)
    parser.add_argument("--source-rgb-sha256", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--triage", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    metadata = [json.loads(file.read_text()) for file in args.triage]
    export_packet(args.labels, args.labels_sha256, args.source_rgb_sha256, args.model, metadata, args.out)
    print(args.out.resolve())
