"""Generate matched-count synthetic research manifests with new source imagery."""
import argparse, copy, hashlib, importlib.util, json, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r9', HERE / 'round9.py')
r9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r9)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--images',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.project_root))
 from ml.rgb_segmentation.dataset import validate_manifest
 base=validate_manifest(a.base/'manifest.json',allow_synthetic=True);assert base['synthetic'] and base['counts']=={'train':192,'validation':32,'test':32}
 files=['train24-arm.png','train24-hand.png','test24-arm.png','test24-hand.png']; hashes={n:sha(a.images/n) for n in files}; assert len(set(hashes.values()))==4
 old={i['source_sha256'] for i in base['items']};assert old.isdisjoint(hashes.values())
 if a.output.exists() and any(a.output.iterdir()):raise ValueError('output must be empty')
 a.output.mkdir(parents=True,exist_ok=True)
 def make(root,split,site,name,count,start):
  path=a.images/name;src=hashes[name];rgb,skin=r9.r8.source(path) if site=='arm' else r9.hand_source(path); items=[]
  for j in range(count):
   image,mask=r9.r8.make(rgb,skin,start+j); iid=f'image_{split}_{site}_r24_{j:03d}';ip=root/'images'/f'{iid}.png';mp=root/'masks'/f'{iid}.png'
   Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(ip);Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(mp)
   items.append({'id':iid,'subject_id':'subject_'+src[:16],'split':split,'image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':src,'generator_seed':start+j})
  return items
 results={}
 for mode in ('control','diverse'):
  root=a.output/mode;root.mkdir();(root/'images').mkdir();(root/'masks').mkdir();doc=copy.deepcopy(base)
  for k in ('root','manifest_sha256','counts','subject_count'):doc.pop(k,None)
  doc['items']=[];doc['dataset_review_id']='synthetic-provenance-no-human-review-'+mode;doc['provenance_note']='Synthetic source and program labels only; no human review.'
  for item in base['items']:
   if item['split'] not in ('train','validation') or (mode=='diverse' and '_extra_control_' in item['id']):continue
   for key in ('image','mask'):shutil.copyfile(a.base/item[key],root/item[key])
   doc['items'].append(copy.deepcopy(item))
  if mode=='diverse':
   for site,name,start in [('arm','train24-arm.png',1800000),('hand','train24-hand.png',1810000)]:doc['items']+=make(root,'train',site,name,32,start)
  for site,name,start in [('arm','test24-arm.png',2400000),('hand','test24-hand.png',2410000)]:doc['items']+=make(root,'test',site,name,16,start)
  (root/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');v=validate_manifest(root/'manifest.json',allow_synthetic=True);assert v['counts']=={'train':192,'validation':32,'test':32}
  counts={}
  for split in ('train','validation','test'):
   its=[x for x in doc['items'] if x['split']==split]; masks=[np.asarray(Image.open(root/x['mask'])) for x in its];pos=sum(bool((x==2).any()) for x in masks);classes=np.bincount(np.concatenate([x[x!=255] for x in masks]),minlength=5)
   assert 0<pos<len(its) and np.all(classes[:5]>0);counts[split]={'positive':pos,'negative':len(its)-pos,'ignored_pct':float(sum((x==255).sum() for x in masks)/sum(x.size for x in masks)*100)}
  results[mode]={'manifest_sha256':v['manifest_sha256'],'counts':counts}
 docs=[json.loads((a.output/m/'manifest.json').read_text()) for m in ('control','diverse')]
 for split in ('validation','test'):
  ident=lambda d:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==split]
  assert ident(docs[0])==ident(docs[1])
 (a.output/'summary.json').write_text(json.dumps({'sources':hashes,'datasets':results},indent=2)+'\n');print(json.dumps(results,indent=2),flush=True)
if __name__=='__main__':main()
