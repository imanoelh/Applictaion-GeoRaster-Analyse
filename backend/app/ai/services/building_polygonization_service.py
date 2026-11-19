from __future__ import annotations

import math
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from affine import Affine
from rasterio.crs import CRS
from rasterio.features import shapes
from rasterio.warp import transform, transform_geom
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from ..errors import AIRasterError
from .postprocessing_service import BuildingMaskResult


@dataclass(frozen=True)
class PolygonizationConfig:
    polygon_connectivity: int = 8
    simplify_tolerance: float = 0.0

    def __post_init__(self) -> None:
        if self.polygon_connectivity not in {4, 8}:
            raise ValueError("polygon_connectivity doit valoir 4 ou 8.")
        if not math.isfinite(self.simplify_tolerance) or self.simplify_tolerance < 0:
            raise ValueError("simplify_tolerance doit etre fini et positif ou nul.")

    def public_summary(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "simplification_enabled": self.simplify_tolerance > 0,
            "multipolygon_strategy": "keep_as_one_feature",
            "invalid_geometry_strategy": "make_valid_when_needed",
        }


@dataclass(frozen=True)
class BuildingFeature:
    building_id: str
    raster_id: str
    geometry: Polygon | MultiPolygon
    geometry_type: str
    crs: str
    pixel_count: int
    area_map_units: float
    area_m2: float | None
    perimeter_map_units: float
    perimeter_m: float | None
    centroid_x: float
    centroid_y: float
    bbox: tuple[float, float, float, float]
    model_name: str
    model_version: str
    probability_threshold: float
    postprocessing_version: str
    model_id: str = "unet_resnet34"
    model_architecture: str | None = None
    model_checkpoint_hash: str | None = None
    preprocessing_profile: str | None = None
    tile_size: int | None = None

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.building_id,
            "geometry": mapping(self.geometry),
            "properties": {
                "building_id": self.building_id,
                "raster_id": self.raster_id,
                "geometry_type": self.geometry_type,
                "pixel_count": self.pixel_count,
                "area_map_units": self.area_map_units,
                "area_m2": self.area_m2,
                "perimeter_map_units": self.perimeter_map_units,
                "perimeter_m": self.perimeter_m,
                "centroid_x": self.centroid_x,
                "centroid_y": self.centroid_y,
                "bbox": list(self.bbox),
                "model_id": self.model_id,
                "model_architecture": self.model_architecture,
                "model_checkpoint_hash": self.model_checkpoint_hash,
                "preprocessing_profile": self.preprocessing_profile,
                "tile_size": self.tile_size,
            },
        }


@dataclass(frozen=True)
class BuildingVectorResult:
    raster_id: str
    source_type: str | None
    source_resolution: tuple[float, float]
    crs: str
    building_features: tuple[BuildingFeature, ...]
    feature_count: int
    total_area_map_units: float
    total_area_m2: float | None
    bounds: dict[str, float]
    model_name: str
    model_version: str
    model_mode: str
    threshold: float
    postprocessing_version: str
    polygonization_version: str
    polygonization_config: dict[str, Any]
    postprocessing_config: dict[str, Any]
    geometry_types: dict[str, int]
    postprocessing_time_ms: float
    polygonization_time_ms: float
    model_id: str = "unet_resnet34"
    model_architecture: str | None = None
    model_checkpoint_hash: str | None = None
    tile_size: int | None = None
    preprocessing_profile: str | None = None
    model_metadata: dict[str, Any] | None = None

    def to_geojson(self) -> dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "features": [feature.to_geojson_feature() for feature in self.building_features],
        }


class BuildingPolygonizationService:
    """Convert one cleaned global raster mask to georeferenced polygon candidates."""

    POSTPROCESSING_VERSION = "stage-6-v1"
    POLYGONIZATION_VERSION = "stage-7-v1"

    def polygonize(
        self,
        mask_result: BuildingMaskResult,
        *,
        config: PolygonizationConfig | None = None,
    ) -> BuildingVectorResult:
        config = config or PolygonizationConfig()
        self._validate_mask_result(mask_result)
        started = time.perf_counter()
        affine = Affine(*mask_result.transform[:6])
        effective_mask = np.logical_and(
            mask_result.global_binary_mask == 1,
            mask_result.global_valid_mask,
        )

        geometries: list[Polygon | MultiPolygon] = []
        for geometry_mapping, value in shapes(
            mask_result.global_binary_mask,
            mask=effective_mask,
            connectivity=config.polygon_connectivity,
            transform=affine,
        ):
            if int(value) != 1:
                continue
            geometry = self._validated_polygonal_geometry(shape(geometry_mapping))
            if geometry is None:
                continue
            if config.simplify_tolerance > 0:
                geometry = self._validated_polygonal_geometry(
                    geometry.simplify(config.simplify_tolerance, preserve_topology=True)
                )
                if geometry is None:
                    continue
            geometries.append(geometry)

        inverse = ~affine
        geometries.sort(key=lambda geometry: self._raster_sort_key(geometry, inverse))
        metre_units = self._uses_metre_units(mask_result.crs)
        pixel_area = abs(float(affine.determinant))
        features: list[BuildingFeature] = []
        for index, geometry in enumerate(geometries, start=1):
            centroid = geometry.centroid
            area = float(geometry.area)
            perimeter = float(geometry.length)
            metric_area, metric_perimeter = self._metric_measurements(
                geometry,
                source_crs=mask_result.crs,
                native_area=area,
                native_perimeter=perimeter,
                native_is_metric=metre_units,
            )
            features.append(
                BuildingFeature(
                    building_id=f"building_{index:06d}",
                    raster_id=mask_result.raster_id,
                    geometry=geometry,
                    geometry_type=geometry.geom_type,
                    crs=mask_result.crs,
                    pixel_count=int(round(area / pixel_area)),
                    area_map_units=area,
                    area_m2=metric_area,
                    perimeter_map_units=perimeter,
                    perimeter_m=metric_perimeter,
                    centroid_x=float(centroid.x),
                    centroid_y=float(centroid.y),
                    bbox=tuple(float(value) for value in geometry.bounds),
                    model_name=mask_result.model_name,
                    model_version=mask_result.model_version,
                    probability_threshold=mask_result.threshold,
                    postprocessing_version=self.POSTPROCESSING_VERSION,
                    model_id=mask_result.model_id,
                    model_architecture=mask_result.model_architecture,
                    model_checkpoint_hash=mask_result.model_checkpoint_hash,
                    preprocessing_profile=mask_result.preprocessing_profile,
                    tile_size=mask_result.tile_size,
                )
            )

        geometry_types = dict(sorted(Counter(item.geometry_type for item in features).items()))
        total_area = float(sum(item.area_map_units for item in features))
        metric_areas = [float(item.area_m2) for item in features if item.area_m2 is not None]
        return BuildingVectorResult(
            raster_id=mask_result.raster_id,
            source_type=mask_result.source_type,
            source_resolution=mask_result.resolution,
            crs=mask_result.crs,
            building_features=tuple(features),
            feature_count=len(features),
            total_area_map_units=total_area,
            total_area_m2=sum(metric_areas) if len(metric_areas) == len(features) and metric_areas else None,
            bounds=dict(mask_result.bounds),
            model_name=mask_result.model_name,
            model_version=mask_result.model_version,
            model_mode=mask_result.model_mode,
            threshold=mask_result.threshold,
            postprocessing_version=self.POSTPROCESSING_VERSION,
            polygonization_version=self.POLYGONIZATION_VERSION,
            polygonization_config=config.public_summary(),
            postprocessing_config=dict(mask_result.postprocessing_config),
            geometry_types=geometry_types,
            postprocessing_time_ms=mask_result.processing_time_ms,
            polygonization_time_ms=(time.perf_counter() - started) * 1000.0,
            model_id=mask_result.model_id,
            model_architecture=mask_result.model_architecture,
            model_checkpoint_hash=mask_result.model_checkpoint_hash,
            tile_size=mask_result.tile_size,
            preprocessing_profile=mask_result.preprocessing_profile,
            model_metadata=dict(mask_result.model_metadata or {}),
        )

    @classmethod
    def _validated_polygonal_geometry(
        cls,
        geometry: BaseGeometry,
    ) -> Polygon | MultiPolygon | None:
        if geometry.is_empty:
            return None
        repaired = make_valid(geometry) if not geometry.is_valid else geometry
        polygonal = cls._polygonal_only(repaired)
        if polygonal is None or polygonal.is_empty or not polygonal.is_valid:
            return None
        return polygonal

    @staticmethod
    def _polygonal_only(geometry: BaseGeometry) -> Polygon | MultiPolygon | None:
        if isinstance(geometry, Polygon):
            return geometry
        if isinstance(geometry, MultiPolygon):
            return geometry
        if isinstance(geometry, GeometryCollection):
            parts: list[Polygon] = []
            for item in geometry.geoms:
                if isinstance(item, Polygon):
                    parts.append(item)
                elif isinstance(item, MultiPolygon):
                    parts.extend(item.geoms)
            if not parts:
                return None
            merged = unary_union(parts)
            return merged if isinstance(merged, (Polygon, MultiPolygon)) else None
        return None

    @staticmethod
    def _raster_sort_key(
        geometry: Polygon | MultiPolygon,
        inverse_transform: Affine,
    ) -> tuple[float, float, str]:
        point = geometry.representative_point()
        col, row = inverse_transform * (point.x, point.y)
        return (round(float(row), 9), round(float(col), 9), geometry.wkb_hex)

    @staticmethod
    def _uses_metre_units(crs_value: str) -> bool:
        crs = CRS.from_string(crs_value)
        if not crs.is_projected:
            return False
        unit_name, unit_factor = crs.linear_units_factor
        return unit_name.lower() in {"metre", "meter", "metres", "meters"} and math.isclose(
            float(unit_factor), 1.0, rel_tol=0.0, abs_tol=1e-12
        )

    @classmethod
    def _metric_measurements(
        cls,
        geometry: Polygon | MultiPolygon,
        *,
        source_crs: str,
        native_area: float,
        native_perimeter: float,
        native_is_metric: bool,
    ) -> tuple[float | None, float | None]:
        if native_is_metric:
            return native_area, native_perimeter
        source = CRS.from_string(source_crs)
        if not source.is_geographic and not source.is_projected:
            return None, None
        # Select a local UTM zone from the native centroid. This is only for
        # measurements; the feature geometry and API GeoJSON remain native/WGS84.
        lon_values, lat_values = transform(
            source,
            CRS.from_epsg(4326),
            [float(geometry.centroid.x)],
            [float(geometry.centroid.y)],
        )
        lon, lat = float(lon_values[0]), float(lat_values[0])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return None, None
        zone = min(60, max(1, int(math.floor((lon + 180.0) / 6.0)) + 1))
        epsg = (32600 if lat >= 0 else 32700) + zone
        metric_mapping = transform_geom(
            source,
            CRS.from_epsg(epsg),
            geometry.__geo_interface__,
            precision=-1,
        )
        metric_geometry = shape(metric_mapping)
        if metric_geometry.is_empty or not metric_geometry.is_valid:
            metric_geometry = make_valid(metric_geometry)
        if metric_geometry.is_empty:
            return None, None
        return float(metric_geometry.area), float(metric_geometry.length)

    @staticmethod
    def _validate_mask_result(mask_result: BuildingMaskResult) -> None:
        expected = (mask_result.height, mask_result.width)
        if mask_result.global_binary_mask.shape != expected:
            raise AIRasterError("POLYGONIZATION_MASK_INVALID", "Le masque binaire a des dimensions invalides.")
        if mask_result.global_valid_mask.shape != expected:
            raise AIRasterError("POLYGONIZATION_MASK_INVALID", "Le masque de validite a des dimensions invalides.")
        if mask_result.global_binary_mask.ndim != 2:
            raise AIRasterError("POLYGONIZATION_MASK_INVALID", "Le masque doit etre bidimensionnel.")
        values = np.unique(mask_result.global_binary_mask)
        if not np.isin(values, (0, 1)).all():
            raise AIRasterError("POLYGONIZATION_MASK_INVALID", "Le masque doit contenir uniquement 0 et 1.")
        if not mask_result.crs or len(mask_result.transform) < 6:
            raise AIRasterError("POLYGONIZATION_GEOREFERENCE_INVALID", "CRS ou transform manquant.")
        affine = Affine(*mask_result.transform[:6])
        if math.isclose(float(affine.determinant), 0.0, abs_tol=1e-15):
            raise AIRasterError("POLYGONIZATION_GEOREFERENCE_INVALID", "Transform non inversible.")
