"""Calibrated synthetic partial labels with independent negative assessment."""
import argparse,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round56 as sim
import round58 as partial

SOURCES=('test10-arm.png','test10-hand.png','test40-arm.png','test51-hand.png')
METHODS=('dual','guarded')

def labels(calibration,observed,core,guard):
    if calibration.shape!=observed.shape or calibration.shape!=core.shape:raise ValueError('shape mismatch')
    left=core.copy();left[:,core.shape[1]//2:]=False
    if not left.any():raise ValueError('empty calibration region')
    high=float(max(3.,np.quantile(calibration[left],.999)));low=float(max(2.,np.quantile(calibration[left],.990)))
    if low>high:raise ValueError('threshold order invalid')
    unstable=cv2.GaussianBlur(np.abs(calibration.astype('float32')),(0,0),5)>3
    union=(observed>low)&core;confirmed=(observed>high)&core
    if guard:confirmed &= ~unstable
    unknown=union&~confirmed
    return confirmed,unknown,{'high':high,'low':low,'unstable_skin_pct':float(100*(unstable&core).sum()/core.sum())}

def control_stats(confirmed,unknown,core):
    right=core.copy();right[:,:core.shape[1]//2]=False
    if not right.any():raise ValueError('empty control evaluation region')
    return {'control_confirmed_pct':float(100*confirmed[right].mean()),'control_union_pct':float(100*(confirmed|unknown)[right].mean())}

def choose(cases):
    eligible=[]
    for m in METHODS:
        rows=[x for x in cases if x['method']==m]
        if len(rows)!=24:continue
        if all(x.get('success') and x['thresholds']['control_confirmed_pct']<=1 and x['thresholds']['control_union_pct']<=5 and x['metrics']['confirmed_precision']>=.8 and x['metrics']['covered_big_recall']>=.8 and x['metrics']['covered_small_recall']>=.8 and x['metrics']['confirmed_big_recall']>=.2 and x['metrics']['confirmed_small_recall']>=.2 and x['metrics']['unknown_skin_pct']<=10 for x in rows):eligible.append((min(x['metrics']['covered_small_recall'] for x in rows),-METHODS.index(m),m))
    return max(eligible)[2] if eligible else None

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','images','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();cv2.setNumThreads(2);reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);paths=[a.images/n for n in SOURCES];assert len({sim.sha(x) for x in paths})==4;cases=[]
    for si,path in enumerate(paths):
        src,shape=sim.base.read(path);core=sim.base.skin_core(src);alpha,big,small,ignore=sim.make_shapes(core);valid=core&~ignore
        for gi,scenario in enumerate(('translation','affine','nonrigid')):
            for ti,strength in enumerate((.12,.28)):
                seed=5900000+si*1000+gi*10+ti;rng=np.random.default_rng(seed);edit=np.clip(src.astype('float32')+alpha[...,None]*strength*(255-src.astype('float32')),0,255).astype('uint8')
                def camera(image,branch):return np.clip(sim.move(image,scenario,branch).astype('float32')+1+rng.normal(0,2,image.shape),0,255).astype('uint8')
                aimg=camera(src,'control');bimg=camera(src,'edited');cimg=camera(src,'edited');eimg=camera(edit,'edited')
                try:
                    aa,ia=sim.align(src,aimg,core,'ecc');bb,ib=sim.align(src,bimg,core,'ecc');cc,ic=sim.align(src,cimg,core,'ecc');ee,ie=sim.align(src,eimg,core,'ecc')
                    if not all(z['success'] for z in (ia,ib,ic,ie)):raise ValueError('alignment gate failed')
                    alignments={'a':ia,'b':ib,'c':ic,'edited':ie};failure=None
                except Exception as exc:alignments=None;failure=type(exc).__name__
                if si==0 and gi==0 and ti==0:
                    for name,img in [('source',src),('control-a',aimg),('control-b',bimg),('control-c',cimg),('intervention',eimg),('core',((big|small)*255).astype('uint8'))]:Image.fromarray(img).save(a.output_dir/(name+'.png'))
                for m in METHODS:
                    row={'source':path.name,'source_sha256':sim.sha(path),'source_size':shape,'scenario':scenario,'strength':strength,'seed':seed,'method':m,'alignment':alignments}
                    try:
                        if failure:raise ValueError('alignment failed: '+failure)
                        calibration=sim.base.luma(bb)-sim.base.luma(aa);negative=sim.base.luma(cc)-sim.base.luma(aa);positive=sim.base.luma(ee)-sim.base.luma(aa)
                        cs,cu,t=labels(calibration,negative,core,m=='guarded');ps,pu,_=labels(calibration,positive,core,m=='guarded');t.update(control_stats(cs,cu,core));row.update(success=True,thresholds=t,metrics=partial.metrics(ps,pu,big,small,valid,core))
                        if si==0 and gi==0 and ti==0:Image.fromarray((ps*255).astype('uint8')).save(a.output_dir/(m+'-confirmed.png'));Image.fromarray((pu*255).astype('uint8')).save(a.output_dir/(m+'-unknown.png'))
                    except Exception as exc:row.update(success=False,error_type=type(exc).__name__)
                    cases.append(row)
        print('completed source',path.name,flush=True)
    assert reg.read_bytes()==before;selected=choose(cases);summary={m:{'cases':sum(x['method']==m for x in cases),'failures':sum(not x.get('success',False) for x in cases if x['method']==m),'eligible':m==selected} for m in METHODS};out={'protocol':'round59-protocol.md','source_sha256':{x.name:sim.sha(x) for x in paths},'selected_method':selected,'status':'selected_for_further_study' if selected else 'no_eligible_method','summary':summary,'cases':cases,'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['synthetic interventions not medical truth','C and E share transform class','source aspect ratio stretched','unknown is not normal skin']};(a.output_dir/'results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'selected':selected,'summary':summary},indent=2),flush=True)
if __name__=='__main__':main()
