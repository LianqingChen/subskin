"""Offline synthetic loss ablation using the project's trainer unchanged on disk."""
import argparse,hashlib,importlib,json,subprocess,sys,time
from pathlib import Path
import torch
from torch.nn import functional as F

def lesion_dice_extra(logits,target):
 valid=target!=255;truth=(target==2)&valid;prob=torch.softmax(logits,1)[:,2]*valid;pos=truth.flatten(1).sum(1);positive=pos>0
 if not positive.any():return prob.sum()*0
 inter=(prob*truth).flatten(1).sum(1);denom=prob.flatten(1).sum(1)+pos
 return (1-(2*inter[positive]+1)/(denom[positive]+1)).mean()

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--manifest',required=True);p.add_argument('--prior-manifest',required=True);p.add_argument('--prior-model',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();start=time.time();root=Path(a.project_root);sys.path.insert(0,str(root))
 from ml.rgb_segmentation.dataset import validate_manifest
 from ml.rgb_segmentation.evaluate import evaluate
 trainer=importlib.import_module('ml.rgb_segmentation.train');newdoc=validate_manifest(Path(a.manifest),allow_synthetic=True);olddoc=validate_manifest(Path(a.prior_manifest),allow_synthetic=True)
 assert newdoc['synthetic'] and olddoc['synthetic'] and newdoc['counts']=={'train':192,'validation':32,'test':32}
 identity=lambda d,split:[(x['id'],x['subject_id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==split]
 assert identity(newdoc,'train')==identity(olddoc,'train') and identity(newdoc,'validation')==identity(olddoc,'validation')
 old_sources={x['source_sha256'] for x in olddoc['items']};new_sources={x['source_sha256'] for x in newdoc['items'] if x['split']=='test'};assert old_sources.isdisjoint(new_sources)
 prior=Path(a.prior_model);oldhash=hashlib.sha256(prior.read_bytes()).hexdigest();assert oldhash=='10a4b6d992744669651749fe0b1227eb9e58f187f8ae443f093a0a016262e653'
 reg=root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert json.loads(before)['enabled'] is False
 output=Path(a.output_dir)
 if output.exists() and any(output.iterdir()):raise ValueError('output directory must be empty')
 output.mkdir(parents=True,exist_ok=True)
 base_loss=trainer.loss
 def research_loss(logits,target):return base_loss(logits,target)+.5*lesion_dice_extra(logits,target)
 trainer.loss=research_loss
 try:report=trainer.train(Path(a.manifest),output/'run',epochs=15,side=128,allow_synthetic=True)
 finally:trainer.loss=base_loss
 assert report['training_source']=='synthetic' and report['enabled'] is False and report['automatic_measurement'] is False
 print('trained; evaluating fixed holdout',flush=True)
 oldeval=evaluate(Path(a.manifest),prior,output/'control-eval.json',allow_synthetic=True)
 neweval=evaluate(Path(a.manifest),output/'run'/'model.pt',output/'candidate-eval.json',allow_synthetic=True)
 policy=Path(__file__).with_name('round19_policy.py')
 for name,weights in [('control',prior),('candidate',output/'run'/'model.pt')]:
  subprocess.run([sys.executable,str(policy),'--project-root',str(root),'--manifest',str(a.manifest),'--weights',str(weights),'--output',str(output/(name+'-policy.json'))],check=True,stdout=subprocess.DEVNULL)
 assert reg.read_bytes()==before
 summary={'protocol':'round22-protocol.md','manifest_sha256':newdoc['manifest_sha256'],'prior_manifest_sha256':olddoc['manifest_sha256'],'train_validation_byte_identical':True,'old_weights_sha256':oldhash,'new_weights_sha256':report['sha256'],'training_source':report['training_source'],'enabled':report['enabled'],'loss_override':'original CE + all-class Dice + 0.5 positive-only lesion soft Dice','epochs':len(report['history']),'control_raw':oldeval['summary'],'candidate_raw':neweval['summary'],'control_policy':json.loads((output/'control-policy.json').read_text())['summary'],'candidate_policy':json.loads((output/'candidate-policy.json').read_text())['summary'],'control_policy_statuses':json.loads((output/'control-policy.json').read_text())['policy_statuses'],'candidate_policy_statuses':json.loads((output/'candidate-policy.json').read_text())['policy_statuses'],'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['only two generated holdout bases','same synthetic editing mechanism across splits','validation checkpoint selection uses same validation set','single training seed','not real medical images','policy is offline emulation'],'elapsed_seconds':round(time.time()-start,2)}
 (output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
