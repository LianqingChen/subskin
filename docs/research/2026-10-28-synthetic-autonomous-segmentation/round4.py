"""Research-only held-out synthetic base stress test with saved experiment heads."""
import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('round3',ROOT/'round3.py');r3=importlib.util.module_from_spec(spec);spec.loader.exec_module(r3)
Y,X=np.mgrid[:64,:64].astype('float32')


def make_case(base,seed,kind):
    rng=np.random.default_rng(seed);h,w=base.shape[:2];side=int(rng.integers(220,351));xx=int(rng.integers(0,w-side+1));yy=int(rng.integers(0,h-side+1))
    crop=cv2.resize(base[yy:yy+side,xx:xx+side],(64,64),interpolation=cv2.INTER_AREA).astype('float32')/255
    if rng.random()<.5:crop=np.flip(crop,axis=1).copy()
    small=bool(rng.random()<.35);radius=rng.uniform(3,5) if small else rng.uniform(7,16)
    cx,cy=rng.uniform(18,46,2);theta=np.linspace(0,2*np.pi,23,endpoint=False);rad=radius*rng.uniform(.65,1.35,len(theta))
    pts=np.stack([cx+rad*np.cos(theta),cy+rad*np.sin(theta)],1).astype('int32');shape=np.zeros((64,64),'uint8');cv2.fillPoly(shape,[pts],1)
    alpha=cv2.GaussianBlur(shape.astype('float32'),(0,0),float(rng.uniform(.8,1.7)))
    if kind=='glare':
        # Shape-like bright patch denotes a lighting artifact and has no lesion label.
        gain=float(rng.uniform(.18,.38));crop+=alpha[...,None]*gain
        mask=np.zeros((64,64),'float32');small=False
    else:
        gain=float(rng.uniform(.035,.09) if kind=='weak' else rng.uniform(.12,.25))
        # Preserve underlying texture while changing the mean and saturation.
        crop+=alpha[...,None]*gain*(1-crop)
        mask=(alpha>=.5).astype('float32')
    # Independent smooth illumination field, both positive and negative.
    cx2,cy2=rng.uniform(0,64,2); sx,sy=rng.uniform(7,20,2)
    blob=np.exp(-((X-cx2)**2/(2*sx*sx)+(Y-cy2)**2/(2*sy*sy)))
    crop+=blob[...,None]*float(rng.uniform(-.08,.08))
    return np.clip(crop,0,1).astype('float32'),mask,{'seed':seed,'negative':kind=='glare','small':small,'kind':kind}


def cases(path,base_index):
    with Image.open(path) as im:base=np.asarray(im.convert('RGB'))
    ans={}
    for kindex,kind in enumerate(('standard','weak','glare')):
        start=600000+base_index*10000+kindex*1000
        rows=[make_case(base,seed,kind) for seed in range(start,start+32)]
        x=torch.from_numpy(np.stack([a.transpose(2,0,1) for a,_,_ in rows]))
        y=torch.from_numpy(np.stack([b for _,b,_ in rows])[:,None]);meta=[m for _,_,m in rows]
        assert all(bool(y[i].any()) != m['negative'] for i,m in enumerate(meta))
        ans[kind]=(x,y,meta)
    return ans


def score(prob,y,meta,threshold):
    truth=y.numpy()[:,0].astype(bool);pred=prob>=threshold
    area=pred.mean(axis=(1,2))*100;gold=truth.mean(axis=(1,2))*100
    result={'n':len(meta),'mean_area_error_pp':float(np.mean(np.abs(area-gold)))}
    if meta[0]['negative']:
        result.update(mean_fp_area_pct=float(np.mean(area)),fp_image_gt_1pct=float(np.mean(area>1)*100),fp_image_any=float(np.mean(area>0)*100))
    else:
        intersection=(pred&truth).sum(axis=(1,2));denom=pred.sum(axis=(1,2))+truth.sum(axis=(1,2))
        result.update(positive_dice=float(np.mean(2*intersection/(denom+1e-9))),pixel_recall=float(intersection.sum()/truth.sum()),detection_image_rate=float(np.mean(intersection>0)*100))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',required=True);ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);ap.add_argument('--head-dir',required=True);a=ap.parse_args()
    start=time.time();torch.set_num_threads(4);images=Path(a.images);paths=[images/x for x in ('train-medium.png','val-light.png','test-dark.png','test4-light.png','test4-dark.png')]
    hashes=[r3.digest(p) for p in paths];assert len(set(hashes))==len(paths)
    x,y,m=r3.load_data(paths[0],10000,128);vx,vy,vm=r3.load_data(paths[1],200000,64);oldx,oldy,oldm=r3.load_data(paths[2],500000,64)
    groups={}
    for j,path in enumerate(paths[3:]):
        for kind,entry in cases(path,j).items():groups[path.stem+'/'+kind]=entry
    print('Prepared',len(groups),'new groups',flush=True)
    sizes=[len(x),len(vx),len(oldx)]+[len(z[0]) for z in groups.values()]
    allx=torch.cat([x,vx,oldx]+[z[0] for z in groups.values()]);offset=np.cumsum([0]+sizes)
    baseline=json.loads((ROOT/'round3-results.json').read_text())
    results={'protocol':'round4-protocol.md','training_background':paths[0].name,'validation_background':paths[1].name,'old_test_background':paths[2].name,'new_test_backgrounds':[p.name for p in paths[3:]],'image_sha256':hashes,'sam_weights_sha256':r3.digest(a.sam_weights),'samples_per_group':32,'models':{},'limitations':['synthetic masks only','two held-out generated test bases','3-case controlled edits','binary segmentation assumes all skin','nonstandard SAM input','SAM and generator pretraining provenance unknown']}
    outdir=Path(a.head_dir);outdir.mkdir(parents=True,exist_ok=True)
    for modelname in ('rgb_cnn','pretrained_sam'):
        features=None
        if modelname=='pretrained_sam':features=r3.encode(r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights)),allx)
        sl=lambda i:None if features is None else features[offset[i]:offset[i+1]]
        rows=[]
        for seed in (0,1):
            model=r3.train(x,y,sl(0),seed);pv=r3.predict(model,vx,sl(1));threshold,feasible=r3.round2.threshold(pv,vy,vm)
            old=r3.pilot.evaluate(r3.predict(model,oldx,sl(2)),oldy,oldm,threshold)
            expected=baseline['models'][modelname][seed]
            delta=abs(old['positive_dice']-expected['test']['positive_dice']);threshold_delta=abs(threshold-expected['threshold'])
            entry={'seed':seed,'threshold':round(threshold,3),'validation_constraint_met':feasible,'old_holdout_dice':old['positive_dice'],'reproduction_dice_difference':delta,'reproduction_threshold_difference':threshold_delta,'groups':{}}
            for gi,(name,(gx,gy,gm)) in enumerate(groups.items()):entry['groups'][name]=score(r3.predict(model,gx,sl(gi+3)),gy,gm,threshold)
            ckpt=outdir/f'{modelname}_seed{seed}.pt';torch.save({'model_state_dict':model.state_dict(),'model':modelname,'seed':seed,'threshold':threshold,'sam_weights_sha256':results['sam_weights_sha256'] if modelname=='pretrained_sam' else None},ckpt)
            entry['head_checkpoint_sha256']=hashlib.sha256(ckpt.read_bytes()).hexdigest();rows.append(entry)
            print(modelname,seed,'old reproduction delta',delta,'threshold delta',threshold_delta,flush=True)
        results['models'][modelname]=rows;del features
    results['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n');print(json.dumps(results,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
