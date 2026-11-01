"""Synthetic stress-set contract checks; no photos or human labels."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location('round2', Path(__file__).with_name('round2.py'))
round2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round2)


class SyntheticTestSetTests(unittest.TestCase):
    def test_masks_counts_and_reproducibility(self):
        negative_count = small_count = 0
        for seed in range(400000, 400128):
            image, mask, info = round2.make_test(seed)
            repeated_image, repeated_mask, repeated_info = round2.make_test(seed)
            self.assertTrue(np.array_equal(image, repeated_image))
            self.assertTrue(np.array_equal(mask, repeated_mask))
            self.assertEqual(info, repeated_info)
            self.assertEqual(image.shape, (64, 64, 3))
            self.assertTrue(np.isfinite(image).all())
            self.assertTrue(np.isin(mask, (0, 1)).all())
            self.assertEqual(bool(mask.any()), not info['negative'])
            negative_count += info['negative']
            small_count += info['small']
        self.assertGreaterEqual(negative_count, 20)
        self.assertGreaterEqual(small_count, 20)

    def test_seed_ranges_are_disjoint(self):
        train, valid, test = set(range(10000, 10512)), set(range(200000, 200128)), set(range(400000, 400128))
        self.assertTrue(train.isdisjoint(valid) and train.isdisjoint(test) and valid.isdisjoint(test))


if __name__ == '__main__':
    unittest.main()
