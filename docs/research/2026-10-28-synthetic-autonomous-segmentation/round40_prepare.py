"""Build equal-sized paired datasets differing only in extra source diversity."""
import argparse,copy,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
import round29_prepare as gen

SOURCES={'old':{'arm':['train8-arm.png','train24-arm.png'],'hand':['train9-hand.png','train24-hand.png']},'diverse':{'arm':[f'test{x}-arm.png' for x in (20,21,22,28)],'hand':[f'test{x}-hand.png' for x in (20,21,22,28)]}}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','base','images','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));from ml.rgb_segmentation.dataset import validate_manifest
    base=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert base['synthetic'] and base['counts']=={'train':192,'validation':32,'test':64}
    forbidden={i['source_sha256'] for i in base['items'] if i['split'] in ('validation','test')};allfiles=[n for d in SOURCES.values() for names in d.values() for n in names];hashes={n:sha(a.images/n) for n in allfiles};assert len(set(hashes.values()))==12 and forbidden.isdisjoint(hashes.values())
    original_train={i['source_sha256'] for i in base['items'] if i['split']=='train'};assert original_train=={hashes[n] for names in SOURCES['old'].values() for n in names}
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('nonempty output')
    a.output.mkdir(parents=True,exist_ok=True);docs={};roots={};src={}
    for n in allfiles:
        path=a.images/n;src[n]=gen.r9.r8.source(path) if '-arm' in n else gen.r9.hand_source(path)
    for mode in ('old','diverse'):
        root=a.output/mode;root.mkdir();(root/'images').mkdir();(root/'masks').mkdir();doc=copy.deepcopy(base)
        for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
        doc['dataset_review_id']='synthetic-round40-'+mode+'-no-human-review';doc['provenance_note']='AI-generated bases and program masks, no human review, research only.'
        for item in base['items']:
            for key in ('image','mask'):shutil.copyfile(a.base/item[key],root/item[key])
        roots[mode]=root;docs[mode]=doc
    common=[]
    for si,site in enumerate(('arm','hand')):
        offset=0
        for j in range(48):
            oldname=SOURCES['old'][site][j//24];newname=SOURCES['diverse'][site][j//12]
            while True:
                seed=4000000+si*100000+offset;offset+=1
                if offset>10000:raise RuntimeError('insufficient jointly valid pairs')
                samples={mode:gen.paired_make(*src[name],seed) for mode,name in [('old',oldname),('diverse',newname)]}
                if all((v[1]==2).any() for v in samples.values()):break
            pair_id=f'extra_{site}_{j:03d}';common.append({'pair_id':pair_id,'seed':seed,'old_source':hashes[oldname],'diverse_source':hashes[newname]})
            for mode,name in [('old',oldname),('diverse',newname)]:
                positive,pm,negative,nm,_=samples[mode];assert not (nm==2).any()
                for kind,image,mask in [('positive',positive,pm),('negative',negative,nm)]:
                    iid=f'image_train_{pair_id}_{kind}';ip=roots[mode]/'images'/(iid+'.png');mp=roots[mode]/'masks'/(iid+'.png')
                    Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(ip);Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(mp)
                    docs[mode]['items'].append({'id':iid,'subject_id':'subject_'+hashes[name][:16],'split':'train','image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':hashes[name],'generator_seed':seed,'pair_id':pair_id,'pair_kind':kind})
    result={'source_sha256':hashes,'shared_extra_seeds':common,'groups':{}}
    for mode in ('old','diverse'):
        path=roots[mode]/'manifest.json';path.write_text(json.dumps(docs[mode],indent=2)+'\n');v=validate_manifest(path,allow_synthetic=True);assert v['counts']=={'train':384,'validation':32,'test':64}
        pairs={}
        for item in v['items']:
            if item['split']=='train':pairs.setdefault(item['pair_id'],[]).append(item)
        assert len(pairs)==192 and all(len(x)==2 and {y['pair_kind'] for y in x}=={'positive','negative'} for x in pairs.values())
        result['groups'][mode]={'manifest_sha256':v['manifest_sha256'],'train_sources':len({x['source_sha256'] for x in v['items'] if x['split']=='train'})}
    for split in ('validation','test'):
        ident=lambda d:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==split]
        assert ident(docs['old'])==ident(docs['diverse'])
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['groups'],indent=2),flush=True)
if __name__=='__main__':main()
