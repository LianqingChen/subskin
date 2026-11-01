"""Five-class synthetic evaluation. No patient photos or real lesion masks."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r3',HERE/'round3.py');r3=importlib.util.module_from_spec(spec);spec.loader.exec_module(r3)
spec2=importlib.util.spec_from_file_location('network',HERE/'rgb_unet_reference.py');network=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(network)
Y,X=np.mgrid[:64,:64].astype('float32')


def make(base,seed):
    rng=np.random.default_rng(seed)
    skin_img,lesion,_=r3.render(base,seed)
    # Background is a random-colored textured surface with no photographic source.
    bg=np.empty((64,64,3),dtype='float32');color=rng.uniform(.12,.83,3).astype('float32')
    noise=cv2.resize(rng.normal(0,.035,(8,8)).astype('float32'),(64,64),interpolation=cv2.INTER_CUBIC)
    bg[:]=np.clip(color+noise[...,None],0,1)
    skin=np.zeros((64,64),np.uint8);center=(int(rng.integers(27,38)),int(rng.integers(27,38)));axes=(int(rng.integers(19,28)),int(rng.integers(17,26)))
    cv2.ellipse(skin,center,axes,float(rng.uniform(0,180)),0,360,1,-1);skin=skin.astype(bool)
    img=np.where(skin[...,None],skin_img,bg);label=np.zeros((64,64),np.uint8);label[skin]=1;label[skin&(lesion>0)]=2
    if rng.random()<.70:
        # Opaque object can cross skin and background; exact program label.
        x=int(rng.integers(3,45));y=int(rng.integers(3,45));w=int(rng.integers(8,20));h=int(rng.integers(8,20))
        occ=np.zeros((64,64),np.uint8);cv2.rectangle(occ,(x,y),(min(63,x+w),min(63,y+h)),1,-1);occ=occ.astype(bool)
        shade=rng.uniform(.02,.32,3).astype('float32');img[occ]=shade;label[occ]=3
    if rng.random()<.70:
        # Saturated highlight represents insufficient information, only on skin not covered by occlusion.
        visible=skin&(label!=3);q=np.zeros((64,64),np.uint8)
        cv2.ellipse(q,(int(rng.integers(15,49)),int(rng.integers(15,49))),(int(rng.integers(5,12)),int(rng.integers(4,10))),float(rng.uniform(0,180)),0,360,1,-1)
        q=q.astype(bool)&visible;img[q]=rng.uniform(.94,1.0);label[q]=4
    return np.clip(img,0,1).astype('float32'),label


def load_data(path,start,count):
    with Image.open(path) as im:base=np.asarray(im.convert('RGB'))
    rows=[make(base,seed) for seed in range(start,start+count)]
    return torch.from_numpy(np.stack([a.transpose(2,0,1) for a,_ in rows])),torch.from_numpy(np.stack([b for _,b in rows]).astype('int64'))


class SamHead(nn.Module):
    def __init__(self):
        super().__init__();self.f=nn.Sequential(nn.Conv2d(259,24,1),nn.ReLU(),nn.Conv2d(24,12,3,padding=1),nn.ReLU(),nn.Conv2d(12,5,1))
    def forward(self,x,features):
        v=F.interpolate(features,size=x.shape[-2:],mode='bilinear',align_corners=False);return self.f(torch.cat([x,v],1))


def train(x,y,feat,seed):
    torch.manual_seed(seed);r=np.random.default_rng(seed);model=network.RGBUNet(base=8) if feat is None else SamHead();opt=torch.optim.Adam(model.parameters(),lr=.002);weight=torch.tensor([1.,1.,5.,2.,2.])
    for ep in range(15):
        for idx in r.permutation(len(x)).reshape(-1,16):
            logits=model(x[idx]) if feat is None else model(x[idx],feat[idx]);loss=F.cross_entropy(logits,y[idx],weight=weight)
            opt.zero_grad();loss.backward();opt.step()
    return model.eval()


def predict(model,x,feat):
    ans=[]
    with torch.inference_mode():
        for i in range(0,len(x),16):
            logits=model(x[i:i+16]) if feat is None else model(x[i:i+16],feat[i:i+16]);ans.append(logits.argmax(1).cpu().numpy())
    return np.concatenate(ans)


def metrics(pred,y):
    truth=y.numpy();cm=np.bincount((truth*5+pred).ravel(),minlength=25).reshape(5,5)
    ps=np.isin(pred,[1,2]);ts=np.isin(truth,[1,2]);pl=pred==2;tl=truth==2
    def dice(a,b):return float(2*np.logical_and(a,b).sum()/(a.sum()+b.sum()+1e-9))
    skin_d=[dice(a,b) for a,b in zip(ps,ts)];lesion_d=[dice(a,b) for a,b in zip(pl,tl) if b.any()]
    errors=[];empty=0;negfp=[]
    for i in range(len(pred)):
        pd=int(ps[i].sum());gt=int(ts[i].sum());empty+=int(pd==0)
        pp=float(pl[i].sum()/pd) if pd else 0.;gp=float(tl[i].sum()/gt) if gt else 0.
        errors.append(abs(pp-gp)*100)
        if not tl[i].any():negfp.append(float(pl[i].mean()*100))
    class_iou={}
    for k,name in [(3,'occlusion'),(4,'unreadable')]:
        inter=cm[k,k];union=cm[k,:].sum()+cm[:,k].sum()-inter;class_iou[name]=float(inter/union) if union else None
    return {'pixel_accuracy':float((pred==truth).mean()),'skin_dice_mean':float(np.mean(skin_d)),'lesion_dice_positive_mean':float(np.mean(lesion_d)) if lesion_d else None,'lesion_positive_images':len(lesion_d),'negative_lesion_fp_image_pct':float(np.mean(negfp)) if negfp else None,'negative_images':len(negfp),'area_share_mae_pp':float(np.mean(errors)),'predicted_empty_skin_images':empty,'class_iou':class_iou,'confusion_matrix':cm.tolist()}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',required=True);ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);ap.add_argument('--preview',required=True);ap.add_argument('--head-dir',required=True);a=ap.parse_args()
    start=time.time();torch.set_num_threads(4);paths=[Path(a.images)/z for z in ('train-medium.png','val-light.png','test7-medium.png')];hashes=[r3.digest(p) for p in paths];assert len(set(hashes))==3
    tx,ty=load_data(paths[0],750000,128);vx,vy=load_data(paths[1],800000,64);xx,yy=load_data(paths[2],850000,64)
    for name,target in [('train',ty),('validation',vy),('test',yy)]:
        counts=torch.bincount(target.flatten(),minlength=5);pos=(target==2).flatten(1).any(1);assert (counts>0).all() and pos.any() and (~pos).any();print(name,'pixel counts',counts.tolist(),'positive',int(pos.sum()),flush=True)
    img=Image.new('RGB',(768,384),'white');draw=ImageDraw.Draw(img)
    for i in range(8):
        z=(xx[i].numpy().transpose(1,2,0)*255).astype('uint8');x=(i%4)*192;y=(i//4)*192;img.paste(Image.fromarray(z).resize((160,160)),(x,y));draw.text((x,y+161),f'test {850000+i}',fill='black')
    img.save(a.preview)
    sam=r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights));feat=r3.encode(sam,torch.cat([tx,vx,xx]));del sam
    feat_train=feat[:128];feat_val=feat[128:192];feat_test=feat[192:]
    out={'protocol':'round7-protocol.md','image_sha256':hashes,'sam_weights_sha256':r3.digest(a.sam_weights),'rgb_unet_source_sha256':r3.digest(HERE/'rgb_unet_reference.py'),'sample_counts':{'train':128,'validation':64,'test':64},'class_names':['background','normal_skin','depigmented_skin','occlusion','unreadable'],'models':{},'limitations':['synthetic masks and geometry only','one base per split','artificial class definitions','nonstandard SAM input','pretraining data unknown','not clinical area'],'elapsed_seconds':0}
    head=Path(a.head_dir);head.mkdir(parents=True,exist_ok=True)
    for name,ft,fv,ftest in [('rgb_unet',None,None,None),('pretrained_sam',feat_train,feat_val,feat_test)]:
        out['models'][name]=[]
        for seed in (0,1):
            net=train(tx,ty,ft,seed);val=predict(net,vx,fv);test=predict(net,xx,ftest)
            ck=head/f'{name}_seed{seed}.pt';torch.save({'state_dict':net.state_dict(),'seed':seed,'model':name,'sam_weights_sha256':out['sam_weights_sha256'] if name=='pretrained_sam' else None},ck)
            out['models'][name].append({'seed':seed,'validation':metrics(val,vy),'test':metrics(test,yy),'head_sha256':hashlib.sha256(ck.read_bytes()).hexdigest()});print(name,seed,'finished',flush=True)
    out['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps(out,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
