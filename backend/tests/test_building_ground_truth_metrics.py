from __future__ import annotations

import numpy as np
from shapely.geometry import box

from scripts.building_ground_truth_metrics import object_metrics, pixel_metrics, size_class


def test_pixel_metrics_formulas() -> None:
    predicted = np.array([[1, 1, 0], [0, 0, 0]], dtype=bool)
    reference = np.array([[1, 0, 1], [0, 0, 0]], dtype=bool)
    result = pixel_metrics(predicted, reference)
    assert result["tp_pixels"] == 1
    assert result["fp_pixels"] == 1
    assert result["fn_pixels"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["iou"] == 1 / 3


def test_object_matching_is_one_to_one_and_deterministic() -> None:
    predictions = [box(0, 0, 2, 2), box(10, 10, 12, 12)]
    references = [box(0, 0, 2, 2), box(10, 10, 12, 12)]
    result = object_metrics(predictions, references)
    assert result["tp_objects"] == 2
    assert result["fp_objects"] == 0
    assert result["fn_objects"] == 0
    assert [(item["prediction_index"], item["reference_index"]) for item in result["matches"]] == [(0, 0), (1, 1)]


def test_merged_and_split_are_reported_without_extra_true_positives() -> None:
    merged = [box(0, 0, 4, 2)]
    two_references = [box(0, 0, 2, 2), box(2, 0, 4, 2)]
    result = object_metrics(merged, two_references, iou_threshold=0.5)
    assert result["merged_detection_count"] == 1
    assert result["tp_objects"] == 1
    assert result["fn_objects"] == 1
    split = object_metrics([box(0, 0, 2, 2), box(0, 0, 2, 2)], [box(0, 0, 2, 2)])
    assert split["split_detection_count"] == 1
    assert split["tp_objects"] == 1
    assert split["fp_objects"] == 1


def test_size_classes_are_explicitly_provisional() -> None:
    assert size_class(10) == "small"
    assert size_class(25) == "medium"
    assert size_class(100) == "large"
