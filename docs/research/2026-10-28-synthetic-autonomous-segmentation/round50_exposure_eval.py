"""Paired synthetic sRGB exposure stress with a common assessable mask."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import torch

FACTORS=(.8,1.,1.2)

def common_reference(rgb,truth):
    if rgb.shape[:2]!=truth.shape or rgb.shape[2]!=3:raise ValueError('shape mismatch')
    newly_unreadable=(rgb.astype('float64')*1.2>255).any(axis=2)&(truth!=255)
    adjusted=truth.copy();adjusted[newly_unreadable]=255
    positive_before=bool((truth==2).any());positive_after=bool((adjusted==2).any())
    assessable=int((adjusted!=255).sum())>=64 and (not positive_before or positive_after)
    return adjusted,int(newly_unreadable.sum()),assessable

def scale_srgb(rgb,factor):
    if factor not in FACTORS:raise ValueError('factor not in protocol')
    return np.clip(np.rint(rgb.astype('float64')*factor),0,255).astype('uint8')

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','prior-runs','runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.evaluate import predict
    from ml.rgb_segmentation.metrics import score_labels,aggregate
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':384,'validation':320,'test':64}
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];models={};hashes={};results={}
    for seed in (19,43):
        for name,folder in [('prior',a.prior_runs/('small-'+str(seed))),('exposure',a.runs/('exposure-'+str(seed)))]:
            meta=json.loads((folder/'summary.json').read_text());w=folder/'baseline.pt';h=hashlib.sha256(w.read_bytes()).hexdigest();assert h==meta['model_sha256'] and meta['manifest_sha256']==doc['manifest_sha256'];key=name+'-'+str(seed);models[key]=torch.jit.load(str(w)).eval();hashes[key]=h;results[key]={str(f):[] for f in FACTORS}
    records=[i for i in doc['items'] if i['split']=='validation'];assert len(records)==320
    for idx,item in enumerate(records):
        group='ordinary' if idx<160 else 'small';base={'id':item['id'],'subject_id':item['subject_id'],'groups':item['groups'],'validation_group':group}
        try:
            rgb,truth=load_item(Path(doc['root']),item);reference,ignored,assessable=common_reference(rgb,truth)
        except Exception as exc:
            for key in models:
                for factor in FACTORS:results[key][str(factor)].append({**base,'metrics':None,'outcome':'reference_error','error_type':type(exc).__name__})
            continue
        for factor in FACTORS:
            image=scale_srgb(rgb,factor)
            for key,model in models.items():
                row={**base,'newly_ignored_pixels':ignored}
                if not assessable:row.update(metrics=None,outcome='reference_unassessable')
                else:
                    try:prediction=predict(model,image);row.update(metrics=score_labels(prediction,reference,image),outcome='processed')
                    except Exception as exc:row.update(metrics=None,outcome='error',error_type=type(exc).__name__)
                results[key][str(factor)].append(row)
    grouped={}
    for key,levels in results.items():
        grouped[key]={}
        for factor,rows in levels.items():
            assert len(rows)==320
            grouped[key][factor]={}
            for group in ('ordinary','small'):
                selected=[r for r in rows if r['validation_group']==group];good=[r for r in selected if r['metrics'] is not None];positive=[r for r in good if not r['metrics']['negative_image']]
                grouped[key][factor][group]={'summary':aggregate(selected),'completely_missed_positives':sum(r['metrics']['recall']==0 for r in positive),'by_source':{source:aggregate([r for r in selected if r['subject_id']==source]) for source in sorted({r['subject_id'] for r in selected})},'unassessable':sum(r['outcome']=='reference_unassessable' for r in selected),'errors':sum(r['outcome'] in ('error','reference_error') for r in selected),'newly_ignored_pixels':sum(r.get('newly_ignored_pixels',0) for r in selected)}
    assert before==reg.read_bytes()
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps({'manifest_sha256':doc['manifest_sha256'],'weights_sha256':hashes,'factors':FACTORS,'registry_sha256':hashlib.sha256(before).hexdigest(),'groups':grouped,'rows':results,'limitations':['synthetic sRGB multiplier, not camera exposure','common mask excludes clipped pixels','development validation already observed','no clinical truth']},indent=2)+'\n');print('exposure stress complete',flush=True)
if __name__=='__main__':main()
