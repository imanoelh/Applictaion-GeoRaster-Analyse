from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def pixel_metrics(predicted: np.ndarray, reference: np.ndarray) -> dict[str, float | int]:
    predicted = np.asarray(predicted, dtype=bool)
    reference = np.asarray(reference, dtype=bool)
    if predicted.shape != reference.shape:
        raise ValueError("predicted et reference doivent avoir les memes dimensions")
    tp = int(np.count_nonzero(predicted & reference))
    fp = int(np.count_nonzero(predicted & ~reference))
    fn = int(np.count_nonzero(~predicted & reference))
    tn = int(np.count_nonzero(~predicted & ~reference))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "tp_pixels": tp,
        "fp_pixels": fp,
        "fn_pixels": fn,
        "tn_pixels": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
    }


def object_metrics(
    predictions: Sequence[Any],
    references: Sequence[Any],
    *,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError("iou_threshold doit etre compris entre 0 et 1")
    candidates: list[tuple[float, int, int]] = []
    for prediction_index, prediction in enumerate(predictions):
        for reference_index, reference in enumerate(references):
            union = prediction.union(reference).area
            iou = prediction.intersection(reference).area / union if union else 0.0
            if iou >= iou_threshold:
                candidates.append((float(iou), prediction_index, reference_index))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    matched_predictions: set[int] = set()
    matched_references: set[int] = set()
    matches: list[dict[str, Any]] = []
    for iou, prediction_index, reference_index in candidates:
        if prediction_index in matched_predictions or reference_index in matched_references:
            continue
        matched_predictions.add(prediction_index)
        matched_references.add(reference_index)
        matches.append({"prediction_index": prediction_index, "reference_index": reference_index, "iou": iou})
    merged = sum(
        len({reference_index for _, prediction_index, reference_index in candidates if prediction_index == index}) > 1
        for index in range(len(predictions))
    )
    split = sum(
        len({prediction_index for _, prediction_index, reference_index in candidates if reference_index == index}) > 1
        for index in range(len(references))
    )
    tp = len(matches)
    fp = len(predictions) - tp
    fn = len(references) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp_objects": tp,
        "fp_objects": fp,
        "fn_objects": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matches": matches,
        "merged_detection_count": merged,
        "split_detection_count": split,
    }


def size_class(area_m2: float) -> str:
    if area_m2 < 25:
        return "small"
    if area_m2 < 100:
        return "medium"
    return "large"
