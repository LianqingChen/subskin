"""Programmatic intervention and candidate semantics checks."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r18',HERE/'round18.py');r18=importlib.util.module_from_spec(s);s.loader.exec_module(r18)
class TestRound18(unittest.TestCase):
 def test_intervention_repeat_and_scope(self):
  rgb=np.full((128,128,3),[150,110,80],dtype=np.uint8);core=np.ones((128,128),bool)
  a,truth,meta=r18.intervention(rgb,core,10,.2);b,truth2,meta2=r18.intervention(rgb,core,10,.2)
  self.assertTrue(np.array_equal(a,b) and np.array_equal(truth,truth2));self.assertEqual(meta,meta2);self.assertTrue(truth.any());self.assertTrue(np.all(a[truth]>=rgb[truth]))
 def test_unconstructible_and_coverage(self):
  rgb=np.zeros((128,128,3),np.uint8);self.assertIsNone(r18.intervention(rgb,np.zeros((128,128),bool),1,.2))
  truth=np.array([[True,True],[False,False]]);mask=np.array([[True,False],[True,False]])
  self.assertEqual(r18.coverage(mask,truth),.5);self.assertIsNone(r18.coverage(mask,np.zeros_like(truth)))
 def test_uncertain_not_formal_lesion(self):
  logits=torch.zeros((1,5,4,4));logits[:,2]=2;out=r18.candidate_masks(logits,(8,8))
  self.assertTrue(out['uncertain'].all());self.assertFalse(out['lesion'].any())
if __name__=='__main__':unittest.main()
