"""Score frozen research models on paired synthetic color-mechanism test."""
import argparse,hashlib,json,subprocess,sys
from collections import Counter
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','train-manifest','model-folder','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--name',required=True);a=p.parse_args();sys.path.insert(0,str(a.project_root))
    from ml.rgb_segmentation.dataset import validate_manifest
    from ml.rgb_segmentation.evaluate import evaluate
    from ml.rgb_segmentation.metrics import aggregate
    test=validate_manifest(a.manifest,allow_synthetic=True);train=validate_manifest(a.train_manifest,allow_synthetic=True)
    assert test['synthetic'] and train['synthetic'] and test['counts']=={'train':384,'validation':320,'test':48}
    assert {i['source_sha256'] for i in train['items'] if i['split'] in ('train','validation')}.isdisjoint({i['source_sha256'] for i in test['items'] if i['split']=='test'})
    meta=json.loads((a.model_folder/'summary.json').read_text());weights=a.model_folder/'baseline.pt';h=hashlib.sha256(weights.read_bytes()).hexdigest();assert h==meta['model_sha256'] and meta['manifest_sha256']==train['manifest_sha256'] and meta['status']=='no_eligible_checkpoint'
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);raw=evaluate(a.manifest,weights,a.output_dir/'raw.json',allow_synthetic=True)
    subprocess.run([sys.executable,str(Path(__file__).with_name('round19_policy.py')),'--project-root',str(a.project_root),'--manifest',str(a.manifest),'--weights',str(weights),'--output',str(a.output_dir/'policy.json')],check=True,stdout=subprocess.DEVNULL);policy=json.loads((a.output_dir/'policy.json').read_text());groups={}
    for mechanism in ('none','rgb','lab'):
        r=[x for x in raw['rows'] if x['groups']['synthesis']==mechanism];q=[x for x in policy['rows'] if x['groups']['synthesis']==mechanism];assert len(r)==len(q)==16
        groups[mechanism]={'raw':aggregate(r),'policy':aggregate(q),'policy_outcomes':dict(Counter(x['outcome'] for x in q)),'policy_statuses':dict(Counter(x.get('policy_status','not_processed') for x in q)),'released_area_count':sum(x.get('released_area') is not None for x in q),'by_site':{site:aggregate([x for x in r if x['groups']['body_site']==site]) for site in ('leg','hand')}}
    assert reg.read_bytes()==before
    out={'name':a.name,'weights_sha256':h,'train_manifest_sha256':train['manifest_sha256'],'test_manifest_sha256':test['manifest_sha256'],'status':'unqualified_research_only','groups':groups,'registry_sha256':hashlib.sha256(before).hexdigest()};(a.output_dir/'summary.json').write_text(json.dumps(out,indent=2)+'\n');print(a.name,'done',flush=True)
if __name__=='__main__':main()
