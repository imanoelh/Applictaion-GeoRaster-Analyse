from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import rasterio

from ..errors import AIRasterError
from .base_raster_source import RasterSource


logger = logging.getLogger(__name__)


class LocalRasterSource(RasterSource):
    """Materialize a server-controlled local GeoTIFF in the isolated AI cache."""

    SOURCE = "orthophoto_local"

    def __init__(
        self,
        source_path: Path,
        cache_dir: Path,
        raster_id: str,
        *,
        original_filename: str,
    ) -> None:
        self.source_path = Path(source_path)
        self.cache_dir = Path(cache_dir)
        self.raster_id = raster_id
        self.original_filename = original_filename
        self._metadata: dict[str, Any] = {}

    @property
    def raster_path(self) -> Path:
        return self.cache_dir / f"{self.raster_id}.tif"

    @property
    def partial_path(self) -> Path:
        return self.cache_dir / f"{self.raster_id}.tif.part"

    def get_raster(self) -> Path:
        if not self.source_path.is_file():
            raise AIRasterError("LOCAL_RASTER_NOT_FOUND", "Le raster local temporaire est introuvable.")
        if self.source_path.suffix.lower() not in {".tif", ".tiff", ".part"}:
            raise AIRasterError("LOCAL_RASTER_INVALID", "Le fichier local doit etre un GeoTIFF .tif ou .tiff.")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            with rasterio.open(self.source_path) as dataset:
                bounds = dataset.bounds
                self._metadata = {
                    "source_type": self.SOURCE,
                    "original_filename": self.original_filename,
                    "crs": dataset.crs.to_string() if dataset.crs else None,
                    "transform": [float(value) for value in tuple(dataset.transform)],
                    "bounds": [float(bounds.left), float(bounds.bottom), float(bounds.right), float(bounds.top)],
                    "resolution_x": abs(float(dataset.res[0])),
                    "resolution_y": abs(float(dataset.res[1])),
                    "bands": int(dataset.count),
                    "band_names": [str(value) if value else "" for value in dataset.descriptions],
                    "dtype": list(dataset.dtypes),
                    "nodata": float(dataset.nodata) if dataset.nodata is not None else None,
                    "color_interpretation": [item.name for item in dataset.colorinterp],
                }
            with self.source_path.open("rb") as source, self.partial_path.open("xb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            self.partial_path.replace(self.raster_path)
            logger.info("[AI-RASTER] source=orthophoto_local raster_id=%s", self.raster_id)
            return self.raster_path
        except AIRasterError:
            raise
        except Exception as exc:
            self.partial_path.unlink(missing_ok=True)
            self.raster_path.unlink(missing_ok=True)
            raise AIRasterError(
                "LOCAL_RASTER_INVALID",
                "Le fichier fourni n'est pas un GeoTIFF local exploitable.",
                technical_detail=str(exc),
            ) from exc

    def get_metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    def get_crs(self) -> str | None:
        value = self._metadata.get("crs")
        return str(value) if value else None

    def get_resolution(self) -> float | None:
        values = (self._metadata.get("resolution_x"), self._metadata.get("resolution_y"))
        if any(value is None for value in values):
            return None
        return (float(values[0]) + float(values[1])) / 2.0

    def get_bounds(self) -> list[float] | None:
        bounds = self._metadata.get("bounds")
        return [float(value) for value in bounds] if isinstance(bounds, list) and len(bounds) == 4 else None
