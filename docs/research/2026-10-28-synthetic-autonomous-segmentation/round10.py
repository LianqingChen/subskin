"""Controlled loss ablation for generated scenes, not real medical data."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.nn import functional as F
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(sp);sp.loader.exec_module(r9)
r8=r9.r8;r7=r9.r7;r3=r9.r3;diag=r9.diag


def lesion_dice_loss(logits,truth):
    valid=truth!=255;target=(truth==2)&valid;p=torch.softmax(logits,dim=1)[:,2]*valid
    s=target.flatten(1).sum(1);is_pos=s>0
    if not is_pos.any():return p.sum()*0
    intersection=(p*target).flatten(1).sum(1);denom=p.flatten(1).sum(1)+s
    return (1-(2*intersection[is_pos]+1)/(denom[is_pos]+1)).mean()


def train(x,y,feat,seed):
    torch.manual_seed(seed);rng=np.random.default_rng(seed);model=r7.SamHead();opt=torch.optim.Adam(model.parameters(),lr=.002);weight=torch.tensor([1.,1.,5.,2.,2.])
    for ep in range(15):
        for idx in rng.permutation(len(x)).reshape(-1,16):
            logits=model(x[idx],feat[idx]);loss=F.cross_entropy(logits,y[idx],weight=weight,ignore_index=255)+.5*lesion_dice_loss(logits,y[idx])
            opt.zero_grad();loss.backward();opt.step()
    return model.eval()


def boundary_score(pred,truth):
    values=[];kernel=np.ones((3,3),np.uint8);tolerance=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))
    for pr,y in zip(pred,truth.numpy()):
        valid=(y!=255).astype('uint8');inner=cv2.erode(valid,kernel).astype(bool)
        gt=(y==2).astype('uint8');pm=(pr==2).astype('uint8')*valid
        gb=(gt.astype(bool)&~cv2.erode(gt,kernel).astype(bool))&inner
        pb=(pm.astype(bool)&~cv2.erode(pm,kernel).astype(bool))&inner
        if not gb.any():continue
        if not pb.any():values.append(0.);continue
        gd=cv2.dilate(gb.astype('uint8'),tolerance).astype(bool);pd=cv2.dilate(pb.astype('uint8'),tolerance).astype(bool)
        precision=float((pb&gd).sum()/pb.sum());recall=float((gb&pd).sum()/gb.sum());values.append(2*precision*recall/(precision+recall+1e-12))
    return {'f1_mean':float(np.mean(values)) if values else None,'n_evaluable':len(values),'tolerance_pixels':2}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',required=True);ap.add_argument('--old-heads',required=True);ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);ap.add_argument('--head-dir',required=True);ap.add_argument('--preview',required=True);a=ap.parse_args();start=time.time();torch.set_num_threads(4)
    im=Path(a.images);paths=[im/x for x in ('train8-arm.png','train9-hand.png','test10-arm.png','test10-hand.png')];hashes=[r3.digest(x) for x in paths];assert len(set(hashes))==4
    for p in (paths[0],paths[2]):r8.source(p)
    for p in (paths[1],paths[3]):r9.hand_source(p)
    ax,ay=r8.dataset(paths[0],950000,64);hx,hy=r9.hand_dataset(paths[1],970000,64);x=torch.cat([ax,hx]);y=torch.cat([ay,hy])
    ux,uy=r8.dataset(paths[2],990000,64);vx,vy=r9.hand_dataset(paths[3],1000000,64)
    stats={n:r9.check(z,n) for n,z in [('training',y),('test_arm',uy),('test_hand',vy)]}
    picture=Image.new('RGB',(768,384),'white');d=ImageDraw.Draw(picture)
    for k,xx in enumerate((ux,vx)):
        for i in range(4):
            z=(xx[i].numpy().transpose(1,2,0)*255).astype('uint8');px=i*192;py=k*192;picture.paste(Image.fromarray(z).resize((160,160)),(px,py));d.text((px,py+161),('arm ' if k==0 else 'hand ')+str(i),fill='black')
    picture.save(a.preview)
    enc=r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights));feat=r3.encode(enc,torch.cat([x,ux,vx]));del enc;ft,fu,fv=feat[:128],feat[128:192],feat[192:]
    prev=json.loads((HERE/'round9-results.json').read_text());out={'protocol':'round10-protocol.md','source_sha256':hashes,'sam_sha256':r3.digest(a.sam_weights),'data_summary':stats,'models':[],'limitations':['one generated test base per body site','approximate cyan segmentation','same artificial lesion generator across partitions','SAM nonstandard input and pretraining source unknown','ignored pixels excluded'],'elapsed_seconds':0}
    save=Path(a.head_dir);save.mkdir(parents=True,exist_ok=True)
    for seed in (0,1):
        path=Path(a.old_heads)/f'arm_and_hand_seed{seed}.pt';sha=hashlib.sha256(path.read_bytes()).hexdigest();ref=next(row for row in prev['models'] if row['seed']==seed);assert sha==ref['new_head_sha256']
        ck=torch.load(path,map_location='cpu',weights_only=True);old=r7.SamHead();old.load_state_dict(ck['state_dict']);old.eval();new=train(x,y,ft,seed);row={'seed':seed,'old_head_sha256':sha}
        for mode,model in [('cross_entropy',old),('ce_plus_dice',new)]:
            row[mode]={}
            for name,xx,yy,ff in [('test_arm',ux,uy,fu),('test_hand',vx,vy,fv)]:
                pred=r7.predict(model,xx,ff);v=r8.metrics(pred,yy);v['diagnostic']=diag.diagnose(pred,yy);v['boundary']=boundary_score(pred,yy);row[mode][name]=v
        dest=save/f'ce_dice_seed{seed}.pt';torch.save({'state_dict':new.state_dict(),'seed':seed,'model':'pretrained_sam','loss':'weighted_ce_plus_0.5_positive_soft_dice'},dest);row['new_head_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest();out['models'].append(row);print('seed',seed,'finished',flush=True)
    out['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
