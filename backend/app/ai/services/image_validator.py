from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.io import DatasetReader

from ..errors import AIRasterError


class RasterValidationError(AIRasterError):
    """Raised when a materialized raster is not safe for downstream use."""

    def __init__(self, message: str, *, code: str = "LOCAL_RASTER_INVALID", technical_detail: str | None = None) -> None:
        super().__init__(code, message, technical_detail=technical_detail)


class ImageValidator:
    """Validate source-specific structural and geospatial raster contracts."""

    SENTINEL_SOURCES = {"sentinel2", "sentinel2_gee"}
    ORTHOPHOTO_SOURCES = {"orthophoto", "orthophoto_local"}
    SENTINEL_BANDS = ("B4", "B3", "B2")
    SENTINEL_PROFILE = "sentinel2_sr_v1"
    ORTHOPHOTO_PROFILE = "rgb_orthophoto_uint8_v1"

    def validate(
        self,
        raster_path: Path,
        *,
        source: str,
        band_mapping: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        path = Path(raster_path)
        if not path.is_file() or path.stat().st_size <= 0:
            raise RasterValidationError("Le GeoTIFF est absent ou vide.", code="LOCAL_RASTER_NOT_FOUND")

        source_type = str(source or "").strip().lower()
        try:
            with rasterio.open(path) as dataset:
                self._validate_geospatial_contract(dataset)
                if source_type in self.SENTINEL_SOURCES:
                    band_names, band_indexes, source_profile = self._validate_sentinel(dataset)
                    normalized_source = "sentinel2_gee"
                elif source_type in self.ORTHOPHOTO_SOURCES:
                    band_names, band_indexes, source_profile = self._validate_orthophoto(dataset, band_mapping)
                    normalized_source = "orthophoto_local"
                else:
                    raise RasterValidationError(f"Type de source raster inconnu: {source_type or 'vide'}.")

                bounds = dataset.bounds
                resolution_x = abs(float(dataset.res[0]))
                resolution_y = abs(float(dataset.res[1]))
                resolution = round((resolution_x + resolution_y) / 2.0, 6)
                return {
                    "valid": True,
                    "source": source,
                    "source_type": normalized_source,
                    "source_profile": source_profile,
                    "bands": int(dataset.count),
                    "band_names": list(band_names),
                    "band_indexes": list(band_indexes),
                    "color_interpretation": [item.name for item in dataset.colorinterp],
                    "crs": dataset.crs.to_string(),
                    "width": int(dataset.width),
                    "height": int(dataset.height),
                    "resolution_x": resolution_x,
                    "resolution_y": resolution_y,
                    "resolution_m": resolution,
                    "resolution_class": self._resolution_class(dataset.crs, resolution),
                    "bounds": {
                        "left": float(bounds.left),
                        "bottom": float(bounds.bottom),
                        "right": float(bounds.right),
                        "top": float(bounds.top),
                    },
                    "transform": [float(value) for value in tuple(dataset.transform)],
                    "dtype": str(dataset.dtypes[band_indexes[0] - 1]),
                    "nodata": float(dataset.nodata) if dataset.nodata is not None else None,
                }
        except RasterValidationError:
            raise
        except AIRasterError as exc:
            raise RasterValidationError(exc.message, code=exc.code) from exc
        except Exception as exc:
            raise RasterValidationError("GeoTIFF illisible par Rasterio.", technical_detail=str(exc)) from exc

    @classmethod
    def _validate_geospatial_contract(cls, dataset: DatasetReader) -> None:
        if dataset.width <= 0 or dataset.height <= 0:
            raise RasterValidationError("Les dimensions du raster sont invalides.")
        if dataset.count < 3:
            raise RasterValidationError("Le raster RGB doit contenir au moins 3 bandes.", code="UNSUPPORTED_BAND_CONFIGURATION")
        if dataset.crs is None:
            raise RasterValidationError("Le raster ne contient aucun CRS.", code="RASTER_CRS_MISSING")
        if not cls._valid_transform(dataset.transform):
            raise RasterValidationError("La transformation affine du raster est invalide.")
        bounds = dataset.bounds
        values = (bounds.left, bounds.bottom, bounds.right, bounds.top)
        if not all(math.isfinite(float(value)) for value in values):
            raise RasterValidationError("Les limites geographiques du raster sont invalides.")
        if bounds.left >= bounds.right or bounds.bottom >= bounds.top:
            raise RasterValidationError("Les limites geographiques du raster sont vides.")
        resolution_x = abs(float(dataset.res[0]))
        resolution_y = abs(float(dataset.res[1]))
        if not all(math.isfinite(value) and value > 0 for value in (resolution_x, resolution_y)):
            raise RasterValidationError("La resolution du raster doit etre finie et positive.")

    @classmethod
    def _validate_sentinel(cls, dataset: DatasetReader) -> tuple[tuple[str, str, str], tuple[int, int, int], str]:
        if dataset.count != 3:
            raise RasterValidationError("Le raster Sentinel-2 doit contenir exactement les bandes B4/B3/B2.", code="UNSUPPORTED_BAND_CONFIGURATION")
        if tuple(dataset.dtypes) != ("uint16", "uint16", "uint16"):
            raise RasterValidationError("Le raster Sentinel-2 doit etre uint16.", code="UNSUPPORTED_RASTER_DTYPE")
        descriptions = tuple(str(value) if value else "" for value in dataset.descriptions)
        if any(descriptions) and not all(descriptions):
            raise RasterValidationError("Les noms de bandes Sentinel-2 sont incomplets.", code="UNSUPPORTED_BAND_CONFIGURATION")
        if all(descriptions) and descriptions != cls.SENTINEL_BANDS:
            raise RasterValidationError("L'ordre des bandes Sentinel-2 doit etre B4, B3, B2.", code="UNSUPPORTED_BAND_CONFIGURATION")
        return cls.SENTINEL_BANDS, (1, 2, 3), cls.SENTINEL_PROFILE

    @classmethod
    def _validate_orthophoto(
        cls,
        dataset: DatasetReader,
        configured_mapping: dict[str, int] | None,
    ) -> tuple[tuple[str, str, str], tuple[int, int, int], str]:
        if dataset.count != 3:
            raise RasterValidationError("L'orthophoto doit contenir exactement trois bandes RGB.", code="UNSUPPORTED_BAND_CONFIGURATION")
        if tuple(dataset.dtypes) != ("uint8", "uint8", "uint8"):
            raise RasterValidationError("Le profil orthophoto actuel accepte uniquement le dtype uint8.", code="UNSUPPORTED_RASTER_DTYPE")
        indexes = cls._colorinterp_mapping(dataset) or cls._description_mapping(dataset)
        if indexes is None and configured_mapping is not None:
            try:
                indexes = tuple(int(configured_mapping[key]) for key in ("R", "G", "B"))
            except (KeyError, TypeError, ValueError) as exc:
                raise RasterValidationError("Le mapping explicite doit definir R, G et B.", code="UNSUPPORTED_BAND_CONFIGURATION") from exc
        if indexes is None:
            raise RasterValidationError(
                "L'ordre RGB est ambigu: ColorInterp, descriptions R/G/B ou mapping explicite requis.",
                code="UNSUPPORTED_BAND_CONFIGURATION",
            )
        if len(set(indexes)) != 3 or any(value < 1 or value > dataset.count for value in indexes):
            raise RasterValidationError("Le mapping RGB doit utiliser trois bandes distinctes et valides.", code="UNSUPPORTED_BAND_CONFIGURATION")
        return ("R", "G", "B"), indexes, cls.ORTHOPHOTO_PROFILE

    @staticmethod
    def _colorinterp_mapping(dataset: DatasetReader) -> tuple[int, int, int] | None:
        names = [item.name.lower() for item in dataset.colorinterp]
        if all(name in names for name in ("red", "green", "blue")):
            values = tuple(names.index(name) + 1 for name in ("red", "green", "blue"))
            return values  # type: ignore[return-value]
        return None

    @staticmethod
    def _description_mapping(dataset: DatasetReader) -> tuple[int, int, int] | None:
        aliases = {"r": "r", "red": "r", "g": "g", "green": "g", "b": "b", "blue": "b"}
        normalized = [aliases.get(str(value or "").strip().lower()) for value in dataset.descriptions]
        if all(channel in normalized for channel in ("r", "g", "b")):
            values = tuple(normalized.index(channel) + 1 for channel in ("r", "g", "b"))
            return values  # type: ignore[return-value]
        return None

    @staticmethod
    def _resolution_class(crs: CRS, resolution: float) -> str:
        if not crs.is_projected:
            return "UNKNOWN_UNITS"
        if resolution <= 0.5:
            return "VERY_HIGH_RESOLUTION"
        if resolution <= 2.0:
            return "HIGH_RESOLUTION"
        return "LOW_RESOLUTION"

    @staticmethod
    def _valid_transform(transform: Affine) -> bool:
        values = tuple(transform)
        if not all(math.isfinite(float(value)) for value in values):
            return False
        if transform == Affine.identity():
            return False
        return not math.isclose(float(transform.determinant), 0.0, abs_tol=1e-15)
