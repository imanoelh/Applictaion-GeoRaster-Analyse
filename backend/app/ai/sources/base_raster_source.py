from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class RasterSource(ABC):
    """Provider-neutral input contract for a future AI engine.

    The future inference layer can consume this interface without importing or
    knowing anything about Google Earth Engine.
    """

    @abstractmethod
    def get_raster(self) -> Path:
        """Materialize and return a local, georeferenced raster."""

    @abstractmethod
    def get_metadata(self) -> dict[str, Any]:
        """Return source-side metadata known before raster validation."""

    @abstractmethod
    def get_crs(self) -> str | None:
        """Return the requested source CRS, when known."""

    @abstractmethod
    def get_resolution(self) -> float | None:
        """Return the requested source resolution in metres, when known."""

    @abstractmethod
    def get_bounds(self) -> list[float] | None:
        """Return the requested WGS84 AOI bounds as [west, south, east, north]."""

