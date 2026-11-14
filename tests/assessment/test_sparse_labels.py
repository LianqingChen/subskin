import numpy as np
import pytest
from ml.rgb_segmentation.sparse_labels import rasterize_partial_polygons


def poly(label, left, right):
    return {"class_id": label, "points": [[left, 1], [right, 1], [right, 4], [left, 4]]}


def test_uncovered_pixels_are_unknown_not_background_or_healthy():
    result = rasterize_partial_polygons(12, 8, [poly(2, 2, 5)])
    assert result[2, 3] == 2 and result[6, 10] == 255
    assert set(np.unique(result)) == {2, 255}


def test_only_explicit_background_is_zero_and_overlap_is_ignored():
    result = rasterize_partial_polygons(12, 8, [poly(0, 1, 3), poly(1, 5, 8), poly(2, 7, 10)])
    assert result[2, 2] == 0 and result[2, 6] == 1 and result[2, 9] == 2
    assert result[2, 7] == 255 and result[7, 7] == 255


def test_same_class_union_and_conflicts_are_order_independent():
    annotations = [poly(2, 1, 5), poly(2, 3, 7), poly(1, 6, 9)]
    result = rasterize_partial_polygons(12, 8, annotations)
    assert result[2, 4] == 2 and result[2, 6] == 255
    assert np.array_equal(result, rasterize_partial_polygons(12, 8, annotations[::-1]))


def test_empty_annotations_do_not_create_a_negative_example():
    assert (rasterize_partial_polygons(12, 8, []) == 255).all()


@pytest.mark.parametrize("annotation", [
    {"class_id": 4, "points": [[1,1],[4,1],[4,4]]},
    {"class_id": 2, "points": [[1,1],[float('nan'),1],[4,4]]},
    {"class_id": 2, "points": [[-1,1],[4,1],[4,4]]},
    {"class_id": 2, "points": [[1,1],[2,2],[3,3]]},
])
def test_unusable_annotations_fail_closed(annotation):
    with pytest.raises(ValueError):
        rasterize_partial_polygons(12, 8, [annotation])
