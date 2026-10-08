"""Offline segmentation benchmark. Inputs stay local; no model/API calls.

Usage: python scripts/assessment_benchmark.py --manifest dataset.json --output metrics.json
Each sample needs pseudonymous patient_id, split, ground_truth, prediction,
label_source='clinician', consent=true. Optional: skin_tone, body_site,
repeat_group, unchanged=true. All masks must use a common coordinate system.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def mask(path):
    img=Image.open(path)
    return np.asarray(img.getchannel('A') if 'A' in img.getbands() else img.convert('L')) > 127


def evaluate(gt, pred):
    if gt.shape != pred.shape: raise ValueError('Prediction/ground-truth shape mismatch')
    intersection=int((gt & pred).sum());total=int(gt.sum()+pred.sum());union=int((gt|pred).sum())
    k=np.ones((3,3),np.uint8)
    edge=lambda x: x & ~cv2.erode(x.astype(np.uint8),k).astype(bool)
    eg,ep=edge(gt),edge(pred)
    dg=cv2.distanceTransform((~eg).astype(np.uint8),cv2.DIST_L2,5)
    dp=cv2.distanceTransform((~ep).astype(np.uint8),cv2.DIST_L2,5)
    distances=np.concatenate([dg[ep],dp[eg]]) if eg.any() and ep.any() else None
    recall=float((dp[eg]<=2).mean()) if eg.any() else float(not ep.any())
    precision=float((dg[ep]<=2).mean()) if ep.any() else float(not eg.any())
    return {'dice':2*intersection/total if total else 1.0,'iou':intersection/union if union else 1.0,
      'boundary_f1_2px':2*precision*recall/(precision+recall) if precision+recall else 0.0,
      'hd95_px':float(np.percentile(distances,95)) if distances is not None else None,
      'area_error_px':int(pred.sum())-int(gt.sum()),
      'area_error_percent':float((pred.sum()-gt.sum())/gt.sum()*100) if gt.any() else None,
      'false_positive_pixels':int((pred & ~gt).sum()),'predicted_area_px':int(pred.sum())}


def run(manifest, output):
    path=Path(manifest);data=json.loads(path.read_text());samples=data['samples']
    patients={};results=[];groups=defaultdict(list);repeats=defaultdict(list)
    for sample in samples:
        patient=sample['patient_id'];split=sample['split']
        if patient in patients and patients[patient]!=split: raise ValueError('Patient leakage across splits')
        patients[patient]=split
        if not sample.get('consent') or sample.get('label_source')!='clinician': raise ValueError('Authorized clinician labels required')
    for i,sample in enumerate(samples):
        if sample['split']!='test': continue
        metric=evaluate(mask(path.parent/sample['ground_truth']),mask(path.parent/sample['prediction']))
        metric['sample_index']=i;results.append(metric)
        for dimension in ('skin_tone','body_site'):
            groups[f'{dimension}:{sample.get(dimension,"unknown")}'].append(metric)
        if sample.get('repeat_group') and sample.get('unchanged'):
            repeats[(sample['patient_id'],sample['repeat_group'])].append(metric['predicted_area_px'])
    if not results: raise ValueError('No held-out test samples')
    def summary(rows):
        return {key:float(np.mean([r[key] for r in rows if r.get(key) is not None])) if any(r.get(key) is not None for r in rows) else None for key in ('dice','iou','boundary_f1_2px','hd95_px','area_error_percent')}
    repeat=[float(np.std(v,ddof=1)/np.mean(v)*100) for v in repeats.values() if len(v)>1 and np.mean(v)>0]
    report={'status':'offline_benchmark_not_clinical_certification','test_sample_count':len(results),
      'overall':summary(results),'strata':{k:summary(v) for k,v in groups.items()},
      'repeat_area_cv_percent':repeat,'samples':results,'model_version':data.get('model_version'),
      'limitations':['No diagnosis sensitivity/specificity evaluation','2px boundary tolerance depends on image resolution','Expert sample-size planning still required']}
    Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.manifest,args.output)
