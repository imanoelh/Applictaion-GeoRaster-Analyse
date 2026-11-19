from __future__ import annotations

import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import gee_client
from app.gee_client import (
    CHANGE_DETECTION_CONFIG,
    INDEX_CONFIG,
    NDBI_BUILT_DETECTION_CONFIG,
    OSI_SAR_REFERENCE,
    SAVI_CANOPY_L,
    SAVI_CHANGE_PERIOD_CONFIG,
    S2_SR_REFLECTANCE_SCALE,
    _build_supervised_datasets,
    _classification_vis,
    _compute_index_image,
    _compute_savi_float_image,
    _index_native_scale,
    _effective_output_resolution_m,
    _requested_resolution_m,
    _resolution_contract,
    _ndbi_class_masks,
    _osi_sar_options,
    _scl_reference_payload,
    _sentinel1_asset_id,
    _supervised_options,
    osi_sar_suspicion_class,
)
from app.mock_engine import compute_mock_index
from app.request_contracts import supported_sensors_for_index
from app.main import (
    CURRENT_CHANGE_DETECTION_PROCESSING_VERSION,
    CURRENT_CHANGE_SAVI_PROCESSING_VERSION,
    CURRENT_NDVI_PROCESSING_VERSION,
    CURRENT_OSI_SAR_PROCESSING_VERSION,
    CURRENT_SAVI_PROCESSING_VERSION,
    cache_key_for_analysis,
    is_cache_row_compatible,
    processing_version_for_analysis,
)


class ScalarImage:
    """Small Earth Engine-like scalar used to verify NDBI mask semantics."""

    def __init__(self, value: float | bool) -> None:
        self.value = value

    def gte(self, other: float | "ScalarImage") -> "ScalarImage":
        value = other.value if isinstance(other, ScalarImage) else other
        return ScalarImage(float(self.value) >= float(value))

    def gt(self, other: float | "ScalarImage") -> "ScalarImage":
        value = other.value if isinstance(other, ScalarImage) else other
        return ScalarImage(float(self.value) > float(value))

    def lt(self, other: float) -> "ScalarImage":
        return ScalarImage(float(self.value) < other)

    def eq(self, other: float) -> "ScalarImage":
        return ScalarImage(float(self.value) == other)

    def add(self, other: float) -> "ScalarImage":
        return ScalarImage(float(self.value) + other)

    def multiply(self, other: float) -> "ScalarImage":
        return ScalarImage(float(self.value) * other)

    def And(self, other: "ScalarImage") -> "ScalarImage":
        return ScalarImage(bool(self.value) and bool(other.value))

    def Or(self, other: "ScalarImage") -> "ScalarImage":
        return ScalarImage(bool(self.value) or bool(other.value))

    def Not(self) -> "ScalarImage":
        return ScalarImage(not bool(self.value))


class GeeContractTests(unittest.TestCase):
    def test_optical_scene_id_changes_analysis_cache_identity(self) -> None:
        base = {
            "source": "S2_SR_HARMONIZED",
            "sensor": "sentinel-2",
            "resolution": "auto",
            "date_start": "2026-01-01",
            "date_end": "2026-01-31",
            "image_method": "selected_scene",
            "index": "NDVI",
            "aoi": {"geojson": {"type": "Polygon", "coordinates": []}},
        }
        first = cache_key_for_analysis({**base, "image_id": "scene-a"})
        second = cache_key_for_analysis({**base, "image_id": "scene-b"})
        self.assertNotEqual(first, second)

    def test_resolution_contract_never_claims_finer_than_native(self) -> None:
        self.assertEqual(_requested_resolution_m({"resolution": "10m"}), 10)
        self.assertEqual(_effective_output_resolution_m({"resolution": "10m"}, 30), 30)
        self.assertEqual(_effective_output_resolution_m({"resolution": "30m"}, 10), 30)
        contract = _resolution_contract({"resolution": "20m"}, 10, 40)
        self.assertEqual(contract["native_resolution_m"], 10)
        self.assertEqual(contract["requested_export_resolution_m"], 20)
        self.assertEqual(contract["effective_export_resolution_m"], 20)
        self.assertEqual(contract["statistics_scale_m"], 40)
        self.assertEqual(contract["continuous_resampling"], "bilinear")
        self.assertEqual(contract["categorical_resampling"], "nearest_neighbor")

    def test_guided_supervised_options_preserve_selected_classes_and_strict_mode(self) -> None:
        options = _supervised_options(
            {
                "supervised_options": {
                    "class_ids": ["water-id", "built-id"],
                    "require_user_samples": True,
                }
            }
        )
        self.assertEqual(options["class_ids"], ["water-id", "built-id"])
        self.assertTrue(options["require_user_samples"])

    def test_supervised_options_default_requires_user_samples(self) -> None:
        self.assertTrue(_supervised_options({})["require_user_samples"])
        self.assertTrue(_supervised_options({"supervised_options": {}})["require_user_samples"])
        self.assertFalse(
            _supervised_options({"supervised_options": {"require_user_samples": False}})["require_user_samples"]
        )

    def test_supervised_visualization_supports_non_contiguous_class_codes(self) -> None:
        vis = _classification_vis(
            [
                {"code": 1, "color": "#111111"},
                {"code": 4, "color": "#444444"},
            ]
        )
        self.assertEqual(vis["min"], 1)
        self.assertEqual(vis["max"], 4)
        self.assertEqual(vis["palette"], ["#111111", "#000000", "#000000", "#444444"])

    def test_guided_supervised_workflow_rejects_missing_classes_and_samples(self) -> None:
        options = _supervised_options({"supervised_options": {"require_user_samples": True}})
        with patch.object(
            gee_client,
            "_load_user_training_features",
            return_value=(None, [], {"reason": "no_active_classes"}),
        ):
            with self.assertRaisesRegex(ValueError, "at least two"):
                _build_supervised_datasets({}, object(), object(), 10, options)

        classes = [
            {"id": "water", "code": 1, "name": "Water", "color": "#111111"},
            {"id": "built", "code": 5, "name": "Built", "color": "#555555"},
        ]
        with patch.object(
            gee_client,
            "_load_user_training_features",
            return_value=(None, classes, {"reason": "no_user_samples"}),
        ):
            with self.assertRaisesRegex(ValueError, "required"):
                _build_supervised_datasets({}, object(), object(), 10, options)

        with patch.object(
            gee_client,
            "_load_user_training_features",
            return_value=(object(), classes, {"missing_training_class_ids": ["built"]}),
        ):
            with self.assertRaisesRegex(ValueError, "Each selected"):
                _build_supervised_datasets({}, object(), object(), 10, options)

    def test_index_config_has_expected_business_fields(self) -> None:
        for index_id in ("NDVI", "NDWI", "NDBI", "BSI", "SAVI"):
            with self.subTest(index=index_id):
                config = INDEX_CONFIG[index_id]
                self.assertIn("formula", config)
                self.assertIn("bands", config)
                self.assertIn("palette", config)
                self.assertGreater(len(config["palette"]), 0)
                self.assertGreater(len(config["classes"]), 0)

    def test_change_detection_config_has_palette_classes_and_interpretation(self) -> None:
        for index_id, config in CHANGE_DETECTION_CONFIG.items():
            with self.subTest(index=index_id):
                self.assertEqual(len(config["palette"]), len(config["classes"]))
                self.assertTrue(config["interpretation"])

    def test_ndbi_class_metadata_matches_backend_thresholds(self) -> None:
        classes = INDEX_CONFIG["NDBI"]["classes"]
        self.assertEqual(INDEX_CONFIG["NDBI"]["bands"], ["B11", "B8"])
        self.assertEqual(INDEX_CONFIG["NDBI"]["formula"], "(SWIR - NIR) / (SWIR + NIR)")
        self.assertEqual(INDEX_CONFIG["NDBI"]["min"], -0.20)
        self.assertEqual(INDEX_CONFIG["NDBI"]["max"], 0.25)
        self.assertEqual(
            INDEX_CONFIG["NDBI"]["palette"],
            ["#EDE6DA", "#F3EBD4", "#F5E6A3", "#F5C56B", "#F08A3C", "#E85D2A", "#C41E1E"],
        )
        self.assertEqual(classes[0][:3], (-2.0, 0.0, "Non-built / vegetation / water"))
        self.assertEqual(classes[1][:3], (0.0, 0.05, "Transition / weak response"))
        self.assertEqual(classes[2][:3], (0.05, 0.12, "Moderate positive (possible built or bare)"))
        self.assertEqual(classes[3][:3], (0.12, 2.0, "Strong positive (dense built or bright bare)"))
        self.assertEqual([item[3] for item in classes], ["#EDE6DA", "#F5E6A3", "#F08A3C", "#C41E1E"])
        self.assertEqual(_index_native_scale("NDBI", "sentinel-2"), 20)
        self.assertTrue(_scl_reference_payload({"index": "NDBI"}))
        self.assertEqual(NDBI_BUILT_DETECTION_CONFIG["classes"][2][2], "Built-up area detected")

    def test_ndwi_contract_matches_gee_surface_water_reference(self) -> None:
        config = INDEX_CONFIG["NDWI"]
        classes = config["classes"]
        self.assertEqual(config["bands"], ["B3", "B8"])
        self.assertEqual(config["formula"], "(Green - NIR) / (Green + NIR)")
        self.assertEqual(config["min"], -0.50)
        self.assertEqual(config["max"], 0.50)
        self.assertEqual(config["palette"], ["#8C510A", "#BF812D", "#DFC27D", "#F6E8C3", "#F5F5F5", "#C7EAE5", "#80CDC1", "#35978F", "#01665E"])
        self.assertEqual(classes[0][:3], (-2.0, -0.20, "Strong negative NDWI response / probable dry land"))
        self.assertEqual(classes[1][:3], (-0.20, 0.0, "Negative NDWI response"))
        self.assertEqual(classes[2][:3], (0.0, 0.10, "Transition / weak water response"))
        self.assertEqual(classes[3][:3], (0.10, 0.30, "Water-compatible NDWI response"))
        self.assertEqual(classes[4][:3], (0.30, 2.0, "Strong water response"))
        self.assertEqual(_index_native_scale("NDWI", "sentinel-2"), 10)
        self.assertTrue(_scl_reference_payload({"index": "NDWI"}))

    def test_ndbi_temporal_probability_recovers_bright_roof(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(-0.08),
            ScalarImage(0.03),
            ScalarImage(-0.15),
            ScalarImage(0.31),
            ScalarImage(0.72),
            ScalarImage(0.12),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [False, False, False, True])

    def test_ndbi_bare_soil_stays_non_built(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(0.08),
            ScalarImage(0.02),
            ScalarImage(-0.10),
            ScalarImage(0.35),
            ScalarImage(0.05),
            ScalarImage(0.80),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [True, False, False, False])

    def test_ndbi_high_ndbi_arid_desert_stays_non_built(self) -> None:
        # Desert mineral soils often have NDBI >> 0.10 with elevated BSI and
        # Dynamic World bare >> built. They must not become high-confidence built.
        masks = _ndbi_class_masks(
            ScalarImage(0.22),
            ScalarImage(0.08),
            ScalarImage(-0.27),
            ScalarImage(0.29),
            ScalarImage(0.06),
            ScalarImage(0.55),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [True, False, False, False])

    def test_ndbi_high_ndbi_arid_desert_without_dw_stays_non_built(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(0.22),
            ScalarImage(0.08),
            ScalarImage(-0.27),
            ScalarImage(0.29),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [True, False, False, False])

    def test_ndbi_low_confidence_auxiliary_signal_stays_non_built(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(-0.03),
            ScalarImage(0.20),
            ScalarImage(-0.25),
            ScalarImage(0.10),
            ScalarImage(0.25),
            ScalarImage(0.10),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [True, False, False, False])

    def test_ndbi_spectral_road_detection_is_preserved_without_auxiliary_data(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(0.10),
            ScalarImage(0.01),
            ScalarImage(-0.10),
            ScalarImage(0.15),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [False, False, True, False])

    def test_ndbi_stable_reference_alone_does_not_create_built_surface(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(-0.08),
            ScalarImage(0.10),
            ScalarImage(-0.15),
            ScalarImage(0.05),
            ScalarImage(0.10),
            ScalarImage(0.20),
            ScalarImage(1),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [True, False, False, False])

    def test_ndbi_stable_reference_promotes_low_spectral_evidence(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(0.06),
            ScalarImage(0.01),
            ScalarImage(-0.10),
            ScalarImage(0.15),
            None,
            None,
            ScalarImage(1),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [False, False, True, False])

    def test_ndbi_worldcover_does_not_override_bare_soil_evidence(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(0.08),
            ScalarImage(0.02),
            ScalarImage(-0.10),
            ScalarImage(0.35),
            ScalarImage(0.05),
            ScalarImage(0.80),
            ScalarImage(1),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [True, False, False, False])

    def test_ndbi_ghsl_strong_reference_recovers_missed_bright_roof(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(-0.08),
            ScalarImage(0.03),
            ScalarImage(-0.15),
            ScalarImage(0.31),
            ScalarImage(0.10),
            ScalarImage(0.20),
            ScalarImage(0),
            ScalarImage(65),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [False, False, True, False])

    def test_ndbi_ghsl_weak_reference_does_not_create_built_surface(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(-0.08),
            ScalarImage(0.03),
            ScalarImage(-0.15),
            ScalarImage(0.31),
            ScalarImage(0.10),
            ScalarImage(0.20),
            ScalarImage(0),
            ScalarImage(25),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [True, False, False, False])

    def test_ndbi_ghsl_reference_never_promotes_to_high_confidence(self) -> None:
        masks = _ndbi_class_masks(
            ScalarImage(-0.08),
            ScalarImage(0.03),
            ScalarImage(-0.15),
            ScalarImage(0.31),
            ScalarImage(0.10),
            ScalarImage(0.20),
            ScalarImage(1),
            ScalarImage(100),
        )
        self.assertEqual([bool(mask.value) for mask in masks], [False, False, True, False])

    def test_ndvi_class_labels_are_canonical_english(self) -> None:
        expected = [
            "Water / negative values",
            "Bare soil / very dry desert",
            "Very low vegetation activity",
            "Very sparse vegetation",
            "Low vegetation",
            "Moderate vegetation",
            "Dense vegetation",
            "Very dense vegetation",
        ]
        self.assertEqual([item[2] for item in INDEX_CONFIG["NDVI"]["classes"]], expected)
        self.assertEqual([item["name"] for item in compute_mock_index("NDVI", surface_ha=1250)["classes"]], expected)

    def test_supported_sensor_mapping_stays_explicit(self) -> None:
        self.assertEqual(supported_sensors_for_index("OSI_SAR"), ("sentinel-1",))
        self.assertEqual(supported_sensors_for_index("CHANGE_NDVI"), ("sentinel-2", "landsat-8-9"))
        self.assertEqual(supported_sensors_for_index("SUPERVISED_CLASSIFICATION"), ("sentinel-2", "landsat-8-9"))

    def test_mock_results_keep_minimum_expected_structure(self) -> None:
        for index_id in (
            "NDVI",
            "NDWI",
            "NDBI",
            "BSI",
            "SAVI",
            "CHANGE_NDVI",
            "SUPERVISED_CLASSIFICATION",
            "UNSUPERVISED_CLASSIFICATION",
            "OSI_SAR",
        ):
            with self.subTest(index=index_id):
                result = compute_mock_index(index_id, surface_ha=1250)
                self.assertIn("stats", result)
                self.assertIn("classes", result)
                self.assertIn("palette", result)
                self.assertGreater(len(result["classes"]), 0)
                self.assertGreater(len(result["palette"]), 0)
                self.assertEqual(result["mode"], "mock")
                self.assertFalse(result["mock"]["operational"])
                self.assertIn("Mock", result["warning"])

    def test_change_ndvi_mock_palette_matches_reference_ndvi_family(self) -> None:
        result = compute_mock_index("CHANGE_NDVI", surface_ha=1250)
        self.assertEqual(result["palette"], ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"])

    def test_change_bsi_palette_and_labels_match_bare_soil_change_semantics(self) -> None:
        config = CHANGE_DETECTION_CONFIG["BSI"]
        self.assertEqual(config["palette"], ["#f5ecd9", "#e4c58d", "#c99a5d", "#9f6d3c", "#6f4422"])
        self.assertEqual(config["classes"][0][2], "Strong bare-soil decrease")
        self.assertEqual(config["classes"][1][2], "Moderate bare-soil decrease")
        self.assertEqual(config["classes"][3][2], "Moderate bare-soil increase")
        self.assertEqual(config["classes"][4][2], "Strong bare-soil increase")

    def test_savi_online_contract_matches_gee_reflectance_reference(self) -> None:
        config = INDEX_CONFIG["SAVI"]
        classes = config["classes"]
        self.assertEqual(config["bands"], ["B8", "B4"])
        self.assertEqual(config["formula"], "((NIR - Red) / (NIR + Red + 0.5)) * 1.5")
        self.assertEqual(config["l"], 0.5)
        self.assertEqual(config["s2_reflectance_scale"], 0.0001)
        self.assertEqual(config["min"], -0.20)
        self.assertEqual(config["max"], 0.80)
        self.assertEqual(
            config["palette"],
            ["#8C510A", "#BF812D", "#DFC27D", "#F6E8C3", "#FFFFBF", "#D9EF8B", "#A6D96A", "#66BD63", "#1A9850", "#006837"],
        )
        self.assertEqual(len(classes), 5)
        self.assertEqual(classes[0][:3], (-2.0, 0.10, "No / very sparse vegetation"))
        self.assertEqual(classes[1][:3], (0.10, 0.25, "Low vegetation"))
        self.assertEqual(classes[2][:3], (0.25, 0.40, "Moderate vegetation"))
        self.assertEqual(classes[3][:3], (0.40, 0.60, "Dense vegetation"))
        self.assertEqual(classes[4][:3], (0.60, 2.0, "Very dense vegetation"))
        self.assertEqual(_index_native_scale("SAVI", "sentinel-2"), 10)
        self.assertTrue(_scl_reference_payload({"index": "SAVI"}))
        self.assertEqual(SAVI_CANOPY_L, 0.5)
        self.assertEqual(S2_SR_REFLECTANCE_SCALE, 0.0001)

    def test_savi_float_scales_sentinel2_bands_once_and_keeps_landsat_reflectance(self) -> None:
        class RecordingBand:
            def __init__(self, name: str) -> None:
                self.name = name
                self.factor = None

            def multiply(self, factor: float) -> "RecordingBand":
                self.factor = float(factor)
                return self

        class RecordingImage:
            def __init__(self) -> None:
                self.bands: dict[str, RecordingBand] = {}
                self.expression_text = ""
                self.mapping: dict[str, object] = {}
                self.renamed = ""
                self.clamped = False

            def select(self, name: str) -> RecordingBand:
                band = RecordingBand(name)
                self.bands[name] = band
                return band

            def expression(self, text: str, mapping: dict[str, object]) -> "RecordingImage":
                self.expression_text = text
                self.mapping = mapping
                return self

            def clamp(self, *_args: object) -> "RecordingImage":
                self.clamped = True
                return self

            def rename(self, name: str) -> "RecordingImage":
                self.renamed = name
                return self

        sentinel = RecordingImage()
        result = _compute_savi_float_image(sentinel, ["B8", "B4"])
        self.assertIs(result, sentinel)
        self.assertEqual(sentinel.bands["B8"].factor, 0.0001)
        self.assertEqual(sentinel.bands["B4"].factor, 0.0001)
        self.assertIn("L", sentinel.expression_text)
        self.assertEqual(sentinel.mapping["L"], 0.5)
        self.assertFalse(sentinel.clamped)
        self.assertEqual(sentinel.renamed, "SAVI")

        landsat = RecordingImage()
        _compute_savi_float_image(landsat, ["SR_B5", "SR_B4"])
        self.assertIsNone(landsat.bands["SR_B5"].factor)
        self.assertIsNone(landsat.bands["SR_B4"].factor)

        legacy = RecordingImage()
        _compute_index_image(legacy, "SAVI", ["B8", "B4"])
        self.assertIsNone(legacy.bands["B8"].factor)
        self.assertTrue(legacy.clamped)

    def test_savi_cache_version_invalidates_only_old_savi_rows(self) -> None:
        self.assertEqual(
            processing_version_for_analysis({"index": "SAVI"}),
            CURRENT_SAVI_PROCESSING_VERSION,
        )
        self.assertTrue(is_cache_row_compatible({"index": "SAVI", "processing_version": CURRENT_SAVI_PROCESSING_VERSION}))
        self.assertFalse(is_cache_row_compatible({"index": "SAVI", "processing_version": "default-v1"}))
        self.assertTrue(is_cache_row_compatible({"index": "NDVI", "processing_version": CURRENT_NDVI_PROCESSING_VERSION}))
        self.assertFalse(is_cache_row_compatible({"index": "NDVI", "processing_version": "ndvi-gee-reference-continuous-fast-map-v6+analysis-lazy-grid-v1"}))
        self.assertEqual(len(SAVI_CHANGE_PERIOD_CONFIG["classes"]), 6)
        self.assertEqual(CHANGE_DETECTION_CONFIG["SAVI"]["classes"][2][2], "Stable area")
        self.assertEqual(CHANGE_DETECTION_CONFIG["NDBI"]["min"], -1.0)
        self.assertEqual(CHANGE_DETECTION_CONFIG["NDBI"]["max"], 1.0)
        self.assertTrue(_scl_reference_payload({"index": "CHANGE_SAVI"}))
        self.assertEqual(_index_native_scale("NDBI", "sentinel-2"), 20)
        self.assertEqual(_index_native_scale("BSI", "sentinel-2"), 20)
        self.assertIn(CURRENT_SAVI_PROCESSING_VERSION, CURRENT_CHANGE_SAVI_PROCESSING_VERSION)
        self.assertIn(CURRENT_CHANGE_DETECTION_PROCESSING_VERSION, CURRENT_CHANGE_SAVI_PROCESSING_VERSION)
        self.assertEqual(
            processing_version_for_analysis({"index": "CHANGE_NDVI"}),
            f"{CURRENT_CHANGE_DETECTION_PROCESSING_VERSION}+{CURRENT_NDVI_PROCESSING_VERSION}",
        )
        self.assertFalse(
            is_cache_row_compatible({"index": "CHANGE_SAVI", "processing_version": "change-savi-comparison-layers-v3"})
        )
        mock_change_savi = compute_mock_index("CHANGE_SAVI", surface_ha=1250)
        self.assertEqual(mock_change_savi["classes"][2]["name"], "Stable area")
        mock = compute_mock_index("SAVI", surface_ha=1250)
        self.assertEqual([item["name"] for item in mock["classes"]], [item[2] for item in INDEX_CONFIG["SAVI"]["classes"]])
        self.assertEqual(mock["palette"], INDEX_CONFIG["SAVI"]["palette"])

    def test_osi_sar_requires_and_of_three_conditions_before_classification(self) -> None:
        self.assertEqual(OSI_SAR_REFERENCE["logic"], "AND")
        self.assertEqual(OSI_SAR_REFERENCE["dataset"], "COPERNICUS/S1_GRD")
        self.assertEqual(OSI_SAR_REFERENCE["vv_dark_threshold_db"], -18.0)
        self.assertEqual(OSI_SAR_REFERENCE["vh_dark_threshold_db"], -25.0)
        self.assertEqual(OSI_SAR_REFERENCE["contrast_threshold_db"], 2.5)
        self.assertEqual(OSI_SAR_REFERENCE["min_connected_pixels"], 8)
        self.assertEqual(OSI_SAR_REFERENCE["angle_min_deg"], 30.0)
        self.assertEqual(OSI_SAR_REFERENCE["angle_max_deg"], 45.0)
        kwargs = {"connected_pixels": 20, "water": True, "angle_ok": True}
        self.assertEqual(osi_sar_suspicion_class(vv_db=-20, vh_db=-20, contrast_db=4.0, **kwargs), 0)
        self.assertEqual(osi_sar_suspicion_class(vv_db=-20, vh_db=-26, contrast_db=1.0, **kwargs), 0)
        self.assertEqual(osi_sar_suspicion_class(vv_db=-16, vh_db=-26, contrast_db=4.0, **kwargs), 0)
        self.assertEqual(osi_sar_suspicion_class(vv_db=-20, vh_db=-26, contrast_db=4.0, water=False, **{k: kwargs[k] for k in kwargs if k != "water"}), 0)
        self.assertEqual(osi_sar_suspicion_class(vv_db=-18.5, vh_db=-25.5, contrast_db=2.7, **kwargs), 1)
        self.assertEqual(osi_sar_suspicion_class(vv_db=-19.5, vh_db=-25.5, contrast_db=2.7, **kwargs), 2)
        self.assertEqual(osi_sar_suspicion_class(vv_db=-21, vh_db=-28, contrast_db=4.5, **kwargs), 3)
        self.assertEqual(osi_sar_suspicion_class(vv_db=-21, vh_db=-28, contrast_db=4.5, connected_pixels=3, water=True, angle_ok=True), 0)

    def test_osi_sar_options_and_cache_version_are_isolated(self) -> None:
        options = _osi_sar_options({})
        self.assertTrue(options["gee_strict_validation"])
        self.assertEqual(options["processing_logic"], "AND")
        self.assertEqual(options["min_connected_pixels"], 8)
        self.assertEqual(options["speckle_radius_m"], 0)
        self.assertEqual(options["angle_min_deg"], 30.0)
        self.assertEqual(_sentinel1_asset_id("S1A_IW_GRDH_1SDV_20250908T022145_x"), "COPERNICUS/S1_GRD/S1A_IW_GRDH_1SDV_20250908T022145_x")
        self.assertIsNone(_sentinel1_asset_id("sentinel-1-sar-2025-01-01-2026-09-08"))
        self.assertIsNone(_sentinel1_asset_id("sentinel-1_mosaic_gulf"))
        self.assertEqual(processing_version_for_analysis({"index": "OSI_SAR"}), CURRENT_OSI_SAR_PROCESSING_VERSION)
        self.assertTrue(is_cache_row_compatible({"index": "OSI_SAR", "processing_version": CURRENT_OSI_SAR_PROCESSING_VERSION}))
        self.assertFalse(is_cache_row_compatible({"index": "OSI_SAR", "processing_version": "osi-sar-v3"}))
        mock = compute_mock_index("OSI_SAR", surface_ha=1250)
        self.assertEqual([item["name"] for item in mock["classes"]], ["Normal water", "Oil-spill suspect"])
        self.assertTrue(is_cache_row_compatible({"index": "SAVI", "processing_version": CURRENT_SAVI_PROCESSING_VERSION}))
        self.assertTrue(is_cache_row_compatible({"index": "NDVI", "processing_version": CURRENT_NDVI_PROCESSING_VERSION}))


if __name__ == "__main__":
    unittest.main()
