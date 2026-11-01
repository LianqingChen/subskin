"""Summarize each pre-specified synthetic model and contrast group."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','runs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.metrics import aggregate
    result={'models':{},'scope':'synthetic heldout','selection':'pre-fixed, all seeds and groups'}
    for group in ('old','diverse'):
        for seed in (19,43):
            root=a.runs/(group+'-'+str(seed));s=json.loads((root/'summary.json').read_text());models={}
            for label in ('baseline','gated'):
                if label not in s['results']:continue
                raw=json.loads((root/(label+'-eval.json')).read_text());pol=json.loads((root/(label+'-policy.json')).read_text());assert len(raw['rows'])==len(pol['rows'])==64
                groups={}
                for level in ('0','25','50','100'):
                    r=[x for x in raw['rows'] if x['groups']['contrast']==level];q=[x for x in pol['rows'] if x['groups']['contrast']==level];assert len(r)==len(q)==16
                    groups[level]={'raw':aggregate(r),'policy':aggregate(q),'policy_outcomes':dict(Counter(x['outcome'] for x in q)),'policy_statuses':dict(Counter(x.get('policy_status','not_processed') for x in q)),'released_area_count':sum(x.get('released_area') is not None for x in q)}
                models[label]=groups
            result['models'][group+'-'+str(seed)]={'status':s['status'],'gated_epoch':s['gated_epoch'],'epochs':len(s['history']),'manifest_sha256':s['manifest_sha256'],'model_sha256':s['model_sha256'],'groups':models,'registry_sha256':s['registry_sha256']}
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print('summary saved')
if __name__=='__main__':main()
