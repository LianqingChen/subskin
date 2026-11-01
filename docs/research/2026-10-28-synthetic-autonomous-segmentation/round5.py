"""Hard-example ablation using generated skin only; synthetic, not clinical."""
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

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r4',HERE/'round4.py');r4=importlib.util.module_from_spec(spec);spec.loader.exec_module(r4)
r3=r4.r3
Y,X=np.mgrid[:64,:64].astype('float32')


def independent_case(base,seed,kind):
    """Test-only non-polygon geometry; zero lesion label for constructed glare."""
    rng=np.random.default_rng(seed);h,w=base.shape[:2];side=int(rng.integers(220,351));xx=int(rng.integers(0,w-side+1));yy=int(rng.integers(0,h-side+1))
    crop=cv2.resize(base[yy:yy+side,xx:xx+side],(64,64),interpolation=cv2.INTER_AREA).astype('float32')/255
    if rng.random()<.5:crop=np.flip(crop,axis=1).copy()
    small=bool(rng.random()<.35); radius=rng.uniform(3,5) if small else rng.uniform(7,16)
    cx,cy=rng.uniform(18,46,2);dx=X-cx;dy=Y-cy;theta=np.arctan2(dy,dx)
    boundary=radius*(1+.14*np.sin(3*theta+rng.uniform(0,6.28))+.10*np.sin(5*theta+rng.uniform(0,6.28)))
    # Soft continuous radial boundary, distinct from training polygon masks.
    dist=np.sqrt((dx*rng.uniform(.85,1.15))**2+(dy*rng.uniform(.85,1.15))**2)
    alpha=np.clip((boundary-dist)/rng.uniform(1.5,3.5)+.5,0,1).astype('float32')
    if kind=='glare':
        # Elliptical illumination artifact; exact absence of simulated lesion.
        crop+=alpha[...,None]*float(rng.uniform(.18,.38)); mask=np.zeros((64,64),'float32');small=False
    else:
        strength=float(rng.uniform(.035,.09) if kind=='weak' else rng.uniform(.12,.25))
        crop+=alpha[...,None]*strength*(1-crop);mask=(alpha>=.5).astype('float32')
    phase=rng.uniform(0,6.28);crop+=.018*np.sin(X*.08+Y*.05+phase)[...,None]
    return np.clip(crop,0,1).astype('float32'),mask,{'seed':seed,'negative':kind=='glare','small':small,'kind':kind}


def batch_rows(rows):
    x=torch.from_numpy(np.stack([a.transpose(2,0,1) for a,_,_ in rows]));y=torch.from_numpy(np.stack([b for _,b,_ in rows])[:,None]);return x,y,[m for _,_,m in rows]


def load_pixels(path):
    with Image.open(path) as im:return np.asarray(im.convert('RGB'))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',required=True);ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);ap.add_argument('--head-dir',required=True);a=ap.parse_args()
    start=time.time();torch.set_num_threads(4);img=Path(a.images);paths=[img/x for x in ('train-medium.png','val-light.png','test5-medium.png')];hashes=[r3.digest(p) for p in paths];assert len(set(hashes))==3
    origx,origy,origm=r3.load_data(paths[0],10000,128);train_base=load_pixels(paths[0]);val_base=load_pixels(paths[1]);test_base_full=load_pixels(paths[2]); hh,ww=test_base_full.shape[:2]; test_base=test_base_full[int(hh*.25):int(hh*.75),int(ww*.10):int(ww*.90)]
    # 21 medium, 21 weak, 22 glare; fixed, equal total sample count to control.
    extra=[]
    for j,(kind,n) in enumerate((('standard',21),('weak',21),('glare',22))):extra += [r4.make_case(train_base,900000+j*1000+i,kind) for i in range(n)]
    ex,ey,em=batch_rows(extra)
    vx,vy,vm=r3.load_data(paths[1],200000,64);val_extra=[]
    for j,kind in enumerate(('standard','weak','glare')):val_extra += [r4.make_case(val_base,910000+j*1000+i,kind) for i in range(32)]
    v2x,v2y,v2m=batch_rows(val_extra);vx=torch.cat([vx,v2x]);vy=torch.cat([vy,v2y]);vm+=v2m
    tests={}
    for j,kind in enumerate(('standard','weak','glare')):tests[kind]=batch_rows([independent_case(test_base,920000+j*1000+i,kind) for i in range(32)])
    for kind,(tx,ty,tm) in tests.items():assert all(bool(ty[i].any()) != m['negative'] for i,m in enumerate(tm))
    allx=torch.cat([origx,ex,vx]+[item[0] for item in tests.values()]);sizes=[len(origx),len(ex),len(vx)]+[len(item[0]) for item in tests.values()];offs=np.cumsum([0]+sizes)
    enc=r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights));features=r3.encode(enc,allx);del enc
    sl=lambda i:features[offs[i]:offs[i+1]]
    result={'protocol':'round5-protocol.md','data_provenance':'generated skin, procedural masks, no real patient images or manual lesion annotations','hashes':hashes,'sam_sha256':r3.digest(a.sam_weights),'groups':{},'limitations':['one held-out generated test base','binary segmentation assumes all skin','SAM nonstandard input','pretraining source unknown','synthetic highlights and lesions may be ambiguous']}
    out=Path(a.head_dir);out.mkdir(parents=True,exist_ok=True)
    for group in ('original','hard_examples'):
        tx=origx if group=='original' else torch.cat([origx[:64],ex]);ty=origy if group=='original' else torch.cat([origy[:64],ey]);tf=sl(0) if group=='original' else torch.cat([sl(0)[:64],sl(1)])
        result['groups'][group]=[]
        for seed in (0,1):
            net=r3.train(tx,ty,tf,seed);vp=r3.predict(net,vx,sl(2));threshold,feasible=r3.round2.threshold(vp,vy,vm)
            entry={'seed':seed,'threshold':round(threshold,3),'validation_constraint_met':feasible,'validation':r3.pilot.evaluate(vp,vy,vm,threshold),'test':{}}
            for j,(kind,(xx,yy,mm)) in enumerate(tests.items()):entry['test'][kind]=r4.score(r3.predict(net,xx,sl(j+3)),yy,mm,threshold)
            path=out/f'{group}_seed{seed}.pt';torch.save({'model_state_dict':net.state_dict(),'seed':seed,'threshold':threshold,'sam_sha256':result['sam_sha256']},path)
            entry['checkpoint_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();result['groups'][group].append(entry)
            print(group,seed,'trained threshold',threshold,'feasible',feasible,flush=True)
    result['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
