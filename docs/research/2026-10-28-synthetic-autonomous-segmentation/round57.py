"""Evaluate dual-control synthetic difference masks without clinical labels."""
import argparse,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round56 as previous

SOURCES=('test19-arm.png','test28-hand.png','test34-arm.png','test37-hand.png')
METHODS=('single','dual')

def dual_measure(control_a,control_b,edited,core):
    h,w=core.shape;left=core.copy();left[:,w//2:]=False;right=core.copy();right[:,:w//2]=False
    if not left.any() or not right.any():raise ValueError('empty calibration or assessment area')
    negative=previous.base.luma(control_b)-previous.base.luma(control_a);positive=previous.base.luma(edited)-previous.base.luma(control_a);threshold=float(max(3.,np.quantile(negative[left],.995)));candidate=(positive>threshold)&core;control=(negative>threshold)&core
    return {'threshold_l_encoded':threshold,'control_right_false_positive_pct':float(100*control[right].mean())},candidate,control

def choose(cases):
    eligible=[]
    for method in METHODS:
        rows=[x for x in cases if x['method']==method]
        if len(rows)!=24:continue
        if all(x.get('success') and x['control_right_fp_pct']<=1 and x['metrics']['precision']>=.8 and x['metrics']['big_recall']>=.8 and x['metrics']['small_recall']>=.8 for x in rows):eligible.append((min(x['metrics']['small_recall'] for x in rows),-METHODS.index(method),method))
    return max(eligible)[2] if eligible else None

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','images','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();cv2.setNumThreads(2);reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);paths=[a.images/n for n in SOURCES];assert len({previous.sha(x) for x in paths})==4;cases=[]
    for si,path in enumerate(paths):
        src,shape=previous.base.read(path);core=previous.base.skin_core(src);alpha,big,small,ignore=previous.make_shapes(core);valid=core&~ignore
        for gi,scenario in enumerate(('translation','affine','nonrigid')):
            for ti,strength in enumerate((.12,.28)):
                seed=5700000+si*1000+gi*10+ti;rng=np.random.default_rng(seed);intervention=np.clip(src.astype('float32')+alpha[...,None]*strength*(255-src.astype('float32')),0,255).astype('uint8')
                def camera(image,branch):return np.clip(previous.move(image,scenario,branch).astype('float32')+1+rng.normal(0,2,image.shape),0,255).astype('uint8')
                ca=camera(src,'control');cb=camera(src,'edited');edit=camera(intervention,'edited')
                try:
                    aa,ia=previous.align(src,ca,core,'ecc');bb,ib=previous.align(src,cb,core,'ecc');ee,ie=previous.align(src,edit,core,'ecc')
                    if not (ia['success'] and ib['success'] and ie['success']):raise ValueError('alignment gate failed')
                    alignment={'control_a':ia,'control_b':ib,'edited':ie};errors=None
                except Exception as exc:alignment=None;errors=type(exc).__name__
                if si==0 and gi==0 and ti==0:
                    for name,img in [('source',src),('control-a',ca),('control-b',cb),('intervention',edit),('core',((big|small)*255).astype('uint8')),('ignored',(ignore*255).astype('uint8'))]:Image.fromarray(img).save(a.output_dir/(name+'.png'))
                for method in METHODS:
                    row={'source':path.name,'source_sha256':previous.sha(path),'source_size':shape,'scenario':scenario,'strength':strength,'seed':seed,'method':method,'alignment':alignment}
                    try:
                        if errors:raise ValueError('alignment failed: '+errors)
                        if method=='single':met,pred,_=previous.base.measure(src,aa,ee,core)
                        else:met,pred,_=dual_measure(aa,bb,ee,core)
                        row.update(success=True,threshold=met['threshold_l_encoded'],control_right_fp_pct=met['control_right_false_positive_pct'],metrics=previous.score(pred,big,small,valid))
                        if si==0 and gi==0 and ti==0:Image.fromarray((pred*255).astype('uint8')).save(a.output_dir/(method+'-candidate.png'))
                    except Exception as exc:row.update(success=False,error_type=type(exc).__name__)
                    cases.append(row)
        print('completed source',path.name,flush=True)
    assert reg.read_bytes()==before;selected=choose(cases);summary={m:{'cases':sum(x['method']==m for x in cases),'failures':sum(not x.get('success',False) for x in cases if x['method']==m),'eligible':m==selected} for m in METHODS}
    output={'protocol':'round57-protocol.md','source_sha256':{x.name:previous.sha(x) for x in paths},'selected_method':selected,'status':'selected_for_further_study' if selected else 'no_eligible_method','summary':summary,'cases':cases,'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['program interventions, no medical truth','control B shares transform class with edited image','synthetic motion not imagegen drift','source aspect ratio stretched']};(a.output_dir/'results.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps({'status':output['status'],'selected':selected,'summary':summary},indent=2),flush=True)
if __name__=='__main__':main()
