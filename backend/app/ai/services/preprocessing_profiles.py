from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

import numpy as np
from rasterio.io import DatasetReader

from ..errors import AIRasterError


class BasePreprocessingProfile(ABC):
    name: str
    band_names: tuple[str, str, str]
    band_mapping: dict[str, str]
    normalization_method: str
    normalization_version: str = "v1"
    output_dtype: str = "float32"
    clipping_min: float
    clipping_max: float
    scale_factor: float

    @abstractmethod
    def validate_dataset(
        self,
        dataset: DatasetReader,
        band_indexes: Sequence[int] | None = None,
    ) -> tuple[int, int, int]:
        """Validate and return the physical band indexes in RGB order."""

    @abstractmethod
    def normalize(self, source_rgb: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
        """Apply one deterministic transform without per-image statistics."""

    def metadata(
        self,
        dataset: DatasetReader,
        band_indexes: Sequence[int] | None = None,
    ) -> dict[str, Any]:
        indexes = self.validate_dataset(dataset, band_indexes)
        return {
            "profile": self.name,
            "bands": list(self.band_names),
            "band_mapping": dict(self.band_mapping),
            "band_indexes": list(indexes),
            "input_dtype": str(dataset.dtypes[indexes[0] - 1]),
            "output_dtype": self.output_dtype,
            "normalization_method": self.normalization_method,
            "normalization_version": self.normalization_version,
            "input_range": [self.clipping_min, self.clipping_max],
            "clipping_min": self.clipping_min,
            "clipping_max": self.clipping_max,
            "scale_factor": self.scale_factor,
            "nodata": float(dataset.nodata) if dataset.nodata is not None else None,
        }

    @staticmethod
    def validate_arrays(source_rgb: np.ndarray, valid_mask: np.ndarray) -> None:
        if source_rgb.ndim != 3 or source_rgb.shape[0] != 3:
            raise AIRasterError(
                "UNSUPPORTED_BAND_CONFIGURATION",
                "source_rgb doit avoir la forme (3, hauteur, largeur).",
            )
        if valid_mask.shape != source_rgb.shape[1:]:
            raise AIRasterError(
                "LOCAL_RASTER_INVALID",
                "Le valid_mask ne correspond pas aux dimensions RGB.",
            )


class Sentinel2SRProfile(BasePreprocessingProfile):
    name = "sentinel2_sr_v1"
    band_names = ("B4", "B3", "B2")
    band_mapping = {"R": "B4", "G": "B3", "B": "B2"}
    normalization_method = "sentinel2_sr_fixed_reflectance_clip_scale"
    clipping_min = 0.0
    clipping_max = 10_000.0
    scale_factor = 0.0001

    def validate_dataset(
        self,
        dataset: DatasetReader,
        band_indexes: Sequence[int] | None = None,
    ) -> tuple[int, int, int]:
        if dataset.count != 3:
            raise AIRasterError(
                "UNSUPPORTED_BAND_CONFIGURATION",
                "Le preprocessing Sentinel-2 exige exactement trois bandes RGB.",
            )
        if tuple(dataset.dtypes) != ("uint16", "uint16", "uint16"):
            raise AIRasterError(
                "UNSUPPORTED_RASTER_DTYPE",
                "Le profil Sentinel-2 SR exige trois bandes uint16.",
            )
        if dataset.crs is None:
            raise AIRasterError("RASTER_CRS_MISSING", "Le raster ne contient aucun CRS.")
        descriptions = tuple(str(item) if item else "" for item in dataset.descriptions)
        if any(descriptions) and descriptions != self.band_names:
            raise AIRasterError(
                "UNSUPPORTED_BAND_CONFIGURATION",
                "L'ordre des bandes Sentinel-2 doit etre B4, B3, B2.",
            )
        if band_indexes is not None and tuple(int(value) for value in band_indexes) != (1, 2, 3):
            raise AIRasterError(
                "UNSUPPORTED_BAND_CONFIGURATION",
                "Le mapping Sentinel-2 valide est fixe: B4/B3/B2 sur les bandes 1/2/3.",
            )
        return (1, 2, 3)

    def normalize(self, source_rgb: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
        self.validate_arrays(source_rgb, valid_mask)
        normalized = np.clip(
            source_rgb.astype(np.float32, copy=False),
            self.clipping_min,
            self.clipping_max,
        )
        normalized *= np.float32(self.scale_factor)
        normalized[:, ~valid_mask] = np.float32(0.0)
        return normalized.astype(np.float32, copy=False)


class RGBOrthophotoProfile(BasePreprocessingProfile):
    name = "rgb_orthophoto_uint8_v1"
    band_names = ("R", "G", "B")
    band_mapping = {"R": "red", "G": "green", "B": "blue"}
    normalization_method = "rgb_uint8_fixed_divide_255"
    clipping_min = 0.0
    clipping_max = 255.0
    scale_factor = 1.0 / 255.0

    def validate_dataset(
        self,
        dataset: DatasetReader,
        band_indexes: Sequence[int] | None = None,
    ) -> tuple[int, int, int]:
        if dataset.count != 3:
            raise AIRasterError(
                "UNSUPPORTED_BAND_CONFIGURATION",
                "L'orthophoto IA doit contenir exactement trois bandes RGB.",
            )
        if tuple(dataset.dtypes) != ("uint8", "uint8", "uint8"):
            raise AIRasterError(
                "UNSUPPORTED_RASTER_DTYPE",
                "Le profil orthophoto actuel accepte uniquement trois bandes uint8.",
            )
        if dataset.crs is None:
            raise AIRasterError("RASTER_CRS_MISSING", "L'orthophoto ne contient aucun CRS.")
        if band_indexes is None:
            raise AIRasterError(
                "UNSUPPORTED_BAND_CONFIGURATION",
                "Le mapping physique R/G/B de l'orthophoto doit etre explicite.",
            )
        indexes = tuple(int(value) for value in band_indexes)
        if len(indexes) != 3 or len(set(indexes)) != 3 or any(value < 1 or value > dataset.count for value in indexes):
            raise AIRasterError(
                "UNSUPPORTED_BAND_CONFIGURATION",
                "Le mapping R/G/B doit contenir trois indices de bandes distincts et valides.",
            )
        return indexes

    def normalize(self, source_rgb: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
        self.validate_arrays(source_rgb, valid_mask)
        if source_rgb.dtype != np.uint8:
            raise AIRasterError(
                "UNSUPPORTED_RASTER_DTYPE",
                "La normalisation orthophoto attend un tableau uint8.",
            )
        normalized = source_rgb.astype(np.float32, copy=False) / np.float32(255.0)
        normalized[:, ~valid_mask] = np.float32(0.0)
        return normalized.astype(np.float32, copy=False)


PREPROCESSING_PROFILES: dict[str, BasePreprocessingProfile] = {
    Sentinel2SRProfile.name: Sentinel2SRProfile(),
    RGBOrthophotoProfile.name: RGBOrthophotoProfile(),
}


def get_preprocessing_profile(name: str) -> BasePreprocessingProfile:
    profile = PREPROCESSING_PROFILES.get(str(name or "").strip())
    if profile is None:
        raise AIRasterError(
            "PREPROCESSING_PROFILE_NOT_FOUND",
            f"Profil de preprocessing inconnu: {name or 'vide'}.",
        )
    return profile
