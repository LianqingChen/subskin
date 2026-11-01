"""Train one synthetic ablation with the unmodified project trainer."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--manifest',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();start=time.time();root=Path(a.project_root);sys.path.insert(0,str(root))
 from ml.rgb_segmentation.dataset import validate_manifest
 from ml.rgb_segmentation.train import train
 from ml.rgb_segmentation.evaluate import evaluate
 man=Path(a.manifest);doc=validate_manifest(man,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':192,'validation':32,'test':32}
 output=Path(a.output_dir)
 if output.exists() and any(output.iterdir()):raise ValueError('output must be empty')
 output.mkdir(parents=True,exist_ok=True);reg=root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert json.loads(before)['enabled'] is False
 print('training',man.parent.name,flush=True)
 report=train(man,output/'run',epochs=15,side=128,allow_synthetic=True);assert report['training_source']=='synthetic' and report['enabled'] is False and report['automatic_measurement'] is False
 print('evaluating',man.parent.name,flush=True)
 result=evaluate(man,output/'run'/'model.pt',output/'model-eval.json',allow_synthetic=True)
 policy_script=Path(__file__).with_name('round19_policy.py')
 subprocess.run([sys.executable,str(policy_script),'--project-root',str(root),'--manifest',str(man),'--weights',str(output/'run'/'model.pt'),'--output',str(output/'policy-eval.json')],check=True,stdout=subprocess.DEVNULL)
 assert reg.read_bytes()==before
 policy=json.loads((output/'policy-eval.json').read_text());summary={'manifest_sha256':doc['manifest_sha256'],'model_sha256':report['sha256'],'counts':doc['counts'],'training_source':report['training_source'],'enabled':report['enabled'],'epochs':len(report['history']),'raw_summary':result['summary'],'policy_summary':policy['summary'],'policy_outcomes':policy['outcomes'],'policy_statuses':policy['policy_statuses'],'released_area_count':policy['released_area_count'],'registry_sha256':hashlib.sha256(before).hexdigest(),'elapsed_seconds':round(time.time()-start,2)}
 (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
