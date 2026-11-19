from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.windows import Window

from ..errors import AIRasterError


class MaxarMultispectralProfile:
    """Identify and stream-convert the tested Maxar Multi-8 product.

    This profile is deliberately separate from the existing RGB orthophoto
    contract. It only accepts a documented Maxar-like eight-band uint16 COG
    and emits the same RGB uint8 contract consumed by the existing pipeline.
    """

    name = "maxar_multispectral_p2p98_v1"
    rgb_bands = (5, 3, 2)  # Rasterio one-based: Red, Green, Blue.
    max_upload_bytes = 4 * 1024 * 1024 * 1024
    filename_hint = re.compile(r"(?:maxar|skywatch|s3ds|cog)", re.IGNORECASE)

    @classmethod
    def identify(cls, path: Path) -> dict[str, Any] | None:
        try:
            with rasterio.open(path) as dataset:
                if dataset.count != 8 or tuple(dataset.dtypes) != ("uint16",) * 8:
                    return None
                if dataset.crs is None or not dataset.transform:
                    return None
                tags = {str(k).lower(): str(v).lower() for k, v in dataset.tags().items()}
                image_tags = {str(k).lower(): str(v).lower() for k, v in dataset.tags(ns="IMAGE_STRUCTURE").items()}
                descriptor = " ".join((*tags.keys(), *tags.values(), *image_tags.keys(), *image_tags.values(), path.name))
                if not cls.filename_hint.search(descriptor):
                    return None
                return {
                    "profile": cls.name,
                    "band_count": 8,
                    "dtype": "uint16",
                    "rgb_bands": {"R": 5, "G": 3, "B": 2},
                    "crs": dataset.crs.to_string(),
                    "width": dataset.width,
                    "height": dataset.height,
                    "resolution_x": abs(float(dataset.res[0])),
                    "resolution_y": abs(float(dataset.res[1])),
                    "nodata": dataset.nodata,
                    "colorinterp": [item.name for item in dataset.colorinterp],
                    "descriptions": [str(item) if item else "" for item in dataset.descriptions],
                }
        except Exception:
            return None

    @staticmethod
    def _sample_percentiles(dataset: rasterio.io.DatasetReader, band: int, sample_size: int = 2048) -> tuple[float, float]:
        scale = min(1.0, sample_size / max(dataset.width, dataset.height))
        height = max(1, int(round(dataset.height * scale)))
        width = max(1, int(round(dataset.width * scale)))
        sampled = dataset.read(band, out_shape=(height, width), masked=True)
        values = sampled.compressed().astype(np.float32, copy=False)
        if values.size == 0:
            raise AIRasterError("MAXAR_INVALID", f"La bande Maxar {band} ne contient aucun pixel valide.")
        low, high = np.percentile(values, [2, 98]).tolist()
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise AIRasterError("MAXAR_INVALID", f"Le stretch p2-p98 de la bande {band} est invalide.")
        return float(low), float(high)

    @classmethod
    def convert_to_rgb(cls, source: Path, output: Path) -> dict[str, Any]:
        identity = cls.identify(source)
        if identity is None:
            raise AIRasterError("MAXAR_PROFILE_NOT_MATCHED", "Le fichier ne correspond pas au profil Maxar Multi-8 attendu.")
        output.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(source) as src:
            stretches = {band: cls._sample_percentiles(src, band) for band in cls.rgb_bands}
            profile = src.profile.copy()
            profile.update(
                driver="GTiff", count=3, dtype="uint8", nodata=0, tiled=True,
                blockxsize=512, blockysize=512, compress="DEFLATE", predictor=2,
                interleave="pixel",
            )
            with rasterio.open(output, "w", **profile) as dst:
                for band_index, source_band in enumerate(cls.rgb_bands, 1):
                    for _, window in src.block_windows(source_band):
                        values = src.read(source_band, window=window, masked=True)
                        low, high = stretches[source_band]
                        data = values.filled(0).astype(np.float32, copy=False)
                        scaled = np.rint(np.clip((data - low) * 255.0 / (high - low), 0.0, 255.0)).astype(np.uint8)
                        scaled[values.mask] = 0
                        dst.write(scaled, band_index, window=window)
                for _, window in src.block_windows(1):
                    dst.write_mask(src.dataset_mask(window=window), window=window)
                dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
                for index, description in enumerate(("Red from Maxar band 5", "Green from Maxar band 3", "Blue from Maxar band 2"), 1):
                    dst.set_band_description(index, description)
                dst.update_tags(
                    SOURCE_PROFILE=cls.name,
                    SOURCE_RGB_BANDS="5,3,2",
                    STRETCH_STRATEGY="p2-p98_per_channel",
                    STRETCH_LOW=json.dumps([stretches[b][0] for b in cls.rgb_bands]),
                    STRETCH_HIGH=json.dumps([stretches[b][1] for b in cls.rgb_bands]),
                    SCIENTIFIC_ACCURACY="NOT_VALIDATED",
                )
        return {**identity, "output": str(output), "stretch": {str(b): list(stretches[b]) for b in cls.rgb_bands}}
