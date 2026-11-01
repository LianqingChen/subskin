"""Photometric fit and degenerate input contracts, not clinical validation."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r15',HERE/'round15.py');r15=importlib.util.module_from_spec(s);s.loader.exec_module(r15)
class TestRound15(unittest.TestCase):
 def test_affine_mapping_with_outlier(self):
  ref=np.tile(np.linspace(40,210,512,dtype='float32'),(256,1));core=np.ones(ref.shape,bool);moving=ref*.6+10;moving[40:60,100:120]+=30
  result,status=r15.fit_map(moving,ref,core,1);self.assertTrue(status['success']);self.assertLess(float(np.mean(np.abs(result[100:]-ref[100:]))),2)
 def test_flat_input_rejected(self):
  x=np.full((256,512),80,dtype='float32');result,status=r15.fit_map(x,x,np.ones(x.shape,bool),1)
  self.assertIsNone(result);self.assertEqual(status['reason'],'insufficient_dynamic_range')
 def test_generated_sources_distinct_and_cores(self):
  paths=[HERE/'generated'/x for x in ('test15-light.png','test15-dark.png')];self.assertNotEqual(r15.r11.checksum(paths[0]),r15.r11.checksum(paths[1]))
  for p in paths:
   img,_=r15.r11.read(p);self.assertGreater(r15.r11.skin_core(img).sum(),0)
if __name__=='__main__':unittest.main()
