"""Post-hoc constraint-aware grid diagnostic; never changes experiment outcome."""
import argparse,json
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

def lab(rgb):return cv2.cvtColor(rgb.astype('float32')/255,cv2.COLOR_RGB2LAB)

def candidate_stats(pos,neg,mask,scale):
    core=mask==2
    if not core.any():raise ValueError('missing core')
    p=pos[core].reshape(1,-1,3);n=neg[core].reshape(1,-1,3);base=lab(n);positive=lab(p);diff=positive-base;changed=(p!=n).any(2)
    work=base.copy();work[:,:,0]=np.clip(base[:,:,0]+scale*diff[:,:,0],0,100);work[:,:,1]=base[:,:,1]+.5*diff[:,:,1];work[:,:,2]=base[:,:,2]+.5*diff[:,:,2]
    out=np.clip(np.rint(cv2.cvtColor(work,cv2.COLOR_LAB2RGB)*255),0,255).astype('uint8');out[~changed]=n[~changed]
    orig_sat=np.any((p==0)|(p==255),axis=2);fallback=changed & np.any((out==0)|(out==255),axis=2) & ~orig_sat;out[fallback]=p[fallback]
    delta=lab(out)-base;target=float(np.linalg.norm(diff,axis=2).mean());actual=float(np.linalg.norm(delta,axis=2).mean());new_sat=float(100*(np.any((out==0)|(out==255),axis=2)&~orig_sat).mean());fallback_pct=float(100*fallback.mean())
    return {'scale':float(scale),'absolute_error':abs(target-actual),'fallback_core_pct':fallback_pct,'new_saturated_core_pct':new_sat,'passes':abs(target-actual)<=.5 and fallback_pct<=20 and new_sat<=1}

def main():
    p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True);p.add_argument('--matching-summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();d=json.loads((a.original/'manifest.json').read_text());prior=json.loads(a.matching_summary.read_text());pairs=defaultdict(dict)
    for i in d['items']:
        if i['split'] in ('train','validation'):pairs[(i['split'],i['pair_id'])][i['pair_kind']]=i
    result={}
    for mode,split in [('mixed','train'),('lab-dev','validation')]:
        rows=[]
        for priorrow in prior['rows'][mode]:
            pair=pairs[(split,priorrow['pair_id'])];pos=np.asarray(Image.open(a.original/pair['positive']['image']).convert('RGB'));neg=np.asarray(Image.open(a.original/pair['negative']['image']).convert('RGB'));mask=np.asarray(Image.open(a.original/pair['positive']['mask']))
            candidates=[candidate_stats(pos,neg,mask,k/20) for k in range(81)];feasible=[x for x in candidates if x['passes']];chosen=min(feasible,key=lambda x:(x['absolute_error'],x['fallback_core_pct'])) if feasible else None
            rows.append({'pair_id':priorrow['pair_id'],'original_pass':priorrow['matched'],'grid_feasible':bool(feasible),'best_feasible':chosen})
        result[mode]={'total':len(rows),'original_failed':sum(not x['original_pass'] for x in rows),'original_failed_but_grid_feasible':sum(not x['original_pass'] and x['grid_feasible'] for x in rows),'grid_infeasible':sum(not x['grid_feasible'] for x in rows),'rows':rows}
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps({'status':'post_hoc_diagnostic_no_training','grid':'0 to 4 by 0.05','groups':result},indent=2)+'\n');print(json.dumps({k:{x:v for x,v in r.items() if x!='rows'} for k,r in result.items()},indent=2))
if __name__=='__main__':main()
