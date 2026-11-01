"""Research-only MediaPipe confidence shape normalization checks."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r18shim',HERE/'round18-shim.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fake:
 def __init__(self,a):self.a=a
 def numpy_view(self):return self.a
class TestShim(unittest.TestCase):
 def test_2d_and_singleton_are_equivalent(self):
  a=np.arange(12).reshape(3,4);result=m.research_stack_2d([Fake(a),Fake(a[...,None])]);self.assertEqual(result.shape,(3,4,2));self.assertTrue(np.array_equal(result[:,:,0],result[:,:,1]))
 def test_multichannel_rejected(self):
  with self.assertRaises(ValueError):m.research_stack_2d([Fake(np.zeros((3,4,2)))])
if __name__=='__main__':unittest.main()
