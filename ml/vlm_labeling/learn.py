"""Positive loop: compare a finished run with the gold, attribute every error to a region, and
produce the material a reviewer (human or agent) turns into rubric entries.

Gold is used here ONLY after the run is frozen — never fed to the model during a run.
Outputs (work dir, gitignored): learn_false_L.jpg / learn_false_N.jpg contact sheets,
learn_gold_suspect.jpg; and a JSON summary (committed) with region-level verdict accuracy.
"""

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np

from ml.pixel_labeling import features, metrics, system_io as sio
from ml.vlm_labeling import fuse, protocol, regions, sim


def coating_scores(labels: np.ndarray, gold: np.ndarray) -> Dict[str, Any]:
    if labels.shape != gold.shape or labels.ndim != 2:
        raise ValueError("Predicted and approved coatings must share the same image grid")

    known = gold != 255
    coatings = {}
    for name, classes in (("white", (2,)), ("normal_skin", (1,)), ("visible_skin", (1, 2))):
        pred = np.isin(labels, classes) & known
        ref = np.isin(gold, classes) & known
        intersection = int(np.count_nonzero(pred & ref))
        fp = int(np.count_nonzero(pred & ~ref))
        fn = int(np.count_nonzero(ref & ~pred))
        denominator = 2 * intersection + fp + fn
        coatings[name] = {
            "dice": 2 * intersection / denominator if denominator else None,
            "false_positive_pixels": fp,
            "false_negative_pixels": fn,
        }

    different = labels != gold
    return {
        "coatings": coatings,
        "known_pixel_errors": int(np.count_nonzero(different & known)),
        "different_pixels": int(np.count_nonzero(different)),
        "pixel_exact": not bool(different.any()),
        "unknown_on_known_pixels": int(np.count_nonzero((labels == 255) & known)),
    }


def stage_scores(out_dir: Path, gold: np.ndarray) -> Dict[str, Any]:
    out = {}
    for f in sorted(out_dir.glob("p*_*.npy")) + [out_dir / "labels.npy"]:
        if f.exists():
            labels = np.load(f, allow_pickle=False)
            agreement = coating_scores(labels, gold)
            s = metrics.summary(labels, gold)
            out[f.stem] = {k: s[k] for k in ("lesion_dice", "lesion_dice_tol2", "skin_dice", "ai_ratio", "gold_ratio",
                                              "bg_as_occl", "occl_as_lesion")}
            out[f.stem].update(agreement)
    return out


def analyse(out_dir: Path, gold: np.ndarray, top: int = 24) -> Dict[str, Any]:
    dec = json.load(open(out_dir / "decision.json"))
    tid = dec["task_id"]
    rgb = sio.load_image(tid)
    seg = np.load(out_dir / "seg.npy")
    meta = json.load(open(out_dir / "regions.json"))
    R = regions.Regions(seg=seg, table=meta["table"], tiles=meta["tiles"], params=meta["params"])
    truth = sim.oracle_verdicts(R, gold, flip=0.0)
    v = {int(k): c for k, c in dec["verdicts"].items()}
    feats, _ = features.cached(tid, rgb)

    # Count every region assigned L or N by the approved-label oracle.
    conf: Dict[str, Dict[str, int]] = {}
    err_L, err_N, other_codes = [], [], []
    n_ln = ok = 0
    for t in R.table:
        g, m = truth[t["id"]], v.get(t["id"], "U")
        conf.setdefault(g, {}).setdefault(m, 0)
        conf[g][m] += 1
        if g in ("L", "N"):
            n_ln += 1
            if g == m:
                ok += 1
            elif m == "L":
                err_L.append(t["id"])
            elif m == "N":
                err_N.append(t["id"])
            else:
                other_codes.append(t["id"])
    answered_ln = n_ln - len(other_codes)
    area = {t["id"]: t["area"] for t in R.table}
    err_L.sort(key=lambda i: -area[i])
    err_N.sort(key=lambda i: -area[i])
    other_codes.sort(key=lambda i: -area[i])
    wd = sio.work_dir(tid)
    tag = out_dir.name
    if err_L:
        protocol.contact_sheet(rgb, R, err_L[:top]).save(wd / f"learn_{tag}_false_L.jpg", quality=88)
    if err_N:
        protocol.contact_sheet(rgb, R, err_N[:top]).save(wd / f"learn_{tag}_false_N.jpg", quality=88)
    if other_codes:
        protocol.contact_sheet(rgb, R, other_codes[:top]).save(
            wd / f"learn_{tag}_other_codes_on_LN.jpg", quality=88,
        )

    # gold-suspect: model verdict AND out-of-fold colour model both disagree with gold
    V = np.array([v.get(i, "U") for i in range(len(R.table))])
    pos, neg = (V == "L")[seg.clip(0)] & (seg >= 0), (V == "N")[seg.clip(0)] & (seg >= 0)
    skin = np.isin(V, fuse.SKIN_CODES)[seg.clip(0)] & (seg >= 0)
    p = fuse.crossfit_proba(feats, features.NAMES, seg, pos, neg, skin)
    rid = np.where(seg >= 0, seg, seg.max() + 1)
    rp = np.bincount(rid.ravel(), p.ravel()) / np.maximum(np.bincount(rid.ravel()), 1)
    suspect = [i for i in err_L if rp[i] > 0.8] + [i for i in err_N if rp[i] < 0.2]
    if suspect:
        protocol.contact_sheet(rgb, R, suspect[:top]).save(wd / f"learn_{tag}_gold_suspect.jpg", quality=88)

    tiles_err: Dict[int, int] = {}
    errors = set(err_L) | set(err_N) | set(other_codes)
    for t in R.tiles:
        e = sum(area[i] for i in t["regions"] if i in errors)
        if e:
            tiles_err[t["id"]] = e
    return {
        "region_accuracy_LN": round(ok / max(n_ln, 1), 4), "n_LN": n_ln,
        "region_accuracy_LN_answered": round(ok / max(answered_ln, 1), 4),
        "region_coverage_LN": round(answered_ln / max(n_ln, 1), 4),
        "n_LN_answered": answered_ln, "n_LN_other_code": len(other_codes),
        "false_L": len(err_L), "false_N": len(err_N),
        "false_L_px": int(sum(area[i] for i in err_L)), "false_N_px": int(sum(area[i] for i in err_N)),
        "confusion_gold_to_model": conf,
        "worst_tiles": sorted(tiles_err.items(), key=lambda x: -x[1])[:6],
        "gold_suspect": suspect[:top],
        "sheets": [str(p) for p in sorted(wd.glob(f"learn_{tag}_*.jpg"))],
    }
