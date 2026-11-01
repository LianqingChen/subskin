"""Validation-selected synthetic lesion-probability filter; never deploys."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

THRESHOLDS = [i / 10 for i in range(1, 10)]


def filter_lesion(probability, threshold):
    prediction = probability.argmax(axis=0).astype(np.uint8)
    prediction[(prediction == 2) & (probability[2] < threshold)] = 1
    return prediction


def choose(results):
    eligible = [r for r in results if r['total']==32 and r['failures']==0 and r['positives']==25 and r['negatives']==7 and r['false_positives']<=2 and r['recall']>=0.30]
    return max(eligible, key=lambda r: (r['dice'], r['threshold']))['threshold'] if eligible else None


def main():
    p=argparse.ArgumentParser()
    for name in ('project-root','manifest','weights','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.metrics import score_labels,aggregate
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':192,'validation':32,'test':32}
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);weights_hash=hashlib.sha256(a.weights.read_bytes()).hexdigest();model=torch.jit.load(str(a.weights),map_location='cpu').eval()
    def load(split):
        out=[]
        for item in doc['items']:
            if item['split']!=split:continue
            row={'id':item['id'],'subject_id':item['subject_id'],'groups':item['groups']}
            try:
                rgb,truth=load_item(Path(doc['root']),item);h,w=truth.shape;assert (h,w)==(128,128)
                x=torch.from_numpy(rgb.copy()).permute(2,0,1).float().unsqueeze(0)/255
                with torch.inference_mode(): prob=torch.softmax(model(x),1)[0].cpu().numpy()
                if prob.shape!=(5,h,w) or not np.isfinite(prob).all():raise ValueError('invalid probabilities')
                row.update(rgb=rgb,truth=truth,prob=prob)
            except Exception as e:row['error']=type(e).__name__
            out.append(row)
        return out
    def score(items,threshold):
        rows=[]
        for it in items:
            row={k:it[k] for k in ('id','subject_id','groups')}
            if 'error' in it:row.update(metrics=None,error=it['error'])
            else:
                try:row['metrics']=score_labels(filter_lesion(it['prob'],threshold),it['truth'],it['rgb'])
                except Exception as e:row.update(metrics=None,error=type(e).__name__)
            rows.append(row)
        good=[r['metrics'] for r in rows if r['metrics'] is not None];pos=[r for r in good if not r['negative_image']];neg=[r for r in good if r['negative_image']]
        values={'threshold':threshold,'total':len(rows),'failures':len(rows)-len(good),'positives':len(pos),'negatives':len(neg),'false_positives':sum(r['false_positive_image'] for r in neg),'recall':float(np.mean([r['recall'] for r in pos])) if pos else None,'dice':float(np.mean([r['dice'] for r in pos])) if pos else None}
        return {'selection':values,'summary':aggregate(rows),'rows':rows,'groups':{site:aggregate([r for r in rows if r['groups']['body_site']==site]) for site in ('arm','hand')}}
    validation=load('validation');calibration=[score(validation,t) for t in THRESHOLDS];selected=choose([x['selection'] for x in calibration])
    # Test predictions are created only after the validation-only threshold has been frozen.
    test=load('test');tests={'argmax':score(test,0.0)}
    if selected is not None:tests['selected']=score(test,selected)
    subprocess.run([sys.executable,str(Path(__file__).with_name('round19_policy.py')),'--project-root',str(a.project_root),'--manifest',str(a.manifest),'--weights',str(a.weights),'--output',str(a.output_dir/'policy.json')],check=True,stdout=subprocess.DEVNULL)
    assert reg.read_bytes()==before
    result={'protocol':'round28-protocol.md','manifest_sha256':doc['manifest_sha256'],'weights_sha256':weights_hash,'thresholds':THRESHOLDS,'selected_threshold':selected,'status':'selected' if selected is not None else 'no_eligible_threshold','validation':calibration,'test':tests,'registry_sha256':hashlib.sha256(before).hexdigest(),'training_source':'synthetic','enabled':False,'automatic_measurement':False}
    (a.output_dir/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'threshold':selected,'validation':[x['selection'] for x in calibration]},indent=2),flush=True)
if __name__=='__main__':main()
