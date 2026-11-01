"""Run approved synthetic-only project trainer and evaluator without registry writes."""
import argparse,hashlib,json,sys,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--manifest',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();t=time.time();root=Path(a.project_root);sys.path.insert(0,str(root))
 from ml.rgb_segmentation.dataset import validate_manifest,load_item
 from ml.rgb_segmentation.train import train
 from ml.rgb_segmentation.evaluate import evaluate
 from web.backend.services.rgb_segmentation.inference import infer_rgb
 registry=root/'configs/rgb_segmentation_registry.json';before=registry.read_bytes();assert json.loads(before)['enabled'] is False
 man=Path(a.manifest);output=Path(a.output_dir)
 if output.exists() and any(output.iterdir()):raise ValueError('output directory must be empty')
 output.mkdir(parents=True,exist_ok=True)
 try:validate_manifest(man)
 except ValueError as e:
  if 'Synthetic dataset requires' not in str(e):raise
 else:raise RuntimeError('synthetic gate unexpectedly bypassed')
 document=validate_manifest(man,allow_synthetic=True);assert document['synthetic'] is True
 report=train(man,output/'run',epochs=15,side=128,allow_synthetic=True)
 assert report['training_source']=='synthetic' and report['enabled'] is False and report['automatic_measurement'] is False
 model=evaluate(man,output/'run'/'model.pt',output/'model-eval.json',allow_synthetic=True)
 baseline=evaluate(man,None,output/'baseline-eval.json',allow_synthetic=True)
 branches=[]
 for item in document['items']:
  if item['split']!='test':continue
  try:
   rgb,_=load_item(Path(document['root']),item);_,metadata=infer_rgb(rgb);branches.append({'id':item['id'],'source':metadata.get('source','unknown')})
  except Exception as e:branches.append({'id':item['id'],'source':'error','error_type':type(e).__name__})
 assert registry.read_bytes()==before
 import cv2,mediapipe,torch
 out={'manifest_sha256':document['manifest_sha256'],'counts':document['counts'],'subjects':document['subject_count'],'training_source':report['training_source'],'model_sha256':report['sha256'],'history':report['history'],'baseline_summary':baseline['summary'],'model_summary':model['summary'],'branch_counts':{key:sum(x['source']==key for x in branches) for key in sorted({x['source'] for x in branches})},'branches':branches,'registry_sha256':hashlib.sha256(before).hexdigest(),'registry_enabled':False,'versions':{'opencv':cv2.__version__,'mediapipe':mediapipe.__version__,'torch':torch.__version__},'elapsed_seconds':round(time.time()-t,2)}
 (output/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
