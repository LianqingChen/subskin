"""Fixed synthetic validation study of lesion component area filtering."""
import argparse,hashlib,json,sys
from pathlib import Path
import cv2
import numpy as np
import torch

SIZES=(1,4,16,64,256)

def filter_components(prediction,min_area):
    if prediction.ndim!=2 or min_area<1:raise ValueError('invalid input')
    original=prediction.astype('uint8');lesion=(original==2).astype('uint8');n,labels,stats,_=cv2.connectedComponentsWithStats(lesion,connectivity=8)
    keep=np.zeros(n,dtype=bool);keep[1:]=stats[1:,cv2.CC_STAT_AREA]>=min_area
    out=original.copy();out[(lesion==1)&~keep[labels]]=1
    return out

def choose(scans):
    eligible=[s for s in scans if s['passed']]
    return min(eligible,key=lambda s:(-s['mean_positive_dice'],s['min_area']))['min_area'] if eligible else None

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','prior-runs','hard-runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.evaluate import predict
    from round42_validation import validation_stats,passes_validation
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':384,'validation':160,'test':64}
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];results={}
    for kind in ('prior','hard'):
        for seed in (19,43):
            folder=(a.prior_runs/('run-'+str(seed))) if kind=='prior' else (a.hard_runs/('hard-'+str(seed)));meta=json.loads((folder/'summary.json').read_text());path=folder/'baseline.pt';h=hashlib.sha256(path.read_bytes()).hexdigest();assert h==meta['model_sha256'] and meta['manifest_sha256']==doc['manifest_sha256'];model=torch.jit.load(str(path),map_location='cpu').eval();cache=[];failures=[]
            for item in doc['items']:
                if item['split']!='validation':continue
                try:
                    rgb,truth=load_item(Path(doc['root']),item);assert rgb.shape==(128,128,3);pred=predict(model,rgb);cache.append({'item':item,'truth':truth,'pred':pred})
                except Exception as exc:failures.append({'id':item['id'],'error':type(exc).__name__})
            scans=[];mismatch=None
            if not failures and len(cache)==160:
                for area in SIZES:
                    pairs=[];rows=[];dice=[];small=[];difference=0
                    for entry in cache:
                        truth=entry['truth'];pred=filter_components(entry['pred'],area);valid=truth!=255;gt=(truth==2)&valid;pl=(pred==2)&valid;n=int(gt.sum());m=int(pl.sum());tp=int((gt&pl).sum());d=2*tp/(n+m) if n else None;rec=tp/n if n else None
                        if d is not None:dice.append(d)
                        if 0<n<=64:small.append(rec)
                        if area==1:difference+=int(np.count_nonzero(pred!=entry['pred']))
                        pairs.append((torch.from_numpy(pred),torch.from_numpy(truth)));rows.append({'id':entry['item']['id'],'subject_id':entry['item']['subject_id'],'positive':bool(n),'reference_lesion_pixels':n,'dice':d,'recall':rec,'false_positive_image':bool(m) if not n else None})
                    stats=validation_stats(pairs);assert len(dice)==80
                    small_recall=sum(small)/len(small) if small else None;passed=passes_validation(stats) and small_recall is not None and small_recall>=.20
                    scans.append({'min_area':area,'mean_positive_dice':sum(dice)/len(dice),'small_count':len(small),'small_mean_recall':small_recall,'statistics':stats,'passed':passed,'rows':rows})
                    if area==1:mismatch=difference
                assert mismatch==0
            selected=choose(scans) if not failures else None
            results[kind+'-'+str(seed)]={'weights_sha256':h,'validation_failures':failures,'original_mismatch_pixels':mismatch,'selected_min_area':selected,'status':'selected' if selected is not None else 'no_eligible_area','scans':scans}
    assert before==reg.read_bytes()
    if a.output.exists():raise ValueError('output exists')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'manifest_sha256':doc['manifest_sha256'],'registry_sha256':hashlib.sha256(before).hexdigest(),'models':results,'limitations':['validation reused for training selection','correlated synthetic sources','minimum area not clinical measurement','no clinical reference']},indent=2)+'\n');print(json.dumps({k:{'status':v['status'],'selected':v['selected_min_area'],'failures':len(v['validation_failures'])} for k,v in results.items()},indent=2))
if __name__=='__main__':main()
