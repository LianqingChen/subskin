"""Build matched-size synthetic data variants, preserving provenance and test split."""
import argparse,copy,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(sp);sp.loader.exec_module(r9)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def visible_negative(mask):
 return not bool(np.any(mask==2))

def verify_shared_holdout(a1,a2):
 for split in ('validation','test'):
  left=[(z['id'],z['image_sha256'],z['mask_sha256']) for z in a1['items'] if z['split']==split]
  right=[(z['id'],z['image_sha256'],z['mask_sha256']) for z in a2['items'] if z['split']==split]
  if left!=right:raise ValueError('validation/test mismatch across variants')
def build(root,mode,base_path,base_doc,images):
 root.mkdir(parents=True);(root/'images').mkdir();(root/'masks').mkdir();doc=copy.deepcopy(base_doc);doc['items']=[];doc['dataset_review_id']='synthetic-provenance-no-human-review-'+mode;doc['provenance_note']='Auto-generated synthetic labels; no human review; offline only; never eligible for registry.'
 for item in base_doc['items']:
  if item['split'] not in ('train','validation'):continue
  for key in ('image','mask'):shutil.copy2(base_path/item[key],root/item[key])
  doc['items'].append(copy.deepcopy(item))
 def make_items(split,site,name,count,start,negative_only=False):
  source=images/name;source_sha=sha(source);subject='subject_'+source_sha[:16];rgb,skin=r9.r8.source(source) if site=='arm' else r9.hand_source(source)
  selected=[];offset=0
  while len(selected)<count:
   if offset>=10000:raise RuntimeError('insufficient negative candidates')
   seed=start+offset;offset+=1;image,mask=r9.r8.make(rgb,skin,seed)
   if negative_only and not visible_negative(mask):continue
   idx=len(selected);prefix='image_'+split+'_'+site+'_'+('extra_'+mode if split=='train' else 'new')+'_'+str(idx).zfill(3);ip=root/'images'/(prefix+'.png');mp=root/'masks'/(prefix+'.png')
   Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(ip);Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(mp)
   item={'id':prefix,'subject_id':subject,'split':split,'image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':source_sha,'generator_seed':seed}
   selected.append(item)
  doc['items']+=selected
 for site,name,start in [('arm','train8-arm.png',1800000),('hand','train9-hand.png',1810000)]:make_items('train',site,name,32,start,negative_only=mode=='negative')
 for site,name,start in [('arm','test20-arm.png',2000000),('hand','test20-hand.png',2010000)]:make_items('test',site,name,16,start)
 counts={}
 for split in ('train','validation','test'):
  items=[x for x in doc['items'] if x['split']==split];positive=0;classes=np.zeros(5,dtype='int64');ignored=0;total=0
  for item in items:
   with Image.open(root/item['mask']) as im:a=np.asarray(im)
   positive+=bool((a==2).any());classes+=np.bincount(a[a!=255],minlength=5)[:5];ignored+=int((a==255).sum());total+=a.size
  assert positive>0 and positive<len(items) and (classes>0).all();counts[split]={'images':len(items),'positive':int(positive),'negative':len(items)-int(positive),'classes':classes.tolist(),'ignored_pct':100*ignored/total}
 (root/'manifest.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');(root/'generation-summary.json').write_text(json.dumps(counts,indent=2)+'\n')
 return doc,counts

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--base-dataset',required=True);p.add_argument('--images',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();sys.path.insert(0,a.project_root)
 from ml.rgb_segmentation.dataset import validate_manifest
 base_path=Path(a.base_dataset);base=validate_manifest(base_path/'manifest.json',allow_synthetic=True);assert base['synthetic'] is True
 # Remove validator-only fields so the newly serialized manifest is portable.
 for key in ('root','manifest_sha256','counts','subject_count'):base.pop(key,None)
 images=Path(a.images);existing={x['source_sha256'] for x in base['items'] if x['split'] in ('train','validation')};new={sha(images/x) for x in ('test20-arm.png','test20-hand.png')};assert len(new)==2 and existing.isdisjoint(new)
 out=Path(a.output_dir)
 if out.exists() and any(out.iterdir()):raise ValueError('output must be empty')
 out.mkdir(parents=True,exist_ok=True);result={}
 for mode in ('control','negative'):
  doc,summary=build(out/mode,mode,base_path,base,images);validated=validate_manifest(out/mode/'manifest.json',allow_synthetic=True);assert validated['synthetic'] and validated['counts']=={'train':192,'validation':32,'test':32};result[mode]={'summary':summary,'manifest_sha256':validated['manifest_sha256']}
 a1=json.loads((out/'control'/'manifest.json').read_text());a2=json.loads((out/'negative'/'manifest.json').read_text())
 verify_shared_holdout(a1,a2)
 (out/'build-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
