"""Mark low-signal synthetic lesion cores as ignore using paired intervention."""
import argparse,copy,hashlib,json,shutil,sys
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def ignore_low_signal(positive,negative,mask,threshold=2.0):
    if positive.shape!=negative.shape or positive.shape[:2]!=mask.shape:raise ValueError('shape mismatch')
    a=cv2.cvtColor(positive.astype('float32')/255,cv2.COLOR_RGB2LAB);b=cv2.cvtColor(negative.astype('float32')/255,cv2.COLOR_RGB2LAB)
    delta=np.linalg.norm(a-b,axis=2);out=mask.copy();out[(mask==2)&(delta<threshold)]=255
    return out


def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    old=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert old['synthetic'] and old['counts']=={'train':192,'validation':32,'test':32}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();doc=copy.deepcopy(old)
    for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
    doc['dataset_review_id']='synthetic-lowsignal-ignore-no-human-review';doc['provenance_note']='Synthetic paired delta E intervention rule; no human review; not clinical truth.'
    pairs={}
    for item in doc['items']:
        for key in ('image','mask'):shutil.copyfile(a.base/item[key],a.output/item[key])
        if item['split']=='train':pairs.setdefault(item['pair_id'],{})[item['pair_kind']]=item
    assert len(pairs)==96 and all(set(x)=={'positive','negative'} for x in pairs.values())
    stats=defaultdict(lambda:{'images':0,'original_lesion_pixels':0,'ignored_lesion_pixels':0,'empty_after':0,'total_pixels':0})
    for pair in pairs.values():
        pos,neg=pair['positive'],pair['negative'];rgb=np.asarray(Image.open(a.base/pos['image']).convert('RGB'));clean=np.asarray(Image.open(a.base/neg['image']).convert('RGB'));mask=np.asarray(Image.open(a.base/pos['mask']).convert('L'));new=ignore_low_signal(rgb,clean,mask)
        assert np.array_equal(new[mask!=2],mask[mask!=2]) and np.isin(new[mask==2],[2,255]).all()
        key=str(pos['training_contrast_scale']);st=stats[key];st['images']+=1;st['original_lesion_pixels']+=int((mask==2).sum());st['ignored_lesion_pixels']+=int(((mask==2)&(new==255)).sum());st['empty_after']+=int(not (new==2).any());st['total_pixels']+=mask.size
        target=a.output/pos['mask'];Image.fromarray(new,'L').save(target);pos['mask_sha256']=sha(target)
    (a.output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');v=validate_manifest(a.output/'manifest.json',allow_synthetic=True);assert v['counts']==old['counts']
    assert [(i['id'],i['image_sha256']) for i in doc['items']]==[(i['id'],i['image_sha256']) for i in old['items']]
    assert [(i['id'],i['mask_sha256']) for i in doc['items'] if i['split']!='train' or i.get('pair_kind')=='negative']==[(i['id'],i['mask_sha256']) for i in old['items'] if i['split']!='train' or i.get('pair_kind')=='negative']
    result={'manifest_sha256':v['manifest_sha256'],'prior_manifest_sha256':old['manifest_sha256'],'threshold_delta_e76':2.0,'levels':dict(stats)};(a.output/'ignore-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
