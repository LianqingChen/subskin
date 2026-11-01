"""Select a synthetic lesion-vs-skin threshold on development data only."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import torch


def conditional_decode(prob,threshold):
    if prob.ndim!=3 or prob.shape[0]!=5 or not 0<threshold<1 or not np.isfinite(prob).all():raise ValueError('invalid probabilities/threshold')
    original=prob.argmax(axis=0).astype('uint8');skin=np.isin(original,[1,2]);denom=prob[1]+prob[2]
    if np.any(denom[skin]<=0):raise ValueError('zero skin probability')
    conditional=np.divide(prob[2],denom,out=np.zeros_like(denom),where=denom>0)
    output=original.copy();output[skin]=np.where(conditional[skin]>threshold,2,1)
    return output


def select(rows):
    eligible=[x for x in rows if x['passed']]
    return max(eligible,key=lambda x:(x['mean_positive_dice'],x['threshold']))['threshold'] if eligible else None


def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','prior-runs','hard-runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from round42_validation import validation_stats,passes_validation
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':384,'validation':160,'test':64}
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];results={}
    for kind in ('prior','hard'):
        for seed in (19,43):
            folder=(a.prior_runs/('run-'+str(seed))) if kind=='prior' else (a.hard_runs/('hard-'+str(seed)));meta=json.loads((folder/'summary.json').read_text());w=folder/'baseline.pt';wh=hashlib.sha256(w.read_bytes()).hexdigest();assert wh==meta['model_sha256'] and meta['manifest_sha256']==doc['manifest_sha256']
            model=torch.jit.load(str(w),map_location='cpu').eval();cache=[];failures=[]
            for item in doc['items']:
                if item['split']!='validation':continue
                try:
                    rgb,truth=load_item(Path(doc['root']),item);assert rgb.shape==(128,128,3);x=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255
                    with torch.inference_mode():prob=torch.softmax(model(x),1)[0].cpu().numpy()
                    if not np.isfinite(prob).all():raise ValueError('nonfinite probability')
                    cache.append({'item':item,'truth':truth,'prob':prob})
                except Exception as exc:failures.append({'id':item['id'],'error':type(exc).__name__})
            scans=[];equal_mismatch=None
            if not failures and len(cache)==160:
                for k in range(1,10):
                    threshold=k/10;pairs=[];rows=[];dice=[];mismatch=0
                    for entry in cache:
                        truth=entry['truth'];prob=entry['prob'];pred=conditional_decode(prob,threshold);valid=truth!=255;gt=(truth==2)&valid;pl=(pred==2)&valid;n=int(gt.sum());m=int(pl.sum());tp=int((gt&pl).sum());value=2*tp/(n+m) if n else None
                        if value is not None:dice.append(value)
                        if k==5:mismatch+=int(np.count_nonzero(pred!=prob.argmax(axis=0)))
                        pairs.append((torch.from_numpy(pred),torch.from_numpy(truth)));rows.append({'id':entry['item']['id'],'subject_id':entry['item']['subject_id'],'positive':bool(n),'dice':value,'recall':tp/n if n else None,'false_positive_image':bool(m) if not n else None})
                    stats=validation_stats(pairs);passed=passes_validation(stats);assert len(dice)==80
                    scans.append({'threshold':threshold,'mean_positive_dice':sum(dice)/len(dice),'statistics':stats,'passed':passed,'rows':rows})
                    if k==5:equal_mismatch=mismatch
                assert equal_mismatch==0,'threshold .5 must reproduce argmax on this data'
            chosen=select(scans) if not failures else None
            results[kind+'-'+str(seed)]={'weights_sha256':wh,'validation_failures':failures,'argmax_half_mismatch_pixels':equal_mismatch,'selected_threshold':chosen,'status':'selected' if chosen is not None else 'no_eligible_threshold','scans':scans}
    assert reg.read_bytes()==before
    if a.output.exists():raise ValueError('output exists')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'manifest_sha256':doc['manifest_sha256'],'registry_sha256':hashlib.sha256(before).hexdigest(),'models':results,'limitations':['validation reused for early stopping and model selection','synthetic sources are correlated','conditional threshold is not product behavior','no clinical truth']},indent=2)+'\n');print(json.dumps({k:{'status':v['status'],'threshold':v['selected_threshold'],'failures':len(v['validation_failures'])} for k,v in results.items()},indent=2))
if __name__=='__main__':main()
