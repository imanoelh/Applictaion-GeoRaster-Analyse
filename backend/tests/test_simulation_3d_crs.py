import pytest

from app.main import CRS_CATALOG, ALLOWED_MANUAL_ANALYSIS_CRS, ALLOWED_MANUAL_REFERENCE_CRS, _clean_platform_settings, _effective_spatial_reference
from app.models import Coordinate3D


def test_epsg_9332_is_catalogued_as_isolated_experimental_3d_crs():
    descriptor = CRS_CATALOG["EPSG:9332"]
    assert descriptor["type"] == "geographic_3d"
    assert descriptor["dimension"] == 3
    assert descriptor["status"] == "experimental"
    assert descriptor["capabilities"]["simulation_3d"] is True
    assert descriptor["capabilities"]["raster_analysis"] is False
    assert "EPSG:9332" not in ALLOWED_MANUAL_ANALYSIS_CRS


def test_simulation_3d_settings_are_backward_compatible_and_strictly_fixed():
    defaults = _clean_platform_settings({})
    assert defaults["simulation_3d_enabled"] is False
    assert defaults["simulation_3d_crs"] == "EPSG:9332"

    configured = _clean_platform_settings(
        {"simulation_3d_enabled": True, "simulation_3d_crs": "EPSG:9333"}
    )
    assert configured["simulation_3d_enabled"] is True
    assert configured["simulation_3d_crs"] == "EPSG:9332"


def test_coordinate_3d_model_validates_geographic_bounds():
    point = Coordinate3D(latitude=24.7, longitude=46.7, ellipsoidal_height_m=650)
    assert point.crs == "EPSG:9332"

    with pytest.raises(ValueError):
        Coordinate3D(latitude=91, longitude=46.7)


def test_epsg_9333_is_restricted_to_geographic_reference():
    descriptor = CRS_CATALOG["EPSG:9333"]
    assert descriptor["type"] == "geographic_2d"
    assert descriptor["capabilities"]["raster_analysis"] is False
    assert "EPSG:9333" not in ALLOWED_MANUAL_ANALYSIS_CRS
    assert "EPSG:9333" in ALLOWED_MANUAL_REFERENCE_CRS

    analysis = {
        "aoi": {
            "geojson": {
                "type": "Polygon",
                "coordinates": [[
                    [46.7, 24.7], [46.8, 24.7], [46.8, 24.8], [46.7, 24.8], [46.7, 24.7],
                ]],
            }
        }
    }
    ref = _effective_spatial_reference(
        analysis,
        settings={"projection_mode": "manual", "manual_crs": "EPSG:9333"},
    )
    assert ref["selected_reference_crs"] == "EPSG:9333"
    assert ref["analysis_crs"] != "EPSG:9333"
    assert str(ref["analysis_crs"]).startswith("EPSG:935")
    assert ref["unit"] == "metre"
    assert "9333" in (ref["warning"] or "")
    assert ref["gee_analysis_crs"] not in {None, "EPSG:9333"}
