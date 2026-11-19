import copy
import csv
import io

from PIL import Image

from app.main import (
    MAP_LAYOUT_SIZE,
    _content_disposition,
    _csv_export_bytes,
    _export_download_filename,
    _localize_result_export,
    _map_layout_image,
)
from app.models import ExportCreate, MapPdfExportRequest


def _result() -> dict:
    return {
        "analysis_type": "SAVI",
        "analysis": {
            "index": "SAVI",
            "id": "analysis-1",
            "spatial_reference": {
                "national_system": "SANRS",
                "reference_frame": "KSA-GRF17",
                "analysis_crs": "EPSG:9359",
                "analysis_crs_name": "KSA-GRF17 / UTM zone 39N",
                "unit": "metre",
                "selection_mode": "automatic",
                "crosses_utm_zone": False,
            },
        },
        "run_id": "run-1234567890",
        "stats": {"min": -0.1, "max": 0.9, "mean": 0.42, "surface_ha": 34, "pixels": 3627},
        "classes": [
            {
                "name": "Bare soil or no vegetation",
                "description": "Bare soil or no vegetation",
                "surface_ha": 3.4,
                "pct": 10,
                "pixels": 363,
                "color": "#8c510a",
            },
            {
                "name": "Very high vegetation vigor",
                "description": "Very high vegetation vigor",
                "surface_ha": 7.09,
                "pct": 20.9,
                "pixels": 759,
                "color": "#006837",
            },
        ],
        "histogram": [{"bin": 0.5, "count": 12}],
        "interpretation": "English interpretation",
        "quality_summary": {"message": "English quality message"},
    }


def test_export_language_contract_defaults_to_english_and_accepts_arabic():
    assert ExportCreate().language == "en"
    assert ExportCreate(language="ar").language == "ar"


def test_arabic_csv_localizes_display_text_but_keeps_official_analysis_name():
    csv_bytes = _csv_export_bytes(_result(), "ar")
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    text = csv_bytes.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=","))
    assert "المفتاح" in text
    assert "المساحة بالهكتار" in text
    assert "تربة عارية أو غياب الغطاء النباتي" in text
    assert "SAVI" in text
    assert rows[0] == ["البيانات الوصفية", "المفتاح", "القيمة"]
    assert any(row and row[0] == "الإحصاءات" for row in rows)
    assert any(row and row[0] == "الفئات" for row in rows)
    assert any(row and row[0] == "المدرج التكراري" for row in rows)
    assert not {"metadata", "stats", "classes", "histogram"}.intersection(
        cell for row in rows for cell in row
    )


def test_english_csv_format_remains_unchanged():
    text = _csv_export_bytes(_result(), "en").decode("utf-8-sig")
    assert text.startswith("metadata;key;value")
    assert "stats;mean;0.42" in text
    assert "classes;name;surface_ha;pct;pixels" in text
    assert "histogram;bin;count" in text


def test_arabic_json_copy_does_not_modify_stored_scientific_result():
    source = _result()
    before = copy.deepcopy(source)
    localized = _localize_result_export(source, "ar")

    assert source == before
    assert localized is not source
    assert localized["analysis_type"] == "SAVI"
    assert localized["analysis"]["index"] == "SAVI"
    assert localized["stats"] == source["stats"]
    assert localized["classes"][0]["name"] == "تربة عارية أو غياب الغطاء النباتي"
    assert localized["interpretation"] != source["interpretation"]


def test_arabic_download_names_keep_official_analysis_slug_and_extension():
    assert _export_download_filename("stats_csv", "run-1234567890", _result(), "ar").startswith("GeoRaster_إحصاءات_SAVI_")
    assert _export_download_filename("map_png", "run-1234567890", _result(), "ar").startswith("GeoRaster_خريطة_SAVI_")
    assert _export_download_filename("geotiff", "run-1234567890", _result(), "ar").startswith("GeoRaster_راستر_SAVI_")
    assert _export_download_filename("geotiff", "run-1234567890", _result(), "en").endswith(".tif")


def test_gee_url_exports_are_stored_with_url_suffix_not_tif_or_png():
    from app.main import _export_storage_filename

    assert _export_storage_filename("raster_run-1.tif", "application/vnd.google-earth-engine.url").endswith(".url")
    assert _export_storage_filename("map_run-1.png", "application/vnd.google-earth-engine.url").endswith(".url")
    assert _export_storage_filename("stats_run-1.csv", "text/csv; charset=utf-8").endswith(".csv")


def test_unicode_content_disposition_has_safe_fallback_and_utf8_filename():
    header = _content_disposition("GeoRaster_إحصاءات_SAVI.csv")
    assert header.isascii()
    assert "filename=\"" in header
    assert "filename*=UTF-8''" in header
    assert "%D8%A5" in header


def test_arabic_map_layout_preserves_dimensions_and_renders_without_data_changes():
    payload = MapPdfExportRequest(
        analysis_type="SAVI",
        language="ar",
        map_screenshot="placeholder",
        classes=_result()["classes"],
    )
    source_image = Image.new("RGB", (900, 600), "#d7e3c5")
    layout = _map_layout_image(payload, source_image, "2026-07-31 12:00 UTC")
    assert layout.size == MAP_LAYOUT_SIZE
    assert source_image.size == (900, 600)
