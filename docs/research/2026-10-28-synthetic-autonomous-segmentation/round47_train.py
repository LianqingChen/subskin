"""Synthetic paired-batch consistency ablation; not a production trainer."""
import argparse,hashlib,json,random,subprocess,sys
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F


def consistency(logits, images, targets):
    """Penalize different lesion probabilities only on identical normal skin."""
    same_pixel = (images[0] == images[1]).all(dim=0)
    mask = (targets[0] == 1) & (targets[1] == 1) & same_pixel
    probabilities = torch.softmax(logits,dim=1)[:,2]
    if not bool(mask.any()): return logits.sum()*0
    return (probabilities[0][mask] - probabilities[1][mask]).square().mean()


def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--seed',type=int,choices=(19,43),required=True);p.add_argument('--mode',choices=('baseline','consistency'),required=True);a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest
    from ml.rgb_segmentation.train import ReviewedDataset,loss
    from ml.rgb_segmentation.network import RGBUNet
    from ml.rgb_segmentation.evaluate import evaluate
    from round47_validation import validation_stats,passes_validation
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':384,'validation':320,'test':64}
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output directory')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    train=ReviewedDataset(doc,'train',128);train.augment=False;pairmap={}
    for i,it in enumerate(train.items):pairmap.setdefault(it['pair_id'],{})[it['pair_kind']]=i
    assert len(pairmap)==192 and all(set(p)=={'positive','negative'} for p in pairmap.values())
    pairs=[(p['positive'],p['negative']) for _,p in sorted(pairmap.items())]
    val=torch.utils.data.DataLoader(ReviewedDataset(doc,'validation',128),batch_size=1,num_workers=0)
    torch.manual_seed(a.seed);np.random.seed(a.seed);random.seed(a.seed)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');model=RGBUNet().to(device);opt=torch.optim.AdamW(model.parameters(),lr=1e-3)
    best=float('inf');gatebest=float('inf');stale=0;history=[];gate_epoch=None
    for epoch in range(1,16):
        model.train();total=0.;con=0.;valid_pairs=0
        for i in torch.randperm(len(pairs)).tolist():
            indices=pairs[i];items=[train[k] for k in indices];images=torch.stack([v[0] for v in items]);targets=torch.stack([v[1] for v in items])
            if random.random()<.5:images=images.flip(-1);targets=targets.flip(-1)
            factor=random.uniform(.9,1.1);images=(images*factor).clamp(0,1)
            mask=(targets[0]==1)&(targets[1]==1)&(images[0]==images[1]).all(0);valid_pairs+=int(mask.any())
            images=images.to(device);targets=targets.to(device);opt.zero_grad();logits=model(images);c=consistency(logits,images,targets);objective=loss(logits,targets)+(0.5*c if a.mode=='consistency' else 0*c);objective.backward();opt.step();total+=float(objective.detach());con+=float(c.detach())
        model.eval();vl=0.;records=[]
        with torch.inference_mode():
            for image,target in val:
                logits=model(image.to(device));vl+=float(loss(logits,target.to(device)));records.append((logits.argmax(1).cpu(),target))
        vl/=len(val)
        if not np.isfinite(vl):raise ValueError('nonfinite validation loss')
        s=validation_stats(records);passes=passes_validation(s);history.append({'epoch':epoch,'train_loss':total/len(pairs),'mean_consistency':con/len(pairs),'pairs_with_valid_skin':valid_pairs,'validation_loss':vl,'validation':s,'gate_pass':passes})
        if vl<best:best=vl;stale=0;torch.jit.script(model.cpu()).save(str(a.output_dir/'baseline.pt'));model.to(device)
        else:stale+=1
        if passes and vl<gatebest:gatebest=vl;gate_epoch=epoch;torch.jit.script(model.cpu()).save(str(a.output_dir/'gated.pt'));model.to(device)
        print(a.mode,a.seed,'epoch',epoch,'pass',passes,flush=True)
        if stale>=5:break
    results={}
    for name in ('baseline','gated'):
        weights=a.output_dir/(name+'.pt')
        if not weights.exists():continue
        ev=evaluate(a.manifest,weights,a.output_dir/(name+'-eval.json'),allow_synthetic=True)
        subprocess.run([sys.executable,str(Path(__file__).with_name('round19_policy.py')),'--project-root',str(a.project_root),'--manifest',str(a.manifest),'--weights',str(weights),'--output',str(a.output_dir/(name+'-policy.json'))],check=True,stdout=subprocess.DEVNULL)
        pol=json.loads((a.output_dir/(name+'-policy.json')).read_text());results[name]={'raw':ev['summary'],'policy':pol['summary'],'outcomes':pol['outcomes'],'statuses':pol['policy_statuses'],'released_area_count':pol['released_area_count']}
    assert before==reg.read_bytes()
    summary={'mode':a.mode,'seed':a.seed,'manifest_sha256':doc['manifest_sha256'],'model_sha256':hashlib.sha256((a.output_dir/'baseline.pt').read_bytes()).hexdigest(),'history':history,'gated_epoch':gate_epoch,'status':'selected' if gate_epoch else 'no_eligible_checkpoint','results':results,'registry_sha256':hashlib.sha256(before).hexdigest(),'training_source':'synthetic','enabled':False,'automatic_measurement':False}
    (a.output_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('done',a.mode,a.seed,summary['status'],flush=True)
if __name__=='__main__':main()
