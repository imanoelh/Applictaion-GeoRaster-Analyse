from __future__ import annotations

import math
import os
import shutil
import tempfile
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from ..errors import AIRasterError
from ..schemas.prediction_schemas import TilePrediction


@dataclass(frozen=True)
class RasterGrid:
    raster_id: str
    width: int
    height: int
    crs: str
    transform: tuple[float, ...]
    bounds: dict[str, float]

    @property
    def resolution_x(self) -> float:
        a, _b, _c, d, _e, _f = self.transform[:6]
        return float(math.hypot(a, d))

    @property
    def resolution_y(self) -> float:
        _a, b, _c, _d, e, _f = self.transform[:6]
        return float(math.hypot(b, e))

    @property
    def pixel_area(self) -> float:
        return abs(self.resolution_x * self.resolution_y)


@dataclass(frozen=True)
class PostProcessingConfig:
    probability_threshold: float = 0.50
    min_object_pixels: int = 4
    max_hole_pixels: int = 0
    opening_enabled: bool = False
    closing_enabled: bool = False
    morphology_kernel_size: int = 3
    morphology_iterations: int = 1
    connectivity: int = 8

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability_threshold <= 1.0:
            raise ValueError("probability_threshold doit etre compris entre 0 et 1.")
        if self.min_object_pixels < 0 or self.max_hole_pixels < 0:
            raise ValueError("Les seuils de pixels doivent etre positifs ou nuls.")
        if self.morphology_kernel_size < 1 or self.morphology_kernel_size % 2 == 0:
            raise ValueError("morphology_kernel_size doit etre un entier impair positif.")
        if self.morphology_iterations < 1:
            raise ValueError("morphology_iterations doit etre strictement positif.")
        if self.connectivity not in {4, 8}:
            raise ValueError("connectivity doit valoir 4 ou 8.")

    def public_summary(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "small_object_status": "NOT_CALIBRATED",
            "hole_filling_enabled": self.max_hole_pixels > 0,
            "morphology_enabled": self.opening_enabled or self.closing_enabled,
            "merge_strategy": "uniform_probability_mean",
        }


@dataclass(frozen=True)
class ComponentInfo:
    component_id: int
    pixel_count: int
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class BuildingMaskResult:
    """Internal raster result. Arrays are deliberately not Pydantic/API fields."""

    raster_id: str
    source_type: str | None
    model_name: str
    model_version: str
    model_mode: str
    threshold: float
    width: int
    height: int
    crs: str
    transform: tuple[float, ...]
    bounds: dict[str, float]
    resolution: tuple[float, float]
    pixel_area: float
    positive_pixel_count: int
    positive_pixel_ratio: float
    valid_pixel_count: int
    tiles_total: int
    tiles_processed: int
    tiles_skipped: int
    postprocessing_config: dict[str, Any]
    processing_time_ms: float
    estimated_global_memory_bytes: int
    global_probability_map: np.ndarray | None
    global_binary_mask: np.ndarray
    global_valid_mask: np.ndarray
    components: tuple[ComponentInfo, ...]
    storage_dir: str | None = None
    model_id: str = "unet_resnet34"
    model_architecture: str | None = None
    model_checkpoint_hash: str | None = None
    preprocessing_profile: str | None = None
    tile_size: int | None = None
    model_metadata: dict[str, Any] | None = None

    def cleanup(self) -> None:
        """Release optional disk-backed arrays created for a large raster."""
        if not self.storage_dir:
            return
        arrays = tuple(value for value in (self.global_probability_map, self.global_binary_mask, self.global_valid_mask) if value is not None)
        for value in arrays:
            flush = getattr(value, "flush", None)
            if callable(flush):
                flush()
        storage_dir = self.storage_dir
        object.__setattr__(self, "storage_dir", None)
        # Close mmap handles before removing files (important on Windows).
        try:
            seen: set[int] = set()
            for value in arrays:
                if id(value) in seen:
                    continue
                seen.add(id(value))
                mmap_handle = getattr(value, "_mmap", None)
                if mmap_handle is not None:
                    mmap_handle.close()
        except (AttributeError, BufferError):
            pass
        shutil.rmtree(storage_dir, ignore_errors=True)


@dataclass(frozen=True)
class ThresholdedModelMask:
    """One component model's overlap-fused, thresholded global mask."""

    global_binary_mask: np.ndarray
    global_valid_mask: np.ndarray
    tiles_total: int
    tiles_processed: int
    tiles_skipped: int
    inference_time_ms: float
    model_identity: tuple[Any, ...]
    source_type: str | None
    tile_layout: tuple[tuple[Any, ...], ...]
    storage_dir: str | None = None

    def cleanup(self) -> None:
        if not self.storage_dir:
            return
        for value in (self.global_binary_mask, self.global_valid_mask):
            flush = getattr(value, "flush", None)
            if callable(flush): flush()
            mmap_handle = getattr(value, "_mmap", None)
            if mmap_handle is not None:
                try: mmap_handle.close()
                except (AttributeError, BufferError, OSError): pass
        shutil.rmtree(self.storage_dir, ignore_errors=True)


class PostProcessingService:
    """Merge streamed tile probabilities and clean one georeferenced raster mask."""

    def __init__(self, *, max_global_pixels: int | None = None) -> None:
        configured = os.getenv("AI_POSTPROCESS_MAX_GLOBAL_PIXELS", "25000000")
        self.max_global_pixels = int(configured) if max_global_pixels is None else int(max_global_pixels)
        if self.max_global_pixels <= 0:
            raise ValueError("AI_POSTPROCESS_MAX_GLOBAL_PIXELS doit etre strictement positif.")

    def process(
        self,
        predictions: Iterable[TilePrediction],
        *,
        grid: RasterGrid,
        config: PostProcessingConfig | None = None,
    ) -> BuildingMaskResult:
        config = config or PostProcessingConfig()
        self._validate_grid(grid)
        pixel_count = grid.width * grid.height
        large_raster = pixel_count > self.max_global_pixels

        started = time.perf_counter()
        storage_dir: str | None = None
        if large_raster:
            # Keep the historical limit as the strategy threshold, but use sparse,
            # disk-backed arrays above it instead of failing before inference.
            storage_dir = tempfile.mkdtemp(prefix="georaster-postprocess-")
            probability_sum = np.memmap(
                os.path.join(storage_dir, "probability_sum.f32"), mode="w+",
                dtype=np.float32, shape=(grid.height, grid.width),
            )
            weight_sum = np.memmap(
                os.path.join(storage_dir, "weight_sum.f32"), mode="w+",
                dtype=np.float32, shape=(grid.height, grid.width),
            )
            global_valid = np.memmap(
                os.path.join(storage_dir, "valid.u8"), mode="w+",
                dtype=np.bool_, shape=(grid.height, grid.width),
            )
            binary = np.memmap(
                os.path.join(storage_dir, "binary.u8"), mode="w+",
                dtype=np.bool_, shape=(grid.height, grid.width),
            )
            probability_sum[:] = 0.0
            weight_sum[:] = 0.0
            global_valid[:] = False
            binary[:] = False
        else:
            probability_sum = np.zeros((grid.height, grid.width), dtype=np.float32)
            weight_sum = np.zeros((grid.height, grid.width), dtype=np.float32)
            global_valid = np.zeros((grid.height, grid.width), dtype=np.bool_)
        tiles_total = tiles_processed = tiles_skipped = 0
        model_identity: tuple[str, str, str, str, str | None, str | None, str | None, int | None] | None = None
        source_type: str | None = None

        for prediction in predictions:
            tiles_total += 1
            identity = (
                prediction.metadata.model_name,
                prediction.metadata.model_version,
                prediction.metadata.model_mode,
                prediction.metadata.model_id,
                prediction.metadata.model_architecture,
                prediction.metadata.model_checkpoint_hash,
                prediction.metadata.preprocessing_profile,
                prediction.metadata.tile_size,
            )
            if model_identity is None:
                model_identity = identity
                source_type = prediction.metadata.source_type
            elif identity != model_identity:
                raise AIRasterError(
                    "POSTPROCESSING_MODEL_MISMATCH",
                    "Toutes les tuiles doivent provenir du meme modele.",
                )
            self._accumulate_prediction(
                prediction,
                grid=grid,
                probability_sum=probability_sum,
                weight_sum=weight_sum,
                global_valid=global_valid,
            )
            if prediction.metadata.status == "skipped":
                tiles_skipped += 1
            else:
                tiles_processed += 1

        if tiles_total == 0 or model_identity is None:
            raise AIRasterError("POSTPROCESSING_EMPTY", "Aucune prediction de tuile a fusionner.")

        np.divide(
            probability_sum,
            weight_sum,
            out=probability_sum,
            where=weight_sum > 0,
        )
        probability_sum[~global_valid] = np.float32(0.0)
        if large_raster:
            # Threshold in bounded row windows so no second full-size boolean
            # array is required in RAM.
            for row_start in range(0, grid.height, 1024):
                row_end = min(grid.height, row_start + 1024)
                binary[row_start:row_end] = np.logical_and(
                    probability_sum[row_start:row_end] >= np.float32(config.probability_threshold),
                    global_valid[row_start:row_end],
                )
        else:
            binary = np.logical_and(
                probability_sum >= np.float32(config.probability_threshold),
                global_valid,
            )
        if config.min_object_pixels > 1:
            binary = self.remove_small_objects(
                binary,
                min_object_pixels=config.min_object_pixels,
                connectivity=config.connectivity,
            )
        if config.max_hole_pixels > 0:
            binary = self.fill_small_holes(
                binary,
                valid_mask=global_valid,
                max_hole_pixels=config.max_hole_pixels,
                connectivity=config.connectivity,
            )
        binary = self.apply_morphology(binary, valid_mask=global_valid, config=config)
        binary[~global_valid] = False

        components = self.connected_components(binary, connectivity=config.connectivity)
        positive_pixels = int(binary.sum())
        valid_pixels = int(global_valid.sum())
        positive_ratio = float(positive_pixels) / float(valid_pixels) if valid_pixels else 0.0
        (model_name, model_version, model_mode, model_id, model_architecture,
         model_checkpoint_hash, preprocessing_profile, tile_size) = model_identity
        # Conservative peak estimate: two float32 accumulators plus the valid,
        # binary, morphology/component work masks and the final uint8 mask.
        estimated_memory = pixel_count * (4 + 4 + 1 + 1) if large_raster else pixel_count * 16
        # Keep the public final mask uint8 without materialising a full
        # HxW conversion in RAM for large rasters.  The boolean working mask
        # remains disk-backed and is copied row-wise to another memmap.
        if large_raster:
            binary_u8 = np.memmap(
                os.path.join(storage_dir, "binary.u8"), mode="w+",
                dtype=np.uint8, shape=(grid.height, grid.width),
            )
            for row_start in range(0, grid.height, 1024):
                row_end = min(grid.height, row_start + 1024)
                binary_u8[row_start:row_end] = binary[row_start:row_end]
            binary_u8.flush()
            bool_handle = getattr(binary, "_mmap", None)
            if bool_handle is not None:
                bool_handle.close()
            final_binary: np.ndarray = binary_u8
        else:
            final_binary = binary.astype(np.uint8, copy=False)
        return BuildingMaskResult(
            raster_id=grid.raster_id,
            source_type=source_type,
            model_name=model_name,
            model_version=model_version,
            model_mode=model_mode,
            threshold=config.probability_threshold,
            width=grid.width,
            height=grid.height,
            crs=grid.crs,
            transform=grid.transform,
            bounds=dict(grid.bounds),
            resolution=(grid.resolution_x, grid.resolution_y),
            pixel_area=grid.pixel_area,
            positive_pixel_count=positive_pixels,
            positive_pixel_ratio=positive_ratio,
            valid_pixel_count=valid_pixels,
            tiles_total=tiles_total,
            tiles_processed=tiles_processed,
            tiles_skipped=tiles_skipped,
            postprocessing_config=config.public_summary(),
            processing_time_ms=(time.perf_counter() - started) * 1000.0,
            estimated_global_memory_bytes=estimated_memory,
            global_probability_map=probability_sum,
            global_binary_mask=final_binary,
            global_valid_mask=global_valid,
            components=components,
            storage_dir=storage_dir,
            model_id=model_id,
            model_architecture=model_architecture,
            model_checkpoint_hash=model_checkpoint_hash,
            preprocessing_profile=preprocessing_profile,
            tile_size=tile_size,
        )

    def threshold_model_mask(
        self,
        predictions: Iterable[TilePrediction],
        *,
        grid: RasterGrid,
        threshold: float,
    ) -> ThresholdedModelMask:
        """Overlap-fuse one component model and threshold it without cleanup."""
        self._validate_grid(grid)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold doit etre compris entre 0 et 1.")
        pixel_count = grid.width * grid.height
        storage_dir = tempfile.mkdtemp(prefix="georaster-hybrid-pass-") if pixel_count > self.max_global_pixels else None

        def allocate(name: str, dtype: Any) -> np.ndarray:
            if storage_dir:
                value = np.memmap(Path(storage_dir) / name, mode="w+", dtype=dtype, shape=(grid.height, grid.width))
                value[:] = 0
                return value
            return np.zeros((grid.height, grid.width), dtype=dtype)

        probability_sum = allocate("probability.f32", np.float32)
        weight_sum = allocate("weight.f32", np.float32)
        global_valid = allocate("valid.bool", np.bool_)
        binary = allocate("binary.bool", np.bool_)
        identity: tuple[Any, ...] | None = None
        source_type: str | None = None
        total = processed = skipped = 0
        inference_time_ms = 0.0
        tile_layout: list[tuple[Any, ...]] = []
        try:
            for prediction in predictions:
                total += 1
                tile = prediction.tile_metadata
                tile_layout.append((tile.tile_id, tile.row_offset, tile.col_offset, tile.valid_width,
                                    tile.valid_height, tile.crs, tuple(float(v) for v in tile.transform),
                                    tuple(sorted((key, float(value)) for key, value in tile.bounds.model_dump().items()))))
                current_identity = (
                    prediction.metadata.model_name,
                    prediction.metadata.model_version,
                    prediction.metadata.model_mode,
                    prediction.metadata.model_id,
                    prediction.metadata.model_architecture,
                    prediction.metadata.model_checkpoint_hash,
                    prediction.metadata.preprocessing_profile,
                    prediction.metadata.tile_size,
                )
                if identity is None:
                    identity = current_identity
                    source_type = prediction.metadata.source_type
                elif current_identity != identity:
                    raise AIRasterError("POSTPROCESSING_MODEL_MISMATCH", "Les tuiles d’un modèle doivent partager la même identité.")
                self._accumulate_prediction(
                    prediction, grid=grid, probability_sum=probability_sum,
                    weight_sum=weight_sum, global_valid=global_valid,
                )
                if prediction.metadata.status == "skipped":
                    skipped += 1
                else:
                    processed += 1
                    inference_time_ms += float(prediction.metadata.inference_time_ms)
            if total == 0 or identity is None:
                raise AIRasterError("POSTPROCESSING_EMPTY", "Aucune prediction de composant a fusionner.")
            np.divide(probability_sum, weight_sum, out=probability_sum, where=weight_sum > 0)
            probability_sum[~global_valid] = 0.0
            if storage_dir:
                for row in range(0, grid.height, 1024):
                    end = min(grid.height, row + 1024)
                    binary[row:end] = (probability_sum[row:end] >= np.float32(threshold)) & global_valid[row:end]
            else:
                binary = (probability_sum >= np.float32(threshold)) & global_valid
            for value in (probability_sum, weight_sum, global_valid, binary):
                flush = getattr(value, "flush", None)
                if callable(flush): flush()
            return ThresholdedModelMask(binary, global_valid, total, processed, skipped,
                                        inference_time_ms, identity, source_type, tuple(tile_layout), storage_dir)
        except Exception:
            for value in (probability_sum, weight_sum, global_valid, binary):
                mmap_handle = getattr(value, "_mmap", None)
                if mmap_handle is not None:
                    try: mmap_handle.close()
                    except (AttributeError, BufferError, OSError): pass
            if storage_dir: shutil.rmtree(storage_dir, ignore_errors=True)
            raise

    def process_binary_mask(
        self,
        binary_mask: np.ndarray,
        valid_mask: np.ndarray,
        *,
        grid: RasterGrid,
        config: PostProcessingConfig,
        model_name: str,
        model_version: str,
        model_id: str,
        model_architecture: str,
        model_metadata: dict[str, Any],
        source_type: str | None,
        tiles_total: int,
        tiles_processed: int,
        tiles_skipped: int,
    ) -> BuildingMaskResult:
        """Apply GeoRaster cleanup once to a pre-unioned global binary mask."""
        self._validate_grid(grid)
        expected = (grid.height, grid.width)
        if binary_mask.shape != expected or valid_mask.shape != expected:
            raise AIRasterError("HYBRID_ALIGNMENT_ERROR", "Le masque hybride et le valid_mask ne correspondent pas à la grille.")
        for row in range(0, grid.height, 1024):
            if not np.isin(binary_mask[row : row + 1024], (0, 1, False, True)).all():
                raise AIRasterError("HYBRID_MASK_INVALID", "Le masque hybride doit être binaire.")
        started = time.perf_counter()
        large = grid.width * grid.height > self.max_global_pixels
        storage_dir = tempfile.mkdtemp(prefix="georaster-hybrid-final-") if large else None
        if storage_dir:
            final_binary = np.memmap(Path(storage_dir) / "binary.bool", mode="w+", dtype=np.bool_, shape=expected)
            final_valid = np.memmap(Path(storage_dir) / "valid.bool", mode="w+", dtype=np.bool_, shape=expected)
            for row in range(0, grid.height, 1024):
                end = min(grid.height, row + 1024)
                final_binary[row:end] = np.asarray(binary_mask[row:end], dtype=bool) & np.asarray(valid_mask[row:end], dtype=bool)
                final_valid[row:end] = valid_mask[row:end]
        else:
            final_valid = np.asarray(valid_mask, dtype=bool).copy()
            final_binary = np.asarray(binary_mask, dtype=bool).copy() & final_valid
        try:
            if config.min_object_pixels > 1:
                final_binary = self.remove_small_objects(final_binary, min_object_pixels=config.min_object_pixels,
                                                         connectivity=config.connectivity)
            if config.max_hole_pixels > 0:
                final_binary = self.fill_small_holes(final_binary, valid_mask=final_valid,
                                                      max_hole_pixels=config.max_hole_pixels,
                                                      connectivity=config.connectivity)
            final_binary = self.apply_morphology(final_binary, valid_mask=final_valid, config=config)
            final_binary[~final_valid] = False
            components = self.connected_components(final_binary, connectivity=config.connectivity)
            positive_pixels = int(final_binary.sum()); valid_pixels = int(final_valid.sum())
            if storage_dir:
                binary_path = Path(storage_dir) / "binary.u8"
                binary_map = np.memmap(binary_path, mode="w+", dtype=np.uint8, shape=expected)
                for row in range(0, grid.height, 1024):
                    end = min(grid.height, row + 1024); binary_map[row:end] = final_binary[row:end]
                binary_map.flush(); final_binary = binary_map
            return BuildingMaskResult(
                raster_id=grid.raster_id, source_type=source_type, model_name=model_name,
                model_version=model_version, model_mode="EXPERIMENTAL", threshold=config.probability_threshold,
                width=grid.width, height=grid.height, crs=grid.crs, transform=grid.transform,
                bounds=dict(grid.bounds), resolution=(grid.resolution_x, grid.resolution_y),
                pixel_area=grid.pixel_area, positive_pixel_count=positive_pixels,
                positive_pixel_ratio=float(positive_pixels) / valid_pixels if valid_pixels else 0.0,
                valid_pixel_count=valid_pixels, tiles_total=tiles_total, tiles_processed=tiles_processed,
                tiles_skipped=tiles_skipped, postprocessing_config={
                    **config.public_summary(), "merge_strategy": "binary_mask_union",
                    "fusion_method": "UNION", "component_models": ["spacenet2_deeplab", "whu_unetplusplus_effb4"]},
                processing_time_ms=(time.perf_counter() - started) * 1000.0,
                estimated_global_memory_bytes=grid.width * grid.height * 16,
                global_probability_map=None,
                global_binary_mask=final_binary if storage_dir else final_binary.astype(np.uint8, copy=False),
                global_valid_mask=final_valid, components=components, storage_dir=storage_dir,
                model_id=model_id, model_architecture=model_architecture,
                model_checkpoint_hash=None, preprocessing_profile="component_specific",
                tile_size=512, model_metadata=dict(model_metadata),
            )
        except Exception:
            if storage_dir:
                for value in (final_binary, final_valid):
                    mmap_handle = getattr(value, "_mmap", None)
                    if mmap_handle is not None:
                        try: mmap_handle.close()
                        except (AttributeError, BufferError, OSError): pass
                shutil.rmtree(storage_dir, ignore_errors=True)
            raise

    @staticmethod
    def pixels_to_area(pixel_count: int, *, resolution_x: float, resolution_y: float) -> float:
        if pixel_count < 0:
            raise ValueError("pixel_count doit etre positif ou nul.")
        if not all(math.isfinite(value) and value > 0 for value in (resolution_x, resolution_y)):
            raise ValueError("Les resolutions doivent etre finies et strictement positives.")
        return float(pixel_count) * abs(float(resolution_x) * float(resolution_y))

    def _accumulate_prediction(
        self,
        prediction: TilePrediction,
        *,
        grid: RasterGrid,
        probability_sum: np.ndarray,
        weight_sum: np.ndarray,
        global_valid: np.ndarray,
    ) -> None:
        tile = prediction.tile_metadata
        row = int(tile.row_offset)
        col = int(tile.col_offset)
        height = int(tile.valid_height)
        width = int(tile.valid_width)
        if row < 0 or col < 0 or height <= 0 or width <= 0:
            raise AIRasterError("POSTPROCESSING_TILE_INVALID", "Offsets ou dimensions de tuile invalides.")
        if row + height > grid.height or col + width > grid.width:
            raise AIRasterError(
                "POSTPROCESSING_TILE_OUT_OF_BOUNDS",
                "Une tuile depasse les dimensions du raster source.",
            )
        if prediction.valid_mask.shape != (tile.tile_size, tile.tile_size):
            raise AIRasterError("POSTPROCESSING_TILE_INVALID", "Le valid_mask de tuile est invalide.")
        local_valid = prediction.valid_mask[:height, :width]
        target = np.s_[row : row + height, col : col + width]
        global_valid[target] |= local_valid

        if prediction.metadata.status == "skipped":
            if prediction.probability_map is not None:
                raise AIRasterError(
                    "POSTPROCESSING_TILE_INVALID",
                    "Une tuile ignoree ne doit pas contenir de probability_map.",
                )
            return
        probability = prediction.probability_map
        if probability is None or probability.shape != prediction.valid_mask.shape:
            raise AIRasterError("POSTPROCESSING_TILE_INVALID", "La probability_map de tuile est invalide.")
        if probability.dtype != np.float32 or not np.isfinite(probability).all():
            raise AIRasterError(
                "POSTPROCESSING_TILE_INVALID",
                "La probability_map doit etre un tableau float32 fini.",
            )
        if float(probability.min()) < 0.0 or float(probability.max()) > 1.0:
            raise AIRasterError("POSTPROCESSING_TILE_INVALID", "Les probabilites doivent etre dans [0,1].")
        local_probability = probability[:height, :width]
        probability_view = probability_sum[target]
        np.add(probability_view, local_probability, out=probability_view, where=local_valid)
        weight_view = weight_sum[target]
        np.add(weight_view, 1.0, out=weight_view, where=local_valid)

    @classmethod
    def remove_small_objects(
        cls,
        mask: np.ndarray,
        *,
        min_object_pixels: int,
        connectivity: int = 8,
    ) -> np.ndarray:
        output = np.asarray(mask, dtype=np.bool_).copy()
        if min_object_pixels <= 1:
            return output
        visited = np.zeros(output.shape, dtype=np.bool_)
        for row, col in zip(*np.nonzero(output & ~visited), strict=False):
            if visited[row, col]:
                continue
            queue: deque[tuple[int, int]] = deque([(int(row), int(col))])
            visited[row, col] = True
            small_pixels: list[tuple[int, int]] = []
            count = 0
            while queue:
                current_row, current_col = queue.popleft()
                count += 1
                if count < min_object_pixels:
                    small_pixels.append((current_row, current_col))
                for next_row, next_col in cls._neighbors(
                    current_row, current_col, output.shape, connectivity
                ):
                    if output[next_row, next_col] and not visited[next_row, next_col]:
                        visited[next_row, next_col] = True
                        queue.append((next_row, next_col))
            if count < min_object_pixels:
                for pixel_row, pixel_col in small_pixels:
                    output[pixel_row, pixel_col] = False
        return output

    @classmethod
    def fill_small_holes(
        cls,
        mask: np.ndarray,
        *,
        valid_mask: np.ndarray,
        max_hole_pixels: int,
        connectivity: int = 8,
    ) -> np.ndarray:
        output = np.asarray(mask, dtype=np.bool_).copy()
        valid = np.asarray(valid_mask, dtype=np.bool_)
        if output.shape != valid.shape:
            raise ValueError("valid_mask doit avoir les dimensions du masque.")
        if max_hole_pixels <= 0:
            return output
        candidates = valid & ~output
        visited = np.zeros(output.shape, dtype=np.bool_)
        rows, cols = output.shape
        for row, col in zip(*np.nonzero(candidates & ~visited), strict=False):
            if visited[row, col]:
                continue
            queue: deque[tuple[int, int]] = deque([(int(row), int(col))])
            visited[row, col] = True
            pixels: list[tuple[int, int]] = []
            count = 0
            touches_exterior = False
            while queue:
                current_row, current_col = queue.popleft()
                count += 1
                if count <= max_hole_pixels:
                    pixels.append((current_row, current_col))
                if current_row in {0, rows - 1} or current_col in {0, cols - 1}:
                    touches_exterior = True
                for delta_row, delta_col in cls._neighbor_offsets(connectivity):
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < rows and 0 <= next_col < cols):
                        touches_exterior = True
                        continue
                    if not valid[next_row, next_col]:
                        touches_exterior = True
                        continue
                    if candidates[next_row, next_col] and not visited[next_row, next_col]:
                        visited[next_row, next_col] = True
                        queue.append((next_row, next_col))
            if not touches_exterior and count <= max_hole_pixels:
                for pixel_row, pixel_col in pixels:
                    output[pixel_row, pixel_col] = True
        output[~valid] = False
        return output

    @classmethod
    def apply_morphology(
        cls,
        mask: np.ndarray,
        *,
        valid_mask: np.ndarray,
        config: PostProcessingConfig,
    ) -> np.ndarray:
        output = np.asarray(mask, dtype=np.bool_).copy()
        valid = np.asarray(valid_mask, dtype=np.bool_)
        for _ in range(config.morphology_iterations):
            if config.opening_enabled:
                output = cls._dilate(
                    cls._erode(output, config.morphology_kernel_size),
                    config.morphology_kernel_size,
                )
            if config.closing_enabled:
                output = cls._erode(
                    cls._dilate(output, config.morphology_kernel_size),
                    config.morphology_kernel_size,
                )
            output &= valid
        return output

    @classmethod
    def connected_components(
        cls,
        mask: np.ndarray,
        *,
        connectivity: int = 8,
    ) -> tuple[ComponentInfo, ...]:
        source = np.asarray(mask, dtype=np.bool_)
        visited = np.zeros(source.shape, dtype=np.bool_)
        components: list[ComponentInfo] = []
        for row, col in zip(*np.nonzero(source & ~visited), strict=False):
            if visited[row, col]:
                continue
            queue: deque[tuple[int, int]] = deque([(int(row), int(col))])
            visited[row, col] = True
            count = 0
            min_row = max_row = int(row)
            min_col = max_col = int(col)
            while queue:
                current_row, current_col = queue.popleft()
                count += 1
                min_row = min(min_row, current_row)
                max_row = max(max_row, current_row)
                min_col = min(min_col, current_col)
                max_col = max(max_col, current_col)
                for next_row, next_col in cls._neighbors(
                    current_row, current_col, source.shape, connectivity
                ):
                    if source[next_row, next_col] and not visited[next_row, next_col]:
                        visited[next_row, next_col] = True
                        queue.append((next_row, next_col))
            components.append(
                ComponentInfo(
                    component_id=len(components) + 1,
                    pixel_count=count,
                    bbox=(min_col, min_row, max_col + 1, max_row + 1),
                )
            )
        return tuple(components)

    @staticmethod
    def _dilate(mask: np.ndarray, kernel_size: int) -> np.ndarray:
        radius = kernel_size // 2
        padded = np.pad(mask, radius, mode="constant", constant_values=False)
        output = np.zeros(mask.shape, dtype=np.bool_)
        for row in range(kernel_size):
            for col in range(kernel_size):
                output |= padded[row : row + mask.shape[0], col : col + mask.shape[1]]
        return output

    @staticmethod
    def _erode(mask: np.ndarray, kernel_size: int) -> np.ndarray:
        radius = kernel_size // 2
        padded = np.pad(mask, radius, mode="constant", constant_values=False)
        output = np.ones(mask.shape, dtype=np.bool_)
        for row in range(kernel_size):
            for col in range(kernel_size):
                output &= padded[row : row + mask.shape[0], col : col + mask.shape[1]]
        return output

    @classmethod
    def _neighbors(
        cls,
        row: int,
        col: int,
        shape: tuple[int, int],
        connectivity: int,
    ) -> Iterable[tuple[int, int]]:
        rows, cols = shape
        for delta_row, delta_col in cls._neighbor_offsets(connectivity):
            next_row = row + delta_row
            next_col = col + delta_col
            if 0 <= next_row < rows and 0 <= next_col < cols:
                yield next_row, next_col

    @staticmethod
    def _neighbor_offsets(connectivity: int) -> tuple[tuple[int, int], ...]:
        if connectivity == 4:
            return ((-1, 0), (0, -1), (0, 1), (1, 0))
        if connectivity == 8:
            return (
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -1),
                (0, 1),
                (1, -1),
                (1, 0),
                (1, 1),
            )
        raise ValueError("connectivity doit valoir 4 ou 8.")

    @staticmethod
    def _validate_grid(grid: RasterGrid) -> None:
        if grid.width <= 0 or grid.height <= 0:
            raise ValueError("Les dimensions du raster doivent etre positives.")
        if not grid.crs or len(grid.transform) < 6:
            raise ValueError("Le CRS et la transformation du raster sont obligatoires.")
        if not all(math.isfinite(float(value)) for value in grid.transform[:6]):
            raise ValueError("La transformation du raster est invalide.")
        if grid.resolution_x <= 0 or grid.resolution_y <= 0:
            raise ValueError("La resolution du raster doit etre positive.")
