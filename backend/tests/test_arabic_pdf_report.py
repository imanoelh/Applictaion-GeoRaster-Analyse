from PIL import Image

from app.main import (
    PDF_PAGE_SIZE,
    _pdf_cover_page,
    _pdf_display_text,
    _pdf_result_legend,
    _pdf_result_page,
    _pdf_study_area_page,
)
from app.models import MapPdfExportRequest


def _payload(language: str = "ar") -> MapPdfExportRequest:
    return MapPdfExportRequest(
        analysis_type="SUPERVISED_CLASSIFICATION",
        language=language,
        geometry_info={
            "label": "Selected area of interest",
            "bounds_text": "24.5, 49.6 -> 25.4, 49.9",
            "area_ha": 397,
            "area_km2": 3.97,
        },
        parameters={
            "sensor": "Sentinel-2",
            "start_date": "2025-01-01",
            "end_date": "2026-07-31",
            "resolution": "10 m",
        },
        map_screenshot="placeholder",
        statistics={"min": 1, "max": 7, "mean": 3.4, "std": 1.1, "pixels": 39700, "surface_ha": 397},
        classes=[
            {
                "name": "Water",
                "description": "Open water and permanent water surfaces.",
                "color": "#2b83ba",
                "surface_ha": 42,
                "pct": 10.6,
            },
            {
                "name": "Built-up",
                "description": "Urban, industrial, road, and impervious surfaces.",
                "color": "#d7191c",
                "surface_ha": 355,
                "pct": 89.4,
            },
        ],
        interpretation="English backend interpretation.",
        quality_summary={"message": "English backend quality message."},
        metadata={"source_data": "COPERNICUS/S2_SR_HARMONIZED", "spatial_resolution": "10 m"},
    )


def test_pdf_language_is_backward_compatible():
    assert _payload("en").language == "en"
    assert _payload("ar").language == "ar"


def test_arabic_text_is_reshaped_for_pillow_rtl_rendering():
    logical = "التصنيف الموجّه للغطاء الأرضي"
    rendered = _pdf_display_text(logical, "ar")
    assert rendered != logical
    assert _pdf_display_text("Supervised Classification", "en") == "Supervised Classification"


def test_arabic_report_localizes_known_land_cover_legend():
    legend = _pdf_result_legend(_payload())
    assert legend[0]["label"] == "مياه"
    assert legend[1]["label"] == "مناطق مبنية"
    assert "مفتوحة" in legend[0]["description"]


def test_arabic_professional_report_pages_keep_existing_layout_size():
    payload = _payload()
    reference = Image.new("RGB", (900, 500), "#a6b7a0")
    result = Image.new("RGB", (900, 500), "#d9c77f")
    pages = [
        _pdf_cover_page(payload, reference, "2026-07-31 12:00 UTC"),
        _pdf_study_area_page(payload, reference, result, "2026-07-31 12:00 UTC"),
        _pdf_result_page(payload, result, None, "2026-07-31 12:00 UTC"),
    ]
    assert [page.size for page in pages] == [PDF_PAGE_SIZE, PDF_PAGE_SIZE, PDF_PAGE_SIZE]
