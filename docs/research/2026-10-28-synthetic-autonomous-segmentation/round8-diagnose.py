"""Investigate whether low synthetic area error is due to empty predictions."""
import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r8',HERE/'round8.py');r8=importlib.util.module_from_spec(s);s.loader.exec_module(r8)

def diagnose(pred,target):
 y=target.numpy();valid=y!=255;gt=(y==2)&valid;pr=(pred==2)&valid;tp=(gt&pr).sum();fp=(pr&~gt).sum();fn=(gt&~pr).sum()
 positive=gt.reshape(len(gt),-1).any(1);empty=~pr.reshape(len(pr),-1).any(1)
 true_skin=np.isin(y,[1,2])&valid;pred_skin=np.isin(pred,[1,2])&valid
 gtshare=[float(gt[i].sum()/max(1,true_skin[i].sum())*100) for i in range(len(y)) if positive[i]]
 prshare=[float(pr[i].sum()/max(1,pred_skin[i].sum())*100) for i in range(len(y)) if positive[i]]
 return {'positive_count':int(positive.sum()),'positive_images_empty_count':int((positive&empty).sum()),'micro_recall':float(tp/(tp+fn)) if tp+fn else None,'micro_precision':float(tp/(tp+fp)) if tp+fp else None,'median_truth_share_positive_pct':float(np.median(gtshare)),'median_prediction_share_positive_pct':float(np.median(prshare)),'ignored_pixel_pct':float((~valid).mean()*100)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--sam-package',required=True);p.add_argument('--sam-weights',required=True);p.add_argument('--old-heads',required=True);p.add_argument('--new-heads',required=True);p.add_argument('--output',required=True);a=p.parse_args();torch.set_num_threads(4)
 xx,yy=r8.dataset(Path(a.image),960000,64);enc=r8.r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights));features=r8.r3.encode(enc,xx);out={}
 for arch in ('rgb_unet','pretrained_sam'):
  out[arch]=[]
  for seed in (0,1):
   row={'seed':seed}
   for name,directory in (('old',a.old_heads),('new',a.new_heads)):
    cls=r8.r7.network.RGBUNet(base=8) if arch=='rgb_unet' else r8.r7.SamHead();ck=torch.load(Path(directory)/f'{arch}_seed{seed}.pt',map_location='cpu',weights_only=True);cls.load_state_dict(ck['state_dict']);cls.eval()
    pred=r8.r7.predict(cls,xx,None if arch=='rgb_unet' else features);row[name]=diagnose(pred,yy)
   out[arch].append(row)
 Path(a.output).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
