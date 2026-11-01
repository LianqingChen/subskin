"""Build a clearly synthetic manifest with program-generated, not human-reviewed masks."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(sp);sp.loader.exec_module(r9)
LABELS=['background','normal_skin','depigmented_skin','occlusion','unreadable']
SOURCES=[('train','train8-arm.png','arm',64,1500000),('train','train9-hand.png','hand',64,1510000),('validation','test8b-arm.png','arm',16,1600000),('validation','test9-hand.png','hand',16,1610000),('test','test19-arm.png','arm',16,1700000),('test','test19-hand.png','hand',16,1710000)]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--images',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();root=Path(a.output_dir)
 if root.exists() and any(root.iterdir()):raise ValueError('output directory must be empty')
 root.mkdir(parents=True,exist_ok=True);(root/'images').mkdir();(root/'masks').mkdir();imgroot=Path(a.images)
 paths=[imgroot/z[1] for z in SOURCES];hashes=[digest(z) for z in paths];assert len(set(hashes))==len(hashes)
 doc={'labels':LABELS,'coordinate_frame':'normalized_rgb','synthetic':True,'authorization':{'training':True,'reference':'user-requested-synthetic-research-only','expires_at':None},'dataset_review_id':'synthetic-provenance-no-human-review','items':[],'provenance_note':'imagegen fictional backgrounds; program masks; no human annotation; split by generated source hash; never eligible for registry'}
 stats={k:{'images':0,'positive':0,'negative':0,'pixel_counts':[0]*5,'ignored':0,'total_pixels':0} for k in ('train','validation','test')}
 for split,name,site,count,start in SOURCES:
  path=imgroot/name;source_sha=digest(path);subject='subject_'+source_sha[:16];rgb,skin=r9.r8.source(path) if site=='arm' else r9.hand_source(path)
  for offset in range(count):
   seed=start+offset;image,mask=r9.r8.make(rgb,skin,seed);iid='image_'+split+'_'+site+'_'+str(offset).zfill(3)
   imagepath=root/'images'/(iid+'.png');maskpath=root/'masks'/(iid+'.png')
   Image.fromarray((image*255).astype('uint8'),'RGB').resize((128,128),Image.Resampling.BILINEAR).save(imagepath)
   Image.fromarray(mask,'L').resize((128,128),Image.Resampling.NEAREST).save(maskpath)
   labels=np.asarray(Image.open(maskpath));valid=np.isin(labels,[0,1,2,3,4,255]);assert valid.all()
   st=stats[split];st['images']+=1;st['positive']+=int((labels==2).any());st['negative']+=int(not (labels==2).any());st['ignored']+=int((labels==255).sum());st['total_pixels']+=labels.size
   for k in range(5):st['pixel_counts'][k]+=int((labels==k).sum())
   doc['items'].append({'id':iid,'subject_id':subject,'split':split,'image':'images/'+imagepath.name,'mask':'masks/'+maskpath.name,'image_sha256':digest(imagepath),'mask_sha256':digest(maskpath),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':site,'skin_tone':'synthetic_unknown','lighting':'synthetic_generated','quality':'synthetic_unverified','device':'not_a_camera'},'source_sha256':source_sha,'generator_seed':seed})
 for split,st in stats.items():
  assert all(st['pixel_counts']) and st['positive'] and st['negative']
  st['ignored_pct']=100*st['ignored']/st['total_pixels']
 (root/'manifest.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');(root/'generation-summary.json').write_text(json.dumps(stats,indent=2)+'\n')
 print(json.dumps({'manifest':str(root/'manifest.json'),'manifest_sha256':digest(root/'manifest.json'),'summary':stats},indent=2),flush=True)
if __name__=='__main__':main()
