"""Score frozen old/new models on synthetic source-stratified validation."""
import argparse,hashlib,json,sys
from pathlib import Path
import torch

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','prior-runs','runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.evaluate import predict
    from round42_validation import validation_stats,passes_validation
    d=validate_manifest(a.manifest,allow_synthetic=True);assert d['synthetic'] and d['counts']=={'train':384,'validation':160,'test':64}
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];result={}
    for seed in (19,43):
        for name,folder in [('prior',a.prior_runs/('diverse-'+str(seed))),('expanded',a.runs/('run-'+str(seed)))]:
            meta=json.loads((folder/'summary.json').read_text());path=folder/'baseline.pt';assert sha(path)==meta['model_sha256'];model=torch.jit.load(str(path)).eval();pairs=[]
            for item in d['items']:
                if item['split']!='validation':continue
                rgb,truth=load_item(Path(d['root']),item);pred=predict(model,rgb);pairs.append((torch.from_numpy(pred),torch.from_numpy(truth)))
            stats=validation_stats(pairs);result[name+'-'+str(seed)]={'weights_sha256':sha(path),'statistics':stats,'passes':passes_validation(stats)}
            if name=='expanded':
                best=min(meta['history'],key=lambda x:x['validation_loss'])['validation'];assert stats==best
    assert before==reg.read_bytes()
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps({'manifest_sha256':d['manifest_sha256'],'models':result,'registry_sha256':hashlib.sha256(before).hexdigest()},indent=2)+'\n');print('validated frozen models',flush=True)
if __name__=='__main__':main()
