"""Replay two synthetic training runs and gate checkpoints on validation only."""
import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F


def weighted_training_loss(logits, target, base_loss, lesion_weight=3.0):
    """Replace only CE with weighted CE; leave the project Dice term unchanged."""
    weights = logits.new_tensor([1., 1., lesion_weight, 1., 1.])
    return base_loss(logits, target) - F.cross_entropy(logits, target, ignore_index=255) + F.cross_entropy(logits, target, weight=weights, ignore_index=255)


def validation_stats(pairs):
    """Mean image recall and fraction of negative images with any false lesion."""
    recalls, negatives = [], []
    for pred, target in pairs:
        valid = target != 255
        if not valid.any():
            raise ValueError('empty validation image')
        truth = (target == 2) & valid
        candidate = (pred == 2) & valid
        count = int(truth.sum())
        if count:
            recalls.append(int((truth & candidate).sum()) / count)
        else:
            negatives.append(bool(candidate.any()))
    if len(recalls) != 25 or len(negatives) != 7:
        raise ValueError(f'unexpected validation composition {len(recalls)}, {len(negatives)}')
    return {'positive': len(recalls), 'negative': len(negatives), 'recall': sum(recalls) / len(recalls), 'false_positives': sum(negatives)}


def main():
    p=argparse.ArgumentParser()
    for arg in ('project-root','manifest','other-manifest','output-dir'):
        p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--seed',type=int,choices=(19,43),required=True)
    a=p.parse_args(); sys.path.insert(0,str(a.project_root))
    from ml.rgb_segmentation.dataset import validate_manifest
    from ml.rgb_segmentation.train import ReviewedDataset, loss
    from ml.rgb_segmentation.network import RGBUNet
    from ml.rgb_segmentation.evaluate import evaluate
    doc=validate_manifest(a.manifest,allow_synthetic=True);other=validate_manifest(a.other_manifest,allow_synthetic=True)
    assert doc['synthetic'] and other['synthetic'] and doc['counts']=={'train':192,'validation':32,'test':32}
    used={x['source_sha256'] for x in doc['items'] if x['split'] in ('train','validation')}
    for d in (doc,other):
        assert used.isdisjoint({x['source_sha256'] for x in d['items'] if x['split']=='test'})
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()): raise ValueError('output directory must be empty')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(2);torch.manual_seed(a.seed);np.random.seed(a.seed);random.seed(a.seed)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');model=RGBUNet().to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-3)
    train=torch.utils.data.DataLoader(ReviewedDataset(doc,'train',128),batch_size=2,shuffle=True,num_workers=0)
    val=torch.utils.data.DataLoader(ReviewedDataset(doc,'validation',128),batch_size=1,num_workers=0)
    best=float('inf');gatebest=float('inf');stale=0;history=[];gate_epoch=None
    for epoch in range(1,16):
        model.train();train_loss=0.
        for image,target in train:
            optimizer.zero_grad();value=weighted_training_loss(model(image.to(device)),target.to(device),loss);value.backward();optimizer.step();train_loss+=float(value.detach())
        model.eval();val_loss=0.; pairs=[]
        with torch.inference_mode():
            for image,target in val:
                logits=model(image.to(device));val_loss+=float(loss(logits,target.to(device)));pairs.append((logits.argmax(1).cpu(),target))
        val_loss/=len(val)
        if not np.isfinite(val_loss):raise ValueError('nonfinite validation loss')
        stats=validation_stats(pairs);passes=stats['recall']>=.30 and stats['false_positives']<=2
        history.append({'epoch':epoch,'train_loss':train_loss/len(train),'validation_loss':val_loss,'validation':stats,'gate_pass':passes})
        if val_loss<best:
            best=val_loss;stale=0;torch.jit.script(model.cpu()).save(str(a.output_dir/'baseline.pt'));model.to(device)
        else:stale+=1
        if passes and val_loss<gatebest:
            gatebest=val_loss;gate_epoch=epoch;torch.jit.script(model.cpu()).save(str(a.output_dir/'gated.pt'));model.to(device)
        print('epoch',epoch,'pass',passes,flush=True)
        if stale>=5:break
    print('weighted training complete; evaluating',flush=True)
    outputs={}
    for model_name in ('baseline','gated'):
        weights=a.output_dir/(model_name+'.pt')
        if not weights.exists():continue
        for data_name,manifest in [('round24',a.manifest),('round21',a.other_manifest)]:
            prefix=f'{model_name}-{data_name}';ev=evaluate(manifest,weights,a.output_dir/(prefix+'-eval.json'),allow_synthetic=True)
            subprocess.run([sys.executable,str(Path(__file__).with_name('round19_policy.py')),'--project-root',str(a.project_root),'--manifest',str(manifest),'--weights',str(weights),'--output',str(a.output_dir/(prefix+'-policy.json'))],check=True,stdout=subprocess.DEVNULL)
            policy=json.loads((a.output_dir/(prefix+'-policy.json')).read_text())
            outputs[prefix]={'raw':ev['summary'],'policy':policy['summary'],'outcomes':policy['outcomes'],'statuses':policy['policy_statuses'],'released_area_count':policy['released_area_count']}
    assert reg.read_bytes()==before
    summary={'seed':a.seed,'manifest_sha256':doc['manifest_sha256'],'other_manifest_sha256':other['manifest_sha256'],'history':history,'training_loss':'project original Dice + weighted CE (lesion=3, others=1)', 'validation_loss':'project original unweighted CE + Dice', 'training_source':'synthetic', 'enabled':False, 'automatic_measurement':False,'gated_epoch':gate_epoch,'status':'selected' if gate_epoch else 'no_eligible_checkpoint','test_results':outputs,'registry_sha256':hashlib.sha256(before).hexdigest()}
    (a.output_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('done',summary['status'],flush=True)

if __name__=='__main__':main()
