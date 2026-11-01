"""Build controlled synthetic contrast ladder with automatic intervention masks."""
import argparse,copy,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r29',HERE/'round29_prepare.py');r29=importlib.util.module_from_spec(spec);spec.loader.exec_module(r29)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def interpolate(clean,positive,scale):
    if not 0<=scale<=1:raise ValueError('invalid scale')
    if clean.shape!=positive.shape:raise ValueError('shape mismatch')
    return np.clip(clean+(positive-clean)*scale,0,1).astype('float32')

def delta_e(rgb,clean,mask):
    if not (mask==2).any():raise ValueError('empty lesion core')
    a=cv2.cvtColor(rgb.astype('float32')/255,cv2.COLOR_RGB2LAB);b=cv2.cvtColor(clean.astype('float32')/255,cv2.COLOR_RGB2LAB)
    return float(np.linalg.norm(a-b,axis=2)[mask==2].mean())

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','images','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    base=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert base['synthetic']
    sources=[('arm','test33-arm.png'),('hand','test33-hand.png')];newsrc={sha(a.images/name) for _,name in sources};assert len(newsrc)==2 and newsrc.isdisjoint({x['source_sha256'] for x in base['items']})
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();doc=copy.deepcopy(base)
    for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
    doc['items']=[];doc['dataset_review_id']='synthetic-contrast-ladder-no-human-review';doc['provenance_note']='Program intervention masks, not medical truth, no human labeling.'
    for it in base['items']:
        if it['split'] not in ('train','validation'):continue
        for key in ('image','mask'):shutil.copyfile(a.base/it[key],a.output/it[key])
        doc['items'].append(copy.deepcopy(it))
    deltas=[]
    for idx,(site,name) in enumerate(sources):
        source=a.images/name;source_sha=sha(source);rgb,skin=r29.r9.r8.source(source) if site=='arm' else r29.r9.hand_source(source);count=0;offset=0
        while count<8:
            seed=3300000+idx*10000+offset;offset+=1
            if offset>10000:raise RuntimeError('not enough nonempty lesions')
            pos,pm,neg,nm,foot=r29.paired_make(rgb,skin,seed)
            if not (pm==2).any():continue
            pair=f'p{idx}_{count:03d}';scaled=[]
            for scale in (0,.25,.5,1):
                label=nm if scale==0 else pm;arr=interpolate(neg,pos,scale);img=np.asarray(Image.fromarray((arr*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR));mask=np.asarray(Image.fromarray(label,'L').resize((128,128),Image.Resampling.NEAREST));scaled.append((scale,img,mask))
            clean=scaled[0][1]
            for scale,img,mask in scaled:
                iid=f'image_test_{site}_{pair}_c{int(scale*100):03d}';ip=a.output/'images'/(iid+'.png');mp=a.output/'masks'/(iid+'.png');Image.fromarray(img).save(ip);Image.fromarray(mask).save(mp)
                item={'id':iid,'subject_id':'subject_'+source_sha[:16],'split':'test','image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera','contrast':str(int(scale*100))},'source_sha256':source_sha,'generator_seed':seed,'pair_id':pair,'contrast_scale':scale}
                doc['items'].append(item)
                if scale>0:deltas.append({'id':iid,'site':site,'pair_id':pair,'scale':scale,'delta_e76_mean_core':delta_e(img,clean,mask)})
            count+=1
    (a.output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');valid=validate_manifest(a.output/'manifest.json',allow_synthetic=True);assert valid['counts']=={'train':192,'validation':32,'test':64}
    summary={'manifest_sha256':valid['manifest_sha256'],'deltas':deltas};(a.output/'contrast.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'manifest_sha256':valid['manifest_sha256'],'count':len(deltas),'delta_e_by_scale':{str(s):float(np.mean([x['delta_e76_mean_core'] for x in deltas if x['scale']==s])) for s in (.25,.5,1)}},indent=2))
if __name__=='__main__':main()
