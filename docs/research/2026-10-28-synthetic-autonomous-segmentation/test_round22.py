"""Synthetic lesion Dice loss masking and gradients."""
import importlib.util
from pathlib import Path
import unittest
import torch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r22',HERE/'round22_run.py');r22=importlib.util.module_from_spec(s);s.loader.exec_module(r22)
class TestRound22(unittest.TestCase):
 def test_no_positive_has_zero_extra_loss_and_gradient(self):
  x=torch.randn((2,5,8,8),requires_grad=True);y=torch.full((2,8,8),255,dtype=torch.long);loss=r22.lesion_dice_extra(x,y);loss.backward();self.assertTrue(torch.isfinite(loss));self.assertEqual(float(loss.detach()),0);self.assertTrue(torch.all(x.grad==0))
 def test_ignore_pixel_does_not_change_loss(self):
  y=torch.zeros((1,8,8),dtype=torch.long);y[:,2:4,2:4]=2;y[:,0,0]=255;x=torch.zeros((1,5,8,8));z=x.clone();z[:,:,0,0]=100
  self.assertAlmostEqual(float(r22.lesion_dice_extra(x,y)),float(r22.lesion_dice_extra(z,y)),places=6)
 def test_higher_true_lesion_probability_reduces_loss(self):
  y=torch.zeros((1,8,8),dtype=torch.long);y[:,2:4,2:4]=2;x=torch.zeros((1,5,8,8));z=x.clone();z[:,2,2:4,2:4]=8
  self.assertLess(float(r22.lesion_dice_extra(z,y)),float(r22.lesion_dice_extra(x,y)))
if __name__=='__main__':unittest.main()
