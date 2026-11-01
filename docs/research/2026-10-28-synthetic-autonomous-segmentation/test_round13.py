"""Checks the known transform and risk denominator."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import cv2
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r13',HERE/'round13.py');r13=importlib.util.module_from_spec(s);s.loader.exec_module(r13)
class TestRound13(unittest.TestCase):
 def test_transform_composition_and_zero_difference(self):
  before=np.array([[1,0,2],[0,1,-1.5]],float);after=np.array([[2,0,3],[0,2,4]],float);point=np.array([3,5,1.])
  composed=r13.compose(after,before);self.assertTrue(np.allclose(composed@point,after@np.r_[before@point,1.]))
  self.assertEqual(r13.p95_delta(composed,composed,np.ones((10,10),bool)),0)
 def test_opencv_warp_direction_on_known_texture(self):
  rng=np.random.default_rng(17);gray=rng.integers(0,255,(256,512),dtype='uint8');gray=cv2.GaussianBlur(gray,(0,0),1)
  src=np.repeat(gray[...,None],3,axis=2);expected=np.array([[1,0,2],[0,1,-1]],np.float32)
  moved=cv2.warpAffine(src,expected,r13.r11.SIZE,borderMode=cv2.BORDER_REFLECT)
  core=np.zeros((256,512),bool);core[20:-20,20:-20]=True
  _,info=r13.r11.align(src,moved,core);self.assertTrue(info['success']);self.assertLess(r13.p95_delta(info['matrix'],expected,core),.1)
 def test_coverage_and_bad_denominator(self):
  rows=[{'dual_accepted':True,'affine_bad':True,'lesion_scores':{'small_recall':0.}},{'dual_accepted':False,'affine_bad':True,'lesion_scores':None},{'dual_accepted':True,'affine_bad':False,'lesion_scores':{'small_recall':1.}}]
  s=r13.summarize(rows,'dual_accepted');self.assertEqual(s['accepted'],2);self.assertEqual(s['bad_total'],2);self.assertEqual(s['bad_rejection_pct'],50);self.assertEqual(s['bad_among_accepted_pct'],50);self.assertEqual(s['accepted_low_small_recall_count'],1)
if __name__=='__main__':unittest.main()
