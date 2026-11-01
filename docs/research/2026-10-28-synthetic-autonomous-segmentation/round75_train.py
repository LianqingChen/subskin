"""Continue a frozen research model on synthetic generator controls with replay."""
import argparse,hashlib,json,random,sys
from pathlib import Path
import numpy as np
from PIL import Image
import torch
import round68_train as oldloss


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def load_pair(root,item):
    arrays={}
    for role,meta in item['files'].items():
        path=root/meta['name']
        if sha(path)!=meta['sha256']:raise ValueError('generated pair hash mismatch')
        arrays[role]=np.asarray(Image.open(path)).copy()
    imgs=torch.stack([torch.from_numpy(arrays[x]).permute(2,0,1).float()/255 for x in ('positive','negative')]);targets=torch.stack([torch.from_numpy(arrays[x]).long() for x in ('positive-mask','negative-mask')])
    return imgs,targets

def run(project,research,manifest,generated,negatives,output,seed):
    sys.path.insert(0,str(project));from ml.rgb_segmentation.dataset import validate_manifest
    from ml.rgb_segmentation.train import ReviewedDataset,loss
    from round47_validation import validation_stats,passes_validation
    torch.set_num_threads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];doc=validate_manifest(manifest,allow_synthetic=True);assert doc['synthetic'] and doc['manifest_sha256']=='e633bbb65a12e8dfcc5104383299bf1e51659f556e606f696344b659334c95e0'
    new=json.loads((generated/'manifest.json').read_text());assert len(new['pairs'])==96
    negative_doc=json.loads((negatives/'manifest.json').read_text());assert negative_doc['eligible'] and len(negative_doc['pairs'])==24
    init=research/f'round68-artifacts/ranking-{seed}/baseline.pt';meta=json.loads((init.parent/'summary.json').read_text());assert sha(init)==meta['model_sha256']
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);dataset=ReviewedDataset(doc,'train',128);dataset.augment=False;pairmap={}
    for i,item in enumerate(dataset.items):pairmap.setdefault(item['pair_id'],{})[item['pair_kind']]=i
    assert len(pairmap)==192 and all(set(v)=={'positive','negative'} for v in pairmap.values());pairs=[(v['positive'],v['negative']) for _,v in sorted(pairmap.items())]
    prepared=[load_pair(generated,it) for it in new['pairs']];negative_pairs=[load_pair(negatives,it) for it in negative_doc['pairs']]
    assert len(negative_pairs)==24
    torch.manual_seed(seed);np.random.seed(seed);random.seed(seed);model=torch.jit.load(str(init),map_location='cpu').train();opt=torch.optim.AdamW(model.parameters(),lr=1e-4);history=[]
    for epoch in range(1,4):
        indices=torch.randperm(len(pairs))[:72].tolist();schedule=[('new',i) for i in range(96)]+[('old',i) for i in indices]+[('negative',i) for i in range(24)];order=torch.randperm(len(schedule)).tolist();total=0;active=0
        for j in order:
            kind,idx=schedule[j]
            if kind=='new':images,targets=prepared[idx];images=images.clone();targets=targets.clone()
            elif kind=='negative':images,targets=negative_pairs[idx];images=images.clone();targets=targets.clone()
            else:
                v=[dataset[i] for i in pairs[idx]];images=torch.stack([x[0] for x in v]);targets=torch.stack([x[1] for x in v])
            if random.random()<.5:images=images.flip(-1);targets=targets.flip(-1)
            images=(images*random.uniform(.9,1.1)).clamp(0,1);opt.zero_grad();logits=model(images);rank=oldloss.paired_ranking(logits,targets);value=loss(logits,targets)+.1*rank
            if not torch.isfinite(value):raise ValueError('nonfinite loss')
            value.backward();opt.step();total+=float(value.detach());active+=int(((targets[0]==2)&(targets[1]==1)).any())
        history.append({'epoch':epoch,'loss':total/len(schedule),'pairs_with_ranking_pixels':active,'new_pairs':96,'replay_pairs':72,'paired_texture_pairs':24});print('seed',seed,'epoch',epoch,'finished',flush=True)
    model.eval();torch.jit.save(model,str(output/'baseline.pt'));val=torch.utils.data.DataLoader(ReviewedDataset(doc,'validation',128),batch_size=1,num_workers=0);records=[];vl=0
    with torch.inference_mode():
        for image,target in val:
            logits=model(image);vl+=float(loss(logits,target));records.append((logits.argmax(1),target))
    stats=validation_stats(records);assert reg.read_bytes()==before
    result={'protocol':'round75-protocol.md','seed':seed,'manifest_sha256':doc['manifest_sha256'],'generated_manifest_sha256':sha(generated/'manifest.json'),'paired_manifest_sha256':sha(negatives/'manifest.json'),'initial_model_sha256':sha(init),'model_sha256':sha(output/'baseline.pt'),'epochs':history,'validation_loss':vl/len(val),'validation':stats,'validation_gate_pass':passes_validation(stats),'registry_sha256':hashlib.sha256(before).hexdigest(),'status':'research_only','enabled':False};(output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print('seed',seed,'validation gate',result['validation_gate_pass'],flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','research','manifest','generated','negatives','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--seed',type=int,choices=(19,43),required=True);a=p.parse_args();run(a.project,a.research,a.manifest,a.generated,a.negatives,a.output,a.seed)
if __name__=='__main__':main()
