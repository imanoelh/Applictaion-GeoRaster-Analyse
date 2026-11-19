from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..errors import AIRasterError
from ..models.base_model_adapter import AIModelError
from ..registry.model_registry import ModelRegistry, create_default_model_registry
from ..schemas.prediction_schemas import BuildingInferenceRequest, BuildingInferenceResponse
from ..services.ai_raster_service import AIRasterService
from ..services.inference_service import InferenceService
from ..services.tiling_service import TilingService
from .ai_raster_routes import get_ai_raster_service, get_tiling_service


logger = logging.getLogger(__name__)
ORTHOPHOTO_INTEGRATION_WARNING = (
    "Orthophoto RGB valide uniquement l'integration technique. "
    "Le ratio de pixels positifs ne mesure pas la qualite scientifique et ne constitue pas un nombre de batiments."
)
router = APIRouter(prefix="/api/ai/inference", tags=["AI inference"])
_model_registry = create_default_model_registry()
_inference_service = InferenceService(_model_registry)


def get_model_registry() -> ModelRegistry:
    return _model_registry


def get_inference_service() -> InferenceService:
    return _inference_service


@router.get("/models/building")
def list_building_models() -> dict[str, list[dict[str, object]]]:
    return {"models": _model_registry.list_models("building")}


@router.post("/building", response_model=BuildingInferenceResponse)
def run_building_inference(
    request: BuildingInferenceRequest,
    raster_service: AIRasterService = Depends(get_ai_raster_service),
    tiling_service: TilingService = Depends(get_tiling_service),
    inference_service: InferenceService = Depends(get_inference_service),
) -> BuildingInferenceResponse:
    tiles = None
    try:
        raster_path, sidecar = raster_service.get_validated_artifact(request.raster_id)
        profile, band_indexes = raster_service.get_preprocessing_context(sidecar)
        adapter = inference_service.registry.get_selected_model("building", request.model_id)
        tile_size = adapter.preferred_tile_size or request.tile_size
        overlap_ratio = getattr(adapter, "preferred_overlap_ratio", request.overlap_ratio)
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
        threshold = request.probability_threshold
        if "probability_threshold" not in request.model_fields_set:
            configured = getattr(getattr(adapter, "config", None), "probability_threshold", None)
            if configured is not None:
                threshold = float(configured)
        result = inference_service.summarize(
            tiles,
            object_type="building",
            probability_threshold=threshold,
            inference_mode=request.inference_mode,
            model_id=request.model_id,
        )
        if profile == "rgb_orthophoto_uint8_v1":
            result["warning"] = ORTHOPHOTO_INTEGRATION_WARNING
        return BuildingInferenceResponse.model_validate(result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIRasterError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc
    except AIModelError as exc:
        status = 422 if exc.code in {"MODEL_INPUT_INVALID", "MODEL_OUTPUT_INVALID", "MODEL_NOT_FOUND"} else 503
        logger.error("[AI-INFERENCE] code=%s detail=%s", exc.code, exc.technical_detail or exc.message)
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        close_tiles = getattr(tiles, "close", None)
        if callable(close_tiles):
            close_tiles()

