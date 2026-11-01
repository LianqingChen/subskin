"""Apply preassigned lesion contrast to paired synthetic training images."""
import argparse,copy,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def weaken(positive,negative,scale):
    if scale not in (.25,.5,1):raise ValueError('unsupported contrast')
    if positive.shape!=negative.shape:raise ValueError('different dimensions')
    return np.clip(np.rint(negative.astype('float64')+(positive.astype('float64')-negative.astype('float64'))*scale),0,255).astype('uint8')


def main():
    p=argparse.ArgumentParser()
    for name in ('project-root','base','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    old=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert old['synthetic'] and old['counts']=={'train':192,'validation':32,'test':32}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();doc=copy.deepcopy(old)
    for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
    doc['dataset_review_id']='synthetic-multicontrast-no-human-review';doc['provenance_note']='Program-controlled contrast with automatic labels, no human review.'
    pairs={}
    for item in doc['items']:
        for key in ('image','mask'):shutil.copyfile(a.base/item[key],a.output/item[key])
        if item['split']=='train':pairs.setdefault(item['pair_id'],{})[item['pair_kind']]=item
    assert len(pairs)==96 and all(set(x)=={'positive','negative'} for x in pairs.values())
    counts={'.25':0,'.5':0,'1':0};modified=0
    for pid,pair in sorted(pairs.items()):
        local=int(pid.rsplit('_',1)[-1]);scale=(.25,.5,1)[local%3];counts[{.25:'.25',.5:'.5',1:'1'}[scale]]+=1
        pos=pair['positive'];neg=pair['negative'];positive=np.asarray(Image.open(a.base/pos['image']).convert('RGB'));negative=np.asarray(Image.open(a.base/neg['image']).convert('RGB'))
        if scale!=1:
            arr=weaken(positive,negative,scale);out=a.output/pos['image'];Image.fromarray(arr,'RGB').save(out);pos['image_sha256']=sha(out);modified+=1
        pos['training_contrast_scale']=scale
    assert counts=={'.25':32,'.5':32,'1':32} and modified==64
    (a.output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');v=validate_manifest(a.output/'manifest.json',allow_synthetic=True)
    assert v['counts']=={'train':192,'validation':32,'test':32}
    for split in ('validation','test'):
        ident=lambda d:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==split]
        assert ident(old)==ident(doc)
    assert [(x['id'],x['mask_sha256']) for x in old['items']]==[(x['id'],x['mask_sha256']) for x in doc['items']]
    assert all(x['image_sha256']==next(y['image_sha256'] for y in old['items'] if y['id']==x['id']) for x in doc['items'] if x['split']=='train' and x['pair_kind']=='negative')
    print(json.dumps({'manifest_sha256':v['manifest_sha256'],'counts':counts,'modified_positive_images':modified},indent=2))
if __name__=='__main__':main()
