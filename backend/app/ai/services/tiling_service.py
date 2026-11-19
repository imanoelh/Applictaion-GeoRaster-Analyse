from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
from affine import Affine
from rasterio.io import DatasetReader
from rasterio.transform import xy
from rasterio.windows import Window, bounds as window_bounds, transform as window_transform

from ..schemas.tile_schemas import TileMetadata
from .preprocessing_service import PreprocessedWindow, PreprocessingService
from .preprocessing_profiles import Sentinel2SRProfile


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedTile:
    """In-memory future model input plus serializable geospatial metadata."""

    image: np.ndarray
    source_rgb: np.ndarray
    valid_mask: np.ndarray
    metadata: TileMetadata


class TilingService:
    def __init__(self, preprocessing: PreprocessingService | None = None) -> None:
        self.preprocessing = preprocessing or PreprocessingService()

    @staticmethod
    def configuration(tile_size: int = 640, overlap_ratio: float = 0.20) -> tuple[int, int]:
        if tile_size <= 0:
            raise ValueError("tile_size doit etre strictement positif.")
        if not 0.0 <= overlap_ratio < 1.0:
            raise ValueError("overlap_ratio doit etre compris entre 0 inclus et 1 exclu.")
        overlap_pixels = int(round(tile_size * overlap_ratio))
        stride = tile_size - overlap_pixels
        if stride <= 0:
            raise ValueError("Le stride calcule doit etre strictement positif.")
        return overlap_pixels, stride

    def iter_tiles(
        self,
        raster_path: Path,
        *,
        raster_id: str | None = None,
        tile_size: int = 640,
        overlap_ratio: float = 0.20,
        min_valid_pixel_ratio: float = 0.05,
        preprocessing_profile: str = Sentinel2SRProfile.name,
        band_indexes: tuple[int, int, int] | list[int] | None = None,
    ) -> Iterator[PreparedTile]:
        if not 0.0 <= min_valid_pixel_ratio <= 1.0:
            raise ValueError("min_valid_pixel_ratio doit etre compris entre 0 et 1.")
        overlap_pixels, stride = self.configuration(tile_size, overlap_ratio)
        logger.info(
            "[AI-TILING] tile_size=%s overlap=%s stride=%s",
            tile_size,
            overlap_pixels,
            stride,
        )

        with self.preprocessing.open_raster(
            raster_path,
            profile_name=preprocessing_profile,
            band_indexes=band_indexes,
        ) as dataset:
            row_offsets = self._axis_offsets(dataset.height, tile_size, stride)
            col_offsets = self._axis_offsets(dataset.width, tile_size, stride)
            tile_number = 0
            skipped = 0
            for row_index, row_offset in enumerate(row_offsets):
                for col_index, col_offset in enumerate(col_offsets):
                    valid_height = min(tile_size, dataset.height - row_offset)
                    valid_width = min(tile_size, dataset.width - col_offset)
                    window = Window(col_offset, row_offset, valid_width, valid_height)
                    prepared = self.preprocessing.preprocess_window(
                        dataset,
                        window,
                        tile_size=tile_size,
                        profile_name=preprocessing_profile,
                        band_indexes=band_indexes,
                    )
                    tile_number += 1
                    skip_inference = prepared.valid_pixel_ratio < min_valid_pixel_ratio
                    skipped += int(skip_inference)
                    metadata = self._metadata(
                        dataset,
                        prepared,
                        window,
                        raster_id=raster_id,
                        row_index=row_index,
                        col_index=col_index,
                        tile_number=tile_number,
                        tile_size=tile_size,
                        overlap_pixels=overlap_pixels,
                        stride=stride,
                        skip_inference=skip_inference,
                        source_profile=preprocessing_profile,
                    )
                    yield PreparedTile(
                        image=prepared.image,
                        source_rgb=prepared.source_rgb,
                        valid_mask=prepared.valid_mask,
                        metadata=metadata,
                    )
            logger.info("[AI-TILING] tiles=%s", tile_number)
            logger.info("[AI-TILING] skipped_nodata=%s", skipped)

    def summarize(
        self,
        raster_path: Path,
        *,
        raster_id: str,
        tile_size: int = 640,
        overlap_ratio: float = 0.20,
        min_valid_pixel_ratio: float = 0.05,
        max_tiles_metadata: int = 10,
        preprocessing_profile: str = Sentinel2SRProfile.name,
        band_indexes: tuple[int, int, int] | list[int] | None = None,
    ) -> tuple[dict[str, object], dict[str, object], list[TileMetadata]]:
        if max_tiles_metadata < 0:
            raise ValueError("max_tiles_metadata doit etre positif.")
        overlap_pixels, stride = self.configuration(tile_size, overlap_ratio)
        returned: list[TileMetadata] = []
        tiles_count = 0
        skipped_tiles = 0
        with self.preprocessing.open_raster(
            raster_path,
            profile_name=preprocessing_profile,
            band_indexes=band_indexes,
        ) as dataset:
            preprocessing_metadata = self.preprocessing.metadata(
                dataset,
                profile_name=preprocessing_profile,
                band_indexes=band_indexes,
            )
        for tile in self.iter_tiles(
            raster_path,
            raster_id=raster_id,
            tile_size=tile_size,
            overlap_ratio=overlap_ratio,
            min_valid_pixel_ratio=min_valid_pixel_ratio,
            preprocessing_profile=preprocessing_profile,
            band_indexes=band_indexes,
        ):
            tiles_count += 1
            skipped_tiles += int(tile.metadata.skip_inference)
            if len(returned) < max_tiles_metadata:
                returned.append(tile.metadata)
        summary = {
            "tile_size": tile_size,
            "overlap_ratio": overlap_ratio,
            "overlap_pixels": overlap_pixels,
            "stride": stride,
            "tiles_count": tiles_count,
            "valid_tiles": tiles_count - skipped_tiles,
            "skipped_tiles": skipped_tiles,
            "min_valid_pixel_ratio": min_valid_pixel_ratio,
            "metadata_returned": len(returned),
        }
        return preprocessing_metadata, summary, returned

    @staticmethod
    def tile_pixel_to_raster_pixel(tile: TileMetadata, x: int, y: int) -> tuple[int, int]:
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError("Les coordonnees pixel doivent etre des entiers.")
        if x < 0 or y < 0 or x >= tile.valid_width or y >= tile.valid_height:
            raise ValueError("Le pixel local est hors donnees reelles ou situe dans le padding.")
        return tile.col_offset + x, tile.row_offset + y

    @classmethod
    def tile_pixel_to_map_coordinates(cls, tile: TileMetadata, x: int, y: int) -> tuple[float, float]:
        cls.tile_pixel_to_raster_pixel(tile, x, y)
        affine = Affine(*tile.transform[:6])
        map_x, map_y = xy(affine, y, x, offset="center")
        return float(map_x), float(map_y)

    @staticmethod
    def _axis_offsets(length: int, tile_size: int, stride: int) -> list[int]:
        if length <= 0:
            raise ValueError("La dimension raster doit etre positive.")
        offsets = [0]
        while offsets[-1] + tile_size < length:
            offsets.append(offsets[-1] + stride)
        return offsets

    @staticmethod
    def _metadata(
        dataset: DatasetReader,
        prepared: PreprocessedWindow,
        window: Window,
        *,
        raster_id: str | None,
        row_index: int,
        col_index: int,
        tile_number: int,
        tile_size: int,
        overlap_pixels: int,
        stride: int,
        skip_inference: bool,
        source_profile: str,
    ) -> TileMetadata:
        affine = window_transform(window, dataset.transform)
        left, bottom, right, top = window_bounds(window, dataset.transform)
        return TileMetadata(
            tile_id=f"tile_{tile_number:04d}",
            row_index=row_index,
            col_index=col_index,
            row_offset=int(window.row_off),
            col_offset=int(window.col_off),
            width=tile_size,
            height=tile_size,
            valid_width=prepared.valid_width,
            valid_height=prepared.valid_height,
            tile_size=tile_size,
            overlap_pixels=overlap_pixels,
            stride=stride,
            padding_top=0,
            padding_bottom=tile_size - prepared.valid_height,
            padding_left=0,
            padding_right=tile_size - prepared.valid_width,
            valid_pixel_ratio=prepared.valid_pixel_ratio,
            skip_inference=skip_inference,
            transform=[float(value) for value in tuple(affine)],
            bounds={"left": left, "bottom": bottom, "right": right, "top": top},
            crs=dataset.crs.to_string(),
            source_raster_id=raster_id,
            source_profile=source_profile,
        )

