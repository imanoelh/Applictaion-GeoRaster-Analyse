from __future__ import annotations

import logging
import tempfile
import time
import shutil
from pathlib import Path

import rasterio
import numpy as np
from fastapi import APIRouter, Depends, HTTPException

from ..errors import AIRasterError
from ..models.base_model_adapter import AIModelError
from ..models.hybrid_building_adapter import HybridBuildingModelAdapter
from ..schemas.postprocessing_schemas import (
    BuildingMaskGridSummary,
    BuildingMaskModelSummary,
    BuildingMaskPerformanceSummary,
    BuildingMaskPixelSummary,
    BuildingMaskTileSummary,
    BuildingPostProcessRequest,
    BuildingPostProcessResponse,
)
from ..services.ai_raster_service import AIRasterService
from ..services.inference_service import InferenceService
from ..services.postprocessing_service import (
    BuildingMaskResult,
    PostProcessingConfig,
    PostProcessingService,
    RasterGrid,
)
from ..services.tiling_service import TilingService
from .ai_inference_routes import get_inference_service
from .ai_raster_routes import get_ai_raster_service, get_tiling_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai/postprocess", tags=["AI post-processing"])
_postprocessing_service = PostProcessingService()


def get_postprocessing_service() -> PostProcessingService:
    return _postprocessing_service


@router.post("/building", response_model=BuildingPostProcessResponse)
def postprocess_building_mask(
    request: BuildingPostProcessRequest,
    raster_service: AIRasterService = Depends(get_ai_raster_service),
    tiling_service: TilingService = Depends(get_tiling_service),
    inference_service: InferenceService = Depends(get_inference_service),
    postprocessing_service: PostProcessingService = Depends(get_postprocessing_service),
) -> BuildingPostProcessResponse:
    try:
        result = build_building_mask(
            request,
            raster_service=raster_service,
            tiling_service=tiling_service,
            inference_service=inference_service,
            postprocessing_service=postprocessing_service,
        )
        response = BuildingPostProcessResponse(
            raster_id=result.raster_id,
            warning=(
                "Masque raster technique uniquement: les parametres de nettoyage et le seuil "
                "ne sont pas calibres scientifiquement; aucun comptage de batiments n'est fourni."
            ),
            model=BuildingMaskModelSummary(
                name=result.model_name,
                version=result.model_version,
                mode=result.model_mode,
                id=result.model_id,
                architecture=result.model_architecture,
                checkpoint_hash=result.model_checkpoint_hash,
                tile_size=result.tile_size,
                preprocessing_profile=result.preprocessing_profile,
            ),
            grid=BuildingMaskGridSummary(
                width=result.width,
                height=result.height,
                crs=result.crs,
                transform=list(result.transform),
                bounds=result.bounds,
                resolution_x=result.resolution[0],
                resolution_y=result.resolution[1],
                pixel_area=result.pixel_area,
            ),
            mask=BuildingMaskPixelSummary(
                positive_pixel_count=result.positive_pixel_count,
                valid_pixel_count=result.valid_pixel_count,
                positive_pixel_ratio=result.positive_pixel_ratio,
            ),
            tiles=BuildingMaskTileSummary(
                total=result.tiles_total,
                processed=result.tiles_processed,
                skipped=result.tiles_skipped,
            ),
            postprocessing_config=result.postprocessing_config,
            performance=BuildingMaskPerformanceSummary(
                postprocessing_time_ms=result.processing_time_ms,
                estimated_global_memory_bytes=result.estimated_global_memory_bytes,
            ),
        )
        result.cleanup()
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIRasterError as exc:
        status = 413 if exc.code == "POSTPROCESSING_RASTER_TOO_LARGE" else 422
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    except AIModelError as exc:
        logger.error("[AI-POSTPROCESS] code=%s detail=%s", exc.code, exc.technical_detail or exc.message)
        status = 422 if exc.code == "MODEL_NOT_FOUND" else 503
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def build_building_mask(
    request: BuildingPostProcessRequest,
    *,
    raster_service: AIRasterService,
    tiling_service: TilingService,
    inference_service: InferenceService,
    postprocessing_service: PostProcessingService,
) -> BuildingMaskResult:
    """Run the validated stage 1-6 pipeline once for technical backend routes."""
    tiles = predictions = None
    try:
        raster_path, sidecar = raster_service.get_validated_artifact(request.raster_id)
        profile, band_indexes = raster_service.get_preprocessing_context(sidecar)
        adapter = inference_service.registry.get_selected_model("building", request.model_id)
        tile_size = adapter.preferred_tile_size or request.tile_size
        overlap_ratio = getattr(adapter, "preferred_overlap_ratio", request.overlap_ratio)
        with rasterio.open(raster_path) as dataset:
            bounds = dataset.bounds
            grid = RasterGrid(
                raster_id=request.raster_id,
                width=int(dataset.width),
                height=int(dataset.height),
                crs=dataset.crs.to_string() if dataset.crs else "",
                transform=tuple(float(value) for value in tuple(dataset.transform)),
                bounds={
                    "left": float(bounds.left),
                    "bottom": float(bounds.bottom),
                    "right": float(bounds.right),
                    "top": float(bounds.top),
                },
            )
        if isinstance(adapter, HybridBuildingModelAdapter):
            if request.inference_mode != "standard":
                raise AIModelError(
                    "HYBRID_INFERENCE_MODE_UNSUPPORTED",
                    "Le moteur hybride utilise le mode d’inférence standard pour conserver la fusion binaire validée.",
                )
            return _build_hybrid_building_mask(
                request,
                raster_path=raster_path,
                profile=profile,
                band_indexes=tuple(band_indexes),
                grid=grid,
                adapter=adapter,
                tiling_service=tiling_service,
                inference_service=inference_service,
                postprocessing_service=postprocessing_service,
            )
        tiles = tiling_service.iter_tiles(
            raster_path,
            raster_id=request.raster_id,
            tile_size=tile_size,
            overlap_ratio=overlap_ratio,
            min_valid_pixel_ratio=request.min_valid_pixel_ratio,
            preprocessing_profile=profile,
            band_indexes=band_indexes,
        )
        prepare_tiles = getattr(adapter, "prepare_inference_tiles", None)
        if callable(prepare_tiles):
            tiles = adapter.prepare_inference_tiles(
                tiles,
                raster_path,
                raster_id=request.raster_id,
                band_indexes=tuple(band_indexes),
            )
        c8_config = getattr(adapter, "get_application_config", lambda: {})() if request.model_id == "model_c8_hybrid" else {}
        predictions = inference_service.iter_predictions(
            tiles,
            object_type="building",
            probability_threshold=(
                float(c8_config.get("threshold", 0.50))
                if request.model_id == "model_c8_hybrid" else request.probability_threshold
            ),
            inference_mode=request.inference_mode,
            model_id=request.model_id,
        )
        config = PostProcessingConfig(
            probability_threshold=(float(c8_config.get("threshold", 0.50)) if request.model_id == "model_c8_hybrid" else request.probability_threshold),
            min_object_pixels=(int(c8_config.get("min_component", 32)) if request.model_id == "model_c8_hybrid" else request.min_object_pixels),
            max_hole_pixels=request.max_hole_pixels,
            opening_enabled=(False if request.model_id == "model_c8_hybrid" else request.opening_enabled),
            closing_enabled=(False if request.model_id == "model_c8_hybrid" else request.closing_enabled),
            morphology_kernel_size=request.morphology_kernel_size,
            morphology_iterations=request.morphology_iterations,
            connectivity=(int(c8_config.get("connectivity", 4)) if request.model_id == "model_c8_hybrid" else request.connectivity),
        )
        return postprocessing_service.process(predictions, grid=grid, config=config)
    finally:
        for stream in (predictions, tiles):
            close = getattr(stream, "close", None)
            if callable(close):
                close()


def _build_hybrid_building_mask(
    request: BuildingPostProcessRequest,
    *,
    raster_path,
    profile: str,
    band_indexes: tuple[int, int, int],
    grid: RasterGrid,
    adapter: HybridBuildingModelAdapter,
    tiling_service: TilingService,
    inference_service: InferenceService,
    postprocessing_service: PostProcessingService,
) -> BuildingMaskResult:
    started = time.perf_counter()
    adapter.load()
    c_info = adapter.model_c.get_model_info()
    d_info = adapter.model_d.get_model_info()
    tile_size = adapter.preferred_tile_size or 512
    overlap = adapter.preferred_overlap_ratio
    mask_c = mask_d = None
    c_tiles = d_tiles = c_predictions = d_predictions = None
    union_storage = None
    try:
        def tiles():
            return tiling_service.iter_tiles(
                raster_path,
                raster_id=request.raster_id,
                tile_size=tile_size,
                overlap_ratio=overlap,
                min_valid_pixel_ratio=request.min_valid_pixel_ratio,
                preprocessing_profile=profile,
                band_indexes=band_indexes,
            )

        c_tiles = adapter.model_c.prepare_inference_tiles(
            tiles(), raster_path, raster_id=request.raster_id, band_indexes=band_indexes
        )
        c_predictions = inference_service.iter_predictions(
            c_tiles, object_type="building", probability_threshold=request.probability_threshold,
            inference_mode="standard", model_id="spacenet2_deeplab",
        )
        mask_c = postprocessing_service.threshold_model_mask(
            c_predictions, grid=grid, threshold=request.probability_threshold
        )

        # Recreate the same 512 px, 50% overlap windows and validate the resulting global coverage.
        d_tiles = tiles()
        d_predictions = inference_service.iter_predictions(
            d_tiles, object_type="building", probability_threshold=request.probability_threshold,
            inference_mode="standard", model_id="whu_unetplusplus_effb4",
        )
        mask_d = postprocessing_service.threshold_model_mask(
            d_predictions, grid=grid, threshold=request.probability_threshold
        )
        if (mask_c.tiles_total != mask_d.tiles_total or mask_c.tiles_processed != mask_d.tiles_processed
                or mask_c.tiles_skipped != mask_d.tiles_skipped
                or mask_c.tile_layout != mask_d.tile_layout
                or not np.array_equal(mask_c.global_valid_mask, mask_d.global_valid_mask)):
            raise AIRasterError("HYBRID_ALIGNMENT_ERROR", "Les masques globaux C et D n’ont pas la même couverture.")
        if mask_c.model_identity[3] != "spacenet2_deeplab" or mask_d.model_identity[3] != "whu_unetplusplus_effb4":
            raise AIRasterError("HYBRID_ALIGNMENT_ERROR", "L’identité d’un modèle ne correspond pas au masque calculé.")

        pixel_count = grid.width * grid.height
        union_started = time.perf_counter()
        if pixel_count > postprocessing_service.max_global_pixels:
            union_storage = tempfile.mkdtemp(prefix="georaster-hybrid-union-")
            union = np.memmap(Path(union_storage) / "mask_e.bool", mode="w+", dtype=np.bool_, shape=(grid.height, grid.width))
            for row in range(0, grid.height, 1024):
                end = min(grid.height, row + 1024)
                union[row:end] = np.asarray(mask_c.global_binary_mask[row:end], dtype=bool) | np.asarray(mask_d.global_binary_mask[row:end], dtype=bool)
                union[row:end] &= mask_c.global_valid_mask[row:end]
            union.flush()
        else:
            union = np.logical_or(mask_c.global_binary_mask, mask_d.global_binary_mask)
            union &= mask_c.global_valid_mask
        fusion_ms = (time.perf_counter() - union_started) * 1000.0
        c_components = adapter.get_model_info()["component_models"][0]
        d_components = adapter.get_model_info()["component_models"][1]
        model_metadata = {
            "status": adapter.STATUS,
            "model_id": adapter.MODEL_ID,
            "component_models": [c_components, d_components],
            "fusion_method": "UNION",
            "model_c_threshold": request.probability_threshold,
            "model_d_threshold": request.probability_threshold,
            "model_c_engine": c_info.get("runtime"),
            "model_d_engine": d_info.get("runtime"),
            "model_c_checkpoint_hash": c_info.get("checkpoint_sha256"),
            "model_d_checkpoint_hash": d_info.get("checkpoint_sha256"),
            "model_d_identifier": d_info.get("model_version"),
            "processing_time_c": mask_c.inference_time_ms / 1000.0,
            "processing_time_c_ms": mask_c.inference_time_ms,
            "processing_time_d": mask_d.inference_time_ms / 1000.0,
            "processing_time_d_ms": mask_d.inference_time_ms,
            "fusion_time": fusion_ms / 1000.0,
            "fusion_time_ms": fusion_ms,
            "model_c_tiles": mask_c.tiles_total,
            "model_d_tiles": mask_d.tiles_total,
            "tile_size": tile_size,
            "overlap_ratio": overlap,
        }
        config = PostProcessingConfig(
            probability_threshold=request.probability_threshold,
            min_object_pixels=request.min_object_pixels,
            max_hole_pixels=request.max_hole_pixels,
            opening_enabled=request.opening_enabled,
            closing_enabled=request.closing_enabled,
            morphology_kernel_size=request.morphology_kernel_size,
            morphology_iterations=request.morphology_iterations,
            connectivity=request.connectivity,
        )
        result = postprocessing_service.process_binary_mask(
            union, mask_c.global_valid_mask, grid=grid, config=config,
            model_name=adapter.MODEL_NAME, model_version=adapter.MODEL_VERSION,
            model_id=adapter.MODEL_ID, model_architecture=adapter.MODEL_ARCHITECTURE,
            model_metadata=model_metadata, source_type=mask_c.source_type,
            tiles_total=mask_c.tiles_total, tiles_processed=mask_c.tiles_processed,
            tiles_skipped=mask_c.tiles_skipped,
        )
        result.model_metadata["total_processing_time_ms"] = (time.perf_counter() - started) * 1000.0
        result.model_metadata["total_processing_time"] = result.model_metadata["total_processing_time_ms"] / 1000.0
        result.model_metadata["polygonization_time"] = None
        result.model_metadata["processing_time_includes"] = "both model passes, overlap fusion, binary union and GeoRaster post-processing"
        return result
    except AIModelError:
        raise
    finally:
        for stream in (c_predictions, d_predictions, c_tiles, d_tiles):
            close = getattr(stream, "close", None)
            if callable(close): close()
        for model_mask in (mask_c, mask_d):
            if model_mask is not None: model_mask.cleanup()
        if union_storage:
            mmap_handle = getattr(union, "_mmap", None)
            if mmap_handle is not None:
                try: mmap_handle.close()
                except (AttributeError, BufferError, OSError): pass
            shutil.rmtree(union_storage, ignore_errors=True)
