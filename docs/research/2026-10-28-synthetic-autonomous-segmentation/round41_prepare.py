"""Build multi-contrast paired synthetic training data with unchanged masks."""
import argparse,copy,hashlib,json,shutil,sys
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def weaken(pos,neg,scale):
    if scale not in (.25,.5,1) or pos.shape!=neg.shape:raise ValueError('invalid interpolation')
    return np.clip(np.rint(neg.astype('float64')+(pos.astype('float64')-neg.astype('float64'))*scale),0,255).astype('uint8')

def main():
    p=argparse.ArgumentParser()
    for name in ('project-root','base','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    old=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert old['synthetic'] and old['counts']=={'train':384,'validation':32,'test':64}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();doc=copy.deepcopy(old)
    for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
    doc['dataset_review_id']='synthetic-round41-multicontrast-no-human-review';doc['provenance_note']='Program-controlled synthetic contrasts; no human labels.';pairs={}
    for item in doc['items']:
        for key in ('image','mask'):shutil.copyfile(a.base/item[key],a.output/item[key])
        if item['split']=='train':pairs.setdefault(item['pair_id'],{})[item['pair_kind']]=item
    assert len(pairs)==192 and all(set(v)=={'positive','negative'} for v in pairs.values())
    stats=defaultdict(lambda:{'pairs':0,'delta_e_sum':0.,'identical_core_pixels':0,'core_pixels':0});changed=0
    for idx,(pid,pair) in enumerate(sorted(pairs.items())):
        scale=(.25,.5,1)[idx%3];pos,neg=pair['positive'],pair['negative'];aimg=np.asarray(Image.open(a.base/pos['image']).convert('RGB'));bimg=np.asarray(Image.open(a.base/neg['image']).convert('RGB'));mask=np.asarray(Image.open(a.base/pos['mask']))
        out=weaken(aimg,bimg,scale) if scale!=1 else aimg;valid=mask==2;assert valid.any()
        la=cv2.cvtColor(out.astype('float32')/255,cv2.COLOR_RGB2LAB);lb=cv2.cvtColor(bimg.astype('float32')/255,cv2.COLOR_RGB2LAB);delta=np.linalg.norm(la-lb,axis=2)
        st=stats[str(scale)];st['pairs']+=1;st['delta_e_sum']+=float(delta[valid].mean());st['identical_core_pixels']+=int(((out==bimg).all(2)&valid).sum());st['core_pixels']+=int(valid.sum())
        if scale!=1:
            target=a.output/pos['image'];Image.fromarray(out,'RGB').save(target);pos['image_sha256']=sha(target);changed+=1
        pos['training_contrast_scale']=scale
    assert changed==128 and all(v['pairs']==64 for v in stats.values())
    (a.output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');v=validate_manifest(a.output/'manifest.json',allow_synthetic=True);assert v['counts']==old['counts']
    for s in ('validation','test'):
        ident=lambda d:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==s]
        assert ident(old)==ident(doc)
    assert [(x['id'],x['mask_sha256']) for x in old['items']]==[(x['id'],x['mask_sha256']) for x in doc['items']]
    oldbyid={x['id']:x for x in old['items']};assert all(x['image_sha256']==oldbyid[x['id']]['image_sha256'] for x in doc['items'] if x['split']=='train' and x['pair_kind']=='negative')
    out={'manifest_sha256':v['manifest_sha256'],'prior_manifest_sha256':old['manifest_sha256'],'changed_positives':changed,'levels':dict(stats)};(a.output/'contrast-summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
