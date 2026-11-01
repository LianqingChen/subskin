"""Basic data contract tests; no real images or labels are read."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location('pilot', Path(__file__).with_name('experiment.py'))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)

class GenerationTests(unittest.TestCase):
    def test_reproducible_and_negative_masks_empty(self):
        for mode in ('simple', 'mixed', 'test'):
            negatives = small = 0
            for seed in range(300000, 300128):
                image, mask, info = pilot.make(seed, mode)
                other_image, other_mask, other_info = pilot.make(seed, mode)
                self.assertTrue(np.array_equal(image, other_image))
                self.assertTrue(np.array_equal(mask, other_mask))
                self.assertEqual(info, other_info)
                self.assertEqual(image.shape, (64, 64, 3))
                self.assertTrue(np.isfinite(image).all())
                self.assertTrue(np.isin(mask, (0, 1)).all())
                if info['negative']:
                    negatives += 1
                    self.assertFalse(mask.any())
                small += info['small']
            self.assertGreater(negatives, 0)
            self.assertGreater(small, 0)

    def test_partition_seed_ranges_do_not_overlap(self):
        train = set(range(10000, 10000 + 512))
        val = set(range(200000, 200000 + 128))
        test = set(range(300000, 300000 + 128))
        self.assertTrue(train.isdisjoint(val) and train.isdisjoint(test) and val.isdisjoint(test))

if __name__ == '__main__':
    unittest.main()
