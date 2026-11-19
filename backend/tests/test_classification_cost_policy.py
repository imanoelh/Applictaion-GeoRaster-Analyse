from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import (
    CURRENT_SUPERVISED_PROCESSING_VERSION,
    CURRENT_UNSUPERVISED_PROCESSING_VERSION,
    cache_key_for_analysis,
    training_samples_cache_fingerprint,
)
from app.gee_client import (
    _apply_unsupervised_cost_policy,
    _unsupervised_cluster_palette,
    _unsupervised_feature_stack,
    _unsupervised_options,
)
from app.scalability import classification_cost_policy


class ClassificationCostPolicyTests(unittest.TestCase):
    def test_standard_aoi_keeps_algorithm_comparison(self) -> None:
        policy = classification_cost_policy(120, 10)
        self.assertEqual(policy["level"], "standard")
        self.assertTrue(policy["allow_algorithm_comparison"])
        self.assertEqual(policy["tile_scale"], 4)
        self.assertEqual(policy["sample_scale_m"], 10)
        # Small AOIs must keep at least the UI default sample budget.
        self.assertGreaterEqual(policy["max_unsupervised_samples"], 5_000)

    def test_large_aoi_disables_peer_comparison_and_raises_adaptive_budget(self) -> None:
        policy = classification_cost_policy(8_000, 10)
        self.assertEqual(policy["level"], "large")
        self.assertFalse(policy["allow_algorithm_comparison"])
        self.assertEqual(policy["max_samples_per_class"], 200)
        # Adaptive density must stay well above the historical 2000-pixel collapse.
        self.assertGreaterEqual(policy["max_unsupervised_samples"], 4_500)
        self.assertLessEqual(policy["max_unsupervised_samples"], 10_000)
        self.assertEqual(policy["tile_scale"], 6)
        self.assertLessEqual(policy["sample_scale_m"], 25)
        self.assertFalse(policy["apply_focal_mode"])
        self.assertTrue(policy["apply_unsupervised_focal_mode"])
        self.assertEqual(policy["sampling_strategy"], "adaptive_density_v2")

    def test_mid_aoi_disables_peer_comparison_before_large_threshold(self) -> None:
        policy = classification_cost_policy(3_500, 10)
        self.assertEqual(policy["level"], "standard")
        self.assertFalse(policy["allow_algorithm_comparison"])
        self.assertEqual(policy["max_samples_per_class"], 220)
        self.assertGreaterEqual(policy["max_unsupervised_samples"], 3_500)
        self.assertEqual(policy["sample_scale_m"], 15)

    def test_very_large_aoi_keeps_usable_sample_density(self) -> None:
        policy = classification_cost_policy(28_002, 10)
        self.assertEqual(policy["level"], "very_large")
        self.assertFalse(policy["allow_algorithm_comparison"])
        self.assertEqual(policy["max_samples_per_class"], 180)
        self.assertGreaterEqual(policy["max_unsupervised_samples"], 5_000)
        self.assertLessEqual(policy["max_unsupervised_samples"], 12_000)
        self.assertEqual(policy["tile_scale"], 8)
        # Training scale must not jump to the full statistics coarsening (e.g. 137 m).
        self.assertLessEqual(policy["sample_scale_m"], 30)
        self.assertGreaterEqual(policy["sample_scale_m"], 20)
        self.assertFalse(policy["apply_focal_mode"])
        self.assertTrue(policy["apply_unsupervised_focal_mode"])
        self.assertEqual(policy["recommended_clusters"], 8)

    def test_adaptive_budget_grows_with_area(self) -> None:
        small = classification_cost_policy(90, 10)
        medium = classification_cost_policy(2_000, 10)
        large = classification_cost_policy(13_000, 10)
        self.assertLessEqual(small["max_unsupervised_samples"], medium["max_unsupervised_samples"])
        self.assertLess(medium["max_unsupervised_samples"], large["max_unsupervised_samples"])

    def test_processing_versions_bumped_for_cost_policy_cache(self) -> None:
        self.assertIn("spatial-quality", CURRENT_SUPERVISED_PROCESSING_VERSION)
        self.assertIn("grouped-spectral-profiles", CURRENT_UNSUPERVISED_PROCESSING_VERSION)

    def test_large_simple_unsupervised_uses_full_bounded_budget_and_visible_k(self) -> None:
        available = ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"]
        options = _unsupervised_options(
            {
                "unsupervised_options": {
                    "mode": "simple",
                    "clusters_count": 6,
                    "samples_count": 5_000,
                    "seed": 91,
                }
            },
            available,
        )
        applied = _apply_unsupervised_cost_policy(options, classification_cost_policy(28_002, 10))
        self.assertTrue(options["clusters_explicit"])
        self.assertEqual(applied["clusters_count"], 6)
        self.assertEqual(applied["samples_count"], 8_000)

    def test_unsupervised_feature_standardization_is_opt_in_and_validated(self) -> None:
        available = ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"]
        default = _unsupervised_options({}, available)
        zscore = _unsupervised_options(
            {"unsupervised_options": {"feature_standardization": "zscore"}},
            available,
        )
        invalid = _unsupervised_options(
            {"unsupervised_options": {"feature_standardization": "robust"}},
            available,
        )

        self.assertEqual(default["feature_standardization"], "none")
        self.assertEqual(zscore["feature_standardization"], "zscore")
        self.assertEqual(invalid["feature_standardization"], "none")

    def test_unsupervised_palette_is_stable_distinct_and_high_contrast(self) -> None:
        palette = _unsupervised_cluster_palette(8)
        self.assertEqual(palette, _unsupervised_cluster_palette(8))
        self.assertEqual(len(palette), 8)
        self.assertEqual(len(set(palette)), 8)
        self.assertTrue(all(color.startswith("#") and len(color) == 7 for color in palette))

    def test_unsupervised_sentinel_features_scale_reflectance_without_touching_supervised_stack(self) -> None:
        raw_stack = MagicMock()
        scaled_bands = MagicMock()
        normalized_stack = MagicMock()
        raw_stack.select.return_value.multiply.return_value = scaled_bands
        raw_stack.addBands.return_value = normalized_stack
        bands = ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI"]

        with patch("app.gee_client._classification_feature_stack", return_value=(raw_stack, bands)):
            result_stack, result_bands = _unsupervised_feature_stack(object(), "sentinel-2")

        raw_stack.select.assert_called_once_with(["B2", "B3", "B4", "B8", "B11", "B12"])
        raw_stack.select.return_value.multiply.assert_called_once_with(0.0001)
        raw_stack.addBands.assert_called_once_with(scaled_bands, None, True)
        self.assertIs(result_stack, normalized_stack)
        self.assertEqual(result_bands, bands)

    def test_unsupervised_landsat_keeps_already_scaled_reflectance(self) -> None:
        raw_stack = MagicMock()
        bands = ["SR_B2", "SR_B3", "NDVI"]
        with patch("app.gee_client._classification_feature_stack", return_value=(raw_stack, bands)):
            result_stack, result_bands = _unsupervised_feature_stack(object(), "landsat-8-9")
        raw_stack.select.assert_not_called()
        self.assertIs(result_stack, raw_stack)
        self.assertEqual(result_bands, bands)

    def test_supervised_cache_key_includes_training_sample_fingerprint(self) -> None:
        analysis = {
            "analysis_type": "supervised_classification",
            "index": "SUPERVISED_CLASSIFICATION",
            "sensor": "sentinel-2",
            "date_start": "2024-01-01",
            "date_end": "2024-01-31",
            "aoi": {"bbox": [24.0, 46.0, 24.1, 46.1]},
            "supervised_options": {
                "algorithm": "random_forest",
                "project_id": "default",
                "class_ids": ["class-a", "class-b"],
                "compare_algorithms": True,
            },
        }
        rows = [
            {
                "id": "s1",
                "class_id": "class-a",
                "usage": "training",
                "quality_status": "valid",
                "geometry_json": '{"type":"Point","coordinates":[46.05,24.05]}',
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": "s2",
                "class_id": "class-b",
                "usage": "training",
                "quality_status": "valid",
                "geometry_json": '{"type":"Point","coordinates":[46.06,24.06]}',
                "created_at": "2024-01-02T00:00:00Z",
            },
        ]

        class FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("app.main.db.connect", return_value=FakeConn()):
            with patch("app.main.db.fetch_all", return_value=rows):
                fingerprint = training_samples_cache_fingerprint(analysis)
                key_a = cache_key_for_analysis(analysis)
                rows[0]["geometry_json"] = '{"type":"Point","coordinates":[46.07,24.07]}'
                key_b = cache_key_for_analysis(analysis)

        self.assertIsNotNone(fingerprint)
        self.assertEqual(len(fingerprint or ""), 64)
        self.assertNotEqual(key_a, key_b)

        expected_items = [
            {
                "id": "s1",
                "class_id": "class-a",
                "usage": "training",
                "quality_status": "valid",
                "created_at": "2024-01-01T00:00:00Z",
                "geometry_sha": hashlib.sha256(
                    '{"type":"Point","coordinates":[46.07,24.07]}'.encode("utf-8")
                ).hexdigest()[:20],
            },
            {
                "id": "s2",
                "class_id": "class-b",
                "usage": "training",
                "quality_status": "valid",
                "created_at": "2024-01-02T00:00:00Z",
                "geometry_sha": hashlib.sha256(
                    '{"type":"Point","coordinates":[46.06,24.06]}'.encode("utf-8")
                ).hexdigest()[:20],
            },
        ]
        expected = hashlib.sha256(
            json.dumps(expected_items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with patch("app.main.db.connect", return_value=FakeConn()):
            with patch("app.main.db.fetch_all", return_value=rows):
                self.assertEqual(training_samples_cache_fingerprint(analysis), expected)


if __name__ == "__main__":
    unittest.main()
