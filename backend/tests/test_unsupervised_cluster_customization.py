from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gee_client import (
    _gee_stats_crs_for_analysis,
    _unsupervised_result_vis,
    normalize_unsupervised_result_order,
)
from app.main import _update_unsupervised_cluster_metadata


class UnsupervisedClusterCustomizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = {
            "analysis_type": "unsupervised_classification",
            "classes": [
                {"code": 1, "name": "Cluster 1", "color": "#2b83ba"},
                {"code": 2, "name": "Cluster 2", "color": "#1a9850"},
                {"code": 3, "name": "Cluster 3", "color": "#a6d96a"},
            ],
            "cluster_interpretation": [
                {"cluster": 0, "code": 1, "name": "Cluster 1", "color": "#2b83ba"},
                {"cluster": 1, "code": 2, "name": "Cluster 2", "color": "#1a9850"},
                {"cluster": 2, "code": 3, "name": "Cluster 3", "color": "#a6d96a"},
            ],
            "palette": ["#2b83ba", "#1a9850", "#a6d96a"],
        }

    def test_color_is_synchronized_without_changing_cluster_name(self) -> None:
        changed = _update_unsupervised_cluster_metadata(self.result, 2, color="#123abc")

        self.assertTrue(changed)
        self.assertEqual(self.result["classes"][1]["name"], "Cluster 2")
        self.assertEqual(self.result["classes"][1]["color"], "#123abc")
        self.assertEqual(self.result["cluster_interpretation"][1]["color"], "#123abc")
        self.assertEqual(self.result["palette"], ["#2b83ba", "#123abc", "#a6d96a"])
        self.assertEqual(self.result["tile_source_palette"], ["#2b83ba", "#1a9850", "#a6d96a"])

    def test_source_tile_palette_stays_stable_across_visual_color_updates(self) -> None:
        _update_unsupervised_cluster_metadata(self.result, 1, color="#101010")
        _update_unsupervised_cluster_metadata(self.result, 3, color="#303030")

        self.assertEqual(self.result["tile_source_palette"], ["#2b83ba", "#1a9850", "#a6d96a"])
        self.assertEqual(self.result["palette"], ["#101010", "#1a9850", "#303030"])

    def test_name_and_color_can_be_updated_together(self) -> None:
        changed = _update_unsupervised_cluster_metadata(
            self.result,
            1,
            name="Dense vegetation",
            color="#006400",
        )

        self.assertTrue(changed)
        self.assertEqual(self.result["classes"][0]["name"], "Dense vegetation")
        self.assertEqual(self.result["cluster_interpretation"][0]["name"], "Dense vegetation")
        self.assertEqual(self.result["palette"][0], "#006400")

    def test_stored_palette_is_used_only_when_complete_and_valid(self) -> None:
        default_vis = {"min": 1, "max": 3, "palette": ["#111111", "#222222", "#333333"]}

        custom_vis = _unsupervised_result_vis(self.result, default_vis)
        self.assertEqual(custom_vis["palette"], ["#2b83ba", "#1a9850", "#a6d96a"])

        self.result["classes"][1]["color"] = "invalid"
        fallback_vis = _unsupervised_result_vis(self.result, default_vis)
        self.assertEqual(fallback_vis, default_vis)

    def test_unknown_cluster_is_not_modified(self) -> None:
        self.assertFalse(_update_unsupervised_cluster_metadata(self.result, 99, color="#abcdef"))

    def test_stored_clusters_are_reordered_by_stable_spectral_signature(self) -> None:
        self.result["classes"][0]["surface_ha"] = 50
        self.result["classes"][1]["surface_ha"] = 0
        self.result["classes"][2]["surface_ha"] = 20
        self.result["cluster_interpretation"][0]["means"] = {"NDVI": 0.10, "NDWI": -0.20}
        self.result["cluster_interpretation"][1]["means"] = {"NDVI": 0.50, "NDWI": -0.50}
        self.result["cluster_interpretation"][2]["means"] = {"NDVI": 0.24, "NDWI": -0.30}

        normalized = normalize_unsupervised_result_order(self.result)

        self.assertEqual([item["name"] for item in normalized["classes"]], ["Cluster 1", "Cluster 3", "Cluster 2"])
        self.assertEqual([item["surface_ha"] for item in normalized["classes"]], [50, 20, 0])
        self.assertEqual([item["code"] for item in normalized["classes"]], [1, 2, 3])
        self.assertEqual(normalized["palette"], ["#2b83ba", "#a6d96a", "#1a9850"])

    def test_statistics_keep_ksa_zone_locally_and_fallback_outside_ksa(self) -> None:
        ksa_analysis = {
            "spatial_reference": {
                "analysis_crs": "EPSG:9358",
                "center_longitude": 46.7,
                "center_latitude": 24.7,
            }
        }
        morocco_analysis = {
            "spatial_reference": {
                "analysis_crs": "EPSG:9356",
                "center_longitude": -4.18,
                "center_latitude": 33.69,
            }
        }

        self.assertEqual(_gee_stats_crs_for_analysis(ksa_analysis), "EPSG:9358")
        self.assertEqual(_gee_stats_crs_for_analysis(morocco_analysis), "EPSG:32630")


if __name__ == "__main__":
    unittest.main()
