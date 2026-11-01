"""Checks known synthetic small lesion accounting and mask operations."""
import importlib.util
from pathlib import Path
import unittest
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r12',HERE/'round12.py');r12=importlib.util.module_from_spec(s);s.loader.exec_module(r12)
class TestRound12(unittest.TestCase):
 def test_largest_removes_separate_small_component(self):
  a=np.zeros((64,64),np.uint8);b=a.copy();cv2.circle(a,(18,32),8,1,-1);cv2.circle(b,(48,32),2,1,-1)
  big=a.astype(bool);small=b.astype(bool);valid=np.ones_like(big,bool);both=big|small
  x=r12.score(both,big,small,valid);y=r12.score(r12.largest(both),big,small,valid)
  self.assertEqual(x['big_recall'],1);self.assertEqual(x['small_recall'],1);self.assertEqual(y['big_recall'],1);self.assertEqual(y['small_recall'],0)
 def test_empty_prediction_has_no_precision(self):
  z=np.zeros((64,64),bool);self.assertIsNone(r12.score(z,z,z,~z)['precision']);self.assertFalse(r12.largest(z).any())
if __name__=='__main__':unittest.main()
