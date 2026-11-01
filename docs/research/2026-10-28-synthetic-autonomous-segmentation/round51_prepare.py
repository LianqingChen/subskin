"""Generate matched RGB-vs-Lab synthetic lesion interventions, not medical labels."""
import argparse,copy,hashlib,json,shutil,sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round29_prepare as gen


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def alternate_lab(clean,positive):
    if clean.shape!=positive.shape or clean.ndim!=3 or clean.shape[2]!=3:raise ValueError('invalid paired RGB arrays')
    if not np.isfinite(clean).all() or not np.isfinite(positive).all():raise ValueError('nonfinite images')
    difference=positive-clean;denom=1-clean
    amount=np.clip((difference*denom).sum(axis=2)/(np.square(denom).sum(axis=2)+1e-12),0,1).astype('float32')
    lab=cv2.cvtColor(clean.astype('float32'),cv2.COLOR_RGB2LAB);edited=lab.copy();edited[:,:,0]=lab[:,:,0]+amount*(100-lab[:,:,0]);candidate=cv2.cvtColor(edited,cv2.COLOR_LAB2RGB)
    output=clean.copy();changed=np.any(difference!=0,axis=2);output[changed]=np.clip(candidate[changed],0,1)
    if not np.array_equal(output[~changed],clean[~changed]):raise AssertionError('off-intervention change')
    return output.astype('float32')


def core_color(rgb,clean,mask):
    core=mask==2
    if not core.any():raise ValueError('missing lesion core')
    a=cv2.cvtColor(rgb.astype('float32')/255,cv2.COLOR_RGB2LAB);b=cv2.cvtColor(clean.astype('float32')/255,cv2.COLOR_RGB2LAB)
    return {'delta_e76':float(np.linalg.norm(a-b,axis=2)[core].mean()),'delta_l':float((a[:,:,0]-b[:,:,0])[core].mean()),'saturated_pct':float(100*np.any((rgb==0)|(rgb==255),axis=2)[core].mean())}


def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','images','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    base=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert base['synthetic'] and base['counts']=={'train':384,'validation':320,'test':64}
    sources=[('leg','test51-leg.png'),('hand','test51-hand.png')];newsrc={sha(a.images/name) for _,name in sources};assert len(newsrc)==2 and newsrc.isdisjoint({i['source_sha256'] for i in base['items']})
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();doc=copy.deepcopy(base)
    for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
    doc['items']=[];doc['dataset_review_id']='synthetic-round51-colour-mechanisms-no-human-review';doc['provenance_note']='Paired synthetic interventions; not medically validated; no human labels.'
    for item in base['items']:
        if item['split'] not in ('train','validation'):continue
        for key in ('image','mask'):shutil.copyfile(a.base/item[key],a.output/item[key])
        doc['items'].append(copy.deepcopy(item))
    colors=[]
    for idx,(site,name) in enumerate(sources):
        source=a.images/name;h=sha(source);rgb,skin=gen.r9.hand_source(source) if site=='hand' else gen.r9.r8.source(source);count=0;offset=0
        while count<8:
            seed=5100000+idx*10000+offset;offset+=1
            if offset>10000:raise RuntimeError('insufficient valid lesions')
            positive,pm,negative,nm,_=gen.paired_make(rgb,skin,seed)
            if not (pm==2).any():continue
            lab=alternate_lab(negative,positive);pair=f'p{idx}_{count:03d}';variants=[]
            for mechanism,image,mask in [('none',negative,nm),('rgb',positive,pm),('lab',lab,pm)]:
                arr=np.asarray(Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR));target=np.asarray(Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST));variants.append((mechanism,arr,target))
            clean=variants[0][1]
            for mechanism,image,mask in variants:
                iid=f'image_test_{site}_{pair}_{mechanism}';ip=a.output/'images'/(iid+'.png');mp=a.output/'masks'/(iid+'.png');Image.fromarray(image).save(ip);Image.fromarray(mask).save(mp)
                item={'id':iid,'subject_id':'subject_'+h[:16],'split':'test','image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera','synthesis':mechanism},'source_sha256':h,'generator_seed':seed,'pair_id':pair};doc['items'].append(item)
                if mechanism!='none':colors.append({'pair_id':pair,'site':site,'synthesis':mechanism,**core_color(image,clean,mask)})
            count+=1
    (a.output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');v=validate_manifest(a.output/'manifest.json',allow_synthetic=True);assert v['counts']=={'train':384,'validation':320,'test':48}
    for split in ('train','validation'):
        ident=lambda d:[(i['id'],i['image_sha256'],i['mask_sha256']) for i in d['items'] if i['split']==split]
        assert ident(base)==ident(doc)
    stats={'manifest_sha256':v['manifest_sha256'],'pairs':colors};(a.output/'color-stats.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps({'manifest_sha256':v['manifest_sha256'],'means':{m:{k:float(np.mean([x[k] for x in colors if x['synthesis']==m])) for k in ('delta_e76','delta_l','saturated_pct')} for m in ('rgb','lab')}},indent=2),flush=True)
if __name__=='__main__':main()
