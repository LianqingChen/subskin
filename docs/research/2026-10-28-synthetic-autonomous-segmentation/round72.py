"""Evaluate fixed lesion-score cutoffs on frozen research models."""
import argparse, hashlib, json, sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import torch
from torch.nn import functional as F
import round61 as prev
import round62 as prior
import round66 as scoring
import round71 as exp

THRESHOLDS=(0.,.5,.7,.8,.9,.95,.99)

def probabilities(model,rgb):
    h,w=rgb.shape[:2];factor=min(1.,1024/max(h,w));nw=max(1,round(w*factor));nh=max(1,round(h*factor));im=cv2.resize(rgb,(nw,nh),interpolation=cv2.INTER_AREA);x=torch.from_numpy(im.copy()).permute(2,0,1).float().unsqueeze(0)/255;x=F.pad(x,(0,(-nw)%16,0,(-nh)%16))
    with torch.inference_mode():
        p=torch.softmax(model(x),1)[:,:,:nh,:nw]
        if p.shape[1]!=5 or not torch.isfinite(p).all():raise ValueError('invalid probabilities')
        return F.interpolate(p,size=(h,w),mode='bilinear',align_corners=False)[0].numpy()

def classify(probs,threshold):
    raw=probs.argmax(axis=0).astype('uint8');result=raw.copy();suppress=(raw==2)&(probs[2]<threshold)
    if suppress.any():
        remainder=probs.copy();remainder[2]=-1;result[suppress]=remainder.argmax(axis=0)[suppress]
    return result

def run(project,research,manifest,inputs,output):
    sys.path.insert(0,str(project));from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from round47_validation import validation_stats,passes_validation
    torch.set_num_threads(2);cv2.setNumThreads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];doc=validate_manifest(manifest,allow_synthetic=True);assert doc['synthetic'] and doc['manifest_sha256']=='e633bbb65a12e8dfcc5104383299bf1e51659f556e606f696344b659334c95e0'
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);priorfile=research/'round71-artifacts/completed/results.json';old=json.loads(priorfile.read_text());refs=research/'round71-artifacts/completed/references';reference_meta=json.loads((refs.parent/'reference-provenance.json').read_text());rng=np.random.default_rng(7005);sources={}
    for name in exp.NAMES:
        for role,path in [('source',inputs/f'source-{name}.png'),('control',inputs/f'{name}-C.png')]:
            if (prev.sha(path) if path.exists() else None)!=old['input_sha256'][name][role]:raise ValueError('input hash mismatch')
        try:
            z=exp.prepare_source(name,inputs,rng);expected=old['sources'][name]
            if expected['status']!='ok':raise ValueError('source status mismatch')
            for i,pos in enumerate(z['positions']):
                if pos.get('location')!=expected['locations'][i].get('location') or pos['error']!=expected['locations'][i]['error']:raise ValueError('position mismatch')
                if pos['error']:continue
                big,small=pos['big'],pos['small'];core=z['core'];alpha=np.maximum(big,small)
                for suffix,mask in [('full',(alpha>=.5)&core),('big',(big>=.8)&core),('small',(small>=.8)&core)]:
                    namefile=f'{name}-p{i}-{suffix}.png';path=refs/namefile
                    if prev.sha(path)!=reference_meta[namefile]['sha256'] or not np.array_equal(np.asarray(Image.open(path))>0,mask):raise ValueError('reference mismatch')
            sources[name]=z
        except Exception as exc:
            if old['sources'][name]['status']!='error':raise
            sources[name]=None
    results={};rows=[];mismatches=[]
    for seed in (19,43):
        label=f'tuned-{seed}';folder=research/'round69-artifacts'/label;weights=folder/'baseline.pt';meta=json.loads((folder/'summary.json').read_text());assert prev.sha(weights)==meta['model_sha256'];model=torch.jit.load(str(weights),map_location='cpu').eval();records={t:[] for t in THRESHOLDS}
        for item in doc['items']:
            if item['split']!='validation':continue
            rgb,truth=load_item(Path(doc['root']),item);p=probabilities(model,rgb);target=torch.from_numpy(truth).unsqueeze(0)
            for t in THRESHOLDS:records[t].append((torch.from_numpy(classify(p,t)).unsqueeze(0),target))
        grid={}
        for t in THRESHOLDS:
            s=validation_stats(records[t]);grid[str(t)]={'statistics':s,'passes':passes_validation(s)}
        if grid['0.0']['statistics']!=meta['validation']:mismatches.append({'model':label,'stage':'development_baseline'})
        eligible=[t for t in THRESHOLDS if grid[str(t)]['passes']];selected=max(eligible,key=lambda t:(grid[str(t)]['statistics']['small']['recall'],-t)) if eligible else None
        results[label]={'model_sha256':meta['model_sha256'],'selected_threshold':selected,'grid':grid};print(label,'development complete','selected',selected,flush=True)
        for name in exp.NAMES:
            z=sources[name]
            for kind in ('negative','positive'):
                cases=[{'exposure':e} for e in exp.EXPOSURES] if kind=='negative' else [{'position':i,'strength':s,'exposure':e} for i in range(2) for s in exp.STRENGTHS for e in exp.EXPOSURES]
                for case in cases:
                    base={'model':label,'source':name,'kind':kind,**case};error=None
                    try:
                        if z is None:raise ValueError('source rejected')
                        core=z['core'];neg=exp.expose(z['control'],case['exposure'])
                        if kind=='positive':
                            position=z['positions'][case['position']]
                            if position['error']:raise ValueError('position rejected')
                            big,small=position['big'],position['small'];alpha=np.maximum(big,small);img=exp.expose(prior.synthesize(z['control'],alpha,case['strength']),case['exposure']);truth=(alpha>=.5)&core;b=(big>=.8)&core;s=(small>=.8)&core
                        else:img=neg;truth=b=s=None
                        probs=probabilities(model,img)
                    except Exception as exc:error=f'{type(exc).__name__}: {exc}'
                    for t in THRESHOLDS:
                        row={**base,'threshold':t,'success':False}
                        if error:row['error']=error
                        else:
                            pred=classify(probs,t)==2;met=scoring.score(pred,core,truth,b,s);row.update(success=True,metrics=met,prediction_sha256=hashlib.sha256(pred.tobytes()).hexdigest())
                            if t==0:
                                keys=('model','source','kind','exposure','position','strength');matches=[x for x in old['rows'] if all(x.get(k)==row.get(k) for k in keys)]
                                if len(matches)!=1 or not matches[0]['success'] or matches[0]['metrics']!=met:mismatches.append({'stage':'diagnostic_baseline','case':base})
                        rows.append(row)
        print(label,'diagnostic complete',flush=True)
    assert len(rows)==1176 and reg.read_bytes()==before
    result={'protocol':'round72-protocol.md','thresholds':THRESHOLDS,'models':results,'diagnostic_rows':rows,'baseline_reproduced':not mismatches,'mismatches':mismatches,'manifest_sha256':doc['manifest_sha256'],'prior_results_sha256':prev.sha(priorfile),'registry_sha256':hashlib.sha256(before).hexdigest(),'training':False,'limitations':['development validation reused for selection','diagnostic sources previously observed','synthetic reference not clinical truth','softmax not calibrated']};(output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'baseline_reproduced':not mismatches,'rows':len(rows),'selected':{k:v['selected_threshold'] for k,v in results.items()}}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','research','manifest','inputs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.research,a.manifest,a.inputs,a.output)
if __name__=='__main__':main()
