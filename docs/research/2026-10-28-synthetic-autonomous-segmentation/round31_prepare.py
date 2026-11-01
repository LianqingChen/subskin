"""Add synchronized synthetic illumination to half of known pairs."""
import argparse,copy,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def apply_illumination(images, masks, seed):
    if len(images)!=2 or len(masks)!=2:raise ValueError('exactly two images required')
    pos,neg=[np.asarray(x,dtype=np.uint8) for x in images];pm,nm=[np.asarray(x,dtype=np.uint8) for x in masks]
    same=(pos==neg).all(axis=2);available=np.argwhere((pm==1)&(nm==1)&same)
    if len(available)==0:raise ValueError('no identical normal skin for highlight center')
    rng=np.random.default_rng(seed);cy,cx=map(int,available[int(rng.integers(len(available)))]);sigma=float(rng.uniform(12,25));gain=float(rng.uniform(.30,.65));yy,xx=np.indices(pm.shape);field=1+gain*np.exp(-((xx-cx)**2+(yy-cy)**2)/(2*sigma**2))
    result=[];saturated=[]
    for im in (pos,neg):
        x=im.astype(np.float64)*field[...,None];saturated.append(float((x>255).any(axis=2).mean()));result.append(np.clip(np.rint(x),0,255).astype(np.uint8))
    assert np.array_equal(result[0][same],result[1][same])
    return result,{'center':[cy,cx],'sigma':sigma,'gain':gain,'saturated_pixel_fraction':saturated}


def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    original=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert original['synthetic'] and original['counts']=={'train':192,'validation':32,'test':32}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();doc=copy.deepcopy(original)
    for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
    doc['dataset_review_id']='synthetic-paired-illumination-no-human-review';doc['provenance_note']='Paired synthetic lighting intervention, automated labels, no human review.'
    pairs={}
    for item in doc['items']:
        for key in ('image','mask'):shutil.copyfile(a.base/item[key],a.output/item[key])
        if item['split']=='train':pairs.setdefault(item['pair_id'],{})[item['pair_kind']]=item
    assert len(pairs)==96 and all(set(v)=={'positive','negative'} for v in pairs.values())
    changes=[]
    for idx,(pid,pair) in enumerate(sorted(pairs.items())):
        if idx%2:continue
        rows=[pair['positive'],pair['negative']];images=[np.asarray(Image.open(a.base/i['image']).convert('RGB')) for i in rows];masks=[np.asarray(Image.open(a.base/i['mask'])) for i in rows]
        augmented,meta=apply_illumination(images,masks,3100000+idx)
        for row,im in zip(rows,augmented):
            target=a.output/row['image'];Image.fromarray(im,'RGB').save(target);row['image_sha256']=sha(target)
        changes.append({'pair_id':pid,'seed':3100000+idx,**meta})
    assert len(changes)==48
    (a.output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');valid=validate_manifest(a.output/'manifest.json',allow_synthetic=True);assert valid['counts']=={'train':192,'validation':32,'test':32}
    identity=lambda d,split:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==split]
    for s in ('validation','test'):assert identity(original,s)==identity(doc,s)
    assert [(x['id'],x['mask_sha256']) for x in original['items'] if x['split']=='train']==[(x['id'],x['mask_sha256']) for x in doc['items'] if x['split']=='train']
    summary={'manifest_sha256':valid['manifest_sha256'],'source_manifest_sha256':original['manifest_sha256'],'changed_pairs':len(changes),'pairs':changes};(a.output/'illumination.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'manifest_sha256':valid['manifest_sha256'],'changed_pairs':len(changes),'mean_saturated_pct':100*np.mean([z for v in changes for z in v['saturated_pixel_fraction']])},indent=2))
if __name__=='__main__':main()
