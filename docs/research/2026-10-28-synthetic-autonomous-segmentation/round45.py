"""Select intersection thresholds on synthetic development validation only."""
import argparse,hashlib,itertools,json,sys
from pathlib import Path
import numpy as np
import torch

GRID=(.1,.3,.5,.7,.9)

def joint_decode(prior,hard,prior_threshold,hard_threshold):
    if prior.shape!=hard.shape or prior.ndim!=3 or prior.shape[0]!=5 or not np.isfinite(prior).all() or not np.isfinite(hard).all():raise ValueError('invalid probabilities')
    if not 0<prior_threshold<1 or not 0<hard_threshold<1:raise ValueError('invalid threshold')
    base=prior.argmax(0).astype('uint8');other=hard.argmax(0);base_skin=np.isin(base,[1,2]);other_skin=np.isin(other,[1,2]);d1=prior[1]+prior[2];d2=hard[1]+hard[2]
    if np.any(d1[base_skin]<=0) or np.any(d2[other_skin]<=0):raise ValueError('zero skin probability')
    a=np.divide(prior[2],d1,out=np.zeros_like(d1),where=d1>0);b=np.divide(hard[2],d2,out=np.zeros_like(d2),where=d2>0)
    positive=base_skin & other_skin & (a>prior_threshold) & (b>hard_threshold)
    result=base.copy();result[base_skin]=1;result[positive]=2
    return result

def choose(scans):
    candidates=[r for r in scans if r['passed']]
    return max(candidates,key=lambda r:(r['mean_positive_dice'],r['hard_threshold'],r['prior_threshold'])) if candidates else None

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','prior-runs','hard-runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from round42_validation import validation_stats,passes_validation
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':384,'validation':160,'test':64}
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];results={}
    for seed in (19,43):
        models={};hashes={}
        for kind in ('prior','hard'):
            folder=(a.prior_runs/('run-'+str(seed))) if kind=='prior' else (a.hard_runs/('hard-'+str(seed)));meta=json.loads((folder/'summary.json').read_text());path=folder/'baseline.pt';h=hashlib.sha256(path.read_bytes()).hexdigest();assert h==meta['model_sha256'] and meta['manifest_sha256']==doc['manifest_sha256'];hashes[kind]=h;models[kind]=torch.jit.load(str(path),map_location='cpu').eval()
        cache=[];failures=[]
        for item in doc['items']:
            if item['split']!='validation':continue
            try:
                rgb,truth=load_item(Path(doc['root']),item);assert rgb.shape==(128,128,3);x=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255
                with torch.inference_mode(): probs={k:torch.softmax(m(x),1)[0].cpu().numpy() for k,m in models.items()}
                if any(not np.isfinite(z).all() for z in probs.values()):raise ValueError('nonfinite probability')
                cache.append({'item':item,'truth':truth,'probs':probs})
            except Exception as exc:failures.append({'id':item['id'],'error':type(exc).__name__})
        scans=[]
        if not failures and len(cache)==160:
            for pt,ht in itertools.product(GRID,GRID):
                pairs=[];rows=[];dice=[]
                for item in cache:
                    truth=item['truth'];pred=joint_decode(item['probs']['prior'],item['probs']['hard'],pt,ht);valid=truth!=255;gt=(truth==2)&valid;pl=(pred==2)&valid;n=int(gt.sum());m=int(pl.sum());tp=int((gt&pl).sum());d=2*tp/(n+m) if n else None
                    if d is not None:dice.append(d)
                    pairs.append((torch.from_numpy(pred),torch.from_numpy(truth)));rows.append({'id':item['item']['id'],'subject_id':item['item']['subject_id'],'positive':bool(n),'dice':d,'recall':tp/n if n else None,'false_positive_image':bool(m) if not n else None})
                stats=validation_stats(pairs);assert len(dice)==80
                scans.append({'prior_threshold':pt,'hard_threshold':ht,'mean_positive_dice':sum(dice)/len(dice),'statistics':stats,'passed':passes_validation(stats),'rows':rows})
        selected=choose(scans) if not failures else None
        results[str(seed)]={'weights_sha256':hashes,'validation_failures':failures,'status':'selected' if selected is not None else 'no_eligible_combination','selected':None if selected is None else {'prior_threshold':selected['prior_threshold'],'hard_threshold':selected['hard_threshold'],'mean_positive_dice':selected['mean_positive_dice'],'statistics':selected['statistics']},'scans':scans}
    assert reg.read_bytes()==before
    if a.output.exists():raise ValueError('output exists')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'manifest_sha256':doc['manifest_sha256'],'registry_sha256':hashlib.sha256(before).hexdigest(),'grid':GRID,'models':results,'limitations':['validation reused for training selection','correlated synthetic sources','joint decision is not deployed','no clinical reference']},indent=2)+'\n');print(json.dumps({k:{'status':v['status'],'selected':v['selected'],'failures':len(v['validation_failures'])} for k,v in results.items()},indent=2))
if __name__=='__main__':main()
