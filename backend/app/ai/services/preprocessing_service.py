from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import rasterio
from rasterio.io import DatasetReader
from rasterio.windows import Window

from .preprocessing_profiles import Sentinel2SRProfile, get_preprocessing_profile


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreprocessedWindow:
    """One in-memory tile; arrays are intentionally never JSON-serialized."""

    source_rgb: np.ndarray
    image: np.ndarray
    valid_mask: np.ndarray
    valid_width: int
    valid_height: int
    valid_pixel_ratio: float


class PreprocessingService:
    """Window-based deterministic preprocessing selected by source profile."""

    BAND_NAMES = ("B4", "B3", "B2")
    BAND_MAPPING = {"R": "B4", "G": "B3", "B": "B2"}
    NORMALIZATION_METHOD = "sentinel2_sr_fixed_reflectance_clip_scale"
    NORMALIZATION_VERSION = "v1"
    CLIPPING_MIN = 0.0
    CLIPPING_MAX = 10_000.0
    SCALE_FACTOR = 0.0001
    OUTPUT_DTYPE = "float32"

    @contextmanager
    def open_raster(
        self,
        raster_path: Path,
        *,
        profile_name: str = Sentinel2SRProfile.name,
        band_indexes: tuple[int, int, int] | list[int] | None = None,
    ) -> Iterator[DatasetReader]:
        path = Path(raster_path)
        if not path.is_file():
            raise FileNotFoundError("Raster IA introuvable.")
        with rasterio.open(path) as dataset:
            profile = get_preprocessing_profile(profile_name)
            profile.validate_dataset(dataset, band_indexes)
            logger.info("[AI-PREPROCESS] raster=%s", path.name)
            logger.info(
                "[AI-PREPROCESS] normalization=%s:%s",
                profile.normalization_method,
                profile.normalization_version,
            )
            yield dataset

    def metadata(
        self,
        dataset: DatasetReader,
        *,
        profile_name: str = Sentinel2SRProfile.name,
        band_indexes: tuple[int, int, int] | list[int] | None = None,
    ) -> dict[str, object]:
        return get_preprocessing_profile(profile_name).metadata(dataset, band_indexes)

    def preprocess_window(
        self,
        dataset: DatasetReader,
        window: Window,
        *,
        tile_size: int,
        profile_name: str = Sentinel2SRProfile.name,
        band_indexes: tuple[int, int, int] | list[int] | None = None,
    ) -> PreprocessedWindow:
        valid_width = int(window.width)
        valid_height = int(window.height)
        if valid_width <= 0 or valid_height <= 0:
            raise ValueError("La fenetre raster doit avoir des dimensions positives.")
        if valid_width > tile_size or valid_height > tile_size:
            raise ValueError("La fenetre raster depasse tile_size.")

        profile = get_preprocessing_profile(profile_name)
        indexes = profile.validate_dataset(dataset, band_indexes)
        masked = dataset.read(indexes=indexes, window=window, masked=True)
        source = np.asarray(masked.filled(0), dtype=np.dtype(dataset.dtypes[indexes[0] - 1]))
        invalid_by_band = np.ma.getmaskarray(masked)
        valid_real = ~np.any(invalid_by_band, axis=0)

        source_padded = np.zeros((3, tile_size, tile_size), dtype=source.dtype)
        source_padded[:, :valid_height, :valid_width] = source
        valid_mask = np.zeros((tile_size, tile_size), dtype=np.bool_)
        valid_mask[:valid_height, :valid_width] = valid_real
        normalized = profile.normalize(source_padded, valid_mask)
        valid_ratio = float(valid_real.sum()) / float(valid_width * valid_height)
        return PreprocessedWindow(
            source_rgb=source_padded,
            image=normalized,
            valid_mask=valid_mask,
            valid_width=valid_width,
            valid_height=valid_height,
            valid_pixel_ratio=valid_ratio,
        )

    def normalize(
        self,
        source_rgb: np.ndarray,
        valid_mask: np.ndarray,
        *,
        profile_name: str = Sentinel2SRProfile.name,
    ) -> np.ndarray:
        """Apply a fixed profile transform; defaults to the historical Sentinel transform."""
        return get_preprocessing_profile(profile_name).normalize(source_rgb, valid_mask)

    @classmethod
    def _validate_dataset(cls, dataset: DatasetReader) -> None:
        get_preprocessing_profile(Sentinel2SRProfile.name).validate_dataset(dataset)

