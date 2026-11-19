"""Unit tests for unsupervised relative arid cluster labeling."""

from __future__ import annotations

from app.gee_client import _differentiate_relative_cluster_labels


def test_arid_collapse_gets_relative_labels():
    means_list = [
        {"NDVI": 0.05, "NDWI": -0.25, "NDBI": 0.08, "BSI": 0.22, "SAVI": 0.07},
        {"NDVI": 0.12, "NDWI": -0.18, "NDBI": 0.11, "BSI": 0.15, "SAVI": 0.14},
        {"NDVI": 0.08, "NDWI": -0.20, "NDBI": 0.20, "BSI": 0.18, "SAVI": 0.10},
        {"NDVI": 0.03, "NDWI": -0.30, "NDBI": 0.05, "BSI": 0.28, "SAVI": 0.04},
    ]
    mapping = [
        {
            "cluster": i,
            "code": i + 1,
            "semantic_name": "Bare soil / sand",
            "name": f"Cluster {i + 1} - Bare soil / sand",
            "means": means,
        }
        for i, means in enumerate(means_list)
    ]
    out = _differentiate_relative_cluster_labels(mapping)
    names = [item["semantic_name"] for item in out]
    assert len(set(names)) >= 3
    assert all(item.get("description") for item in out)
    assert any("vegetation" in name or "BSI" in name or "NDBI" in name for name in names)


def test_distinct_semantics_keep_base_names():
    mapping = [
        {
            "cluster": 0,
            "code": 1,
            "semantic_name": "Water",
            "name": "Cluster 1 - Water",
            "means": {"NDVI": 0.1, "NDWI": 0.4, "NDBI": -0.1, "BSI": 0.0, "SAVI": 0.1},
        },
        {
            "cluster": 1,
            "code": 2,
            "semantic_name": "Dense vegetation",
            "name": "Cluster 2 - Dense vegetation",
            "means": {"NDVI": 0.6, "NDWI": -0.1, "NDBI": -0.2, "BSI": -0.1, "SAVI": 0.5},
        },
    ]
    out = _differentiate_relative_cluster_labels(mapping)
    assert out[0]["semantic_name"] == "Water"
    assert out[1]["semantic_name"] == "Dense vegetation"
