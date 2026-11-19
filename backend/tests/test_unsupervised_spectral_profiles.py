from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gee_client import _interpret_clusters, _differentiate_relative_cluster_labels


def test_grouped_profile_reducer_places_cluster_after_all_predictors() -> None:
    stack = MagicMock()
    clusters = MagicMock()
    geom = MagicMock()
    feature_bands = ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"]
    stack.select.return_value.addBands.return_value.reduceRegion.return_value.getInfo.return_value = {
        "groups": [
            {
                "cluster": 0,
                "mean": [float(index + 1) for index, _band in enumerate(feature_bands)],
            }
        ]
    }
    reducer = MagicMock()
    repeated_reducer = MagicMock()
    reducer.repeat.return_value = repeated_reducer
    repeated_reducer.group.return_value = MagicMock()
    with patch("app.gee_client.ee.Reducer.mean", return_value=reducer):
        mapping = _interpret_clusters(stack, clusters, geom, 10, 1, sensor="sentinel-2")

    reducer.repeat.assert_called_once_with(len(feature_bands))
    repeated_reducer.group.assert_called_once_with(groupField=len(feature_bands), groupName="cluster")
    stack.select.assert_called_once_with(feature_bands)
    assert mapping[0]["profile_available"] is True
    assert mapping[0]["spectral_means"] == {
        "B2": 1.0,
        "B3": 2.0,
        "B4": 3.0,
        "B8": 4.0,
        "B11": 5.0,
        "B12": 6.0,
    }


def test_unavailable_profile_is_not_assigned_a_semantic_label() -> None:
    mapping = [
        {
            "cluster": 0,
            "code": 1,
            "semantic_name": "Uninterpreted cluster",
            "means": {"NDVI": 0, "NDWI": 0, "NDBI": 0, "BSI": 0, "SAVI": 0},
            "profile_available": False,
        }
    ]

    result = _differentiate_relative_cluster_labels(mapping)

    assert result[0]["probable_label"] == "Uninterpreted cluster"
    assert result[0]["description"] == "Spectral profile unavailable; interpretation was not calculated."
