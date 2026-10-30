"""SAM ViT-B image-encoder embeddings (local weights, no download) for every gold photo."""
import sys
import numpy as np
import torch

sys.path.insert(0, "/root/subskin")
from segment_anything import sam_model_registry, SamPredictor  # noqa: E402
from ml.pixel_labeling import gold  # noqa: E402

torch.set_num_threads(8)
sam = sam_model_registry["vit_b"](checkpoint="/root/subskin/models/sam_vit_b_01ec64.pth").eval()
pred = SamPredictor(sam)
for e in gold.registry():
    rgb, _ = gold.load(e)
    with torch.inference_mode():
        pred.set_image(rgb)
        f = pred.features[0].cpu().numpy().astype(np.float32)  # (256, 64, 64) over the padded 1024 square
    np.save(f"/root/subskin/tmp/pixel_clf/emb/sam_{e['task_id']}.npy", f)
    print("sam", e["task_id"], rgb.shape, f.shape, flush=True)
print("DONE")
