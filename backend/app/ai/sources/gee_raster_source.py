from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path
from typing import Any

from ...gee_client import create_ai_rgb_geotiff_download
from .base_raster_source import RasterSource


logger = logging.getLogger(__name__)


class GeeRasterDownloadError(RuntimeError):
    """Raised when Earth Engine cannot materialize the requested raster."""


class GeeRasterSource(RasterSource):
    SOURCE = "sentinel2"

    def __init__(self, payload: dict[str, Any], cache_dir: Path, raster_id: str) -> None:
        self.payload = dict(payload)
        self.cache_dir = Path(cache_dir)
        self.raster_id = raster_id
        self._metadata: dict[str, Any] = {}

    @property
    def raster_path(self) -> Path:
        return self.cache_dir / f"{self.raster_id}.tif"

    @property
    def partial_path(self) -> Path:
        return self.cache_dir / f"{self.raster_id}.tif.part"

    def get_raster(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("[AI-RASTER] source=sentinel2")
        logger.info("[AI-RASTER] preparing RGB bands=B4,B3,B2")
        try:
            download = create_ai_rgb_geotiff_download(self.payload)
            self._metadata = {key: value for key, value in download.items() if key != "url"}
            logger.info("[AI-RASTER] downloading raster")
            self._download(str(download["url"]), self.partial_path)
            self.partial_path.replace(self.raster_path)
            return self.raster_path
        except Exception as exc:
            self._remove_if_present(self.partial_path)
            self._remove_if_present(self.raster_path)
            if isinstance(exc, ValueError):
                raise
            raise GeeRasterDownloadError(
                f"Echec de preparation ou telechargement du raster GEE: {exc}"
            ) from exc

    def get_metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    def get_crs(self) -> str | None:
        value = self._metadata.get("crs")
        return str(value) if value else None

    def get_resolution(self) -> float | None:
        value = self._metadata.get("resolution_m")
        return float(value) if value is not None else None

    def get_bounds(self) -> list[float] | None:
        value = self._metadata.get("aoi_bounds_wgs84")
        return [float(item) for item in value] if isinstance(value, list) and len(value) == 4 else None

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        timeout_seconds = int(os.getenv("AI_RASTER_DOWNLOAD_TIMEOUT_SECONDS", "180"))
        max_bytes = int(os.getenv("AI_RASTER_MAX_DOWNLOAD_BYTES", str(300 * 1024 * 1024)))
        request = urllib.request.Request(url, headers={"User-Agent": "GeoRaster-AI-Raster/1.0"})
        downloaded = 0
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response, destination.open("xb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    raise GeeRasterDownloadError(
                        "Le GeoTIFF depasse la limite temporaire de telechargement du prototype."
                    )
                output.write(chunk)
        if downloaded <= 0:
            raise GeeRasterDownloadError("Earth Engine a retourne un fichier raster vide.")

    @staticmethod
    def _remove_if_present(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("[AI-RASTER] temporary cleanup failed file=%s", path.name)

