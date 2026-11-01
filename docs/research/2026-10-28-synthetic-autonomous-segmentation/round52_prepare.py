"""Generate source-balanced Lab variants from synthetic paired images."""
import argparse,copy,hashlib,json,shutil,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image
import round51_prepare as color

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def convert(root,base,pair):
    pos,neg=pair['positive'],pair['negative'];p=np.asarray(Image.open(base/pos['image']).convert('RGB'));n=np.asarray(Image.open(base/neg['image']).convert('RGB'));mask=np.asarray(Image.open(base/pos['mask']))
    if not (mask==2).any():raise ValueError('positive core missing')
    out=np.clip(np.rint(color.alternate_lab(n.astype('float32')/255,p.astype('float32')/255)*255),0,255).astype('uint8')
    same=(p==n).all(axis=2);assert np.array_equal(out[same],n[same])
    target=root/pos['image'];Image.fromarray(out,'RGB').save(target);pos['image_sha256']=sha(target)
    return {'pair_id':pos['pair_id'],'source_sha256':pos['source_sha256'],'rgb':color.core_color(p,n,mask),'lab':color.core_color(out,n,mask)}

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    old=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert old['synthetic'] and old['counts']=={'train':384,'validation':320,'test':64}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);docs={};roots={};pairs={}
    for mode in ('mixed','lab-dev'):
        root=a.output/mode;root.mkdir();(root/'images').mkdir();(root/'masks').mkdir();doc=copy.deepcopy(old)
        for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
        doc['dataset_review_id']='synthetic-round52-'+mode+'-no-human-review';doc['provenance_note']='Program color interpolation; no human labels; not clinical truth.'
        pairs[mode]=defaultdict(dict)
        for item in doc['items']:
            for key in ('image','mask'):shutil.copyfile(a.base/item[key],root/item[key])
            if item['split'] in ('train','validation'):pairs[mode][(item['split'],item['pair_id'])][item['pair_kind']]=item
        docs[mode]=doc;roots[mode]=root
    per_source=defaultdict(list)
    for (split,pid),pair in pairs['mixed'].items():
        if split=='train':assert set(pair)=={'positive','negative'};per_source[pair['positive']['source_sha256']].append((pid,pair))
    assert len(per_source)==12
    train_stats=[]
    for h,items in sorted(per_source.items()):
        assert len(items) in (12,24)
        for _,pair in sorted(items)[:len(items)//2]:train_stats.append(convert(roots['mixed'],a.base,pair))
    assert len(train_stats)==96
    val_stats=[]
    for (split,pid),pair in sorted(pairs['lab-dev'].items()):
        if split=='validation':assert set(pair)=={'positive','negative'};val_stats.append(convert(roots['lab-dev'],a.base,pair))
    assert len(val_stats)==160
    oldbyid={i['id']:i for i in old['items']};results={}
    for mode in ('mixed','lab-dev'):
        path=roots[mode]/'manifest.json';path.write_text(json.dumps(docs[mode],indent=2)+'\n');d=validate_manifest(path,allow_synthetic=True);assert d['counts']==old['counts']
        for item in d['items']:
            ref=oldbyid[item['id']];assert item['mask_sha256']==ref['mask_sha256']
            if (mode=='mixed' and item['split']!='train') or (mode=='lab-dev' and item['split']!='validation') or item.get('pair_kind')=='negative':assert item['image_sha256']==ref['image_sha256']
        results[mode]=d['manifest_sha256']
    stats={'base_manifest_sha256':old['manifest_sha256'],'manifests':results,'train':train_stats,'lab_development':val_stats};(a.output/'color-provenance.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps({'manifests':results,'train_altered':len(train_stats),'validation_altered':len(val_stats)},indent=2),flush=True)
if __name__=='__main__':main()
