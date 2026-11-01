"""Build source-separated synthetic validation set without human labels."""
import argparse,copy,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
import round29_prepare as gen

SOURCES=[(site,f'test{n}-{site}.png') for n in (10,19,33,34,37) for site in ('arm','hand')]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','images','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    old=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert old['synthetic'] and old['counts']=={'train':384,'validation':32,'test':64}
    srcs={name:sha(a.images/name) for _,name in SOURCES};forbidden={i['source_sha256'] for i in old['items'] if i['split'] in ('train','test')};assert len(set(srcs.values()))==10 and forbidden.isdisjoint(srcs.values())
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'images').mkdir();(a.output/'masks').mkdir();doc=copy.deepcopy(old)
    for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
    doc['items']=[];doc['dataset_review_id']='synthetic-round42-multisource-validation-no-human-review';doc['provenance_note']='Program synthetic masks, development validation sources previously observed, no human review.'
    for item in old['items']:
        if item['split']=='validation':continue
        for key in ('image','mask'):shutil.copyfile(a.base/item[key],a.output/item[key])
        doc['items'].append(copy.deepcopy(item))
    provenance=[]
    for idx,(site,name) in enumerate(SOURCES):
        source=a.images/name;h=srcs[name];rgb,skin=gen.r9.r8.source(source) if site=='arm' else gen.r9.hand_source(source);offset=0;count=0
        while count<8:
            seed=4200000+idx*10000+offset;offset+=1
            if offset>10000:raise RuntimeError('not enough paired examples')
            positive,pm,negative,nm,_=gen.paired_make(rgb,skin,seed)
            if not (pm==2).any():continue
            assert not (nm==2).any();pair=f'v{idx}_{count:02d}'
            for kind,image,mask in [('positive',positive,pm),('negative',negative,nm)]:
                iid=f'image_validation_{site}_{pair}_{kind}';ip=a.output/'images'/(iid+'.png');mp=a.output/'masks'/(iid+'.png');Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(ip);Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(mp)
                doc['items'].append({'id':iid,'subject_id':'subject_'+h[:16],'split':'validation','image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':h,'generator_seed':seed,'pair_id':pair,'pair_kind':kind})
            provenance.append({'pair_id':pair,'source_sha256':h,'seed':seed});count+=1
    path=a.output/'manifest.json';path.write_text(json.dumps(doc,indent=2)+'\n');valid=validate_manifest(path,allow_synthetic=True);assert valid['counts']=={'train':384,'validation':160,'test':64}
    ident=lambda d,s:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==s]
    for split in ('train','test'):assert ident(old,split)==ident(doc,split)
    result={'manifest_sha256':valid['manifest_sha256'],'base_manifest_sha256':old['manifest_sha256'],'validation_sources':srcs,'validation_positive':80,'validation_negative':80,'pairs':provenance};(a.output/'validation-provenance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'manifest_sha256':valid['manifest_sha256'],'validation_sources':len(srcs),'positive':80,'negative':80},indent=2))
if __name__=='__main__':main()
