"""Offline synthetic validation-selected threshold study, no product change."""
import argparse,hashlib,json,sys,time
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.nn import functional as F

THRESHOLDS=[i/10 for i in range(1,10)]

def select_threshold(rows):
 feasible=[]
 for row in rows:
  s=row['summary']
  if s['processed']!=s['total'] or s['negative_count']==0 or s['positive_count']==0:continue
  if s['false_positive_image_rate'] is None or s['mean_positive_recall'] is None or s['mean_positive_dice'] is None:continue
  if s['false_positive_image_rate']<=.2 and s['mean_positive_recall']>=.3:feasible.append(row)
 return max(feasible,key=lambda r:(r['summary']['mean_positive_dice'],r['threshold']))['threshold'] if feasible else None

def metric(masks,truth):
 valid=truth!=255;gt=(truth==2)&valid;gt_skin=np.isin(truth,[1,2])&valid;skin=masks['skin']&~masks['excluded']&valid;pred=masks['lesion']&skin
 tp=int((pred&gt).sum());npos=int(gt.sum());npred=int(pred.sum());positive=npos>0
 dice=2*tp/(npred+npos) if positive else None;recall=tp/npos if positive else None
 pred_share=100*npred/int(skin.sum()) if skin.any() else None;gt_share=100*npos/int(gt_skin.sum()) if gt_skin.any() else None
 return {'positive':positive,'dice':dice,'recall':recall,'false_positive_image':bool(npred) if not positive else None,'area_error_pp':abs(pred_share-gt_share) if pred_share is not None and gt_share is not None else None,'empty_skin':not skin.any(),'uncertain_pct_valid':float(100*(masks['uncertain']&valid).sum()/max(1,valid.sum()))}

def summarize(rows):
 good=[x for x in rows if x['outcome']=='processed'];m=[x['metrics'] for x in good];pos=[x for x in m if x['positive']];neg=[x for x in m if not x['positive']];mean=lambda a:float(np.mean(a)) if a else None;area=[x['area_error_pp'] for x in m if x['area_error_pp'] is not None]
 return {'total':len(rows),'processed':len(good),'outcomes':dict(Counter(x['outcome'] for x in rows)),'policy_statuses':dict(Counter(x.get('policy_status','not_processed') for x in rows)),'positive_count':len(pos),'negative_count':len(neg),'mean_positive_dice':mean([x['dice'] for x in pos]),'mean_positive_recall':mean([x['recall'] for x in pos]),'false_positive_image_count':sum(x['false_positive_image'] for x in neg),'false_positive_image_rate':float(np.mean([x['false_positive_image'] for x in neg])) if neg else None,'area_error_pp_mean_nonempty':mean(area),'empty_skin_count':sum(x['empty_skin'] for x in m),'uncertain_pct_valid_mean':mean([x['uncertain_pct_valid'] for x in m]),'released_area_count':sum(x.get('released_area') is not None for x in good)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project-root',required=True);ap.add_argument('--datasets',required=True);ap.add_argument('--weights',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();start=time.time();root=Path(a.project_root);sys.path.insert(0,str(root));torch.set_num_threads(2)
 from ml.rgb_segmentation.dataset import validate_manifest,load_item
 from web.backend.services.rgb_segmentation.images import png_bytes,canonical_image,frame_information_lost,apply_soft_quality
 from web.backend.services.rgb_segmentation.policy import measure_rgb
 reg=root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert json.loads(before)['enabled'] is False
 out={'protocol':'round21-protocol.md','models':{},'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['synthetic labels only','validation used for checkpoint selection','7 correlated validation negatives','two generated test bases with correlated samples','selected threshold not deployed','no clinical reference']}
 for mode in ('control','negative'):
  manifest=Path(a.datasets)/mode/'manifest.json';doc=validate_manifest(manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':192,'validation':32,'test':32}
  weights=Path(a.weights)/(mode+'-model.pt');model=torch.jit.load(str(weights),map_location='cpu').eval();cache={}
  def load_split(split):
   items=[]
   for item in doc['items']:
    if item['split']!=split:continue
    try:
     rgb,truth=load_item(Path(doc['root']),item);png=png_bytes(rgb);image,_=canonical_image(png);assert np.array_equal(image,rgb)
     if frame_information_lost(image):items.append({'id':item['id'],'preoutcome':'frame_retake'});continue
     h,w=image.shape[:2];x=torch.from_numpy(image.copy()).permute(2,0,1).float()[None]/255;x=F.pad(x,(0,(-w)%16,0,(-h)%16))
     with torch.inference_mode():
      logits=model(x);prob=torch.softmax(F.interpolate(logits,size=x.shape[-2:],mode='bilinear',align_corners=False)[:,:,:h,:w],1)[0].cpu().numpy()
     assert prob.shape==(5,h,w) and np.isfinite(prob).all()
     items.append({'id':item['id'],'image':image,'truth':truth,'png':png,'prob':prob})
    except Exception as exc:items.append({'id':item['id'],'preoutcome':'error','error_type':type(exc).__name__})
   cache[split]=items
  load_split('validation')
  def run(split,threshold):
   rows=[]
   for item in cache[split]:
    if 'preoutcome' in item:rows.append({'id':item['id'],'outcome':item['preoutcome']});continue
    try:
     prob=item['prob'];lab=prob.argmax(0);skin=np.isin(lab,[1,2]);uncertain=(prob.max(0)<threshold)&skin;masks={'skin':skin,'lesion':(lab==2)&~uncertain,'uncertain':uncertain,'excluded':np.isin(lab,[3,4])}
     masks,_=apply_soft_quality(item['image'],masks);decision=measure_rgb(item['image'],masks,item['png'],reviewed=False,calibration=None)
     if decision['status']=='retake_required':rows.append({'id':item['id'],'outcome':'policy_retake'});continue
     rows.append({'id':item['id'],'outcome':'processed','policy_status':decision['status'],'released_area':decision['measurement']['area_percentage'],'metrics':metric(masks,item['truth'])})
    except Exception as exc:rows.append({'id':item['id'],'outcome':'error','error_type':type(exc).__name__})
   return {'threshold':round(float(threshold),2),'summary':summarize(rows),'rows':rows}
  calibration=[run('validation',t) for t in THRESHOLDS];chosen=select_threshold(calibration);load_split('test');test_fixed=run('test',.7);test_selected=run('test',chosen) if chosen is not None else None
  out['models'][mode]={'manifest_sha256':doc['manifest_sha256'],'weights_sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),'calibration':calibration,'chosen_threshold':chosen,'test_fixed_0_7':test_fixed,'test_selected':test_selected};print(mode,'selected',chosen,'done',flush=True)
 assert reg.read_bytes()==before;out['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'models':{k:{'chosen_threshold':v['chosen_threshold'],'test_fixed':v['test_fixed_0_7']['summary'],'test_selected':v['test_selected']['summary'] if v['test_selected'] else None} for k,v in out['models'].items()},'elapsed_seconds':out['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
