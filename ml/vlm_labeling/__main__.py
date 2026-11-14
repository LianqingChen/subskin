"""VLM labeling protocol CLI.  Rules + workflow: .agents/skills/vlm-vitiligo-labeling/SKILL.md

    python -m ml.vlm_labeling run 182 --model qwen3.8-max [--owner-consent "..."]   # P0-P7, then score vs gold
    python -m ml.vlm_labeling score <run_dir>                                    # per-stage Dice vs gold
    python -m ml.vlm_labeling learn <run_dir>                                    # error attribution -> rubric entries
    python -m ml.vlm_labeling simulate 182 --flip 0 0.1 0.2                      # required verdict accuracy
    python -m ml.vlm_labeling replay <run_dir>                                   # labels from decision.json, no model
    python -m ml.vlm_labeling bench 182 199 185 --model qwen3.8-max --tag r2      # regression over golds
    python -m ml.vlm_labeling vote <run_dir> <run_dir> <run_dir>                  # pixel majority vote (>=3 runs)
    python -m ml.vlm_labeling auto 192 --model qwen3.8-max                      # UNATTENDED v4: 5 runs+anchor+vote
    python -m ml.vlm_labeling regress [tasks]                                     # re-fuse frozen verdicts, no model
"""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import sys

import numpy as np

from ml.pixel_labeling import features, gold as gold_mod, metrics, system_io as sio
from ml.vlm_labeling import fuse, learn, privacy, protocol, sim

RUNS = Path(__file__).resolve().parent / "runs"


def _gold(task_id: int):
    for e in gold_mod.registry():
        if e["task_id"] == task_id:
            return gold_mod.load(e)[1], e
    return None, None


def cmd_run(a):
    sim_gold = None
    if a.model.startswith("sim:"):
        sim_gold, _ = _gold(a.task)          # offline pipeline test; nothing leaves the server
    else:
        privacy.check(a.task, a.model, a.owner_consent)
    stamp = dt.datetime.now().strftime("%m%d-%H%M%S")
    settings = protocol.frozen_run_inputs(Path(a.resume)).get("settings", {}) if a.resume else {}
    n_skin = a.regions if a.regions is not None else settings.get("n_skin", protocol.regions.DEFAULT_SKIN_REGIONS)
    review = a.review if a.review is not None else settings.get("review_rounds", 0)
    recheck = not a.no_recheck and settings.get("recheck_on", True)
    # unique per process: two runs started in the same second once shared a dir (192, 2026-11-09)
    out = Path(a.resume) if a.resume else sio.work_dir(a.task) / "vlm" / f"{a.model}-{stamp}-r{n_skin}-p{os.getpid()}"
    if not a.resume and out.exists():
        raise SystemExit(f"run dir already exists: {out}")
    try:
        res = protocol.run(a.task, a.model, out, workers=a.workers, review_rounds=review,
                           recheck_on=recheck, n_skin=n_skin, gold_for_sim=sim_gold, rubric_path=a.rubric)
    except protocol.ProviderQuotaExhausted:
        print(f"run dir: {out}")
        raise
    print(f"run dir: {out}")
    if not a.no_score:
        _report(a.task, out, res["decision"])


def _report(task_id: int, out: Path, dec):
    g, entry = _gold(task_id)
    summary = {"task_id": task_id, "run": out.name, "model": dec["model"], "rubric": dec["rubric"],
               "n_regions": dec["n_regions"], "steps": [{k: v for k, v in s.items() if k != "asked"} for s in dec["steps"]]}
    snapshot = out / "rubric.snapshot.md"
    if snapshot.is_file():
        summary["rubric_sha256"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if g is not None:
        summary["gold_submission"] = entry["submission_id"]
        summary["gold_revision"] = entry["revision"]
        summary["scores"] = learn.stage_scores(out, g)
        summary["learn"] = learn.analyse(out, g)
        print(json.dumps(summary["scores"], indent=1))
        print(json.dumps({k: summary["learn"][k] for k in ("region_accuracy_LN", "false_L", "false_N", "false_L_px",
                                                           "false_N_px", "worst_tiles")}, ensure_ascii=False))
    RUNS.mkdir(exist_ok=True)
    (RUNS / f"{task_id}-{out.name}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return summary


def cmd_bench(a):
    """Score individual runs and retain the full requested case list for feedback."""
    if len(set(a.tasks)) != len(a.tasks):
        raise SystemExit("Use separate bench invocations for repeated runs of a case.")
    rubric_text = Path(a.rubric or protocol.SKILL / "rubric.md").read_text()
    rubric = protocol.rubric_version(rubric_text)
    rubric_sha256 = hashlib.sha256(rubric_text.encode("utf-8")).hexdigest()
    simulation = a.model.startswith("sim:")
    rows, failures = [], []
    for tid in a.tasks:
        sim_gold = None
        if simulation:
            sim_gold, _ = _gold(tid)
        else:
            privacy.check(tid, a.model, a.owner_consent)
        stamp = dt.datetime.now().strftime("%m%d-%H%M%S")
        out = sio.work_dir(tid) / "vlm" / f"{a.model}-{stamp}-p{os.getpid()}"
        out.mkdir(parents=True, exist_ok=False)
        (out / "rubric.snapshot.md").write_text(rubric_text, encoding="utf-8")
        try:
            res = protocol.run(tid, a.model, out, workers=a.workers, review_rounds=a.review,
                               gold_for_sim=sim_gold)
            report = _report(tid, out, res["decision"])
        except Exception as exc:  # noqa: BLE001
            print(f"task {tid} failed: {type(exc).__name__}")
            failures.append({"task": tid, "run": out.name, "error_type": type(exc).__name__})
            continue
        fin = report.get("scores", {}).get("labels", {})
        rows.append({"task": tid, "run": out.name, "rubric_sha256": report["rubric_sha256"],
                     "gold_submission": report.get("gold_submission"), "gold_revision": report.get("gold_revision"),
                     "dice": fin.get("lesion_dice"), "tol2": fin.get("lesion_dice_tol2"), "skin": fin.get("skin_dice"),
                     "coatings": fin.get("coatings"), "known_pixel_errors": fin.get("known_pixel_errors"),
                     "different_pixels": fin.get("different_pixels"), "pixel_exact": fin.get("pixel_exact"),
                     "region_acc": report.get("learn", {}).get("region_accuracy_LN")})
    unscored = [row["task"] for row in rows if row["coatings"] is None]
    rec = {
        "at": dt.datetime.now().isoformat(timespec="seconds"), "model": a.model,
        "rubric": rubric, "rubric_sha256": rubric_sha256, "tag": a.tag, "simulation": simulation,
        "requested_tasks": a.tasks, "failed_tasks": failures, "unscored_tasks": unscored,
        "scored_all_requested_tasks": not (failures or unscored), "rows": rows,
    }
    RUNS.mkdir(exist_ok=True)
    with (RUNS / "bench.jsonl").open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"| task | dice | ±2px | skin | region acc |  ({a.model}, rubric {rubric})")
    for row in rows:
        print(f"| {row['task']} | {row['dice']} | {row['tol2']} | {row['skin']} | {row['region_acc']} |")
    if failures or unscored:
        print(f"Scored {len(rows) - len(unscored)}/{len(a.tasks)} requested cases. See {RUNS / 'bench.jsonl'}.")


def cmd_regress(a):
    """Re-fuse every finished real run from its frozen verdicts with the current fusion code
    (no model calls) — the regression gate for fuse/regions changes, and the one consistent
    way to compare runs made under different code versions."""
    import glob
    reg = {e["task_id"]: e for e in gold_mod.registry()}
    rows = []
    for f in sorted(glob.glob(str(sio.WORK / "*" / "vlm" / "*" / "decision.json"))):
        d = Path(f).parent
        if d.name.startswith("sim:"):
            continue
        dec = json.load(open(f))
        t = dec["task_id"]
        if t not in reg or (a.tasks and t not in a.tasks):
            continue
        rgb, g = gold_mod.load(reg[t])
        fe, _ = features.cached(t, rgb)
        seg = np.load(d / "seg.npy")
        v = {int(k): c for k, c in dec["verdicts"].items()}
        lab, _ = fuse.fuse(fe, features.NAMES, seg, v)
        s = metrics.summary(lab, g)
        rows.append((t, d.name, dec.get("rubric"), s))
        print(f"| {t} | {d.name} | {dec.get('rubric')} | {s['lesion_dice']} | {s['lesion_dice_tol2']} | {s['skin_dice']} "
              f"| {s['ai_ratio']}/{s['gold_ratio']} | {s['bg_as_occl']}/{s['occl_as_lesion']} |", flush=True)
    return rows


def cmd_compare_regression(a):
    from ml.vlm_labeling import regression

    try:
        report = regression.compare(a.baseline, a.candidate)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["non_regression"]:
        raise SystemExit(1)


def cmd_compare_regression_suite(a):
    from ml.vlm_labeling import regression

    try:
        report = regression.compare_suite(a.baseline, a.candidate)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["improved_without_regression"]:
        raise SystemExit(1)


def vote_labels(run_dirs):
    """Pixel majority vote over independent runs (self-consistency).  Each run is re-fused from
    its frozen verdicts with the current fusion code; ties go to the non-lesion side."""
    paths = [Path(run_dir).resolve() for run_dir in run_dirs]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("Voting requires distinct run directories")
    decisions = [json.loads((path / "decision.json").read_text()) for path in paths]
    task_id = decisions[0]["task_id"]
    if any(decision["task_id"] != task_id for decision in decisions):
        raise ValueError("Voting requires results from the same image task")

    rgb = sio.load_image(task_id)
    fe, _ = features.cached(task_id, rgb)
    for path, decision in zip(paths, decisions):
        protocol.check_replay_inputs(path, decision, rgb, fe)
    labs = []
    for path, decision in zip(paths, decisions):
        segments = np.load(path / "seg.npy", allow_pickle=False)
        if segments.shape != rgb.shape[:2]:
            raise ValueError(f"Run {path.name} segmentation does not match the image grid")
        verdicts = {int(k): code for k, code in decision["verdicts"].items()}
        labs.append(fuse.fuse(fe, features.NAMES, segments, verdicts)[0])
    L = np.stack(labs)
    frac = lambda *c: np.isin(L, c).mean(0)  # noqa: E731
    skin = frac(1, 2, 255) > 0.5
    out = np.where(frac(3) > 0.5, 3, np.where(frac(4) > 0.5, 4, 0)).astype(np.uint8)
    out[skin] = np.where(frac(2)[skin] > 0.5, 2, 1)
    return out, task_id


def cmd_vote(a):
    out, tid = vote_labels(a.run_dirs)
    dest = Path(a.out) if a.out else Path(a.run_dirs[0]).parent / "vote_labels.npy"
    np.save(dest, out)
    g, _ = _gold(tid)
    if g is not None:
        s = metrics.summary(out, g)
        print(f"vote n={len(a.run_dirs)}: dice {s['lesion_dice']} tol2 {s['lesion_dice_tol2']} skin {s['skin_dice']} "
              f"ratio {s['ai_ratio']}/{s['gold_ratio']} cls {s['bg_as_occl']}/{s['occl_as_lesion']}")
    print("saved", dest)


def cmd_anchor(a):
    """P5b on a finished run: anchored boundary recheck; writes a sibling run dir '<run>+anchor'
    (same regions, updated verdicts) so regress/vote treat it as its own run."""
    import shutil
    src = Path(a.run_dir)
    dec = json.load(open(src / "decision.json"))
    tid, model = dec["task_id"], dec["model"]
    if not model.startswith("sim:"):
        privacy.check(tid, model, a.owner_consent)
    rgb = sio.load_image(tid)
    fe, _ = features.cached(tid, rgb)
    protocol.check_replay_inputs(src, dec, rgb, fe)
    dst = src.parent / (src.name + "+anchor")
    dst.mkdir(exist_ok=True)
    for f in ("seg.npy", "regions.json", "rubric.snapshot.md"):
        shutil.copy(src / f, dst / f)
    if (src / "run_inputs.json").is_file():
        shutil.copy(src / "run_inputs.json", dst / "run_inputs.json")
    protocol._RUBRIC = (dst / "rubric.snapshot.md").read_text()
    R = protocol.load_run(dst)
    v = {int(k): c for k, c in dec["verdicts"].items()}
    _, info = fuse.fuse(fe, features.NAMES, R.seg, v)
    if "p_lesion" not in info or not any(c == "L" for c in v.values()):
        raise SystemExit(f"{src.name}: no lesion verdicts — nothing to anchor (run judged the image lesion-free)")
    sw = protocol.anchor_swatches(R, v, info["p_lesion"])
    if not sw["L"] or not sw["N"]:
        raise SystemExit(f"{src.name}: cannot pick swatches {sw}")
    ids = protocol.boundary_regions(R, v)
    from ml.vlm_labeling.client import VLM
    new = protocol.anchored_recheck(VLM(model, dst / "exchanges.jsonl"), rgb, R, ids, sw)
    changed = {k: c for k, c in new.items() if c != v.get(k)}
    v.update(changed)
    dec2 = dict(dec, verdicts={str(k): c for k, c in sorted(v.items())},
                steps=dec["steps"] + [{"step": "anchor", "asked": len(ids), "swatches": sw, "changed": changed}])
    json.dump(dec2, open(dst / "decision.json", "w"), ensure_ascii=False, indent=1)
    print(f"{src.name}: asked {len(ids)} boundary regions, changed {len(changed)} -> {dst.name}")


def cmd_auto(a):
    """Unattended protocol v4 end to end; gold (if any) only scored afterwards as a reference."""
    from ml.vlm_labeling import auto
    res = auto.run_pipeline(a.task, a.model, regions_list=a.regions, parallel=a.parallel, consent=a.owner_consent,
                            rubric_path=a.rubric, resume=Path(a.resume) if a.resume else None)
    g, entry = _gold(a.task)
    if g is not None:
        keys = ("lesion_dice", "lesion_dice_tol2", "skin_dice", "ai_ratio", "gold_ratio", "bg_as_occl", "occl_as_lesion")
        s = metrics.summary(res["labels"], g)
        ref = {k: s[k] for k in keys}
        voted = np.load(res["dir"] / "labels_vote.npy", allow_pickle=False)
        s4 = metrics.summary(voted, g)
        res["meta"]["reference_vs_gold_v4_vote"] = {k: s4[k] for k in keys}
        res["meta"]["reference_vs_gold"] = ref
        res["meta"]["approved_reference"] = {
            "submission_id": entry["submission_id"], "revision": entry["revision"],
            "vote_coatings": learn.coating_scores(voted, g),
            "final_coatings": learn.coating_scores(res["labels"], g),
        }
        json.dump(res["meta"], open(res["dir"] / "auto.json", "w"), ensure_ascii=False, indent=1)
        RUNS.mkdir(exist_ok=True)
        (RUNS / f"{a.task}-{res['dir'].name}.json").write_text(json.dumps(res["meta"], ensure_ascii=False, indent=1))
        print("reference vs gold:", ref)


def cmd_adjudicate(a):
    """AI-vs-gold disagreements judged without a human (colour evidence + blind referee model)."""
    from ml.vlm_labeling import adjudicate
    g, _ = _gold(a.task)
    ai = np.load(a.labels)
    ref = None if a.referee == "none" else a.referee
    if ref:
        privacy.check(a.task, ref, a.owner_consent)
    out = Path(a.labels).parent / f"adjudication_{a.referee}"
    rep = adjudicate.run(a.task, sio.load_image(a.task), ai, g, out, referee_model=ref, max_components=a.max)
    print(json.dumps({k: v for k, v in rep.items() if k != "components"}, ensure_ascii=False, indent=1))
    print("details:", out / "adjudication.json")


def cmd_score(a):
    out = Path(a.run_dir)
    dec = json.load(open(out / "decision.json"))
    _report(dec["task_id"], out, dec)


def cmd_learn(a):
    out = Path(a.run_dir)
    dec = json.load(open(out / "decision.json"))
    g, _ = _gold(dec["task_id"])
    print(json.dumps(learn.analyse(out, g), ensure_ascii=False, indent=1))


def cmd_replay(a):
    out = Path(a.run_dir)
    try:
        lab = protocol.replay(out)
        ref = np.load(out / "labels.npy", allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if lab.shape != ref.shape or lab.dtype != ref.dtype:
        raise SystemExit("Replayed and saved coatings have different shape or dtype")
    differing = int(np.count_nonzero(lab != ref))
    print("identical to saved labels:", differing == 0)
    if differing:
        raise SystemExit(f"Replayed coating differs at {differing:,} pixels")


def cmd_simulate(a):
    rgb, feats, side, R = protocol.prepare(a.task, n_skin=a.regions)
    g, _ = _gold(a.task)
    print(f"{len(R.table)} regions / {len(R.tiles)} tiles")
    for flip in a.flip:
        v = sim.oracle_verdicts(R, g, flip=flip, seed=1)
        lab, info = fuse.fuse(feats, features.NAMES, R.seg, v)
        s = metrics.summary(lab, g)
        print(f"flip {flip:.2f}: dice {s['lesion_dice']} tol2 {s['lesion_dice_tol2']} skin {s['skin_dice']} "
              f"flagged {len(info['disagree'])}")


def main():
    ap = argparse.ArgumentParser(prog="ml.vlm_labeling")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("task", type=int)
    r.add_argument("--model", required=True)
    r.add_argument("--owner-consent", default=None, help="required for diary photos: who authorised, when, scope")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--review", type=int, default=None, help="review rounds (P6; off for new runs by default)")
    r.add_argument("--no-recheck", action="store_true")
    r.add_argument("--no-score", action="store_true", help="freeze model output without reading Gold for scoring")
    r.add_argument("--regions", type=int, default=None, help="target skin regions (default 600 for new runs)")
    r.add_argument("--rubric", default=None, help="candidate rubric file (default: the skill's rubric.md)")
    r.add_argument("--resume", default=None, help="run dir of an interrupted run (reuses logged replies)")
    r.set_defaults(fn=cmd_run)
    b = sp.add_parser("bench")
    b.add_argument("tasks", type=int, nargs="+")
    b.add_argument("--model", required=True)
    b.add_argument("--owner-consent", default=None)
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--review", type=int, default=0)
    b.add_argument("--tag", default="")
    b.add_argument("--rubric", default=None)
    b.set_defaults(fn=cmd_bench)
    ad = sp.add_parser("adjudicate")
    ad.add_argument("task", type=int)
    ad.add_argument("labels")
    ad.add_argument("--referee", default="qwen3.7-plus", help="vision model as blind referee, or 'none'")
    ad.add_argument("--max", type=int, default=40)
    ad.add_argument("--owner-consent", default=None)
    ad.set_defaults(fn=cmd_adjudicate)
    au = sp.add_parser("auto")
    au.add_argument("task", type=int)
    au.add_argument("--model", default="qwen3.8-max")
    au.add_argument("--regions", type=int, nargs="+", default=None, help="default: model picks route (P0b)")
    au.add_argument("--parallel", type=int, default=2)
    au.add_argument("--owner-consent", default=None)
    au.add_argument("--resume", help="resume an incomplete automatic run directory")
    au.add_argument("--rubric", type=Path, default=None, help="candidate rubric frozen for all densities")
    au.set_defaults(fn=cmd_auto)
    an = sp.add_parser("anchor")
    an.add_argument("run_dir")
    an.add_argument("--owner-consent", default=None)
    an.set_defaults(fn=cmd_anchor)
    vo = sp.add_parser("vote")
    vo.add_argument("run_dirs", nargs="+")
    vo.add_argument("--out", default=None)
    vo.set_defaults(fn=cmd_vote)
    rg = sp.add_parser("regress")
    rg.add_argument("tasks", type=int, nargs="*")
    rg.set_defaults(fn=cmd_regress)
    compare = sp.add_parser("compare-regression", help="compare frozen class maps against matching approved references")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.set_defaults(fn=cmd_compare_regression)
    suite = sp.add_parser("compare-regression-suite", help="compare all frozen model cohorts together")
    suite.add_argument("baseline", type=Path)
    suite.add_argument("candidate", type=Path)
    suite.set_defaults(fn=cmd_compare_regression_suite)
    for name, fn in (("score", cmd_score), ("learn", cmd_learn), ("replay", cmd_replay)):
        p = sp.add_parser(name)
        p.add_argument("run_dir")
        p.set_defaults(fn=fn)
    s = sp.add_parser("simulate")
    s.add_argument("task", type=int)
    s.add_argument("--flip", type=float, nargs="+", default=[0.0, 0.1, 0.2])
    s.add_argument("--regions", type=int, default=600)
    s.set_defaults(fn=cmd_simulate)
    a = ap.parse_args()
    try:
        a.fn(a)
    except protocol.ProviderQuotaExhausted as exc:
        from ml.vlm_labeling.client import QUOTA_EXIT_CODE

        print(exc, file=sys.stderr)
        raise SystemExit(QUOTA_EXIT_CODE) from None


if __name__ == "__main__":
    main()
