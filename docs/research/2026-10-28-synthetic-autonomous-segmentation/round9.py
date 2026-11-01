"""Generated-hand cross-shape synthetic experiment, never reads real patients."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
import torch
from PIL import Image,ImageDraw
import cv2
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r8',HERE/'round8.py');r8=importlib.util.module_from_spec(sp);sp.loader.exec_module(r8)
sp2=importlib.util.spec_from_file_location('diag',HERE/'round8-diagnose.py');diag=importlib.util.module_from_spec(sp2);sp2.loader.exec_module(diag)
r3=r8.r3;r7=r8.r7

def hand_source(path):
    # Finger gaps can be disconnected from corner backgrounds; use all cyan pixels.
    with Image.open(path) as im:rgb=np.asarray(im.convert('RGB').resize((64,64),Image.Resampling.BOX))
    z=rgb.astype('int16');cyan=(z[:,:,0]<85)&(z[:,:,1]>120)&(z[:,:,2]>125)&(z[:,:,2]>z[:,:,0]*1.2)
    assert cyan[0,0] and cyan[0,-1] and cyan[-1,0] and cyan[-1,-1]
    skin=~cyan
    assert .1<skin.mean()<.9
    return rgb,skin

def hand_dataset(path,start,count):
    rgb,skin=hand_source(path);rows=[r8.make(rgb,skin,i) for i in range(start,start+count)]
    return torch.from_numpy(np.stack([a.transpose(2,0,1) for a,_ in rows])),torch.from_numpy(np.stack([b for _,b in rows]).astype('int64'))

def check(y,name):
    vals=y.numpy();counts=[int((vals==i).sum()) for i in range(5)];pos=(y==2).flatten(1).any(1);ignored=float((vals==255).mean())
    assert all(counts) and pos.any() and (~pos).any() and ignored<=.20 and all(np.isin(z,[1,2]).any() for z in vals), f'{name}: dataset gate failed {counts} ignored={ignored}'
    return {'counts':counts,'positive':int(pos.sum()),'negative':int((~pos).sum()),'ignored_pct':ignored*100}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',required=True);ap.add_argument('--old-heads',required=True);ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);ap.add_argument('--preview',required=True);ap.add_argument('--head-dir',required=True);a=ap.parse_args();start=time.time();torch.set_num_threads(4)
    im=Path(a.images);paths=[im/x for x in ('train8-arm.png','test8b-arm.png','train9-hand.png','test9-hand.png')];hashes=[r3.digest(x) for x in paths];assert len(set(hashes))==4
    for p in paths[:2]:r8.source(p)
    for p in paths[2:]:hand_source(p)
    ax,ay=r8.dataset(paths[0],950000,64);hx,hy=hand_dataset(paths[2],970000,64);dx,dy=r8.dataset(paths[1],960000,64);tx,ty=hand_dataset(paths[3],980000,64)
    x=torch.cat([ax,hx]);y=torch.cat([ay,hy]);summaries={k:check(v,k) for k,v in [('training',y),('development_arm',dy),('holdout_hand',ty)]}
    preview=Image.new('RGB',(768,384),'white');draw=ImageDraw.Draw(preview)
    for i in range(8):
        z=(tx[i].numpy().transpose(1,2,0)*255).astype('uint8');px=(i%4)*192;py=(i//4)*192
        preview.paste(Image.fromarray(z).resize((160,160)),(px,py));draw.text((px,py+161),f'hand {980000+i}',fill='black')
    preview.save(a.preview)
    encoder=r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights));f=r3.encode(encoder,torch.cat([x,dx,tx]));del encoder;ft,fd,fe=f[:128],f[128:192],f[192:]
    reference=json.loads((HERE/'round8-results.json').read_text());result={'protocol':'round9-protocol.md','sources':[p.name for p in paths],'hashes':hashes,'sam_sha256':r3.digest(a.sam_weights),'data_summary':summaries,'models':[],'limitations':['one new generated hand per partition','approximate chroma skin masks','binary lesion construction not clinical truth','same edit generator across split','SAM nonstandard input and unknown pretraining sources'],'elapsed_seconds':0}
    out=Path(a.head_dir);out.mkdir(parents=True,exist_ok=True)
    for seed in (0,1):
        oldpath=Path(a.old_heads)/f'pretrained_sam_seed{seed}.pt';sha=hashlib.sha256(oldpath.read_bytes()).hexdigest();prior=next(z for z in reference['models']['pretrained_sam'] if z['seed']==seed);assert sha==prior['new_sha256']
        ck=torch.load(oldpath,map_location='cpu',weights_only=True);old=r7.SamHead();old.load_state_dict(ck['state_dict']);old.eval()
        new=r8.train(x,y,ft,seed)
        row={'seed':seed,'old_head_sha256':sha}
        for label,net in [('arm_only',old),('arm_and_hand',new)]:
            row[label]={}
            for dataset,xx,yy,ff in [('development_arm',dx,dy,fd),('holdout_hand',tx,ty,fe)]:
                pred=r7.predict(net,xx,ff);row[label][dataset]=r8.metrics(pred,yy);row[label][dataset]['diagnostic']=diag.diagnose(pred,yy)
        path=out/f'arm_and_hand_seed{seed}.pt';torch.save({'state_dict':new.state_dict(),'seed':seed,'model':'pretrained_sam'},path);row['new_head_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();result['models'].append(row);print('seed',seed,'done',flush=True)
    result['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
