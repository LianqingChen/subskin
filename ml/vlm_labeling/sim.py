"""Simulated judge: verdicts derived from gold with controlled error rates.

Used to (1) test the pipeline without network, (2) answer "how accurate must a model's region
verdicts be to reach the target Dice" — the number every model is held to in rubric.md.
Never used to produce a draft that is reported as a model result.
"""

from typing import Dict

import numpy as np

from ml.vlm_labeling.regions import Regions

GOLD2CODE = {0: "B", 1: "N", 2: "L", 3: "O", 4: "X"}


def oracle_verdicts(r: Regions, gold: np.ndarray, flip: float = 0.0, mixed_below: float = 0.75,
                    seed: int = 0) -> Dict[int, str]:
    rng = np.random.default_rng(seed)
    out = {}
    for t in r.table:
        v = gold[r.seg == t["id"]]
        v = v[v != 255]
        if v.size == 0:
            out[t["id"]] = "U"
            continue
        c = np.bincount(v, minlength=5)
        code = GOLD2CODE[int(c.argmax())]
        if code in "NL" and c.max() / c.sum() < mixed_below:
            code = "M"
        if code in "NL" and rng.random() < flip:
            code = {"N": "L", "L": "N"}[code]
        out[t["id"]] = code
    return out


def second_look(verdicts: Dict[int, str], ids, r: Regions, gold: np.ndarray, accuracy: float,
                seed: int = 1) -> Dict[int, str]:
    """Re-ask on flagged regions; the judge answers correctly with probability ``accuracy``."""
    rng = np.random.default_rng(seed)
    truth = oracle_verdicts(r, gold, flip=0.0)
    out = dict(verdicts)
    for rid in ids:
        if rng.random() < accuracy:
            out[rid] = truth[rid]
    return out


class SimVLM:
    """Stand-in for a vision model (``--model sim:<flip>``): answers from gold with ``flip`` error
    rate.  Only for testing the pipeline offline; its runs are tagged ``sim`` and never reported
    as a model result."""

    def __init__(self, model: str, gold: np.ndarray, r: Regions, log_path=None):
        import json as _json
        self._json = _json
        self.model, self.provider = model, "simulated"
        self.flip = float(model.split(":", 1)[1] or 0)
        self.truth = oracle_verdicts(r, gold, flip=0.0)
        self.noisy = oracle_verdicts(r, gold, flip=self.flip, seed=7)
        self.log_path = log_path

    def ask(self, step, system, parts, retries=1):
        import re
        text = " ".join(p["text"] for p in parts if p["type"] == "text")
        if step == "triage":
            return {"data": {"body_site": "sim", "lesion_map": {}}, "raw": "", "secs": 0}
        if step.startswith("review"):
            return {"data": {"regions": {}}, "raw": "", "secs": 0}
        lists = re.findall(r"\[([0-9, ]+)\]", text)
        ids = [int(x) for x in lists[-1].split(",") if x.strip()] if lists else []
        src = self.noisy if step.startswith("judge") else self.truth if self.rng_ok() else self.noisy
        return {"data": {"regions": {str(i): src[i] for i in ids}}, "raw": "", "secs": 0}

    def rng_ok(self):
        return np.random.random() < 0.7   # second look is right 70% of the time
