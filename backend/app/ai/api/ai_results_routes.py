from __future__ import annotations

import logging
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response

from ..errors import AIRasterError
from ..config.building_model_catalog import model_identity
from ..models.base_model_adapter import AIModelError
from ..schemas.results_schemas import BuildingAnalysisResult
from ..schemas.export_schemas import BuildingExportRequest
from ..schemas.vectorization_schemas import BuildingResultsRequest
from ..services.ai_raster_service import AIRasterService
from ..services.building_polygonization_service import BuildingPolygonizationService
from ..services.building_results_service import BuildingResultsService
from ..services.building_export_service import BuildingExportService
from ..services.inference_service import InferenceService
from ..services.postprocessing_service import PostProcessingService
from ..services.tiling_service import TilingService
from .ai_inference_routes import get_inference_service
from .ai_postprocessing_routes import get_postprocessing_service
from .ai_raster_routes import get_ai_raster_service, get_tiling_service
from .ai_vectorization_routes import build_building_vector_result, get_polygonization_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai/results", tags=["AI results"])
_results_service = BuildingResultsService()
_export_service = BuildingExportService()


def get_results_service() -> BuildingResultsService:
    return _results_service


def get_export_service() -> BuildingExportService:
    return _export_service


@router.post("/building", response_model=BuildingAnalysisResult)
def building_results(
    request: BuildingResultsRequest,
    raster_service: AIRasterService = Depends(get_ai_raster_service),
    tiling_service: TilingService = Depends(get_tiling_service),
    inference_service: InferenceService = Depends(get_inference_service),
    postprocessing_service: PostProcessingService = Depends(get_postprocessing_service),
    polygonization_service: BuildingPolygonizationService = Depends(get_polygonization_service),
    results_service: BuildingResultsService = Depends(get_results_service),
) -> BuildingAnalysisResult:
    started = time.perf_counter()
    try:
        vector_result = build_building_vector_result(
            request,
            raster_service=raster_service,
            tiling_service=tiling_service,
            inference_service=inference_service,
            postprocessing_service=postprocessing_service,
            polygonization_service=polygonization_service,
        )
        result = results_service.build(vector_result)
        adapter = inference_service.registry.get_selected_model("building", request.model_id)
        info = adapter.get_model_info()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        result.model_metadata.update(model_identity(result.model_id, info.get("runtime")))
        result.model_metadata["processing_time"] = elapsed_ms / 1000.0
        result.processing_metadata.total_processing_time_ms = elapsed_ms
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIRasterError as exc:
        status = 413 if exc.code == "POSTPROCESSING_RASTER_TOO_LARGE" else 422
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    except AIModelError as exc:
        logger.error("[AI-RESULTS] code=%s detail=%s", exc.code, exc.technical_detail or exc.message)
        status = 422 if exc.code == "MODEL_NOT_FOUND" else 503
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/building/export")
def export_building_result(
    request: BuildingExportRequest,
    export_service: BuildingExportService = Depends(get_export_service),
) -> Response:
    artifact = export_service.export(request.result, request.format)
    disposition = (
        f'attachment; filename="{artifact.filename}"; '
        f"filename*=UTF-8''{quote(artifact.filename, safe='')}"
    )
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "no-store",
        },
    )
