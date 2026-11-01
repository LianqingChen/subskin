"""Local SigLIP relevance experiment; raw similarities are not calibrated accuracy."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

MODEL = "google/siglip-base-patch16-224"
PROMPTS = {
    "skin_closeup": "This is a photograph of a close-up of human skin.",
    "hand_photo": "This is a photograph of a real human hand or foot.",
    "face_photo": "This is a photograph of a real human face or body.",
    "document": "This is a document page with printed text.",
    "graphic": "This is a computer generated graphic with flat colored shapes.",
    "checkerboard": "This is a checkerboard pattern.",
    "surface": "This is a plain wall, fabric, wood, or painted surface.",
    "object": "This is a photograph of an object, not a human body.",
}
SKIN = {"skin_closeup", "hand_photo", "face_photo"}


def fixtures():
    y,x=np.indices((256,256))
    cases={
        "uniform_skin_coloured_surface":np.full((256,256,3),(190,145,120),np.uint8),
        "checkerboard":np.repeat((((x//24+y//24)%2)*180+30).astype(np.uint8)[...,None],3,axis=2),
        "generated_text_document":np.full((256,256,3),245,np.uint8),
        "skin_coloured_rectangles":np.full((256,256,3),(190,145,120),np.uint8),
    }
    for row in range(25,240,25):
        cv2.putText(cases["generated_text_document"],"TEST DOCUMENT",(8,row),cv2.FONT_HERSHEY_SIMPLEX,.45,(25,25,25),1)
    cv2.rectangle(cases["skin_coloured_rectangles"],(40,40),(170,210),(230,215,200),-1)
    return cases


def main():
    out=Path(__file__).with_name("semantic-probe-results.json")
    if out.exists():raise FileExistsError("Preserve previous results")
    parser=argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path)
    args=parser.parse_args()
    revision="7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed"
    source=str(args.model_dir) if args.model_dir else MODEL
    if args.model_dir:
        with (args.model_dir/"model.safetensors").open("rb") as stream:
            digest=hashlib.sha256()
            for chunk in iter(lambda:stream.read(1024*1024),b""): digest.update(chunk)
        if digest.hexdigest() != "2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8":
            raise ValueError("Model weights do not match frozen upstream revision")
    torch.set_num_threads(2)
    start=time.monotonic()
    processor=AutoProcessor.from_pretrained(source,revision=revision,trust_remote_code=False,local_files_only=bool(args.model_dir))
    model=AutoModel.from_pretrained(source,revision=revision,trust_remote_code=False,use_safetensors=True,local_files_only=bool(args.model_dir)).eval()
    loaded=time.monotonic()-start
    rows=[]
    for name,rgb in fixtures().items():
        start=time.monotonic()
        inputs=processor(text=list(PROMPTS.values()),images=Image.fromarray(rgb),padding="max_length",return_tensors="pt")
        with torch.inference_mode():scores=model(**inputs).logits_per_image[0].tolist()
        named=dict(zip(PROMPTS,scores))
        margin=max(named[k] for k in SKIN)-max(v for k,v in named.items() if k not in SKIN)
        rows.append({"case":name,"input_sha256":hashlib.sha256(rgb.tobytes()).hexdigest(),
                     "known_content":"program_generated_nonmedical", "scores":named,
                     "top_prompt":max(named,key=named.get),"skin_minus_other_margin":margin,
                     "seconds":time.monotonic()-start})
    report={"kind":"offline_relevance_failure_mode_probe", "model":MODEL,"revision":revision,
            "prompts":PROMPTS,"load_seconds":loaded,"rows":rows,
            "calibrated":False,"real_positive_images":0,"clinical_accuracy":None,
            "limitations":"Four generated negatives only; not an OOD benchmark or a deployment threshold. No disease classification or segmentation claim."}
    out.write_text(json.dumps(report,indent=2))
    print(json.dumps({"model":MODEL,"revision":revision,"load_seconds":loaded,"rows":[{k:r[k] for k in ["case","top_prompt","skin_minus_other_margin","seconds"]} for r in rows]},indent=2))

if __name__=="__main__":main()
