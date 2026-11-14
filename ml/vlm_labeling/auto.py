"""Unattended pipeline (protocol v4): K independent runs -> anchored boundary recheck on each ->
pixel vote over all 2K label maps -> final labels.  No human step anywhere.

Each run / anchor is a separate process of this CLI (keeps the frozen-rubric global per run) and at
most ``parallel`` jobs talk to the provider at once (8 concurrent jobs got throttled to ~0 output).
Gold, if any, is only used afterwards for a reference score — never inside the pipeline.
"""

from collections import Counter
import datetime as dt
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image

from ml.pixel_labeling import system_io as sio
from ml.vlm_labeling import privacy, protocol
from ml.vlm_labeling.client import QUOTA_EXIT_CODE

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "bin" / "python")


def _cmd(args: List[str], consent: Optional[str]) -> List[str]:
    return [PY, "-u", "-m", "ml.vlm_labeling", *args] + (["--owner-consent", consent] if consent else [])


def run_pipeline(task_id: int, model: str, regions_list=None, parallel: int = 2,
                 consent: Optional[str] = None, log=print, rubric_path: Optional[Path] = None,
                 resume: Optional[Path] = None) -> Dict:
    if resume is None:
        return _run_pipeline(task_id, model, regions_list, parallel, consent, log, rubric_path, None)
    with (Path(resume) / ".resume.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Automatic labeling resume is already running") from None
        return _run_pipeline(task_id, model, regions_list, parallel, consent, log, rubric_path, resume)


def _run_pipeline(task_id, model, regions_list, parallel, consent, log, rubric_path, resume):
    if parallel < 1:
        raise ValueError("auto requires at least one worker")
    if not model.startswith("sim:"):
        privacy.check(task_id, model, consent)
    resume_state = None
    if resume is not None:
        out = Path(resume).resolve()
        resume_state = json.loads((out / "incomplete.json").read_text(encoding="utf-8"))
        if (resume_state["task_id"], resume_state["model"]) != (task_id, model):
            raise ValueError("Resume requires the original image task and model")
        if (out / "auto.json").exists():
            raise ValueError("Automatic labeling run is already complete")
        planned = resume_state["planned_densities"]
        if regions_list is not None and list(regions_list) != planned:
            raise ValueError("Resume requires the original density list")
        regions_list = planned
    else:
        stamp = dt.datetime.now().strftime("%m%d-%H%M%S-%f")
        out = sio.work_dir(task_id) / f"auto_{model}_{stamp}"
        out.mkdir(parents=True, mode=0o700)
    frozen_rule = out / "rubric.snapshot.md"
    if resume_state is not None:
        rubric = frozen_rule.read_text(encoding="utf-8")
        if rubric_path is not None and Path(rubric_path).read_text(encoding="utf-8") != rubric:
            raise ValueError("Resume requires the original rubric")
        expected = resume_state.get("rubric_sha256")
        if expected is not None and hashlib.sha256(frozen_rule.read_bytes()).hexdigest() != expected:
            raise ValueError("Resume rubric snapshot changed")
    else:
        rubric = Path(rubric_path or protocol.SKILL / "rubric.md").read_text(encoding="utf-8")
        frozen_rule.write_text(rubric, encoding="utf-8")
    rule_bytes = frozen_rule.read_bytes()
    rubric_sha256 = hashlib.sha256(rule_bytes).hexdigest()
    rgb = sio.load_image(task_id)
    rgb_sha256 = protocol._sha256_array(rgb)
    if resume_state is not None:
        expected_rgb = resume_state.get("rgb_pixels_sha256")
        if expected_rgb is not None and expected_rgb != rgb_sha256:
            raise ValueError("Automatic labeling source RGB changed since the original run")
        for path in [*resume_state["completed_runs"], *resume_state.get("completed_anchors", []),
                     *(row["run"] for row in resume_state["failed_runs"] if "run" in row)]:
            manifest = protocol.frozen_run_inputs(Path(path))
            if manifest and (
                (manifest["task_id"], manifest["model"], manifest["rgb_pixels_sha256"], manifest["rgb_shape"])
                != (task_id, model, rgb_sha256, list(rgb.shape))
            ):
                raise ValueError(f"Automatic labeling source or model differs in {Path(path).name}")

    def uses_frozen_rule(folder):
        snapshot = Path(folder) / "rubric.snapshot.md"
        return snapshot.is_file() and snapshot.read_bytes() == rule_bytes

    route = resume_state.get("route") if resume_state is not None else None
    if regions_list is None:                       # P0b: the model picks the route, no human
        from ml.vlm_labeling.client import VLM
        route = protocol.lesion_pattern(VLM(model, out / "route.jsonl"), rgb)
        try:
            n = protocol.regions_for_spot(task_id, rgb, float(route.get("typical_spot_px") or 300))
        except (TypeError, ValueError):
            n = 600
        route["n_regions"] = n
        regions_list = tuple(int(n * f) for f in (0.8, 0.9, 1.0, 1.1, 1.2))
        log(f"[auto] route {route} -> regions {regions_list}")
    regions_list = tuple(regions_list)
    if not regions_list:
        raise ValueError("auto requires at least one region density")
    if resume_state is None:
        queue = [("run", n, None) for n in regions_list]
        runs, anchors = [], []
    else:
        runs = resume_state["completed_runs"].copy()
        completed_densities = []
        for run in runs:
            decision = json.loads((Path(run) / "decision.json").read_text(encoding="utf-8"))
            if (decision["task_id"], decision["model"]) != (task_id, model) or not uses_frozen_rule(run):
                raise ValueError("Completed branch differs from the automatic run")
            completed_densities.append(decision["regions"]["n_skin"])
        anchors = resume_state.get("completed_anchors", []).copy()
        if not set(anchors) <= {str(run) + "+anchor" for run in runs} or any(not uses_frozen_rule(path) for path in anchors):
            raise ValueError("Completed anchor differs from the automatic run")
        pending = [row for row in resume_state["failed_runs"] if "density" in row]
        if Counter(completed_densities + [row["density"] for row in pending]) != Counter(regions_list):
            raise ValueError("Automatic labeling resume inventory does not match the plan")
        started_dirs = runs + [row["run"] for row in pending if "run" in row]
        if len({Path(path).resolve() for path in started_dirs}) != len(started_dirs) or len(set(anchors)) != len(anchors):
            raise ValueError("Automatic labeling resume inventory repeats a branch")
        queue = [("run", row["density"], row.get("run")) for row in pending]
        queue.extend(("anchor", run, None) for run in runs if str(run) + "+anchor" not in anchors)

    running = []
    failed_runs, failed_anchors = [], []
    logs = out / "jobs.log"
    started = max((int(path.stem.removeprefix("job-")) for path in out.glob("job-*.log")
                   if path.stem.removeprefix("job-").isdigit()), default=0)
    quota_exhausted = False

    def launch(kind, arg, run_dir):
        nonlocal started
        if kind == "run":
            args = ["run", str(task_id), "--model", model, "--regions", str(arg),
                    "--rubric", str(frozen_rule), "--no-score"]
            if run_dir is not None:
                args.extend(["--resume", run_dir])
        else:
            args = ["anchor", arg]
        started += 1
        job_log = out / f"job-{started:03d}.log"
        with job_log.open("xb") as stream:
            process = subprocess.Popen(_cmd(args, consent), cwd=REPO, stdout=stream,
                                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        running.append((process, kind, arg, run_dir, job_log))
        log(f"[auto] start {kind} {arg}")

    while running or (queue and not quota_exhausted):
        while queue and not quota_exhausted and len(running) < parallel:
            launch(*queue.pop(0))
        time.sleep(10)
        for item in list(running):
            process, kind, arg, run_dir, job_log = item
            returncode = process.poll()
            if returncode is None:
                continue
            running.remove(item)
            text = job_log.read_text(encoding="utf-8", errors="replace")
            with logs.open("a", encoding="utf-8") as stream:
                stream.write(f"\n=== {kind} {arg} (rc={returncode})\n{text}\n")
            if kind == "run":
                match = re.search(r"^run dir: (.+)$", text, flags=re.MULTILINE)
                run = match.group(1).strip() if match else ""
                has_result = run and (Path(run) / "decision.json").is_file()
                if returncode == 0 and has_result and uses_frozen_rule(run):
                    runs.append(run)
                    queue.insert(0, ("anchor", run, None))
                else:
                    reason = "rubric_mismatch" if has_result else "missing_result"
                    if returncode:
                        reason = "worker_failed"
                    failure = {"density": arg, "exit_code": returncode, "reason": reason, "log": job_log.name}
                    if run or run_dir is not None:
                        failure["run"] = run or run_dir
                    failed_runs.append(failure)
            else:
                path = Path(str(arg) + "+anchor")
                if returncode == 0 and (path / "decision.json").is_file() and uses_frozen_rule(path):
                    anchors.append(str(path))
                else:
                    failed_anchors.append({"run": str(arg), "exit_code": returncode, "log": job_log.name})
            if returncode == QUOTA_EXIT_CODE:
                quota_exhausted = True
            log(f"[auto] done {kind} {arg} rc={returncode}")

    if quota_exhausted:
        for kind, arg, run_dir in queue:
            failures = failed_runs if kind == "run" else failed_anchors
            identity = "density" if kind == "run" else "run"
            failure = {identity: arg, "reason": "provider_quota_exhausted", "exit_code": None}
            if kind == "run" and run_dir is not None:
                failure["run"] = run_dir
            failures.append(failure)

    if failed_runs or quota_exhausted:
        failure = {"task_id": task_id, "model": model, "completed_runs": runs, "failed_runs": failed_runs,
                   "completed_anchors": anchors, "failed_anchors": failed_anchors,
                   "planned_densities": list(regions_list), "route": route, "rubric_sha256": rubric_sha256,
                   "rgb_pixels_sha256": rgb_sha256}
        pending = out / "incomplete.json"
        temporary = pending.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(pending)
        if quota_exhausted:
            raise protocol.ProviderQuotaExhausted(f"Provider quota exhausted. See {out / 'incomplete.json'}")
        raise RuntimeError(f"auto did not finish every planned density. See {out / 'incomplete.json'}")

    from ml.vlm_labeling.__main__ import vote_labels
    voters = runs + anchors
    from ml.vlm_labeling.refine import refine
    voted, _ = vote_labels(voters)
    np.save(out / "labels_vote.npy", voted)          # v4 result (before P8)
    labels = refine(rgb, voted)  # v5 = v4 + boundary-band colour refinement
    np.save(out / "labels.npy", labels)
    Image.fromarray(protocol.overlay(rgb, labels)).save(out / "overlay.jpg", quality=88)
    meta = {"task_id": task_id, "model": model, "protocol": "v5", "rubric": protocol.rubric_version(rubric),
            "rubric_sha256": rubric_sha256, "rgb_pixels_sha256": rgb_sha256,
            "route": route, "regions_list": list(regions_list),
            "runs": runs, "anchors": anchors, "failed_anchors": failed_anchors, "n_votes": len(voters),
            "finished": dt.datetime.now().isoformat(timespec="seconds")}
    complete = out / "auto.json"
    temporary = complete.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(complete)
    (out / "incomplete.json").unlink(missing_ok=True)
    log(f"[auto] {len(voters)} votes -> {out}")
    return {"dir": out, "labels": labels, "meta": meta}


if __name__ == "__main__":
    run_pipeline(int(sys.argv[1]), sys.argv[2])
