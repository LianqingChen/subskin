"""Synthetic-only frozen SAM experiment. Never imports patient images."""
import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pilot', HERE / 'experiment.py')
pilot = importlib.util.module_from_spec(spec); spec.loader.exec_module(pilot)
spec2 = importlib.util.spec_from_file_location('round2', HERE / 'round2.py')
round2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(round2)
Y, X = np.mgrid[:64,:64].astype(np.float32)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(base, seed):
    r=np.random.default_rng(seed)
    h,w=base.shape[:2]; side=int(r.integers(220,351)); y=int(r.integers(0,h-side+1)); x=int(r.integers(0,w-side+1))
    crop=cv2.resize(base[y:y+side,x:x+side],(64,64),interpolation=cv2.INTER_AREA).astype(np.float32)/255
    if r.random()<.5: crop=np.flip(crop,axis=1).copy()
    negative=bool(r.random()<.30); small=False; alpha=np.zeros((64,64),np.float32)
    if not negative:
        small=bool(r.random()<.35); radius=r.uniform(3.0,5.0) if small else r.uniform(7.,18.)
        cx,cy=r.uniform(18,46,2); ang=np.linspace(0,2*np.pi,17,endpoint=False); radii=radius*r.uniform(.65,1.35,len(ang))
        pts=np.stack([cx+radii*np.cos(ang),cy+radii*np.sin(ang)],1).astype(np.int32)
        shape=np.zeros((64,64),np.uint8);cv2.fillPoly(shape,[pts],1)
        alpha=cv2.GaussianBlur(shape.astype(np.float32),(0,0),float(r.uniform(.6,1.5)))
        strength=float(r.uniform(.12,.35));crop=crop+alpha[...,None]*strength*(1-crop)
    # Bright/dark nuisance independent of mask, also on negative images.
    for _ in range(int(r.integers(1,4))):
        cx,cy=r.uniform(0,64,2); sx,sy=r.uniform(4,16,2)
        blob=np.exp(-((X-cx)**2/(2*sx*sx)+(Y-cy)**2/(2*sy*sy)))
        crop+=blob[...,None]*float(r.uniform(-.09,.11))
    return np.clip(crop,0,1).astype(np.float32),(alpha>=.5).astype(np.float32),{'seed':seed,'negative':negative,'small':small}


def load_data(path,start,count):
    with Image.open(path) as im: base=np.asarray(im.convert('RGB'))
    rows=[render(base,i) for i in range(start,start+count)]
    x=torch.from_numpy(np.stack([a.transpose(2,0,1) for a,_,_ in rows]))
    y=torch.from_numpy(np.stack([b for _,b,_ in rows])[:,None])
    return x,y,[m for _,_,m in rows]


def sam_encoder(package_dir,checkpoint):
    package=types.ModuleType('segment_anything');package.__path__=[str(package_dir)];sys.modules['segment_anything']=package
    build=importlib.import_module('segment_anything.build_sam');torch.manual_seed(123)
    full=build.build_sam_vit_b(checkpoint=str(checkpoint) if checkpoint else None).eval();enc=full.image_encoder
    pos=enc.pos_embed.detach().permute(0,3,1,2)
    enc.pos_embed=nn.Parameter(F.interpolate(pos,size=(16,16),mode='bicubic',align_corners=False).permute(0,2,3,1),requires_grad=False)
    return enc.eval()


def encode(enc,x):
    vals=[];mean=torch.tensor([123.675,116.28,103.53]).view(1,3,1,1);std=torch.tensor([58.395,57.12,57.375]).view(1,3,1,1)
    with torch.inference_mode():
        for i in range(len(x)):
            a=F.interpolate(x[i:i+1],size=(256,256),mode='bilinear',align_corners=False)*255
            vals.append(enc((a-mean)/std).cpu().clone())
            if i%64==0:print('encoded',i,'/',len(x),flush=True)
    return torch.cat(vals)


class Head(nn.Module):
    def __init__(self):
        super().__init__();self.f=nn.Sequential(nn.Conv2d(259,24,1),nn.ReLU(),nn.Conv2d(24,12,3,padding=1),nn.ReLU(),nn.Conv2d(12,1,1))
    def forward(self,x,features):
        f=F.interpolate(features,size=x.shape[-2:],mode='bilinear',align_corners=False)
        return self.f(torch.cat((x,f),1))


def train(x,y,features,seed):
    torch.manual_seed(seed);r=np.random.default_rng(seed);model=pilot.Net() if features is None else Head();opt=torch.optim.Adam(model.parameters(),lr=.002)
    for _ in range(15):
        for idx in r.permutation(len(x)).reshape(-1,16):
            pred=model(x[idx]) if features is None else model(x[idx],features[idx])
            loss=F.binary_cross_entropy_with_logits(pred,y[idx],pos_weight=torch.tensor(4.))
            opt.zero_grad();loss.backward();opt.step()
    return model.eval()


def predict(model,x,features):
    outputs=[]
    with torch.inference_mode():
        for i in range(0,len(x),16):
            a=x[i:i+16]; z=model(a) if features is None else model(a,features[i:i+16]);outputs.append(torch.sigmoid(z).numpy()[:,0])
    return np.concatenate(outputs)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',default=str(HERE/'generated'));ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);ap.add_argument('--preview',required=True);args=ap.parse_args()
    torch.set_num_threads(4);start=time.time()
    paths=[Path(args.images)/'train-medium.png',Path(args.images)/'val-light.png',Path(args.images)/'test-dark.png'];hashes=[digest(p) for p in paths];assert len(set(hashes))==3
    x,y,m=load_data(paths[0],10000,128);vx,vy,vm=load_data(paths[1],200000,64);tx,ty,tm=load_data(paths[2],500000,64)
    for labels,meta in [(y,m),(vy,vm),(ty,tm)]:
        assert sum(q['negative'] for q in meta)>=10 and sum(q['small'] for q in meta)>=8
        assert all(bool(labels[i].any()) != a['negative'] for i,a in enumerate(meta))
    tx2=round2.perturb(tx)
    canvas=Image.new('RGB',(768,384),'white');draw=ImageDraw.Draw(canvas)
    for i in range(8):
        a=(tx[i].numpy().transpose(1,2,0)*255).astype('uint8');xx=(i%4)*192;yy=(i//4)*192
        canvas.paste(Image.fromarray(a).resize((160,160)),(xx,yy));draw.text((xx,yy+161),f"{tm[i]['seed']} {'negative' if tm[i]['negative'] else 'positive'}",fill='black')
    canvas.save(args.preview)
    out={'experiment':'generated skin bases plus frozen SAM feature pilot','dataset':{'train':len(m),'validation':len(vm),'test':len(tm),'n_negative_test':sum(q['negative'] for q in tm),'n_small_test':sum(q['small'] for q in tm),'hashes':hashes},'weights_sha256':digest(args.sam_weights),'data_provenance':'three AI-generated synthetic skin bases, no real patient images or human masks','limitations':['single held-out synthetic base','binary segmentation, all pixels assumed skin','SAM pretraining data unknown','SAM nonstandard 256 input and interpolated positional embeddings','generated base exact pixel edits are not clinical ground truth'],'models':{}}
    for method in ('rgb_cnn','random_sam','pretrained_sam'):
        features=None
        if method!='rgb_cnn':
            enc=sam_encoder(Path(args.sam_package),Path(args.sam_weights) if method=='pretrained_sam' else None)
            t=time.time();features=encode(enc,torch.cat([x,vx,tx,tx2]));del enc
            print('encoder',method,'seconds',round(time.time()-t,1),flush=True)
        n1,n2,n3=len(x),len(vx),len(tx)
        ftrain=None if features is None else features[:n1];fval=None if features is None else features[n1:n1+n2];ftest=None if features is None else features[n1+n2:n1+n2+n3];fshift=None if features is None else features[n1+n2+n3:]
        out['models'][method]=[]
        for seed in (0,1):
            net=train(x,y,ftrain,seed);pv=predict(net,vx,fval);t,feasible=round2.threshold(pv,vy,vm)
            orig=predict(net,tx,ftest);shift=predict(net,tx2,fshift)
            out['models'][method].append({'seed':seed,'threshold':round(t,3),'validation_constraint_met':feasible,'validation':pilot.evaluate(pv,vy,vm,t),'test':round2.evaluate(orig,shift,ty,tm,t)})
            print('trained',method,seed,flush=True)
        del features
    out['elapsed_seconds']=round(time.time()-start,2);Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
