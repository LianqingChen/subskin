"""Automatically construct small-visible-core synthetic training/validation pairs."""
import argparse,copy,hashlib,json,shutil,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image
import round29_prepare as gen

VAL_SOURCES=[(site,f'test{n}-{site}.png') for n in (10,19,33,34,37) for site in ('arm','hand')]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def write_pair(root,rows,sample,seed):
    pos,pm,neg,nm,_=sample;assert 0<int((pm==2).sum())<=16 and not (nm==2).any()
    for kind,image,mask in [('positive',pos,pm),('negative',neg,nm)]:
        item=rows[kind];ip=root/item['image'];mp=root/item['mask']
        Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(ip);Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(mp)
        item['image_sha256']=sha(ip);item['mask_sha256']=sha(mp);item['generator_seed']=seed

def next_small(rgb,skin,start):
    for offset in range(10000):
        seed=start+offset;sample=gen.paired_make(rgb,skin,seed)
        if 0<int((sample[1]==2).sum())<=16:return seed,sample
    raise RuntimeError('not enough small visible cores')

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','images','source-map','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    old=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert old['synthetic'] and old['counts']=={'train':384,'validation':160,'test':64}
    source_map=json.loads(a.source_map.read_text())['source_sha256'];byhash={h:name for name,h in source_map.items()};train_sources={i['source_sha256'] for i in old['items'] if i['split']=='train'};assert len(train_sources)==12 and train_sources<=set(byhash)
    val_names={sha(a.images/name):name for _,name in VAL_SOURCES};assert len(val_names)==10 and set(val_names)=={i['source_sha256'] for i in old['items'] if i['split']=='validation'}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);docs={};roots={}
    for mode in ('baseline','small'):
        root=a.output/mode;root.mkdir();(root/'images').mkdir();(root/'masks').mkdir();doc=copy.deepcopy(old)
        for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
        doc['dataset_review_id']='synthetic-round47-'+mode+'-no-human-review';doc['provenance_note']='Synthetic visible-core intervention; no human review; not clinical truth.'
        for i in old['items']:
            for k in ('image','mask'):shutil.copyfile(a.base/i[k],root/i[k])
        docs[mode]=doc;roots[mode]=root
    groups=defaultdict(dict)
    for i in docs['small']['items']:
        if i['split']=='train':groups[i['source_sha256']].setdefault(i['pair_id'],{})[i['pair_kind']]=i
    replacements=[]
    for idx,h in enumerate(sorted(groups)):
        pairs=groups[h];name=byhash[h];path=a.images/name;assert sha(path)==h;rgb,skin=gen.r9.r8.source(path) if '-arm' in name else gen.r9.hand_source(path);ordered=sorted(pairs.items());assert len(ordered) in (12,24) and len(ordered)%2==0;start=4700000+idx*100000;offset=0
        for pid,pair in ordered[:len(ordered)//2]:
            assert set(pair)=={'positive','negative'};seed,sample=next_small(rgb,skin,start+offset);offset=seed-start+1;write_pair(roots['small'],pair,sample,seed);replacements.append({'pair_id':pid,'source_sha256':h,'seed':seed,'core_pixels_64':int((sample[1]==2).sum())})
    assert len(replacements)==96
    vals=[]
    for idx,(site,name) in enumerate(VAL_SOURCES):
        path=a.images/name;h=sha(path);rgb,skin=gen.r9.r8.source(path) if site=='arm' else gen.r9.hand_source(path);start=4900000+idx*100000;offset=0
        for j in range(8):
            seed,sample=next_small(rgb,skin,start+offset);offset=seed-start+1;pid=f'smallv{idx}_{j:02d}';pair={}
            for kind in ('positive','negative'):
                iid=f'image_validation_{site}_{pid}_{kind}';pair[kind]={'id':iid,'subject_id':'subject_'+h[:16],'split':'validation','image':'images/'+iid+'.png','mask':'masks/'+iid+'.png','review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':h,'pair_id':pid,'pair_kind':kind}
            write_pair(roots['baseline'],pair,sample,seed)
            for item in pair.values():
                for k in ('image','mask'):shutil.copyfile(roots['baseline']/item[k],roots['small']/item[k])
            for mode in ('baseline','small'):docs[mode]['items']+=copy.deepcopy(list(pair.values()))
            vals.append({'pair_id':pid,'source_sha256':h,'seed':seed,'core_pixels_64':int((sample[1]==2).sum())})
    assert len(vals)==80
    result={'base_manifest_sha256':old['manifest_sha256'],'train_replacements':replacements,'small_validation_pairs':vals,'groups':{}}
    for mode in ('baseline','small'):
        path=roots[mode]/'manifest.json';path.write_text(json.dumps(docs[mode],indent=2)+'\n');v=validate_manifest(path,allow_synthetic=True);assert v['counts']=={'train':384,'validation':320,'test':64};result['groups'][mode]={'manifest_sha256':v['manifest_sha256']}
    ident=lambda d,split:[(i['id'],i['image_sha256'],i['mask_sha256']) for i in d['items'] if i['split']==split]
    for split in ('validation','test'):assert ident(docs['baseline'],split)==ident(docs['small'],split)
    (a.output/'provenance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['groups'],indent=2),flush=True)
if __name__=='__main__':main()
