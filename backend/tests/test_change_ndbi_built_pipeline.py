from app import gee_client
from app.gee_client import (
    CHANGE_DETECTION_CONFIG,
    NDBI_BUILT_DETECTION_CONFIG,
    _change_index_image,
    _change_period_layer,
    _period_payload,
    _scl_reference_payload,
)


def test_change_ndbi_uses_float_p2_minus_p1():
    config = CHANGE_DETECTION_CONFIG["NDBI"]

    assert config["min"] == -1.0
    assert config["max"] == 1.0
    assert [item[:2] for item in config["classes"]] == [
        (-2.0, -0.25),
        (-0.25, -0.08),
        (-0.08, 0.08),
        (0.08, 0.25),
        (0.25, 2.0),
    ]
    assert config["classes"][2][2] == "Stable area"
    assert "not confirmed new construction" in config["interpretation"].lower()


def test_change_period_payload_uses_base_index_for_scl():
    payload = _period_payload(
        {
            "index": "CHANGE_SAVI",
            "period_1": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
            "max_cloud_pct": 20,
        },
        "period_1",
    )
    assert payload["index"] == "SAVI"
    assert payload["date_start"] == "2024-01-01"
    assert payload["date_end"] == "2024-01-31"
    assert _scl_reference_payload(payload)
    assert _scl_reference_payload({"index": "CHANGE_NDVI"})
    assert _scl_reference_payload({"index": "CHANGE_NDBI"})


def test_change_index_image_reuses_validated_raster(monkeypatch):
    captured = {}

    class Raster:
        def clip(self, geom):
            captured["geom"] = geom
            return "clipped"

    def fake_raster(image, index_id, bands):
        captured["image"] = image
        captured["index_id"] = index_id
        captured["bands"] = bands
        return Raster()

    monkeypatch.setattr(gee_client, "_index_raster_for_analysis", fake_raster)
    monkeypatch.setattr(gee_client, "_index_bands_for_sensor", lambda index, sensor: ["B8", "B4"])

    result = _change_index_image("mosaic", "SAVI", "sentinel-2", "aoi")
    assert captured["index_id"] == "SAVI"
    assert captured["bands"] == ["B8", "B4"]
    assert captured["geom"] == "aoi"
    assert result == "clipped"


def test_change_ndbi_period_layer_keeps_optional_built_detection(monkeypatch):
    raw_image = object()
    source_image = object()
    classified_image = object()
    built_classes = [
        {"name": item[2], "color": item[3], "surface_ha": area}
        for item, area in zip(
            NDBI_BUILT_DETECTION_CONFIG["classes"],
            (50.0, 10.0, 25.0, 15.0),
        )
    ]
    captured = {}

    def fake_context(analysis, selected_source, selected_ndbi, sensor, geom):
        captured.update(
            analysis=analysis,
            source=selected_source,
            ndbi=selected_ndbi,
            sensor=sensor,
            geom=geom,
        )
        return {
            "classified": classified_image,
            "vis": {"min": 0, "max": 3, "palette": NDBI_BUILT_DETECTION_CONFIG["palette"]},
            "cfg": NDBI_BUILT_DETECTION_CONFIG,
            "ndvi": object(),
            "ndwi": object(),
            "bsi": object(),
            "built_probability": object(),
            "bare_probability": object(),
            "stable_built_reference": object(),
            "historical_built_surface": object(),
        }

    monkeypatch.setattr(gee_client, "_ndbi_built_detection_context", fake_context)
    monkeypatch.setattr(gee_client, "_compute_ndbi_classes", lambda *args, **kwargs: built_classes)
    monkeypatch.setattr(
        gee_client,
        "_compute_stats",
        lambda *args, **kwargs: {"min": -0.2, "max": 0.3, "surface_ha": 100},
    )
    monkeypatch.setattr(
        gee_client,
        "_tile_url",
        lambda image, vis: f"tile://{'built' if image is classified_image else 'raw'}",
    )

    layer = _change_period_layer(
        key="ndbi_period_1_built",
        index_key="NDBI",
        title="NDBI built-up evidence - Period 1",
        topic="Built-up / Artificialization",
        period={"start_date": "2025-01-01", "end_date": "2025-03-31"},
        image=raw_image,
        geom="aoi",
        surface_ha=100,
        scale=20,
        sensor="sentinel-2",
        source_image=source_image,
        analysis_crs="EPSG:9359",
        layer_mode="built",
    )

    assert captured["analysis"] == {
        "date_start": "2025-01-01",
        "date_end": "2025-03-31",
    }
    assert captured["source"] is source_image
    assert captured["ndbi"] is raw_image
    assert layer["tiles"]["index_tile_url"] == "tile://built"
    assert layer["palette"] == NDBI_BUILT_DETECTION_CONFIG["palette"]
    assert [item["name"] for item in layer["classes"]] == [
        "No built-up evidence",
        "Potential impervious surface or road",
        "Built-up area detected",
        "High-confidence built-up area",
    ]
    assert layer["stats"]["built_surface_ha"] == 50.0
    assert layer["stats"]["built_pct"] == 50.0
    assert "not the scientific Change Detection source" in layer["metadata"]["visualization"]


def test_change_period_layer_uses_base_index_visualization(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        gee_client,
        "_tile_url",
        lambda image, vis: captured.setdefault("vis", vis) or "tile://ndvi",
    )
    monkeypatch.setattr(
        gee_client,
        "_compute_index_summary",
        lambda *args, **kwargs: (
            {"min": 0.02, "max": 0.41, "mean": 0.12, "std": 0.08, "surface_ha": 100, "pixels": 40},
            [{"bin": 0.1, "count": 12}],
            [{"name": "Low vegetation", "color": "#fee08b", "surface_ha": 40, "pct": 40}],
        ),
    )
    monkeypatch.setattr(gee_client, "_index_bands_for_sensor", lambda index, sensor: ["B8", "B4"])

    layer = _change_period_layer(
        key="ndvi_period_1",
        index_key="NDVI",
        title="NDVI - Period 1",
        topic="Vegetation",
        period={"start_date": "2024-09-01", "end_date": "2025-08-01"},
        image="ndvi-float",
        geom="aoi",
        surface_ha=100,
        scale=10,
        sensor="sentinel-2",
    )

    assert captured["vis"]["min"] == gee_client.INDEX_CONFIG["NDVI"]["min"]
    assert captured["vis"]["max"] == gee_client.INDEX_CONFIG["NDVI"]["max"]
    assert captured["vis"]["palette"] == gee_client.INDEX_CONFIG["NDVI"]["palette"]
    assert layer["palette"] == gee_client.INDEX_CONFIG["NDVI"]["palette"]
    assert layer["stats"]["min"] == 0.02
    assert layer["stats"]["mean"] == 0.12
    assert layer["index"] == "NDVI"

