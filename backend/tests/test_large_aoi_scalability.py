from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app import gee_client
from app.gee_client import (
    FAST_MAP_AOI_THRESHOLD_KM2,
    _sentinel2_mosaic_uses_lazy_tile_graph,
    should_prioritize_first_map,
)
from app.scalability import (
    ANALYSIS_CACHE_TTL_SECONDS,
    MAX_LOGICAL_CHUNKS,
    adaptive_chunk_plan,
    cache_timestamp_is_fresh,
    classification_cost_policy,
    surface_policy,
)


class LargeAoiScalabilityTests(unittest.TestCase):
    def test_small_aoi_stays_interactive(self) -> None:
        policy = surface_policy(25, 10)
        plan = adaptive_chunk_plan([24.6, 46.5, 24.8, 46.8], 25)
        self.assertEqual(policy["status"], "ok")
        self.assertFalse(policy["blocked"])
        self.assertEqual(plan.count, 1)

    def test_medium_aoi_is_supported_with_warning(self) -> None:
        policy = surface_policy(8_000, 10)
        plan = adaptive_chunk_plan([20.0, 40.0, 23.0, 44.0], 8_000)
        self.assertEqual(policy["status"], "warning")
        self.assertFalse(policy["blocked"])
        self.assertGreater(plan.count, 1)
        self.assertLessEqual(policy["estimated_native_pixels"] * 100 / (policy["statistics_scale_m"] ** 2), 3_000_000)

    def test_target_aoi_uses_bounded_atomic_statistics(self) -> None:
        policy = surface_policy(28_002, 10)
        self.assertEqual(policy["status"], "async")
        self.assertEqual(policy["statistics_pixel_budget"], 1_500_000)
        self.assertGreaterEqual(policy["statistics_scale_m"], 137)
        effective_pixels = 28_002 * 1_000_000 / (policy["statistics_scale_m"] ** 2)
        self.assertLessEqual(effective_pixels, policy["statistics_pixel_budget"])

    def test_very_large_imported_aoi_is_not_blocked(self) -> None:
        # Approximate Saudi Arabia envelope: deliberately much larger than the
        # former 32,000 km2 hard stop.
        policy = surface_policy(2_100_000, 10)
        plan = adaptive_chunk_plan([16.0, 34.0, 33.0, 56.0], 2_100_000)
        self.assertEqual(policy["status"], "async")
        self.assertTrue(policy["async_recommended"])
        self.assertFalse(policy["blocked"])
        self.assertLessEqual(plan.count, MAX_LOGICAL_CHUNKS)
        self.assertGreater(policy["statistics_scale_m"], 10)

    def test_cache_expiration(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertTrue(cache_timestamp_is_fresh(now.isoformat()))
        expired = now - timedelta(seconds=ANALYSIS_CACHE_TTL_SECONDS + 1)
        self.assertFalse(cache_timestamp_is_fresh(expired.isoformat()))

    def test_irregular_aoi_grid_never_clips_with_empty_intersections(self) -> None:
        class FakeGeometry:
            @staticmethod
            def Rectangle(coordinates: list[float]) -> list[float]:
                return coordinates

        aoi = {
            "geojson": {
                "type": "Polygon",
                "coordinates": [[
                    [40.0, 20.0], [50.0, 20.0], [50.0, 21.0],
                    [42.0, 25.0], [40.0, 20.0],
                ]],
            }
        }
        original_ee = gee_client.ee
        gee_client.ee = SimpleNamespace(Geometry=FakeGeometry)
        try:
            chunks = gee_client._grid_geometries(aoi, object())
        finally:
            gee_client.ee = original_ee
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(isinstance(chunk, list) and len(chunk) == 4 for chunk in chunks))

    def test_analysis_mosaic_skips_eager_tile_qa_except_catalog_and_huge_grids(self) -> None:
        self.assertFalse(_sentinel2_mosaic_uses_lazy_tile_graph(tile_count=1, eager_tile_qa=False))
        self.assertTrue(_sentinel2_mosaic_uses_lazy_tile_graph(tile_count=8, eager_tile_qa=False))
        self.assertFalse(_sentinel2_mosaic_uses_lazy_tile_graph(tile_count=8, eager_tile_qa=True))
        self.assertTrue(_sentinel2_mosaic_uses_lazy_tile_graph(tile_count=17, eager_tile_qa=True))

    def test_first_map_priority_is_only_for_very_large_spectral_or_change(self) -> None:
        self.assertFalse(should_prioritize_first_map("NDVI", FAST_MAP_AOI_THRESHOLD_KM2))
        self.assertTrue(should_prioritize_first_map("NDVI", FAST_MAP_AOI_THRESHOLD_KM2 + 1))
        self.assertTrue(should_prioritize_first_map("CHANGE_NDBI", 28_002))
        self.assertFalse(should_prioritize_first_map("OSI_SAR", 28_002))
        self.assertFalse(should_prioritize_first_map("SUPERVISED_CLASSIFICATION", 28_002))

    def test_classification_cost_policy_scales_with_aoi(self) -> None:
        small = classification_cost_policy(25, 10)
        large = classification_cost_policy(8_000, 10)
        huge = classification_cost_policy(28_002, 10)
        self.assertTrue(small["allow_algorithm_comparison"])
        self.assertFalse(large["allow_algorithm_comparison"])
        self.assertFalse(huge["allow_algorithm_comparison"])
        self.assertLess(huge["max_unsupervised_samples"], large["max_unsupervised_samples"])
        self.assertGreater(huge["tile_scale"], small["tile_scale"])
        self.assertEqual(small["sample_scale_m"], 10)
        self.assertGreaterEqual(large["sample_scale_m"], 20)
        # KMeans keeps usable spectral detail while its sample count is capped;
        # aggregate statistics may safely use a much coarser grid.
        self.assertLessEqual(huge["sample_scale_m"], 30)
        self.assertLess(huge["sample_scale_m"], huge["statistics_scale_m"])
        self.assertTrue(small["apply_focal_mode"])
        self.assertFalse(huge["apply_focal_mode"])


if __name__ == "__main__":
    unittest.main()
