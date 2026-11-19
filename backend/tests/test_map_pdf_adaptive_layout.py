from PIL import Image, ImageDraw

from app import main
from app.main import (
    PDF_MARGIN,
    PDF_PAGE_SIZE,
    _download_layout_source_image,
    _pdf_adaptive_image_panel,
    _pdf_aoi_area_km2,
    _pdf_draw_change_visual_block,
    _result_visual_layer,
    _pdf_study_area_page,
    _tile_mosaic_from_template,
)
from app.models import MapPdfExportRequest


PIXEL_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+l2kAAAAASUVORK5CYII="
)


def _payload(*, area_km2=None, area_ha=None):
    geometry = {"bounds": [[25.0, 49.0], [25.01, 49.01]]}
    if area_km2 is not None:
        geometry["area_km2"] = area_km2
    if area_ha is not None:
        geometry["area_ha"] = area_ha
    return MapPdfExportRequest(
        analysis_type="NDVI",
        geometry_info=geometry,
        map_screenshot=PIXEL_DATA_URL,
    )


def test_aoi_area_prefers_km2_and_falls_back_to_hectares():
    assert _pdf_aoi_area_km2(_payload(area_km2=0.75, area_ha=900)) == 0.75
    assert _pdf_aoi_area_km2(_payload(area_ha=75)) == 0.75


def test_adaptive_panels_grow_monotonically_with_aoi_surface():
    slot = (PDF_MARGIN, 214, PDF_PAGE_SIZE[0] - PDF_MARGIN, 918)
    panels = [
        _pdf_adaptive_image_panel(slot, area)
        for area in (0.5, 5, 50, 500)
    ]
    widths = [panel[2] - panel[0] for panel in panels]
    heights = [panel[3] - panel[1] for panel in panels]
    assert widths == sorted(widths)
    assert heights == sorted(heights)
    assert widths[0] < widths[-1]
    assert heights[0] < heights[-1]
    for panel in panels:
        assert slot[0] <= panel[0] < panel[2] <= slot[2]
        assert slot[1] <= panel[1] < panel[3] <= slot[3]


def test_small_aoi_report_page_preserves_page_size_and_centered_image_content():
    source = Image.new("RGB", (900, 500), "#456789")
    result = Image.new("RGB", (900, 500), "#117733")
    page = _pdf_study_area_page(
        _payload(area_km2=0.4),
        source,
        result,
        "2026-07-25 12:00 UTC",
    )
    assert page.size == PDF_PAGE_SIZE
    # The adaptive image remains visible near the centre of each compact panel.
    assert page.getpixel((PDF_PAGE_SIZE[0] // 2, 500)) != (255, 255, 255)
    assert page.getpixel((PDF_PAGE_SIZE[0] // 2, 1250)) != (255, 255, 255)


def test_small_aoi_report_tiles_use_a_detailed_but_bounded_zoom(monkeypatch):
    requested_zooms = []

    def fake_download(url):
        requested_zooms.append(int(url.split("/")[-3]))
        return Image.new("RGB", (256, 256), "#537895")

    monkeypatch.setattr(main, "_download_image_from_url", fake_download)
    image = _tile_mosaic_from_template(
        "https://tiles.example/{z}/{x}/{y}.png",
        [[25.0, 49.0], [25.01, 49.01]],
        target_tile_count=16,
        crop_to_bounds=True,
        max_zoom=18,
        tile_buffer=0,
    )

    assert image is not None
    assert image.width >= 350
    assert image.height >= 350
    assert len(requested_zooms) <= 16
    assert min(requested_zooms) >= 16


def test_comparison_layer_keeps_base_reference_tile_when_layer_rgb_is_empty():
    result = {
        "tiles": {
            "rgb_tile_url": "https://tiles.example/reference/{z}/{x}/{y}.png",
            "index_tile_url": "https://tiles.example/raw/{z}/{x}/{y}.png",
        },
        "comparison_layers": [
            {
                "key": "ndbi_built_detection",
                "tiles": {
                    "rgb_tile_url": None,
                    "index_tile_url": "https://tiles.example/built/{z}/{x}/{y}.png",
                },
            }
        ],
    }

    selected = _result_visual_layer(result, "ndbi_built_detection")

    assert selected["tiles"]["rgb_tile_url"] == result["tiles"]["rgb_tile_url"]
    assert selected["tiles"]["index_tile_url"].endswith("/built/{z}/{x}/{y}.png")


def test_map_layout_uses_the_selected_ndbi_comparison_layer(monkeypatch):
    result = {
        "mode": "gee",
        "tiles": {
            "index_tile_url": "https://tiles.example/raw/{z}/{x}/{y}.png",
        },
        "comparison_layers": [
            {
                "key": "ndbi_built_detection",
                "tiles": {
                    "index_tile_url": "https://tiles.example/built/{z}/{x}/{y}.png",
                },
            }
        ],
    }
    captured = {}
    expected = Image.new("RGB", (64, 64), "#ef6c3e")

    monkeypatch.setattr(main, "_load_run_result_for_layout", lambda _run_id: result)

    def fake_create_index_png_url(selected_result, layer_key=None):
        captured["layer_key"] = layer_key
        captured["tile_url"] = selected_result["tiles"]["index_tile_url"]
        raise RuntimeError("force tile fallback")

    monkeypatch.setattr(main, "create_index_png_url", fake_create_index_png_url)
    monkeypatch.setattr(main, "_download_layout_tile_mosaic", lambda selected_result, _payload: expected)

    payload = MapPdfExportRequest(
        analysis_id="run-ndbi",
        analysis_type="NDBI",
        geometry_info={"bounds": [[25.0, 49.0], [25.01, 49.01]]},
        map_screenshot=PIXEL_DATA_URL,
        metadata={"layer_key": "ndbi_built_detection"},
    )
    image = _download_layout_source_image(payload)

    assert captured["layer_key"] == "ndbi_built_detection"
    assert captured["tile_url"].endswith("/built/{z}/{x}/{y}.png")
    assert image is expected


def test_change_detection_visual_block_contains_complete_portrait_aoi():
    source = Image.new("RGB", (200, 600), "#22aa44")
    source_draw = ImageDraw.Draw(source)
    source_draw.rectangle((0, 0, 199, 199), fill="#dd3322")
    source_draw.rectangle((0, 400, 199, 599), fill="#2255dd")
    page = Image.new("RGB", PDF_PAGE_SIZE, "white")
    draw = ImageDraw.Draw(page)

    _pdf_draw_change_visual_block(
        page,
        draw,
        (PDF_MARGIN, 282, PDF_PAGE_SIZE[0] - PDF_MARGIN, 706),
        "5.1 Classified BSI map - Period 1",
        "2026-01-01 to 2026-03-31",
        source,
        "Interpretation text",
    )

    colors = set(page.getdata())
    assert (221, 51, 34) in colors
    assert (34, 170, 68) in colors
    assert (34, 85, 221) in colors
