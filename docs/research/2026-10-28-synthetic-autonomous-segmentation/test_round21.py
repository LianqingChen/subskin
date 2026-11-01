"""Validation gate must reject all-background and incomplete evaluations."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r21',HERE/'round21.py');r21=importlib.util.module_from_spec(s);s.loader.exec_module(r21)
class TestRound21(unittest.TestCase):
 def row(self,t,fp,rec,dice,processed=32):return {'threshold':t,'summary':{'total':32,'processed':processed,'negative_count':7,'positive_count':25,'false_positive_image_rate':fp,'mean_positive_recall':rec,'mean_positive_dice':dice}}
 def test_empty_prediction_not_a_valid_threshold(self):
  self.assertIsNone(r21.select_threshold([self.row(.9,0.,0.,0.)]));self.assertIsNone(r21.select_threshold([self.row(.8,0.,.9,.9,processed=31)]))
 def test_selects_only_valid_and_breaks_tie_high(self):
  rows=[self.row(.2,.3,.8,.9),self.row(.3,.1,.2,.9),self.row(.4,.1,.4,.5),self.row(.5,.1,.4,.5)]
  self.assertEqual(r21.select_threshold(rows),.5)
 def test_ignored_ground_truth_not_scored(self):
  y=np.array([[0,1],[2,255]],np.uint8);mask={'skin':np.array([[0,1],[1,1]],bool),'lesion':np.array([[0,0],[1,1]],bool),'excluded':np.zeros((2,2),bool),'uncertain':np.zeros((2,2),bool)}
  m=r21.metric(mask,y);self.assertAlmostEqual(m['dice'],1);self.assertAlmostEqual(m['area_error_pp'],0)
if __name__=='__main__':unittest.main()
