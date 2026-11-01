"""Ensure explicit synthetic opt-in and split isolation remain enforced."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[2]))
from ml.rgb_segmentation.dataset import validate_manifest,LABELS
class TestSyntheticManifest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);items=[]
  for i,split in enumerate(('train','validation','test')):
   image=self.root/f'i{i}.png';mask=self.root/f'm{i}.png';Image.fromarray(np.full((8,8,3),50+i,np.uint8)).save(image);Image.fromarray(np.ones((8,8),np.uint8)).save(mask)
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
   items.append({'id':f'image_{i}','subject_id':'subject_'+str(i).zfill(8),'split':split,'image':image.name,'mask':mask.name,'image_sha256':sha(image),'mask_sha256':sha(mask),'review_reference':'synthetic-generator-no-human-review','groups':{'body_site':'unknown','skin_tone':'unknown','lighting':'unknown','quality':'unknown','device':'not_a_camera'}})
  self.doc={'labels':LABELS,'coordinate_frame':'normalized_rgb','synthetic':True,'authorization':{'training':True,'reference':'synthetic-research'},'dataset_review_id':'synthetic-provenance-no-human-review','items':items};self.path=self.root/'manifest.json'
 def tearDown(self):self.tmp.cleanup()
 def save(self):self.path.write_text(json.dumps(self.doc))
 def test_synthetic_needs_explicit_opt_in(self):
  self.save()
  with self.assertRaisesRegex(ValueError,'Synthetic dataset requires'):validate_manifest(self.path)
  result=validate_manifest(self.path,allow_synthetic=True);self.assertTrue(result['synthetic']);self.assertEqual(result['counts'],{'train':1,'validation':1,'test':1})
 def test_subject_cannot_cross_splits(self):
  self.doc['items'][2]['subject_id']=self.doc['items'][0]['subject_id'];self.save()
  with self.assertRaisesRegex(ValueError,'Subject leakage'):validate_manifest(self.path,allow_synthetic=True)
if __name__=='__main__':unittest.main()
