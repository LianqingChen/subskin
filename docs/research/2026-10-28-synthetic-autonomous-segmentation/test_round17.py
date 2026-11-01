"""Offline candidate mapping, excluded pixels, and review policy contracts."""
import importlib.util,sys,unittest
from pathlib import Path
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r17',HERE/'round17.py');r17=importlib.util.module_from_spec(s);s.loader.exec_module(r17)
class TestRound17(unittest.TestCase):
 def test_uncertain_candidate_is_not_lesion(self):
  logits=torch.zeros((1,5,4,4));logits[:,2]=2
  result=r17.candidate_masks(logits)
  self.assertTrue(result['skin'].all());self.assertTrue(result['uncertain'].all());self.assertFalse(result['lesion'].any())
  logits[:,2]=8;result=r17.candidate_masks(logits);self.assertTrue(result['lesion'].all());self.assertFalse(result['uncertain'].any())
 def test_unknown_pixel_not_in_scoring(self):
  truth=np.array([[0,1],[2,255]],np.uint8);mask={'skin':np.array([[0,1],[1,1]],bool),'lesion':np.array([[0,0],[1,1]],bool),'uncertain':np.zeros((2,2),bool),'excluded':np.zeros((2,2),bool)}
  result=r17.metrics(mask,truth);self.assertEqual(result['tp'],1);self.assertEqual(result['fp'],0);self.assertEqual(result['valid_pixel_count'],3);self.assertAlmostEqual(result['area_error_pp'],0)
 def test_unreviewed_policy_blocks_measurement(self):
  sys.path.insert(0,str(HERE.parents[2]))
  from web.backend.services.rgb_segmentation.policy import measure_rgb
  from web.backend.services.rgb_segmentation.images import png_bytes
  rng=np.random.default_rng(12);rgb=rng.integers(30,220,(64,64,3),dtype=np.uint8);skin=np.ones((64,64),bool);empty=np.zeros_like(skin)
  d=measure_rgb(rgb,{'skin':skin,'lesion':empty.copy(),'uncertain':empty.copy(),'excluded':empty.copy()},png_bytes(rgb),reviewed=False)
  self.assertIn('USER_REVIEW_REQUIRED',d['blocking_reasons']);self.assertIsNone(d['measurement']['area_percentage'])
if __name__=='__main__':unittest.main()
