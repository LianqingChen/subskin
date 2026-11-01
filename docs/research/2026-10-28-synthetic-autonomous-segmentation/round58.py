"""Partial synthetic difference labels: confident, unknown, no detection."""
import argparse,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round56 as sim

SOURCES=('test20-arm.png','test21-hand.png','test33-arm.png','test46-hand.png')
METHODS=('single','dual')

def partition(calibration,positive,core):
    if calibration.shape!=positive.shape or calibration.shape!=core.shape:raise ValueError('shape mismatch')
    left=core.copy();left[:,core.shape[1]//2:]=False;right=core.copy();right[:,:core.shape[1]//2]=False
    if not left.any() or not right.any():raise ValueError('empty control side')
    high=float(max(3.,np.quantile(calibration[left],.999)));low=float(max(2.,np.quantile(calibration[left],.990)))
    if low>high:raise ValueError('threshold order invalid')
    confirmed=(positive>high)&core;unknown=(positive>low)&~confirmed&core
    return confirmed,unknown,{'low_threshold':low,'high_threshold':high,'control_confirmed_pct':float(100*(calibration[right]>high).mean()),'control_union_pct':float(100*(calibration[right]>low).mean())}

def metrics(confirmed,unknown,big,small,valid,core):
    if (confirmed&unknown).any():raise ValueError('overlapping labels')
    strong=confirmed&valid;cover=(confirmed|unknown)&valid;truth=(big|small)&valid;pn=int(strong.sum());bn=int((big&valid).sum());sn=int((small&valid).sum())
    if not bn or not sn or not core.any():raise ValueError('missing ground truth core')
    return {'confirmed_precision':int((strong&truth).sum())/pn if pn else 0.,'confirmed_big_recall':int((strong&big).sum())/bn,'confirmed_small_recall':int((strong&small).sum())/sn,'covered_big_recall':int((cover&big).sum())/bn,'covered_small_recall':int((cover&small).sum())/sn,'unknown_skin_pct':float(100*(unknown&core).sum()/core.sum()),'confirmed_pixels':pn,'unknown_pixels':int((unknown&core).sum()),'big_pixels':bn,'small_pixels':sn}

def choose(cases):
    options=[]
    for method in METHODS:
        rows=[x for x in cases if x['method']==method]
        if len(rows)!=24:continue
        if all(x.get('success') and x['thresholds']['control_confirmed_pct']<=1 and x['thresholds']['control_union_pct']<=5 and x['metrics']['confirmed_precision']>=.8 and x['metrics']['covered_big_recall']>=.8 and x['metrics']['covered_small_recall']>=.8 and x['metrics']['confirmed_big_recall']>=.2 and x['metrics']['confirmed_small_recall']>=.2 and x['metrics']['unknown_skin_pct']<=10 for x in rows):options.append((min(x['metrics']['covered_small_recall'] for x in rows),-METHODS.index(method),method))
    return max(options)[2] if options else None

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
                seed=5800000+si*1000+gi*10+ti;rng=np.random.default_rng(seed);intervention=np.clip(src.astype('float32')+alpha[...,None]*strength*(255-src.astype('float32')),0,255).astype('uint8')
                def camera(image,branch):return np.clip(sim.move(image,scenario,branch).astype('float32')+1+rng.normal(0,2,image.shape),0,255).astype('uint8')
                ca=camera(src,'control');cb=camera(src,'edited');edit=camera(intervention,'edited')
                try:
                    aa,ia=sim.align(src,ca,core,'ecc');bb,ib=sim.align(src,cb,core,'ecc');ee,ie=sim.align(src,edit,core,'ecc')
                    if not (ia['success'] and ib['success'] and ie['success']):raise ValueError('alignment gate failed')
                    alignment={'control_a':ia,'control_b':ib,'edited':ie};failure=None
                except Exception as exc:alignment=None;failure=type(exc).__name__
                for method in METHODS:
                    row={'source':path.name,'source_sha256':sim.sha(path),'source_size':shape,'scenario':scenario,'strength':strength,'seed':seed,'method':method,'alignment':alignment}
                    try:
                        if failure:raise ValueError('alignment failed: '+failure)
                        if method=='single':negative=sim.base.luma(aa)-sim.base.luma(src);positive=sim.base.luma(ee)-sim.base.luma(src)
                        else:negative=sim.base.luma(bb)-sim.base.luma(aa);positive=sim.base.luma(ee)-sim.base.luma(aa)
                        confirmed,unknown,thresholds=partition(negative,positive,core);row.update(success=True,thresholds=thresholds,metrics=metrics(confirmed,unknown,big,small,valid,core))
                        if si==0 and gi==0 and ti==0:
                            Image.fromarray((confirmed*255).astype('uint8')).save(a.output_dir/(method+'-confirmed.png'));Image.fromarray((unknown*255).astype('uint8')).save(a.output_dir/(method+'-unknown.png'))
                    except Exception as exc:row.update(success=False,error_type=type(exc).__name__)
                    cases.append(row)
                if si==0 and gi==0 and ti==0:
                    for name,img in [('source',src),('control-a',ca),('control-b',cb),('intervention',edit),('core',((big|small)*255).astype('uint8')),('ignored',(ignore*255).astype('uint8'))]:Image.fromarray(img).save(a.output_dir/(name+'.png'))
        print('completed source',path.name,flush=True)
    assert reg.read_bytes()==before;selected=choose(cases);summary={m:{'cases':sum(x['method']==m for x in cases),'failures':sum(not x.get('success',False) for x in cases if x['method']==m),'eligible':m==selected} for m in METHODS};out={'protocol':'round58-protocol.md','source_sha256':{x.name:sim.sha(x) for x in paths},'selected_method':selected,'status':'selected_for_further_study' if selected else 'no_eligible_method','summary':summary,'cases':cases,'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['synthetic intervention not medical truth','reference 255 edges excluded','control B shares transform class with edited','source aspect ratio stretched','unknown is not normal skin']};(a.output_dir/'results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'selected':selected,'summary':summary},indent=2),flush=True)
if __name__=='__main__':main()
