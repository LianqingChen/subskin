"""Spatial correction and synthetic target contracts, not clinical validation."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r16',HERE/'round16.py');r16=importlib.util.module_from_spec(s);s.loader.exec_module(r16)
class TestRound16(unittest.TestCase):
 def test_known_spatial_slope(self):
  h,w=256,512;yy,xx=np.mgrid[:h,:w];ref=np.full((h,w),120,dtype='float32');mapped=ref-(8*(xx/w-.5)+5*(yy/h-.5)).astype('float32');core=np.ones((h,w),bool)
  corrected,status=r16.spatial_correct(mapped,ref,core);self.assertTrue(status['success']);self.assertLess(float(np.mean(np.abs(corrected-ref))),.1)
 def test_known_masks_and_sources(self):
  paths=[HERE/'generated'/x for x in ('test16-light.png','test16-dark.png')];self.assertNotEqual(r16.r11.checksum(paths[0]),r16.r11.checksum(paths[1]))
  for p in paths:
   src,_=r16.r11.read(p);core=r16.r11.skin_core(src)
   for size in ('medium','large'):
    c,e,b,s,ignore=r16.synth(src,core,24000,size);self.assertTrue(b.any() and s.any());self.assertFalse((b&s).any());self.assertTrue(np.isfinite(e).all())
 def test_gate_uses_candidate_and_control_only(self):
  mask=np.zeros((8,8),bool);info={'control_right_fp_pct':.1}
  self.assertFalse(r16.automatic_gate(mask,info));mask[0,0]=True
  self.assertTrue(r16.automatic_gate(mask,info));self.assertFalse(r16.automatic_gate(mask,{'control_right_fp_pct':.6}))
 def test_empty_accepted_set_is_not_reported_as_zero_error(self):
  result=r16.summary([{'registration_ok':False,'methods':{}}],'spatial');self.assertEqual(result['auto_gate_pass'],0);self.assertIsNone(result['mean_small_recall_all_fit'])
if __name__=='__main__':unittest.main()
