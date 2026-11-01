"""Constraint-first paired synthetic color matching, with transparent fallback."""
import argparse,copy,hashlib,json,shutil,sys
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lab(rgb):return cv2.cvtColor(rgb.astype('float32')/255,cv2.COLOR_RGB2LAB)

def at_scale(pos,neg,scale):
    if pos.shape!=neg.shape or pos.ndim!=3 or pos.shape[2]!=3:raise ValueError('bad shape')
    base=lab(neg);delta=lab(pos)-base;changed=(pos!=neg).any(2);work=base.copy();work[:,:,0]=np.clip(base[:,:,0]+scale*delta[:,:,0],0,100);work[:,:,1]=base[:,:,1]+.5*delta[:,:,1];work[:,:,2]=base[:,:,2]+.5*delta[:,:,2]
    converted=np.clip(np.rint(cv2.cvtColor(work,cv2.COLOR_LAB2RGB)*255),0,255).astype('uint8');out=neg.copy();out[changed]=converted[changed]
    orig_sat=np.any((pos==0)|(pos==255),axis=2);fallback=changed & np.any((out==0)|(out==255),axis=2) & ~orig_sat;out[fallback]=pos[fallback]
    return out,fallback

def select_image(pos,neg,mask):
    core=mask==2
    if not core.any():raise ValueError('missing positive core')
    pp=pos[core].reshape(1,-1,3);nn=neg[core].reshape(1,-1,3);base=lab(nn);target=float(np.linalg.norm(lab(pp)-base,axis=2).mean());orig_sat=np.any((pp==0)|(pp==255),axis=2);eligible=[]
    for k in range(81):
        scale=k/20;out,fallback=at_scale(pp,nn,scale);actual=float(np.linalg.norm(lab(out)-base,axis=2).mean());err=abs(actual-target);back=float(100*fallback.mean());sat=float(100*(np.any((out==0)|(out==255),axis=2)&~orig_sat).mean());distinct=float(100*(out!=pp).any(2).mean())
        if err<=.5 and back<=20 and sat<=1 and distinct>=10:eligible.append((err,back,scale,actual,sat,distinct))
    if not eligible:return pos.copy(),{'matched':False,'target_delta_e':target,'fallback_to_original':True}
    err,back,scale,actual,sat,distinct=min(eligible,key=lambda x:(x[0],x[1],x[2]));full,fb=at_scale(pos,neg,scale);core_actual=float(np.linalg.norm(lab(full)-lab(neg),axis=2)[core].mean());assert abs(core_actual-actual)<1e-4 and abs(100*fb[core].mean()-back)<1e-6
    return full,{'matched':True,'target_delta_e':target,'actual_delta_e':actual,'absolute_error':err,'scale':scale,'fallback_core_pct':back,'new_saturated_core_pct':sat,'distinct_core_pct':distinct,'fallback_to_original':False}

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','original','mixed','lab-dev','provenance','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    orig=validate_manifest(a.original/'manifest.json',allow_synthetic=True);old={mode:validate_manifest(path/'manifest.json',allow_synthetic=True) for mode,path in [('mixed',a.mixed),('lab-dev',a.lab_dev)]};assert all(d['synthetic'] and d['counts']=={'train':384,'validation':320,'test':64} for d in [orig,*old.values()]);prov=json.loads(a.provenance.read_text());selected={x['pair_id'] for x in prov['train']};assert len(selected)==96
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);original_pairs=defaultdict(dict)
    for item in orig['items']:
        if item['split'] in ('train','validation'):original_pairs[(item['split'],item['pair_id'])][item['pair_kind']]=item
    stats={};manifests={}
    for mode,base in [('mixed',a.mixed),('lab-dev',a.lab_dev)]:
        root=a.output/mode;root.mkdir();(root/'images').mkdir();(root/'masks').mkdir();doc=copy.deepcopy(old[mode]);rows=[]
        for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
        doc['dataset_review_id']='synthetic-round55-'+mode+'-no-human-review';doc['provenance_note']='Constraint-first program color matching; unresolved images retained as RGB; no human labels.'
        for item in doc['items']:
            for key in ('image','mask'):shutil.copyfile(base/item[key],root/item[key])
            modify=item.get('pair_kind')=='positive' and ((mode=='mixed' and item['split']=='train' and item['pair_id'] in selected) or (mode=='lab-dev' and item['split']=='validation'))
            if not modify:continue
            pair=original_pairs[(item['split'],item['pair_id'])];assert set(pair)=={'positive','negative'};pos=np.asarray(Image.open(a.original/pair['positive']['image']).convert('RGB'));neg=np.asarray(Image.open(a.original/pair['negative']['image']).convert('RGB'));mask=np.asarray(Image.open(a.original/pair['positive']['mask']))
            out,meta=select_image(pos,neg,mask);target=root/item['image'];Image.fromarray(out,'RGB').save(target);item['image_sha256']=sha(target);rows.append({'pair_id':item['pair_id'],'source_sha256':item['source_sha256'],**meta})
        assert len(rows)==(96 if mode=='mixed' else 160);path=root/'manifest.json';path.write_text(json.dumps(doc,indent=2)+'\n');v=validate_manifest(path,allow_synthetic=True);assert v['counts']==orig['counts'];manifests[mode]=v['manifest_sha256'];stats[mode]=rows
        oldbyid={x['id']:x for x in old[mode]['items']};changed_ids={x['pair_id'] for x in rows}
        for item in doc['items']:
            olditem=oldbyid[item['id']];assert item['mask_sha256']==olditem['mask_sha256'];modified=item.get('pair_kind')=='positive' and item.get('pair_id') in changed_ids and ((mode=='mixed' and item['split']=='train') or (mode=='lab-dev' and item['split']=='validation'))
            if not modified:assert item['image_sha256']==olditem['image_sha256']
    fails={m:sum(not row['matched'] for row in rows) for m,rows in stats.items()};passed=all(fails[m]/len(stats[m])<=.05 for m in stats)
    out={'manifests':manifests,'quality_pass':passed,'quality':'deltaE<=0.5, fallback<=20%, new saturation<=1%, distinct>=10%','failure_limit_fraction':.05,'failure_counts':fails,'rows':stats};(a.output/'matching-summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'quality_pass':passed,'failure_counts':fails,'manifests':manifests},indent=2))
if __name__=='__main__':main()
