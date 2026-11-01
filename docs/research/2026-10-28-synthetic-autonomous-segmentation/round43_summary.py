"""Pre-specified old and multi-contrast comparisons on observed synthetic test."""
import argparse,json,sys
from collections import Counter
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    for name in ('project-root','runs','prior-runs','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.metrics import aggregate
    result={'scope':'observed synthetic test; no deployment','models':{}}
    for kind in ('prior','hard'):
        for seed in (19,43):
            root=(a.prior_runs/('run-'+str(seed))) if kind=='prior' else (a.runs/('hard-'+str(seed)));summary=json.loads((root/'summary.json').read_text());models={}
            for name in ('baseline','gated'):
                if name not in summary['results']:continue
                raw=json.loads((root/(name+'-eval.json')).read_text());policy=json.loads((root/(name+'-policy.json')).read_text());assert len(raw['rows'])==len(policy['rows'])==64
                groups={}
                for c in ('0','25','50','100'):
                    r=[x for x in raw['rows'] if x['groups']['contrast']==c];q=[x for x in policy['rows'] if x['groups']['contrast']==c];assert len(r)==len(q)==16
                    groups[c]={'raw':aggregate(r),'policy':aggregate(q),'outcomes':dict(Counter(x['outcome'] for x in q)),'statuses':dict(Counter(x.get('policy_status','not_processed') for x in q)),'released_area_count':sum(x.get('released_area') is not None for x in q)}
                models[name]=groups
            result['models'][kind+'-'+str(seed)]={'status':summary['status'],'gated_epoch':summary['gated_epoch'],'epochs':len(summary['history']),'model_sha256':summary['model_sha256'],'manifest_sha256':summary['manifest_sha256'],'registry_sha256':summary['registry_sha256'],'groups':models}
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print('summary saved',flush=True)
if __name__=='__main__':main()
