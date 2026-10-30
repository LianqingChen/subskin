"""Score the production diary draft (infer_rgb) on every approved gold. Read-only."""
import json
import sys
import numpy as np

sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import gold, metrics  # noqa: E402
from web.backend.services.labeling import class_map  # noqa: E402
from web.backend.services.rgb_segmentation.inference import infer_rgb  # noqa: E402

rows = []
for e in gold.registry():
    rgb, hu = gold.load(e)
    masks, meta = infer_rgb(rgb)
    skin, les, unc = masks["skin"], masks["lesion"], masks["uncertain"]
    lesion_only = class_map.from_masks(skin, les, None)
    merged = class_map.from_masks(skin, les | unc, None)
    row = {"task": e["task_id"], "group": e["group"], "source": meta.get("source"),
           "only": metrics.summary(lesion_only, hu), "merged": metrics.summary(merged, hu)}
    rows.append(row)
    print(e["task_id"], meta.get("source"), "only", row["only"]["lesion_dice"], "merged", row["merged"]["lesion_dice"],
          "skin", row["only"]["skin_dice"], "ratio", row["only"]["ai_ratio"], "/", row["only"]["gold_ratio"], flush=True)

json.dump(rows, open("/root/subskin/tmp/pixel_clf/prod.json", "w"), indent=1)
for k in ("only", "merged"):
    print(k, metrics.mean([r[k] for r in rows]))
