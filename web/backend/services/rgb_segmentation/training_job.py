"""Background RGB training run: train → evaluate model → evaluate current draft.

Started by ``dataset_pipeline.start_training`` as a niced subprocess so the
API process never blocks. Progress lives in ``training_runs/<run>/status.json``.
"""

import json
import sys
import traceback
from datetime import datetime, timezone
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.dataset_pipeline import datasets_dir, runs_dir


def _update(folder, **changes) -> None:
    status = json.loads((folder / "status.json").read_text())
    status.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
    artifacts.atomic_write(folder / "status.json", json.dumps(status, ensure_ascii=False).encode())


def run(run_id: str) -> int:
    folder = runs_dir() / run_id
    status = json.loads((folder / "status.json").read_text())
    manifest = datasets_dir() / status["dataset_id"] / "manifest.json"
    try:
        from ml.rgb_segmentation.evaluate import evaluate
        from ml.rgb_segmentation.train import train

        _update(folder, state="training")
        model_dir = folder / "model"
        report = train(manifest, model_dir, epochs=int(status["epochs"]), side=512)
        for name in ("model.pt", "training-report.json"):
            (model_dir / name).replace(folder / name)
        model_dir.rmdir()
        _update(folder, state="evaluating", epochs_run=len(report["history"]))
        evaluate(manifest, folder / "model.pt", folder / "eval-model.json")
        evaluate(manifest, None, folder / "eval-baseline.json")
        _update(folder, state="completed")
        return 0
    except Exception as exc:  # surfaced to the admin dashboard, details in train.log
        traceback.print_exc()
        _update(folder, state="failed", error=str(exc)[:300])
        return 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
