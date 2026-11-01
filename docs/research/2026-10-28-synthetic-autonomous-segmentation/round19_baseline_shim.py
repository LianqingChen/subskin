"""Post-hoc offline compatibility diagnostic, never alters backend files."""
import argparse,hashlib,importlib.util,json,sys
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--manifest',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();root=Path(a.project_root);sys.path.insert(0,str(root))
 spec=importlib.util.spec_from_file_location('r18shim',HERE/'round18-shim.py');shim=importlib.util.module_from_spec(spec);spec.loader.exec_module(shim)
 from ml.rgb_segmentation.dataset import validate_manifest,load_item
 from ml.rgb_segmentation.evaluate import evaluate
 from web.backend.services.rgb_segmentation.inference import infer_rgb
 info=shim.install_local_shape_shim(root);registry=root/'configs/rgb_segmentation_registry.json';before=registry.read_bytes();assert json.loads(before)['enabled'] is False
 man=Path(a.manifest);doc=validate_manifest(man,allow_synthetic=True);output=Path(a.output_dir);evaluation=evaluate(man,None,output/'baseline-shim-eval.json',allow_synthetic=True)
 branches=[]
 for item in doc['items']:
  if item['split']!='test':continue
  try:
   rgb,_=load_item(Path(doc['root']),item);_,meta=infer_rgb(rgb);branches.append({'id':item['id'],'source':meta.get('source','unknown')})
  except Exception as e:branches.append({'id':item['id'],'source':'error','error_type':type(e).__name__})
 assert registry.read_bytes()==before
 summary={'status':'post_hoc_local_compatibility_diagnostic','shim':info,'manifest_sha256':doc['manifest_sha256'],'summary':evaluation['summary'],'branch_counts':dict(Counter(x['source'] for x in branches)),'branches':branches,'limitations':['runtime-only shim is not actual production code','test already observed','synthetic program labels only','local dependency version differs from remote','baseline evaluation excludes uncertain masks']}
 (output/'baseline-shim-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='branches'},indent=2),flush=True)
if __name__=='__main__':main()
