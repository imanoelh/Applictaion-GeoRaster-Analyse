from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import AnalysisCreate, PreviewRequest
from app.request_contracts import normalize_analysis_payload, normalize_raster_request_payload


GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-6.9, 34.0], [-6.8, 34.0], [-6.8, 34.1], [-6.9, 34.1], [-6.9, 34.0]]],
}


class RequestContractTests(unittest.TestCase):
    def test_canonical_raster_payload_is_backfilled_for_legacy_fields(self) -> None:
        payload = normalize_raster_request_payload(
            {
                "geometry": GEOMETRY,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "sensor": "sentinel-2",
                "resolution": "auto",
                "cloud_max": 18,
            }
        )
        self.assertEqual(payload["date_start"], "2026-01-01")
        self.assertEqual(payload["date_end"], "2026-01-31")
        self.assertEqual(payload["max_cloud_pct"], 18)
        self.assertEqual(payload["source"], "S2_SR_HARMONIZED")
        self.assertIn("geojson", payload["aoi"])

    def test_analysis_type_maps_to_expected_index(self) -> None:
        payload = normalize_analysis_payload(
            {
                "geometry": GEOMETRY,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "sensor": "sentinel-2",
                "resolution": "auto",
                "cloud_max": 18,
                "analysis_type": "change_detection_ndvi",
                "index": "NDVI",
            }
        )
        self.assertEqual(payload["index"], "CHANGE_NDVI")

    def test_preview_request_accepts_canonical_payload(self) -> None:
        payload = PreviewRequest.model_validate(
            {
                "geometry": GEOMETRY,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "sensor": "sentinel-2",
                "resolution": "auto",
                "cloud_max": 12,
                "index": "NDVI",
            }
        )
        self.assertEqual(payload.date_start, "2026-01-01")
        self.assertEqual(payload.max_cloud_pct, 12)
        self.assertIsNotNone(payload.aoi)

    def test_preview_request_keeps_the_selected_live_scene_id(self) -> None:
        payload = PreviewRequest.model_validate(
            {
                "geometry": GEOMETRY,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "sensor": "sentinel-2",
                "scene_id": "20260120T080000_20260120T080500_T38RPU",
            }
        )
        self.assertEqual(payload.scene_id, "20260120T080000_20260120T080500_T38RPU")

    def test_analysis_preserves_selected_scene_mode_and_image_id(self) -> None:
        image_id = "COPERNICUS/S2_SR_HARMONIZED/20260120T080000_20260120T080500_T38RPU"
        payload = AnalysisCreate.model_validate(
            {
                "name": "Selected acquisition NDVI",
                "geometry": GEOMETRY,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "sensor": "sentinel-2",
                "resolution": "20m",
                "cloud_max": 12,
                "index": "NDVI",
                "image_method": "selected_scene",
                "image_id": image_id,
            }
        )
        self.assertEqual(payload.image_method, "selected_scene")
        self.assertEqual(payload.image_id, image_id)
        self.assertEqual(payload.resolution, "20m")

    def test_analysis_create_accepts_canonical_change_detection_payload(self) -> None:
        payload = AnalysisCreate.model_validate(
            {
                "name": "Change detection",
                "geometry": GEOMETRY,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "sensor": "sentinel-2",
                "resolution": "auto",
                "cloud_max": 12,
                "analysis_type": "change_detection_ndbi",
                "index": "NDVI",
                "period_1": {"start_date": "2025-01-01", "end_date": "2025-01-31"},
                "period_2": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
            }
        )
        self.assertEqual(payload.index, "CHANGE_NDBI")

    def test_imported_polygon_uses_the_same_aoi_contract_as_drawn_geometry(self) -> None:
        imported = {
            "type": "Polygon",
            "coordinates": [[[49.72, 25.41], [49.74, 25.41], [49.735, 25.42], [49.72, 25.41]]],
        }
        payload = normalize_raster_request_payload(
            {
                "geometry": imported,
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "sensor": "sentinel-2",
                "resolution": "auto",
                "cloud_max": 25,
                "index": "NDVI",
                "analysis_type": "spectral_index",
            }
        )
        self.assertEqual(payload["aoi"]["geojson"], imported)
        self.assertEqual(payload["geometry"], imported)

    def test_imported_multipolygon_stays_on_the_canonical_geometry_field(self) -> None:
        imported = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[49.72, 25.41], [49.73, 25.41], [49.73, 25.42], [49.72, 25.42], [49.72, 25.41]]],
                [[[49.74, 25.41], [49.75, 25.41], [49.75, 25.42], [49.74, 25.42], [49.74, 25.41]]],
            ],
        }
        payload = normalize_raster_request_payload(
            {
                "geometry": imported,
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "sensor": "sentinel-2",
                "cloud_max": 20,
            }
        )
        self.assertEqual(payload["aoi"]["geojson"]["type"], "MultiPolygon")
        self.assertEqual(payload["aoi"]["geojson"]["coordinates"], imported["coordinates"])

    def test_dynamic_world_and_worldcover_are_not_supported_analysis_sensors(self) -> None:
        from app.request_contracts import supported_sensors_for_index

        for index_id in (
            "NDVI",
            "SAVI",
            "CHANGE_NDVI",
            "SUPERVISED_CLASSIFICATION",
            "UNSUPERVISED_CLASSIFICATION",
            "OSI_SAR",
        ):
            sensors = supported_sensors_for_index(index_id)
            self.assertNotIn("dynamic-world", sensors)
            self.assertNotIn("esa-worldcover", sensors)


if __name__ == "__main__":
    unittest.main()
