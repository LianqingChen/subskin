"""Match synthetic paired Lab interventions to RGB core Delta E, not clinical labels."""
import argparse,copy,hashlib,json,shutil,sys
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def lab_of(rgb):return cv2.cvtColor(rgb.astype('float32')/255,cv2.COLOR_RGB2LAB)

def match_delta_e(positive,negative,mask,tolerance=.5):
    if positive.shape!=negative.shape or positive.shape[:2]!=mask.shape:raise ValueError('shape mismatch')
    core=mask==2
    if not core.any():raise ValueError('positive core missing')
    clean=negative.astype('float32')/255;pos=positive.astype('float32')/255;diff=pos-clean;denom=1-clean
    alpha=np.clip((diff*denom).sum(axis=2)/(np.square(denom).sum(axis=2)+1e-12),0,1).astype('float32');changed=np.any(diff!=0,axis=2)
    base_lab=cv2.cvtColor(clean,cv2.COLOR_RGB2LAB);pos_lab=lab_of(positive);target=float(np.linalg.norm(pos_lab-base_lab,axis=2)[core].mean());best=None;low=0.;high=8.
    for scale in [0.,8.]+[None]*20:
        v=(low+high)/2 if scale is None else scale;work=base_lab.copy();work[:,:,0]=np.clip(base_lab[:,:,0]+v*alpha*(100-base_lab[:,:,0]),0,100);converted=cv2.cvtColor(work,cv2.COLOR_LAB2RGB);out=negative.copy();out[changed]=np.clip(np.rint(converted[changed]*255),0,255).astype('uint8');lab=lab_of(out);actual=float(np.linalg.norm(lab-base_lab,axis=2)[core].mean());err=abs(actual-target)
        if best is None or err<best[0]:best=(err,v,out,lab,actual)
        if scale is None:
            if actual<target:low=v
            else:high=v
    err,v,out,lab,actual=best;assert np.array_equal(out[~changed],negative[~changed])
    meta={'target_delta_e':target,'actual_delta_e':actual,'absolute_error':err,'matched':bool(err<=tolerance),'scale':v,'rgb_delta_l':float((pos_lab[:,:,0]-base_lab[:,:,0])[core].mean()),'lab_delta_l':float((lab[:,:,0]-base_lab[:,:,0])[core].mean()),'lab_saturated_core_pct':float(100*np.any((out==0)|(out==255),axis=2)[core].mean())}
    return out,meta

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','original','mixed','lab-dev','provenance','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    orig=validate_manifest(a.original/'manifest.json',allow_synthetic=True);old={mode:validate_manifest(path/'manifest.json',allow_synthetic=True) for mode,path in [('mixed',a.mixed),('lab-dev',a.lab_dev)]}
    assert all(d['synthetic'] and d['counts']=={'train':384,'validation':320,'test':64} for d in [orig,*old.values()]);prov=json.loads(a.provenance.read_text());selected={x['pair_id'] for x in prov['train']};assert len(selected)==96
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);original_pairs=defaultdict(dict)
    for item in orig['items']:
        if item['split'] in ('train','validation'):original_pairs[(item['split'],item['pair_id'])][item['pair_kind']]=item
    stats={};manifests={}
    for mode,base in [('mixed',a.mixed),('lab-dev',a.lab_dev)]:
        root=a.output/mode;root.mkdir();(root/'images').mkdir();(root/'masks').mkdir();doc=copy.deepcopy(old[mode]);rows=[]
        for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
        doc['dataset_review_id']='synthetic-round53-'+mode+'-no-human-review';doc['provenance_note']='Program color-matched intervention; not clinical truth; no human review.'
        for item in doc['items']:
            for key in ('image','mask'):shutil.copyfile(base/item[key],root/item[key])
            modify=item.get('pair_kind')=='positive' and ((mode=='mixed' and item['split']=='train' and item['pair_id'] in selected) or (mode=='lab-dev' and item['split']=='validation'))
            if not modify:continue
            pair=original_pairs[(item['split'],item['pair_id'])];assert set(pair)=={'positive','negative'}
            pos=np.asarray(Image.open(a.original/pair['positive']['image']).convert('RGB'));neg=np.asarray(Image.open(a.original/pair['negative']['image']).convert('RGB'));mask=np.asarray(Image.open(a.original/pair['positive']['mask']))
            out,meta=match_delta_e(pos,neg,mask);target=root/item['image'];Image.fromarray(out,'RGB').save(target);item['image_sha256']=sha(target);rows.append({'pair_id':item['pair_id'],'source_sha256':item['source_sha256'],**meta})
        assert len(rows)==(96 if mode=='mixed' else 160)
        path=root/'manifest.json';path.write_text(json.dumps(doc,indent=2)+'\n');v=validate_manifest(path,allow_synthetic=True);assert v['counts']==orig['counts'];manifests[mode]=v['manifest_sha256'];stats[mode]=rows
        oldbyid={x['id']:x for x in old[mode]['items']}
        changed_ids={x['pair_id'] for x in rows}
        for item in doc['items']:
            olditem=oldbyid[item['id']];assert item['mask_sha256']==olditem['mask_sha256']
            modified=item.get('pair_kind')=='positive' and item.get('pair_id') in changed_ids and ((mode=='mixed' and item['split']=='train') or (mode=='lab-dev' and item['split']=='validation'))
            if not modified:assert item['image_sha256']==olditem['image_sha256']
    fails={mode:sum(not row['matched'] for row in rows) for mode,rows in stats.items()};passed=all(fails[m]/len(stats[m])<=.05 for m in stats)
    out={'manifests':manifests,'quality_pass':passed,'tolerance_delta_e':.5,'failure_limit_fraction':.05,'failure_counts':fails,'rows':stats};(a.output/'matching-summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'quality_pass':passed,'failure_counts':fails,'manifests':manifests},indent=2))
if __name__=='__main__':main()
