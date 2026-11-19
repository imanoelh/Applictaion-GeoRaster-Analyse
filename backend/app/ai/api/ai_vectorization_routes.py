from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from ..errors import AIRasterError
from ..models.base_model_adapter import AIModelError
from ..models.hybrid_building_adapter import HybridBuildingModelAdapter
from ..schemas.vectorization_schemas import (
    BuildingVectorPipelineRequest,
    BuildingVectorizationRequest,
    BuildingVectorizationResponse,
    BuildingVectorizationSummary,
)
from ..services.ai_raster_service import AIRasterService
from ..services.building_polygonization_service import (
    BuildingPolygonizationService,
    PolygonizationConfig,
)
from ..services.inference_service import InferenceService
from ..services.postprocessing_service import PostProcessingService
from ..services.tiling_service import TilingService
from .ai_inference_routes import get_inference_service
from .ai_postprocessing_routes import build_building_mask, get_postprocessing_service
from .ai_raster_routes import get_ai_raster_service, get_tiling_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai/vectorize", tags=["AI vectorization"])
_polygonization_service = BuildingPolygonizationService()


def get_polygonization_service() -> BuildingPolygonizationService:
    return _polygonization_service


@router.post("/building", response_model=BuildingVectorizationResponse)
def vectorize_building_mask(
    request: BuildingVectorizationRequest,
    raster_service: AIRasterService = Depends(get_ai_raster_service),
    tiling_service: TilingService = Depends(get_tiling_service),
    inference_service: InferenceService = Depends(get_inference_service),
    postprocessing_service: PostProcessingService = Depends(get_postprocessing_service),
    polygonization_service: BuildingPolygonizationService = Depends(get_polygonization_service),
) -> BuildingVectorizationResponse:
    try:
        result = build_building_vector_result(
            request,
            raster_service=raster_service,
            tiling_service=tiling_service,
            inference_service=inference_service,
            postprocessing_service=postprocessing_service,
            polygonization_service=polygonization_service,
        )
        return BuildingVectorizationResponse(
            raster_id=result.raster_id,
            warning=(
                "Candidats Building vectorises: le nombre et les geometries ne constituent "
                "pas une validation scientifique de batiments reels."
            ),
            vectorization=BuildingVectorizationSummary(
                feature_count=result.feature_count,
                geometry_types=result.geometry_types,
                crs=result.crs,
                bounds=result.bounds,
                total_area_map_units=result.total_area_map_units,
                total_area_m2=result.total_area_m2,
                polygonization_time_ms=result.polygonization_time_ms,
            ),
            polygonization_config=result.polygonization_config,
            postprocessing_config=result.postprocessing_config,
            geojson=result.to_geojson() if request.include_geojson else None,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIRasterError as exc:
        status = 413 if exc.code == "POSTPROCESSING_RASTER_TOO_LARGE" else 422
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    except AIModelError as exc:
        logger.error("[AI-VECTORIZE] code=%s detail=%s", exc.code, exc.technical_detail or exc.message)
        status = 422 if exc.code == "MODEL_NOT_FOUND" else 503
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def build_building_vector_result(
    request: BuildingVectorPipelineRequest,
    *,
    raster_service: AIRasterService,
    tiling_service: TilingService,
    inference_service: InferenceService,
    postprocessing_service: PostProcessingService,
    polygonization_service: BuildingPolygonizationService,
):
    """Build stages 1-7 once so downstream technical routes can reuse the vector result."""
    started = time.perf_counter()
    mask_result = build_building_mask(
        request,
        raster_service=raster_service,
        tiling_service=tiling_service,
        inference_service=inference_service,
        postprocessing_service=postprocessing_service,
    )
    try:
        vector_result = polygonization_service.polygonize(
            mask_result,
            config=PolygonizationConfig(
                polygon_connectivity=(
                    int(getattr(inference_service.registry.get_selected_model("building", request.model_id), "get_application_config", lambda: {})().get("connectivity", 4))
                    if request.model_id == "model_c8_hybrid" else request.polygon_connectivity
                ),
                simplify_tolerance=request.simplify_tolerance,
            ),
        )
        if vector_result.model_id == HybridBuildingModelAdapter.MODEL_ID and vector_result.model_metadata is not None:
            vector_result.model_metadata["polygonization_time"] = vector_result.polygonization_time_ms / 1000.0
            vector_result.model_metadata["polygonization_time_ms"] = vector_result.polygonization_time_ms
            vector_result.model_metadata["total_processing_time_ms"] = (time.perf_counter() - started) * 1000.0
            vector_result.model_metadata["total_processing_time"] = vector_result.model_metadata["total_processing_time_ms"] / 1000.0
        return vector_result
    finally:
        mask_result.cleanup()
