"""Synthetic generated-arm evaluation; no real patient photos or manual masks."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.nn import functional as F
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r7',HERE/'round7.py');r7=importlib.util.module_from_spec(sp);sp.loader.exec_module(r7)
r3=r7.r3


def source(path):
    with Image.open(path) as im:rgb=np.asarray(im.convert('RGB').resize((64,64),Image.Resampling.BOX))
    z=rgb.astype('int16');cyan=(z[:,:,0]<85)&(z[:,:,1]>120)&(z[:,:,2]>125)&(z[:,:,2]>z[:,:,0]*1.2)
    assert cyan[0,0] and cyan[0,-1] and cyan[-1,0] and cyan[-1,-1], 'source corners not cyan'
    n,components=cv2.connectedComponents(cyan.astype('uint8'),connectivity=8)
    ids=np.unique([components[0,0],components[0,-1],components[-1,0],components[-1,-1]])
    bg=np.isin(components,ids);skin=~bg
    assert .1<skin.mean()<.9, 'skin coverage outside allowed range'
    return rgb,skin


def make(rgb,skin,seed):
    rng=np.random.default_rng(seed);aff=cv2.getRotationMatrix2D((31.5,31.5),float(rng.uniform(-15,15)),float(rng.uniform(.85,1.05)))
    aff[:,2]+=rng.uniform(-3,3,2)
    face=cv2.warpAffine(rgb,aff,(64,64),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,180,250)).astype('float32')/255
    mask=cv2.warpAffine(skin.astype('uint8'),aff,(64,64),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT).astype(bool)
    edge=cv2.morphologyEx(mask.astype('uint8'),cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8)).astype(bool)
    noise=cv2.resize(rng.normal(0,.025,(8,8)).astype('float32'),(64,64),interpolation=cv2.INTER_CUBIC);base=rng.uniform(.10,.82,3).astype('float32')
    bg=np.clip(base+noise[...,None],0,1);img=np.where(mask[...,None],face,bg);label=np.zeros((64,64),np.uint8);label[mask]=1;label[edge]=255
    if rng.random()>.3:
        eligible=np.argwhere(mask&~edge)
        if len(eligible):
            cy,cx=eligible[int(rng.integers(len(eligible)))];rad=float(rng.uniform(3,10));angles=np.linspace(0,2*np.pi,17,endpoint=False);radii=rad*rng.uniform(.65,1.35,len(angles))
            pts=np.stack([cx+radii*np.cos(angles),cy+radii*np.sin(angles)],1).astype('int32');blob=np.zeros((64,64),np.uint8);cv2.fillPoly(blob,[pts],1)
            alpha=cv2.GaussianBlur(blob.astype('float32'),(0,0),float(rng.uniform(.7,1.5)))*mask
            strength=float(rng.uniform(.12,.35));img+=alpha[...,None]*strength*(1-img)
            label[(alpha>=.8)&mask&~edge]=2;label[(alpha>.2)&(alpha<.8)&mask&~edge]=255
    if rng.random()<.65:
        x=int(rng.integers(5,45));y=int(rng.integers(5,45));w=int(rng.integers(7,17));h=int(rng.integers(7,17));occ=np.zeros((64,64),np.uint8)
        cv2.rectangle(occ,(x,y),(min(63,x+w),min(63,y+h)),1,-1);occ=occ.astype(bool);img[occ]=rng.uniform(.02,.32,3);label[occ]=3
    if rng.random()<.65:
        q=np.zeros((64,64),np.uint8);cv2.ellipse(q,(int(rng.integers(12,52)),int(rng.integers(12,52))),(int(rng.integers(4,10)),int(rng.integers(4,10))),float(rng.uniform(0,180)),0,360,1,-1)
        q=q.astype(bool)&mask&(label!=3)&(label!=255);img[q]=rng.uniform(.94,1.0);label[q]=4
    return np.clip(img,0,1).astype('float32'),label


def dataset(path,start,count):
    rgb,skin=source(path);rows=[make(rgb,skin,s) for s in range(start,start+count)]
    return torch.from_numpy(np.stack([a.transpose(2,0,1) for a,_ in rows])),torch.from_numpy(np.stack([b for _,b in rows]).astype('int64'))


def train(x,y,features,seed):
    torch.manual_seed(seed);rng=np.random.default_rng(seed);model=r7.network.RGBUNet(base=8) if features is None else r7.SamHead();opt=torch.optim.Adam(model.parameters(),lr=.002);weights=torch.tensor([1.,1.,5.,2.,2.])
    for ep in range(15):
        for idx in rng.permutation(len(x)).reshape(-1,16):
            logits=model(x[idx]) if features is None else model(x[idx],features[idx]);loss=F.cross_entropy(logits,y[idx],weight=weights,ignore_index=255)
            opt.zero_grad();loss.backward();opt.step()
    return model.eval()


def metrics(pred,truth):
    y=truth.numpy();valid=y!=255;skin=np.isin(y,[1,2])&valid;pskin=np.isin(pred,[1,2])&valid;lesion=(y==2)&valid;plesion=(pred==2)&valid
    dice=lambda a,b:float(2*(a&b).sum()/(a.sum()+b.sum()+1e-9))
    sd=[dice(a,b) for a,b in zip(pskin,skin)];ld=[dice(a,b) for a,b in zip(plesion,lesion) if b.any()]
    err=[];empty=0;neg=[]
    for i in range(len(y)):
        p=int(pskin[i].sum());t=int(skin[i].sum());empty+=int(p==0);err.append(abs((float(plesion[i].sum())/p if p else 0)-(float(lesion[i].sum())/t if t else 0))*100)
        if not lesion[i].any():neg.append(float(plesion[i].sum()/max(1,valid[i].sum())*100))
    classes={}
    for k,name in ((3,'occlusion'),(4,'unreadable')):
        a=(pred==k)&valid;b=(y==k)&valid;u=(a|b).sum();classes[name]=float((a&b).sum()/u) if u else None
    return {'ignored_pixel_pct':float((~valid).mean()*100),'pixel_accuracy_valid':float((pred[valid]==y[valid]).mean()),'skin_dice_mean':float(np.mean(sd)),'lesion_dice_positive_mean':float(np.mean(ld)) if ld else None,'area_share_mae_pp':float(np.mean(err)),'empty_skin':empty,'positive_images':len(ld),'negative_images':len(neg),'negative_fp_area_pct_valid':float(np.mean(neg)) if neg else None,'class_iou':classes}


def main():
    p=argparse.ArgumentParser();p.add_argument('--images',required=True);p.add_argument('--sam-package',required=True);p.add_argument('--sam-weights',required=True);p.add_argument('--old-heads',required=True);p.add_argument('--output',required=True);p.add_argument('--preview',required=True);p.add_argument('--head-dir',required=True);a=p.parse_args();start=time.time();torch.set_num_threads(4)
    paths=[Path(a.images)/x for x in ('train8-arm.png','test8b-arm.png')];hashes=[r3.digest(x) for x in paths];assert len(set(hashes))==2
    for pth in paths:source(pth)
    tx,ty=dataset(paths[0],950000,128);xx,yy=dataset(paths[1],960000,64)
    for name,labels in [('train',ty),('test',yy)]:
        vals=labels.numpy();count=[int((vals==i).sum()) for i in range(5)];pos=(labels==2).flatten(1).any(1);ignore=float((vals==255).mean())
        assert all(v>0 for v in count) and pos.any() and (~pos).any() and ignore<.20 and all(np.isin(l,[1,2]).any() for l in vals)
        print(name,'counts',count,'ignored',round(ignore,4),'positive',int(pos.sum()),flush=True)
    preview=Image.new('RGB',(768,384),'white');d=ImageDraw.Draw(preview)
    for i in range(8):
        z=(xx[i].numpy().transpose(1,2,0)*255).astype('uint8');x=(i%4)*192;y=(i//4)*192;preview.paste(Image.fromarray(z).resize((160,160)),(x,y));d.text((x,y+161),f'test {960000+i}',fill='black')
    preview.save(a.preview)
    feat=r3.encode(r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights)),torch.cat([tx,xx]));ft,fe=feat[:128],feat[128:]
    result={'protocol':'round8-protocol.md','source_sha256':hashes,'sam_sha256':r3.digest(a.sam_weights),'source_skin_fraction':[float(source(p)[1].mean()) for p in paths],'models':{},'limitations':['automatic chroma masks and ignored boundaries','one AI-generated arm per partition','synthetic lesions and geometry','old/new train sources and labels differ','nonstandard SAM input','pretraining provenance unknown'],'elapsed_seconds':0}
    hd=Path(a.head_dir);hd.mkdir(parents=True,exist_ok=True)
    for arch in ('rgb_unet','pretrained_sam'):
        result['models'][arch]=[]
        for seed in (0,1):
            cls=r7.network.RGBUNet(base=8) if arch=='rgb_unet' else r7.SamHead()
            old=Path(a.old_heads)/f'{arch}_seed{seed}.pt';ck=torch.load(old,map_location='cpu',weights_only=True);assert ck['model']==arch and ck['seed']==seed;cls.load_state_dict(ck['state_dict']);cls.eval()
            testfeat=None if arch=='rgb_unet' else fe;oldpred=r7.predict(cls,xx,testfeat)
            net=train(tx,ty,None if arch=='rgb_unet' else ft,seed);newpred=r7.predict(net,xx,testfeat)
            target=hd/f'{arch}_seed{seed}.pt';torch.save({'state_dict':net.state_dict(),'seed':seed,'model':arch},target)
            result['models'][arch].append({'seed':seed,'old':metrics(oldpred,yy),'new':metrics(newpred,yy),'old_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
            print(arch,seed,'finished',flush=True)
    result['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
