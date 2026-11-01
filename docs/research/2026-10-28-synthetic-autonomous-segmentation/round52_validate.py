"""Evaluate frozen models on matched RGB and Lab development variants."""
import argparse,hashlib,json,sys
from pathlib import Path
import torch


def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','rgb-manifest','lab-manifest','prior-runs','runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.evaluate import predict
    from round47_validation import validation_stats,passes_validation
    docs={k:validate_manifest(v,allow_synthetic=True) for k,v in [('rgb',a.rgb_manifest),('lab',a.lab_manifest)]}
    for d in docs.values():assert d['synthetic'] and d['counts']=={'train':384,'validation':320,'test':64}
    for s in ('train','test'):
        f=lambda d:[(i['id'],i['image_sha256'],i['mask_sha256']) for i in d['items'] if i['split']==s]
        assert f(docs['rgb'])==f(docs['lab'])
    x=[(i['id'],i['mask_sha256']) for i in docs['rgb']['items'] if i['split']=='validation'];y=[(i['id'],i['mask_sha256']) for i in docs['lab']['items'] if i['split']=='validation'];assert x==y
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];results={}
    for seed in (19,43):
        for kind,folder in [('prior',a.prior_runs/('small-'+str(seed))),('mixed',a.runs/('mixed-'+str(seed)))]:
            meta=json.loads((folder/'summary.json').read_text());variants=['baseline']+(['gated'] if meta['status']=='selected' else [])
            for variant in variants:
                weights=folder/(variant+'.pt');h=hashlib.sha256(weights.read_bytes()).hexdigest();assert variant!='baseline' or h==meta['model_sha256'];net=torch.jit.load(str(weights)).eval();values={}
                for color,doc in docs.items():
                    pairs=[]
                    for item in doc['items']:
                        if item['split']!='validation':continue
                        rgb,truth=load_item(Path(doc['root']),item);pred=predict(net,rgb);pairs.append((torch.from_numpy(pred),torch.from_numpy(truth)))
                    stats=validation_stats(pairs);values[color]={'statistics':stats,'passes':passes_validation(stats)}
                    if kind=='mixed' and variant=='baseline' and color=='rgb':assert stats==min(meta['history'],key=lambda x:x['validation_loss'])['validation']
                results[f'{kind}-{seed}-{variant}']={'weights_sha256':h,'groups':values}
    assert reg.read_bytes()==before
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps({'rgb_manifest_sha256':docs['rgb']['manifest_sha256'],'lab_manifest_sha256':docs['lab']['manifest_sha256'],'registry_sha256':hashlib.sha256(before).hexdigest(),'models':results,'limitations':['development validation reused','RGB and Lab share sources and masks','lab unvalidated clinically']},indent=2)+'\n');print('development variants scored',flush=True)
if __name__=='__main__':main()
