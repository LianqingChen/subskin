"""Contract tests for paired-difference masks, not clinical validation."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r11',HERE/'round11.py');r11=importlib.util.module_from_spec(s);s.loader.exec_module(r11)
class TestRound11(unittest.TestCase):
 def test_identity_control_and_known_bright_patch(self):
  src=np.zeros((256,512,3),np.uint8);src[:]=[120,85,65];core=np.ones((256,512),bool)
  changed=src.copy();changed[80:120,300:340]=[210,180,160]
  metrics,candidate,control=r11.measure(src,src,changed,core)
  expected=np.zeros(core.shape,bool);expected[80:120,300:340]=True
  self.assertTrue(np.array_equal(candidate,expected));self.assertFalse(control.any());self.assertEqual(metrics['control_right_false_positive_pct'],0)
  self.assertGreater(metrics['candidate_skin_pct'],0)
 def test_input_sources_separate(self):
  paths=[HERE/'generated'/x for x in ('train8-arm.png','round11-control.png','round11-edited.png')]
  self.assertEqual(len({r11.checksum(p) for p in paths}),3)
if __name__=='__main__':unittest.main()
