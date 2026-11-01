"""Offline diagnostic only: generated non-medical inputs, never patient data."""
import json
from pathlib import Path
import cv2
import numpy as np
from web.backend.services.rgb_segmentation.inference import infer_rgb
from web.backend.services.rgb_segmentation.images import frame_information_lost, png_bytes
from web.backend.services.rgb_segmentation.policy import measure_rgb


def run():
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
    rows=[]
    for name,rgb in cases.items():
        row={"case":name,"known_content":"program_generated_nonmedical","information_lost":bool(frame_information_lost(rgb))}
        try:
            masks,meta=infer_rgb(rgb)
            decision=measure_rgb(rgb,masks,png_bytes(rgb),reviewed=False)
            row.update(source=meta.get("source"),mask_pixels={k:int(v.sum()) for k,v in masks.items()},status=decision["status"],blocking_reasons=decision["blocking_reasons"])
        except Exception as exc:
            row.update(error_type=type(exc).__name__,error_code=getattr(exc,"code",None))
        rows.append(row)
    output=Path(__file__).with_name("irrelevant-input-probe.json")
    if output.exists(): raise FileExistsError("Preserve earlier probe output")
    output.write_text(json.dumps({"kind":"synthetic_failure_mode_probe_not_accuracy_benchmark","rows":rows},indent=2))
    print(output.read_text())

if __name__=="__main__": run()
