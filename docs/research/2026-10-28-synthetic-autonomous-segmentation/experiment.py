"""Offline procedural pilot. No real photos, annotations or pretrained weights."""
import argparse, hashlib, importlib.util, json, time
from pathlib import Path
import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

N=64
Y,X=np.mgrid[:N,:N].astype(np.float32)
def field(rng, scale):
    a=rng.normal(size=(7,7)).astype('float32')
    return cv2.resize(a,(N,N),interpolation=cv2.INTER_CUBIC)*scale

def make(seed, mode):
    r=np.random.default_rng(seed)
    # Fully synthetic flat patches are deliberately not photographs.
    palette=np.array([[.30,.17,.13],[.45,.27,.20],[.60,.40,.31],[.76,.55,.45],[.88,.72,.63]],np.float32)
    index=int(r.integers(0,len(palette)-1)); mix=r.uniform(0,1)
    base=np.clip(palette[index]*(1-mix)+palette[index+1]*mix+r.normal(0,.012,3),0,1).astype('float32')
    texture=field(r,.022) if mode!='simple' else field(r,.008)
    illum=field(r,.045) if mode!='simple' else field(r,.01)
    img=np.clip(base[None,None,:]*(1+illum[...,None])+texture[...,None],0,1)
    negative=r.random()<.30
    small=False
    m=np.zeros((N,N),bool)
    if not negative:
        small=r.random()<.35
        radius=r.uniform(2.5,5) if small else r.uniform(7,19)
        cx,cy=r.uniform(17,47,2)
        if mode=='test':
            # Different shape family: union of multiple rotated ellipses.
            mask=np.zeros((N,N),np.uint8)
            for _ in range(int(r.integers(2,5))):
                dx,dy=r.normal(0,radius*.26,2)
                cv2.ellipse(mask,(int(cx+dx),int(cy+dy)),(max(2,int(radius*r.uniform(.5,1))),max(2,int(radius*r.uniform(.35,.9)))),float(r.uniform(0,180)),0,360,1,-1)
            m=mask.astype(bool)
        else:
            theta=np.arctan2(Y-cy,X-cx); dist=np.hypot(X-cx,Y-cy)
            boundary=radius*(1+(0 if mode=='simple' else .18)*np.sin(3*theta+r.uniform(0,6.28)))
            m=dist<boundary
        strength=r.uniform(.10,.30)
        img=np.where(m[...,None],img+(1-img)*strength,img)
    # Distractors may appear with or without target. No synthetic image is a real clinical example.
    if mode!='simple':
        for _ in range(int(r.integers(1,4))):
            cx,cy=r.uniform(0,N,2); sx,sy=r.uniform(3,14,2)
            blob=np.exp(-((X-cx)**2/sx**2+(Y-cy)**2/sy**2))
            # highlights/shadows are not lesion labels
            img+=blob[...,None]*r.uniform(-.16,.17)
    img=np.clip(img,0,1).astype('float32')
    return img,m.astype('float32'), {'negative':negative,'small':small,'seed':seed}

def batch(start,count,mode):
    data=[make(i,mode) for i in range(start,start+count)]
    x=np.stack([a[0].transpose(2,0,1) for a in data]); y=np.stack([a[1] for a in data])[:,None]
    return torch.from_numpy(x),torch.from_numpy(y),[a[2] for a in data]

class Net(nn.Module):
    def __init__(self):
        super().__init__(); self.a=nn.Sequential(nn.Conv2d(3,12,3,padding=1),nn.ReLU(),nn.Conv2d(12,12,3,padding=1),nn.ReLU()); self.b=nn.Sequential(nn.Conv2d(12,24,3,padding=1),nn.ReLU(),nn.Conv2d(24,24,3,padding=1),nn.ReLU()); self.c=nn.Sequential(nn.Conv2d(36,12,3,padding=1),nn.ReLU(),nn.Conv2d(12,1,1))
    def forward(self,x):
        a=self.a(x); b=self.b(F.avg_pool2d(a,4)); return self.c(torch.cat([a,F.interpolate(b,size=a.shape[-2:],mode='bilinear',align_corners=False)],1))

def fit(mode,augmented,consistency,seed,epochs,count):
    torch.manual_seed(seed); rng=np.random.default_rng(seed); net=Net(); opt=torch.optim.Adam(net.parameters(),lr=.002)
    x,y,_=batch(10000,count,mode)
    for ep in range(epochs):
        for ids in rng.permutation(count).reshape(-1,16):
            a=x[ids]; target=y[ids]; out=net(a)
            loss=F.binary_cross_entropy_with_logits(out,target,pos_weight=torch.tensor(4.))
            if augmented:
                gain=torch.from_numpy(rng.uniform(.8,1.2,(len(ids),3,1,1)).astype('float32'))
                bias=torch.from_numpy(rng.uniform(-.04,.04,(len(ids),3,1,1)).astype('float32'))
                out2=net((a*gain+bias).clamp(0,1))
                loss=(loss+F.binary_cross_entropy_with_logits(out2,target,pos_weight=torch.tensor(4.)))/2
                if consistency:
                    loss=loss+0.5*F.mse_loss(torch.sigmoid(out),torch.sigmoid(out2))
            opt.zero_grad();loss.backward();opt.step()
    return net

def prob(net,x):
    net.eval(); arr=[]
    with torch.no_grad():
        for a in x.split(16): arr.append(torch.sigmoid(net(a)).numpy()[:,0])
    return np.concatenate(arr)

def evaluate(p,y,meta,t):
    y=y.numpy()[:,0].astype(bool); p=p>=t
    values=[]; neg=[]; small=[]; err=[]
    for pred,truth,info in zip(p,y,meta):
        err.append(abs(pred.mean()-truth.mean())*100)
        if info['negative']:neg.append(pred.mean()*100)
        else:
            d=2*np.logical_and(pred,truth).sum()/(pred.sum()+truth.sum()+1e-9);values.append(float(d))
            if info['small']:small.append(float(d))
    return {'positive_dice':float(np.mean(values)), 'small_dice':float(np.mean(small)), 'area_mae_percentage_points':float(np.mean(err)), 'negative_false_positive_area_pct':float(np.mean(neg)), 'n_positive':len(values),'n_negative':len(neg),'n_small':len(small)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--rule',required=True);ap.add_argument('--epochs',type=int,default=5);ap.add_argument('--train',type=int,default=512);ap.add_argument('--test',type=int,default=128);ap.add_argument('--seeds',type=int,default=2);args=ap.parse_args()
    assert args.train%16==0
    torch.set_num_threads(2); start=time.time()
    vx,vy,vm=batch(200000,128,'mixed'); tx,ty,tm=batch(300000,args.test,'test')
    result={'experiment':'procedural synthetic pilot','training_count':args.train,'validation_count':128,'test_count':args.test,'epochs':args.epochs,'seed_count':args.seeds,'data_provenance':'procedurally generated; no photographs; no pretrained weights','limitations':['oracle full-image skin mask','synthetic testing only','no pretrained large model','different test shape family but shared rendering assumptions'],'rules_sha256':hashlib.sha256(Path(args.rule).read_bytes()).hexdigest(),'models':{}}
    spec=importlib.util.spec_from_file_location('draft',args.rule); rule=importlib.util.module_from_spec(spec);spec.loader.exec_module(rule)
    pred=[]
    for image in tx.numpy():
        rgb=(image.transpose(1,2,0)*255).astype(np.uint8); skin=np.ones((N,N),bool)
        pred.append(rule.draft_lesion(rgb,skin,np.zeros_like(skin))['lesion'].astype('float32'))
    result['models']['production_lesion_draft_oracle_skin']={'threshold':.5,'test':evaluate(np.stack(pred),ty,tm,.5)}
    for mode,aug,cons,name in [('simple',False,False,'simple'),('mixed',False,False,'diverse'),('mixed',True,False,'diverse_augmented'),('mixed',True,True,'diverse_consistency')]:
        rows=[]
        for seed in range(args.seeds):
            net=fit(mode,aug,cons,seed,args.epochs,args.train); pv=prob(net,vx)
            # Max positive Dice on validation only; preselected criterion.
            grid=np.arange(.1,.91,.05); threshold=float(max(grid,key=lambda t:evaluate(pv,vy,vm,t)['positive_dice']))
            rows.append({'seed':seed,'threshold':round(threshold,3),'test':evaluate(prob(net,tx),ty,tm,threshold)})
        result['models'][name]=rows
    result['elapsed_seconds']=round(time.time()-start,2)
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__': main()
