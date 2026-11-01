"""Score frozen synthetic models across intervention-strength levels."""
import argparse,hashlib,json,subprocess,sys
from collections import Counter
from pathlib import Path

EXPECTED={'paired':'227f5632f9d72a0e4263e7351f2ec3279940bc148399dd5399db68cf95d8bdb4','weighted':'617d069b04e5b75a5cb0e18e33f6838092d4a17c755a2dbf2fc44ac497638e8c'}

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','weights','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--model',choices=tuple(EXPECTED),required=True);a=p.parse_args();sys.path.insert(0,str(a.project_root))
    from ml.rgb_segmentation.dataset import validate_manifest
    from ml.rgb_segmentation.evaluate import evaluate
    from ml.rgb_segmentation.metrics import aggregate
    v=validate_manifest(a.manifest,allow_synthetic=True);assert v['synthetic'] and v['counts']=={'train':192,'validation':32,'test':64}
    assert hashlib.sha256(a.weights.read_bytes()).hexdigest()==EXPECTED[a.model]
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    ev=evaluate(a.manifest,a.weights,a.output_dir/'raw.json',allow_synthetic=True)
    subprocess.run([sys.executable,str(Path(__file__).with_name('round19_policy.py')),'--project-root',str(a.project_root),'--manifest',str(a.manifest),'--weights',str(a.weights),'--output',str(a.output_dir/'policy.json')],check=True,stdout=subprocess.DEVNULL)
    policy=json.loads((a.output_dir/'policy.json').read_text());groups={}
    for contrast in ('0','25','50','100'):
        rawrows=[r for r in ev['rows'] if r['groups']['contrast']==contrast];prows=[r for r in policy['rows'] if r['groups']['contrast']==contrast];assert len(rawrows)==len(prows)==16
        groups[contrast]={'raw':aggregate(rawrows),'policy':aggregate(prows),'policy_outcomes':dict(Counter(r['outcome'] for r in prows)),'policy_statuses':dict(Counter(r.get('policy_status','not_processed') for r in prows)),'released_area_count':sum(r.get('released_area') is not None for r in prows if r['outcome']=='processed'),'by_site':{site:aggregate([r for r in rawrows if r['groups']['body_site']==site]) for site in ('arm','hand')}}
    assert before==reg.read_bytes()
    summary={'model':a.model,'weights_sha256':EXPECTED[a.model],'manifest_sha256':v['manifest_sha256'],'groups':groups,'registry_sha256':hashlib.sha256(before).hexdigest(),'synthetic':True,'enabled':False}
    (a.output_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('done',a.model,flush=True)
if __name__=='__main__':main()
