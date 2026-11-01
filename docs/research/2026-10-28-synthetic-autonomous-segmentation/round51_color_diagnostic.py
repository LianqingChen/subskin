"""Post-hoc paired color differences; no clinical interpretation."""
import argparse,json
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();doc=json.loads((a.dataset/'manifest.json').read_text());pairs=defaultdict(dict)
    for item in doc['items']:
        if item['split']=='test':pairs[item['pair_id']][item['groups']['synthesis']]=item
    assert len(pairs)==16;rows=[]
    for pid,x in sorted(pairs.items()):
        assert set(x)=={'none','rgb','lab'} and x['rgb']['mask_sha256']==x['lab']['mask_sha256']
        clean=np.asarray(Image.open(a.dataset/x['none']['image']).convert('RGB')).astype('float32')/255;base=cv2.cvtColor(clean,cv2.COLOR_RGB2LAB);r={'pair_id':pid,'site':x['rgb']['groups']['body_site']}
        for kind in ('rgb','lab'):
            image=np.asarray(Image.open(a.dataset/x[kind]['image']).convert('RGB')).astype('float32')/255;mask=np.asarray(Image.open(a.dataset/x[kind]['mask']))==2;assert mask.any();delta=cv2.cvtColor(image,cv2.COLOR_RGB2LAB)-base
            r[kind]={'delta_l':float(delta[:,:,0][mask].mean()),'delta_a':float(delta[:,:,1][mask].mean()),'delta_b':float(delta[:,:,2][mask].mean()),'delta_e76':float(np.linalg.norm(delta,axis=2)[mask].mean())}
        rows.append(r)
    summary={kind:{k:float(np.mean([r[kind][k] for r in rows])) for k in ('delta_l','delta_a','delta_b','delta_e76')} for kind in ('rgb','lab')};summary['paired_absolute_delta_l_difference_mean']=float(np.mean([abs(x['rgb']['delta_l']-x['lab']['delta_l']) for x in rows]));summary['paired_absolute_delta_l_difference_max']=float(max(abs(x['rgb']['delta_l']-x['lab']['delta_l']) for x in rows))
    if a.output.exists():raise ValueError('output exists')
    a.output.write_text(json.dumps({'kind':'post_hoc_not_clinical','summary':summary,'pairs':rows},indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
