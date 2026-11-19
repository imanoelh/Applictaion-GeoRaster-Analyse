from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gee_client import (
    AVAILABLE_DATE_COVERAGE_MIN_PCT,
    S2_DATE_MOSAIC_PREFIX,
    _catalog_coverage_scale_m,
    _fast_scene_items,
    _parse_s2_date_mosaic_id,
)


class AvailableDateMosaicTests(unittest.TestCase):
    def test_parse_date_mosaic_id_accepts_prefix_and_asset_form(self) -> None:
        self.assertEqual(_parse_s2_date_mosaic_id("S2_DATE_MOSAIC_2026-02-17"), "2026-02-17")
        self.assertEqual(
            _parse_s2_date_mosaic_id("COPERNICUS/S2_SR_HARMONIZED/S2_DATE_MOSAIC_2025-11-29"),
            "2025-11-29",
        )

    def test_parse_date_mosaic_id_rejects_granules_and_bad_dates(self) -> None:
        self.assertIsNone(_parse_s2_date_mosaic_id("20260120T080000_20260120T080500_T38RPU"))
        self.assertIsNone(_parse_s2_date_mosaic_id("S2_DATE_MOSAIC_2026-13-40"))
        self.assertIsNone(_parse_s2_date_mosaic_id(""))

    def test_catalog_coverage_scale_grows_with_aoi(self) -> None:
        self.assertLessEqual(_catalog_coverage_scale_m(100), _catalog_coverage_scale_m(2000))
        self.assertGreaterEqual(_catalog_coverage_scale_m(6000), 100)

    def test_fast_scene_items_keeps_full_coverage_dates_only(self) -> None:
        payload = {
            "aoi": {
                "bbox": [33.011, -6.419, 34.078, -4.675],
            },
            "date_start": "2025-01-01",
            "date_end": "2026-09-10",
            "max_cloud_pct": 10,
            "sensor": "sentinel-2",
        }
        metadata = [
            {
                "system:index": "a_T29SPR",
                "system:time_start": 1740000000000,
                "CLOUDY_PIXEL_PERCENTAGE": 1,
                "MGRS_TILE": "29SPR",
            },
            {
                "system:index": "a_T29SPQ",
                "system:time_start": 1740000000000,
                "CLOUDY_PIXEL_PERCENTAGE": 2,
                "MGRS_TILE": "29SPQ",
            },
            {
                "system:index": "b_T29SPR",
                "system:time_start": 1750000000000,
                "CLOUDY_PIXEL_PERCENTAGE": 0,
                "MGRS_TILE": "29SPR",
            },
        ]

        class FakeDictList:
            def getInfo(self):
                return metadata

        class FakeCollection:
            def sort(self, *_args, **_kwargs):
                return self

            def limit(self, _n):
                return self

            def toList(self, _n):
                return self

            def aggregate_array(self, _key):
                class Distinct:
                    def distinct(self_inner):
                        return self_inner

                    def getInfo(self_inner):
                        return ["29SPR", "29SPQ", "30STQ"]

                return Distinct()

        with (
            patch("app.gee_client.ee") as ee_mock,
            patch("app.gee_client._format_date", side_effect=["2025-05-19", "2025-05-19", "2025-05-25"]),
            patch("app.gee_client._aoi_area_km2", return_value=19086.0),
            patch("app.gee_client._aoi_geometry", return_value="geom"),
            patch("app.gee_client._bbox_from_aoi", return_value=[33.011, -6.419, 34.078, -4.675]),
            patch("app.gee_client._region_name", return_value="AOI"),
            patch("app.gee_client._sentinel2_date_mosaic_image", return_value=MagicMock()),
            patch(
                "app.gee_client._estimate_date_mosaic_qa",
                side_effect=[
                    {"coverage_percent": 99.1, "cloud_percent": 1.2},
                    {"coverage_percent": 35.0, "cloud_percent": 0.0},
                ],
            ),
            patch("app.gee_client._tile_url", return_value="https://earthengine.googleapis.com/tiles/{z}/{x}/{y}"),
        ):
            ee_mock.List.sequence.return_value.map.return_value = FakeDictList()
            items = _fast_scene_items(payload, FakeCollection(), count=3, limit=10)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertTrue(item["date_mosaic"])
        self.assertFalse(item["mosaic"])
        self.assertEqual(item["date"], "2025-05-19")
        self.assertEqual(item["id"], f"{S2_DATE_MOSAIC_PREFIX}2025-05-19")
        self.assertEqual(item["cloud"], 1.2)
        self.assertEqual(item["cloud_source"], "scl_aoi")
        self.assertTrue(item["tile_url"])
        self.assertGreaterEqual(item["coverage_percent"], AVAILABLE_DATE_COVERAGE_MIN_PCT)
        self.assertEqual(item["tiles_count"], 2)


if __name__ == "__main__":
    unittest.main()
