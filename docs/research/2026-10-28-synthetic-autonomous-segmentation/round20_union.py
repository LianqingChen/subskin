"""Post-hoc unreviewed runtime policy simulation on synthetic TorchScript."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.nn import functional as F

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--manifest',required=True);p.add_argument('--weights',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=Path(a.project_root);sys.path.insert(0,str(root));torch.set_num_threads(2)
 from ml.rgb_segmentation.dataset import validate_manifest,load_item
 from ml.rgb_segmentation.metrics import score_labels,aggregate
 from web.backend.services.rgb_segmentation.images import png_bytes,canonical_image,frame_information_lost,apply_soft_quality
 from web.backend.services.rgb_segmentation.policy import measure_rgb
 doc=validate_manifest(Path(a.manifest),allow_synthetic=True);assert doc['synthetic'] is True
 registry=root/'configs/rgb_segmentation_registry.json';reg=registry.read_bytes();assert json.loads(reg)['enabled'] is False
 weight=Path(a.weights);model=torch.jit.load(str(weight),map_location='cpu').eval();rows=[]
 for item in doc['items']:
  if item['split']!='test':continue
  row={'id':item['id'],'subject_id':item['subject_id'],'groups':item['groups']}
  try:
   rgb,truth=load_item(Path(doc['root']),item);encoded=png_bytes(rgb);image,_=canonical_image(encoded);assert np.array_equal(image,rgb)
   if frame_information_lost(image):row.update(outcome='frame_retake',metrics=None);rows.append(row);continue
   h,w=image.shape[:2];x=torch.from_numpy(image.copy()).permute(2,0,1).float()[None]/255;x=F.pad(x,(0,(-w)%16,0,(-h)%16))
   with torch.inference_mode():
    logits=model(x);prob=torch.softmax(F.interpolate(logits,size=x.shape[-2:],mode='bilinear',align_corners=False)[:,:,:h,:w],1)[0].cpu().numpy()
   label=prob.argmax(0);skin=np.isin(label,[1,2]);uncertain=(prob.max(0)<.7)&skin
   masks={'skin':skin,'lesion':(label==2)&~uncertain,'uncertain':uncertain,'excluded':np.isin(label,[3,4])}
   masks,quality=apply_soft_quality(image,masks);decision=measure_rgb(image,masks,encoded,reviewed=False,calibration=None)
   if decision['status']=='retake_required':row.update(outcome='policy_retake',metrics=None);rows.append(row);continue
   pred=np.zeros(truth.shape,np.uint8);pred[masks['skin']]=1;pred[(masks['lesion']|masks['uncertain'])&masks['skin']&~masks['excluded']]=2
   row.update(outcome='processed',policy_status=decision['status'],blocking_reasons=decision['blocking_reasons'],released_area=decision['measurement']['area_percentage'],uncertain_pct=float(100*masks['uncertain'].mean()),metrics=score_labels(pred,truth,image))
  except Exception as e:row.update(outcome='error',error_type=type(e).__name__,metrics=None)
  rows.append(row)
 assert registry.read_bytes()==reg
 results={'status':'post_hoc_uncertain_union_diagnostic_not_measurement','weights_sha256':hashlib.sha256(weight.read_bytes()).hexdigest(),'manifest_sha256':doc['manifest_sha256'],'outcomes':dict(Counter(x['outcome'] for x in rows)),'policy_statuses':dict(Counter(x.get('policy_status','not_processed') for x in rows)),'released_area_count':sum(x.get('released_area') is not None for x in rows),'uncertain_pct_mean':float(np.mean([x['uncertain_pct'] for x in rows if x['outcome']=='processed'])) if any(x['outcome']=='processed' for x in rows) else None,'summary':aggregate(rows),'rows':rows,'limitations':['synthetic-only','test was already observed','candidate not registered','unreviewed policy, no actual measurement','local runtime differs from production']}
 Path(a.output).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in results.items() if k!='rows'},indent=2),flush=True)
if __name__=='__main__':main()
