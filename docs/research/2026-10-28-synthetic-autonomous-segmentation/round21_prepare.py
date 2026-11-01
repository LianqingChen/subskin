"""Create new synthetic holdouts, preserving original train/validation sources."""
import argparse,copy,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(s);s.loader.exec_module(r9)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(base,doc,images,out):
 out.mkdir(parents=True);(out/'images').mkdir();(out/'masks').mkdir();result=copy.deepcopy(doc)
 for k in ('root','manifest_sha256','counts','subject_count'):result.pop(k,None)
 result['items']=[];result['provenance_note']='Synthetic generated source and program labels, no human annotation, offline only.'
 for item in doc['items']:
  if item['split'] not in ('train','validation'):continue
  for k in ('image','mask'):shutil.copy2(base/item[k],out/item[k])
  result['items'].append(copy.deepcopy(item))
 for site,name,start in [('arm','test21-arm.png',2100000),('hand','test21-hand.png',2110000)]:
  source=images/name;source_sha=sha(source);subject='subject_'+source_sha[:16];rgb,skin=r9.r8.source(source) if site=='arm' else r9.hand_source(source)
  for i in range(16):
   image,mask=r9.r8.make(rgb,skin,start+i);iid='image_test_'+site+'_r21_'+str(i).zfill(3);ip=out/'images'/(iid+'.png');mp=out/'masks'/(iid+'.png')
   Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(ip);Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(mp)
   result['items'].append({'id':iid,'subject_id':subject,'split':'test','image':'images/'+ip.name,'mask':'masks/'+mp.name,'image_sha256':sha(ip),'mask_sha256':sha(mp),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':source_sha,'generator_seed':start+i})
 test=[x for x in result['items'] if x['split']=='test'];pos=0;ignored=0;total=0;counts=np.zeros(5,dtype='int64')
 for item in test:
  with Image.open(out/item['mask']) as f:m=np.asarray(f)
  pos+=bool((m==2).any());ignored+=int((m==255).sum());total+=m.size;counts+=np.bincount(m[m!=255],minlength=5)[:5]
 assert pos>0 and pos<len(test) and (counts>0).all();(out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return {'images':len(test),'positive':int(pos),'negative':len(test)-int(pos),'ignored_pct':100*ignored/total,'classes':counts.tolist()}

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--base-datasets',required=True);p.add_argument('--images',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();sys.path.insert(0,a.project_root)
 from ml.rgb_segmentation.dataset import validate_manifest
 bases=Path(a.base_datasets);images=Path(a.images);old=[validate_manifest(bases/m/'manifest.json',allow_synthetic=True) for m in ('control','negative')]
 source_hashes={x['source_sha256'] for d in old for x in d['items']};new={sha(images/x) for x in ('test21-arm.png','test21-hand.png')};assert len(new)==2 and source_hashes.isdisjoint(new)
 out=Path(a.output_dir)
 if out.exists() and any(out.iterdir()):raise ValueError('output must be empty')
 out.mkdir(parents=True,exist_ok=True);results={}
 for mode,doc in zip(('control','negative'),old):
  summary=build(bases/mode,doc,images,out/mode);valid=validate_manifest(out/mode/'manifest.json',allow_synthetic=True);assert valid['synthetic'] and valid['counts']=={'train':192,'validation':32,'test':32};results[mode]={'manifest_sha256':valid['manifest_sha256'],'test':summary}
 docs=[json.loads((out/x/'manifest.json').read_text()) for x in ('control','negative')]
 for split in ('validation','test'):
  identity=lambda d:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==split]
  assert identity(docs[0])==identity(docs[1])
 (out/'build-summary.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2),flush=True)
if __name__=='__main__':main()
