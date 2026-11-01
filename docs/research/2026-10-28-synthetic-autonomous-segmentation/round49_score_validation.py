"""Score all frozen research models on shared expanded development validation."""
import argparse,hashlib,json,sys
from pathlib import Path
import torch

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','prior-runs','runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.evaluate import predict
    from round47_validation import validation_stats,passes_validation
    d=validate_manifest(a.manifest,allow_synthetic=True);assert d['synthetic'] and d['counts']=={'train':384,'validation':320,'test':64};reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];result={}
    for seed in (19,43):
        for kind,folder in [('prior',a.prior_runs/('small-'+str(seed))),('contrast',a.runs/('contrast-'+str(seed)))]:
            meta=json.loads((folder/'summary.json').read_text());w=folder/'baseline.pt';h=hashlib.sha256(w.read_bytes()).hexdigest();assert h==meta['model_sha256'];model=torch.jit.load(str(w)).eval();pairs=[]
            for item in d['items']:
                if item['split']!='validation':continue
                rgb,truth=load_item(Path(d['root']),item);pred=predict(model,rgb);pairs.append((torch.from_numpy(pred),torch.from_numpy(truth)))
            stats=validation_stats(pairs);result[kind+'-'+str(seed)]={'weights_sha256':h,'statistics':stats,'passes':passes_validation(stats)}
            if kind=='contrast':assert stats==min(meta['history'],key=lambda x:x['validation_loss'])['validation']
    assert reg.read_bytes()==before
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps({'validation_manifest_sha256':d['manifest_sha256'],'models':result,'registry_sha256':hashlib.sha256(before).hexdigest()},indent=2)+'\n');print('development validation scored',flush=True)
if __name__=='__main__':main()
