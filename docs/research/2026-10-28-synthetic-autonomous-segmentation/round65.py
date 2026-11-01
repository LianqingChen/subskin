"""Fresh generator-control comparison with inclusive synthetic-boundary scores."""
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

def full_metrics(pred, alpha, core):
    truth=(alpha>=.5)&core;pred=pred&core;p=int(pred.sum());n=int(truth.sum());tp=int((pred&truth).sum())
    if not n:raise ValueError('empty full reference')
    return {'dice':2*tp/(p+n),'relative_area_error':abs(p-n)/n,'reference_area_pixels':n,'confirmed_area_pixels':p}

def evaluate(cal,neg,pos,core,method):
    if method=='smooth':cal,neg,pos=[cv2.GaussianBlur(x,(0,0),2) for x in (cal,neg,pos)]
    elif method!='single':raise ValueError('unknown method')
    ns,nu,_=stratify.labels(cal,neg,core,True);ps,pu,t=stratify.labels(cal,pos,core,True);t.update(stratify.control_stats(ns,nu,core));return ps,pu,t

def run(inputs,output,project):
    cv2.setNumThreads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('output not empty')
    output.mkdir(parents=True,exist_ok=True);rows=[];hashes={}
    for name in ('arm','hand'):
        paths={'source':inputs/f'source-{name}.png',**{r:inputs/f'{name}-{r}.png' for r in ('A','B','C')}};hashes[name]={r:prev.sha(p) if p.exists() else None for r,p in paths.items()}
        try:
            if any(not p.exists() for p in paths.values()):raise ValueError('missing input')
            if not prev.native_corners_cyan(paths['source']):raise ValueError('source corners')
            src,info=prev.read_letterbox(paths['source']);core=prev.skin_core(src);aligned={};states={};raw={}
            for role in ('A','B','C'):
                raw[role],meta=prev.read_letterbox(paths[role])
                if not prev.acceptable_aspect(info['aspect'],meta['aspect']):raise ValueError('aspect')
                aligned[role],states[role]=prev.align(src,raw[role],core)
                if not states[role]['success']:raise ValueError('control alignment '+role)
            alpha,big,small,_=sim.make_shapes(core)
            ba=np.where(cv2.dilate(big.astype('uint8'),np.ones((9,9),np.uint8)).astype(bool),alpha,0).astype('float32');sa=np.where(cv2.dilate(small.astype('uint8'),np.ones((9,9),np.uint8)).astype(bool),alpha,0).astype('float32')
            la,lb,lc=[sim.base.luma(aligned[x]) for x in ('A','B','C')];cal=lb-la;neg=lc-la;failure=None
        except Exception as exc:failure=f'{type(exc).__name__}: {exc}'
        for placement in ('original','mirror'):
            for strength in (.06,.12,.28):
                try:
                    if failure:raise ValueError('source preparation: '+failure)
                    b=ba if placement=='original' else np.fliplr(ba).copy();s=sa if placement=='original' else np.fliplr(sa).copy();combined=np.maximum(b,s)
                    if np.any((combined>.2)&~core):raise ValueError('intervention outside core')
                    edited=prior.synthesize(raw['C'],combined,strength);edit_aligned,state=prev.align(src,edited,core)
                    if not state['success']:raise ValueError('edited alignment')
                    wb=prior.warp_alpha(b,state['matrix']);ws=prior.warp_alpha(s,state['matrix']);wa=np.maximum(wb,ws);big=(wb>=.8)&core;small=(ws>=.8)&core;valid=core&~((wa>.2)&(wa<.8));pos=sim.base.luma(edit_aligned)-la;case_failure=None
                    folder=output/f'{name}-{placement}-{strength:.2f}';folder.mkdir();Image.fromarray(edit_aligned).save(folder/'intervention-aligned.png');Image.fromarray(((wa>=.5)&core).astype('uint8')*255).save(folder/'reference-alpha05.png')
                except Exception as exc:case_failure=f'{type(exc).__name__}: {exc}'
                for method in METHODS:
                    row={'source':name,'placement':placement,'strength':strength,'method':method,'success':False}
                    try:
                        if case_failure:raise ValueError(case_failure)
                        ps,pu,t=evaluate(cal,neg,pos,core,method);met=scoring.metrics(ps,pu,big,small,valid,core);full=full_metrics(ps,wa,core);row.update(success=True,thresholds=t,metrics=met,full_region=full,alignments={**states,'E':state});row['gates']=prior.gates(row);row['gates'].update(full_dice=full['dice']>=.8,area_error=full['relative_area_error']<=.2);row['passed']=all(row['gates'].values());Image.fromarray((ps*255).astype('uint8')).save(folder/f'{method}-confirmed.png');Image.fromarray((pu*255).astype('uint8')).save(folder/f'{method}-unknown.png')
                    except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                    rows.append(row)
        print(name,'completed',flush=True)
    assert reg.read_bytes()==before
    summary={m:{'pass':sum(x.get('passed',False) for x in rows if x['method']==m),'total':sum(x['method']==m for x in rows),'failures':sum(not x['success'] for x in rows if x['method']==m)} for m in METHODS}
    out={'protocol':'round65-protocol.md','source_sha256':hashes,'summary':summary,'cases':rows,'registry_sha256':hashlib.sha256(before).hexdigest(),'used_for_training':False,'limitations':['previously observed sources','positive and negative share generated C','full region is an alpha threshold convention','reference is not actual generated lesion truth','not clinical accuracy']};(output/'results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(summary),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('inputs','output','project'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.inputs,a.output,a.project)
if __name__=='__main__':main()
