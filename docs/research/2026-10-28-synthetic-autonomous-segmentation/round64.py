"""Paired experiment of fixed-scale smoothed differences; offline research."""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round56 as sim
import round58 as scoring
import round59 as stratify
import round61 as prev
import round62 as prior

METHODS=('single','smooth')

def reference(core, placement, matrix):
    alpha,big,small,_=sim.make_shapes(core)
    ba=np.where(cv2.dilate(big.astype('uint8'),np.ones((9,9),np.uint8)).astype(bool),alpha,0).astype('float32')
    sa=np.where(cv2.dilate(small.astype('uint8'),np.ones((9,9),np.uint8)).astype(bool),alpha,0).astype('float32')
    if placement=='mirror':ba=np.fliplr(ba).copy();sa=np.fliplr(sa).copy()
    wb=prior.warp_alpha(ba,matrix);ws=prior.warp_alpha(sa,matrix);combined=np.maximum(wb,ws)
    return (wb>=.8)&core,(ws>=.8)&core,core&~((combined>.2)&(combined<.8))

def difference(a,b,observed,method):
    if method=='single':return observed-a
    if method=='smooth':return cv2.GaussianBlur(observed-a,(0,0),2)
    raise ValueError('unknown method')

def run(inputs, cases_dir, output, project):
    cv2.setNumThreads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);previous=json.loads((cases_dir/'results.json').read_text());rows=[];mismatches=[];source_hashes={}
    for name in ('leg','hand'):
        paths={'source':inputs/f'source-{name}.png',**{r:inputs/f'{name}-{r}.png' for r in ('A','B','C')}}
        source_hashes[name]={k:prev.sha(v) for k,v in paths.items()}
        if source_hashes[name]!=previous['source_sha256'][name]:raise ValueError('source hashes do not match round62')
        src,_=prev.read_letterbox(paths['source']);core=prev.skin_core(src); aligned={}
        for role in ('A','B','C'):
            arr,_=prev.read_letterbox(paths[role]);aligned[role],state=prev.align(src,arr,core)
            if not state['success']:raise ValueError('control alignment failed')
        la,lb,lc=[sim.base.luma(aligned[r]) for r in ('A','B','C')];cal=lb-la
        for old in [x for x in previous['cases'] if x['source']==name]:
            for method in METHODS:
                row={'source':name,'placement':old['placement'],'strength':old['strength'],'method':method,'success':False}
                if not old['success']:row['error']='round62: '+old['error'];rows.append(row);continue
                try:
                    folder=cases_dir/f"{name}-{old['placement']}-{old['strength']:.2f}"
                    edit=np.asarray(Image.open(folder/'intervention-aligned.png').convert('RGB'));le=sim.base.luma(edit)
                    b,s,valid=reference(core,old['placement'],old['alignments']['E']['matrix'])
                    control= difference(la,lb,lc,method);positive=difference(la,lb,le,method)
                    calibration=cal if method=='single' else cv2.GaussianBlur(cal,(0,0),2)
                    ns,nu,_=stratify.labels(calibration,control,core,True);ps,pu,t=stratify.labels(calibration,positive,core,True);t.update(stratify.control_stats(ns,nu,core));met=scoring.metrics(ps,pu,b,s,valid,core)
                    row.update(success=True,thresholds=t,metrics=met);row['gates']=prior.gates(row);row['passed']=all(row['gates'].values())
                    if method=='single':
                        keys=list(met);bad=[k for k in keys if abs(met[k]-old['metrics'][k])>1e-9]
                        bad += [k for k in t if abs(t[k]-old['thresholds'][k])>1e-9]
                        if bad:mismatches.append({'source':name,'placement':old['placement'],'strength':old['strength'],'keys':bad})
                    case=output/f"{name}-{old['placement']}-{old['strength']:.2f}";case.mkdir(exist_ok=True);Image.fromarray((ps*255).astype('uint8')).save(case/f'{method}-confirmed.png');Image.fromarray((pu*255).astype('uint8')).save(case/f'{method}-unknown.png')
                except Exception as exc:row.update(success=False,error=f'{type(exc).__name__}: {exc}');mismatches.append({'case':row,'error':'processing error'})
                rows.append(row)
        print(name,'completed',flush=True)
    assert reg.read_bytes()==before
    summary={m:{'pass':sum(x.get('passed',False) for x in rows if x['method']==m),'total':sum(x['method']==m for x in rows),'processing_failures':sum(not x['success'] for x in rows if x['method']==m)} for m in METHODS}
    result={'protocol':'round64-protocol.md','baseline_reproduced':not mismatches,'baseline_mismatches':mismatches,'source_sha256':source_hashes,'round62_results_sha256':prev.sha(cases_dir/'results.json'),'summary':summary,'cases':rows,'used_for_training':False,'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['same previously observed development examples','negative and positive share C','smoothing may blur lesion boundaries','no actual generated lesion truth','not clinical accuracy']}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'baseline_reproduced':not mismatches,'summary':summary}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('inputs','cases-dir','output','project'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.inputs,a.cases_dir,a.output,a.project)
if __name__=='__main__':main()
