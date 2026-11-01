"""Registration quality-gate and denominator checks on artificial arrays."""
import importlib.util
from pathlib import Path
import unittest
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r14',HERE/'round14.py');r14=importlib.util.module_from_spec(s);s.loader.exec_module(r14)
class TestRound14(unittest.TestCase):
 def test_flat_input_is_rejected(self):
  im=np.full((256,512,3),128,np.uint8);_,status=r14.feature_align(im,im,np.ones((256,512),bool),1)
  self.assertFalse(status['success']);self.assertEqual(status['reason'],'insufficient_descriptors')
 def test_known_affine_direction(self):
  rng=np.random.default_rng(111);g=rng.integers(0,255,(256,512),dtype='uint8');g=cv2.GaussianBlur(g,(0,0),1.)
  src=np.repeat(g[...,None],3,axis=2);expected=cv2.getRotationMatrix2D((256,128),1.5,1.01).astype('float32');expected[:,2]+=[2,-1]
  moved=cv2.warpAffine(src,expected,r14.r11.SIZE,borderMode=cv2.BORDER_REFLECT);core=np.zeros((256,512),bool);core[20:-20,20:-20]=True
  _,status=r14.feature_align(src,moved,core,5);self.assertTrue(status['success']);self.assertLess(r14.r13.p95_delta(status['matrix'],expected,core),2.)
 def test_coverage_and_accepted_risk(self):
  rows=[{'methods':{'m':{'accepted':True,'geometry_bad_if_accepted':True,'known_lesion_scores':{'small_recall':0},'control_right_fp_pct':1}}},{'methods':{'m':{'accepted':False}}},{'methods':{'m':{'accepted':True,'geometry_bad_if_accepted':False,'known_lesion_scores':{'small_recall':1},'control_right_fp_pct':0}}}]
  result=r14.summary(rows,'m');self.assertEqual(result['accepted'],2);self.assertEqual(result['bad_among_accepted_pct'],50);self.assertEqual(result['accepted_low_small_recall'],1)
if __name__=='__main__':unittest.main()
