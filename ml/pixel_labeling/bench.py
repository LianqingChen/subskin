"""Regression bench: how good is the AI first draft on every gold — the number that must go up.

- ``auto``: general model draft with NO decisions and NO gold. Each gold is scored by the
  leave-one-group-out fold model that never saw it → honest "next new photo" accuracy.
- ``replay``: ``decisions/<id>.json`` recomposed through the toolkit → proves the decision file
  still reproduces (not an accuracy claim: decisions were made while looking at the photo).
- ``history``: Dice of the draft the human actually corrected (first review JSON per task).

Every run appends to ``bench/history.jsonl``; compare ``auto`` means across runs before
accepting any method/skill change.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from ml.pixel_labeling import gold, metrics, pixel_model, system_io as sio

BENCH = Path(__file__).resolve().parent / "bench"


def _history_dice() -> Dict[int, float]:
    out: Dict[int, Any] = {}
    for f in sorted(sio.REVIEWS.glob("*-s*.json"), key=lambda p: int(p.stem.split("-s")[1])):
        d = json.loads(f.read_text())
        tid = d.get("task_id")
        dice = (d.get("summary") or {}).get("lesion_dice")
        if tid is not None and dice is not None and tid not in out:
            out[tid] = dice
    return out


def run(tag: str = "") -> str:
    from ml.pixel_labeling import __main__ as cli

    BENCH.mkdir(exist_ok=True)
    hist = _history_dice()
    rows: List[Dict[str, Any]] = []
    for e in gold.registry():
        tid = e["task_id"]
        rgb, hu = gold.load(e)
        row: Dict[str, Any] = {"task_id": tid, "submission_id": e["submission_id"], "group": e["group"],
                               "history_dice": hist.get(tid)}
        fold = pixel_model.fold_path(e["group"])
        if fold.exists():
            ai = pixel_model.predict(rgb, pixel_model.load(fold), tid)
            row["auto"] = metrics.summary(ai, hu)
        if sio.load_decisions(tid):
            try:
                _, labels = cli._compose(tid)
                row["replay"] = metrics.summary(labels, hu)
            except SystemExit as exc:
                row["replay_error"] = str(exc)
        rows.append(row)
    auto = metrics.mean([r["auto"] for r in rows if "auto" in r])
    replay = metrics.mean([r["replay"] for r in rows if "replay" in r])
    rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": tag, "auto_mean": auto, "replay_mean": replay,
           "rows": rows}
    with (BENCH / "history.jsonl").open("a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    lines = [f"# bench {rec['time']} {tag}", "",
             "| task | 历史初稿 Dice | auto Dice | auto Dice±2px | auto skin | auto 占比/金标 | replay Dice |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        a, p = r.get("auto", {}), r.get("replay", {})
        lines.append(f"| {r['task_id']} | {r['history_dice']} | {a.get('lesion_dice')} | {a.get('lesion_dice_tol2')} | "
                     f"{a.get('skin_dice')} | {a.get('ai_ratio')}/{a.get('gold_ratio')} | "
                     f"{p.get('lesion_dice', r.get('replay_error', '-'))} |")
    lines += ["", f"auto mean: {auto}", f"replay mean: {replay}"]
    text = "\n".join(lines)
    (BENCH / "latest.md").write_text(text + "\n")
    return text
