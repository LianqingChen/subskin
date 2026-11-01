"""Contract checks for visible-negative filtering and matched holdouts."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r20',HERE/'round20_prepare.py');r20=importlib.util.module_from_spec(s);s.loader.exec_module(r20)
class TestRound20(unittest.TestCase):
 def test_visible_negative_is_not_disease_absence(self):
  self.assertTrue(r20.visible_negative(np.array([[1,255]],np.uint8)))
  self.assertFalse(r20.visible_negative(np.array([[1,2]],np.uint8)))
 def test_shared_holdout_hash_mismatch_is_rejected(self):
  base={'items':[{'id':'a','split':'validation','image_sha256':'i','mask_sha256':'m'},{'id':'b','split':'test','image_sha256':'i2','mask_sha256':'m2'}]}
  other={'items':[dict(z) for z in base['items']]};r20.verify_shared_holdout(base,other);other['items'][1]['mask_sha256']='changed'
  with self.assertRaisesRegex(ValueError,'mismatch'):r20.verify_shared_holdout(base,other)
if __name__=='__main__':unittest.main()
