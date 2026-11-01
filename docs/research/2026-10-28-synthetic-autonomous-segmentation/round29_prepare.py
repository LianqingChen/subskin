"""Create fully synthetic paired counterfactuals and unchanged validation/test."""
import argparse,copy,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(sp);sp.loader.exec_module(r9)


def paired_make(rgb,skin,seed):
    """Replay original RNG and make a clean twin sharing all later occlusions."""
    import cv2
    rng=np.random.default_rng(seed);aff=cv2.getRotationMatrix2D((31.5,31.5),float(rng.uniform(-15,15)),float(rng.uniform(.85,1.05)))
    aff[:,2]+=rng.uniform(-3,3,2)
    face=cv2.warpAffine(rgb,aff,(64,64),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,180,250)).astype('float32')/255
    mask=cv2.warpAffine(skin.astype('uint8'),aff,(64,64),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT).astype(bool)
    edge=cv2.morphologyEx(mask.astype('uint8'),cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8)).astype(bool)
    noise=cv2.resize(rng.normal(0,.025,(8,8)).astype('float32'),(64,64),interpolation=cv2.INTER_CUBIC);base=rng.uniform(.10,.82,3).astype('float32')
    bg=np.clip(base+noise[...,None],0,1);img=np.where(mask[...,None],face,bg);label=np.zeros((64,64),np.uint8);label[mask]=1;label[edge]=255
    clean=img.copy();clean_label=label.copy();lesion_footprint=np.zeros((64,64),dtype=bool)
    if rng.random()>.3:
        eligible=np.argwhere(mask&~edge)
        if len(eligible):
            cy,cx=eligible[int(rng.integers(len(eligible)))];rad=float(rng.uniform(3,10));angles=np.linspace(0,2*np.pi,17,endpoint=False);radii=rad*rng.uniform(.65,1.35,len(angles))
            pts=np.stack([cx+radii*np.cos(angles),cy+radii*np.sin(angles)],1).astype('int32');blob=np.zeros((64,64),np.uint8);cv2.fillPoly(blob,[pts],1)
            alpha=cv2.GaussianBlur(blob.astype('float32'),(0,0),float(rng.uniform(.7,1.5)))*mask
            strength=float(rng.uniform(.12,.35));img+=alpha[...,None]*strength*(1-img);lesion_footprint=alpha>0
            label[(alpha>=.8)&mask&~edge]=2;label[(alpha>.2)&(alpha<.8)&mask&~edge]=255
    if rng.random()<.65:
        x=int(rng.integers(5,45));y=int(rng.integers(5,45));w=int(rng.integers(7,17));h=int(rng.integers(7,17));occ=np.zeros((64,64),np.uint8)
        cv2.rectangle(occ,(x,y),(min(63,x+w),min(63,y+h)),1,-1);occ=occ.astype(bool);color=rng.uniform(.02,.32,3);img[occ]=color;clean[occ]=color;label[occ]=3;clean_label[occ]=3
    if rng.random()<.65:
        q=np.zeros((64,64),np.uint8);cv2.ellipse(q,(int(rng.integers(12,52)),int(rng.integers(12,52))),(int(rng.integers(4,10)),int(rng.integers(4,10))),float(rng.uniform(0,180)),0,360,1,-1)
        q=q.astype(bool)&mask&(label!=3)&(label!=255);color=rng.uniform(.94,1.0);img[q]=color;clean[q]=color;label[q]=4;clean_label[q]=4
    positive=np.clip(img,0,1).astype('float32');negative=np.clip(clean,0,1).astype('float32')
    assert np.array_equal(positive[~lesion_footprint],negative[~lesion_footprint])
    assert np.array_equal(label==3,clean_label==3) and np.array_equal(label==4,clean_label==4)
    original,original_label=r9.r8.make(rgb,skin,seed)
    assert np.array_equal(positive,original) and np.array_equal(label,original_label)
    return positive,label,negative,clean_label,lesion_footprint


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','images','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    doc=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':192,'validation':32,'test':32}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();new=copy.deepcopy(doc)
    for k in ('root','manifest_sha256','counts','subject_count'):new.pop(k,None)
    new['items']=[];new['dataset_review_id']='synthetic-paired-no-human-review';new['provenance_note']='Synthetic counterfactual pair with automatic labels; no human review; offline only.'
    for item in doc['items']:
        if item['split'] not in ('validation','test'):continue
        for key in ('image','mask'):shutil.copyfile(a.base/item[key],a.output/item[key])
        new['items'].append(copy.deepcopy(item))
    used={x['source_sha256'] for x in doc['items'] if x['split']=='train'};sources=[('arm','train8-arm.png'),('hand','train9-hand.png'),('arm','train24-arm.png'),('hand','train24-hand.png')];assert {sha(a.images/n) for _,n in sources}==used
    for idx,(site,name) in enumerate(sources):
        src=a.images/name;source=sha(src);rgb,skin=r9.r8.source(src) if site=='arm' else r9.hand_source(src);count=0;offset=0
        while count<24:
            seed=2900000+idx*10000+offset;offset+=1
            if offset>10000:raise RuntimeError('insufficient pairs')
            pos,pm,neg,nm,foot=paired_make(rgb,skin,seed)
            if not (pm==2).any():continue
            assert not (nm==2).any();pair=f'pair_{idx}_{count:03d}'
            for kind,image,mask in [('positive',pos,pm),('negative',neg,nm)]:
                iid=f'image_train_{site}_{pair}_{kind}';ip=a.output/'images'/(iid+'.png');mp=a.output/'masks'/(iid+'.png')
                Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(ip);Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(mp)
                new['items'].append({'id':iid,'subject_id':'subject_'+source[:16],'split':'train','image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':source,'generator_seed':seed,'pair_id':pair,'pair_kind':kind})
            count+=1
    (a.output/'manifest.json').write_text(json.dumps(new,indent=2)+'\n');v=validate_manifest(a.output/'manifest.json',allow_synthetic=True);assert v['counts']=={'train':192,'validation':32,'test':32}
    print(json.dumps({'manifest_sha256':v['manifest_sha256'],'train_pairs':96,'positive':96,'negative':96,'counts':v['counts']},indent=2))
if __name__=='__main__':main()
