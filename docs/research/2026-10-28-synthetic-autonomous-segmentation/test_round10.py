"""Loss masking, boundary metric and source separation checks."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r10',HERE/'round10.py');r10=importlib.util.module_from_spec(s);s.loader.exec_module(r10)
class TestRound10(unittest.TestCase):
 def test_dice_ignores_all_unlabeled(self):
  logits=torch.randn(2,5,8,8,requires_grad=True);truth=torch.full((2,8,8),255,dtype=torch.long)
  loss=r10.lesion_dice_loss(logits,truth);loss.backward()
  self.assertTrue(torch.isfinite(loss));self.assertTrue(torch.all(logits.grad==0))
 def test_boundary_perfect_and_empty(self):
  truth=torch.zeros((2,8,8),dtype=torch.long);truth[:,2:6,2:6]=2
  result=r10.boundary_score(truth.numpy().copy(),truth);self.assertEqual(result['n_evaluable'],2);self.assertGreater(result['f1_mean'],.999)
  result=r10.boundary_score(np.zeros_like(truth.numpy()),truth);self.assertEqual(result['f1_mean'],0)
 def test_generated_sources_disjoint(self):
  names=('train8-arm.png','train9-hand.png','test10-arm.png','test10-hand.png');paths=[HERE/'generated'/z for z in names]
  self.assertEqual(len({r10.r3.digest(p) for p in paths}),4)
  for p in (paths[0],paths[2]):r10.r8.source(p)
  for p in (paths[1],paths[3]):r10.r9.hand_source(p)
if __name__=='__main__':unittest.main()
