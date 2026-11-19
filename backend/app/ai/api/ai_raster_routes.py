from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
import numpy as np
import rasterio
from PIL import Image
from io import BytesIO

from ..errors import AIRasterError
from ..schemas.ai_raster_schemas import (
    AIRasterCleanupResponse,
    AIRasterPrepareRequest,
    AIRasterPrepareResponse,
)
from ..schemas.tile_schemas import AITilingRequest, AITilingResponse
from ..services.ai_raster_service import AIRasterService
from ..services.image_validator import RasterValidationError
from ..services.tiling_service import TilingService
from ..sources.gee_raster_source import GeeRasterDownloadError


router = APIRouter(prefix="/api/ai/raster", tags=["AI raster preparation"])
_service = AIRasterService()
_tiling_service = TilingService()


def get_ai_raster_service() -> AIRasterService:
    return _service


def get_tiling_service() -> TilingService:
    return _tiling_service


@router.post("/local/maxar/init")
async def init_maxar_upload(
    filename: str = Query(min_length=1, max_length=255),
    size_bytes: int = Query(gt=0),
    service: AIRasterService = Depends(get_ai_raster_service),
) -> dict[str, object]:
    try:
        return service.create_large_upload(filename, size_bytes)
    except AIRasterError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc


@router.post("/local/maxar/{upload_id}/chunk")
async def append_maxar_upload_chunk(
    upload_id: str,
    request: Request,
    index: int = Query(ge=0),
    total_chunks: int = Query(gt=0),
    service: AIRasterService = Depends(get_ai_raster_service),
) -> dict[str, object]:
    try:
        state = service.get_large_upload(upload_id)
        if index != int(state["next_chunk"]):
            raise AIRasterError("UPLOAD_CHUNK_ORDER", "Les chunks Maxar doivent être envoyés dans l’ordre.")
        if total_chunks <= index:
            raise AIRasterError("UPLOAD_CHUNK_INVALID", "Le nombre total de chunks est invalide.")
        path = service.large_upload_path(upload_id)
        written = 0
        initial_size = path.stat().st_size if path.exists() else 0
        with path.open("ab") as output:
            async for chunk in request.stream():
                written += len(chunk)
                if written > service.large_upload_chunk_size():
                    output.flush()
                    output.truncate(initial_size)
                    raise AIRasterError("UPLOAD_CHUNK_TOO_LARGE", "Un chunk Maxar dépasse la taille configurée.")
                output.write(chunk)
        if written <= 0:
            raise AIRasterError("UPLOAD_CHUNK_INVALID", "Le chunk Maxar est vide.")
        received = int(state["received_bytes"]) + written
        if received > int(state["size_bytes"]):
            path.open("r+b").truncate(initial_size)
            raise AIRasterError("MAXAR_UPLOAD_TOO_LARGE", "La taille reçue dépasse la taille annoncée.")
        state.update({"received_bytes": received, "next_chunk": index + 1, "total_chunks": total_chunks})
        service.save_large_upload_state(state)
        return {"upload_id": upload_id, "index": index, "received_bytes": received, "progress": received / int(state["size_bytes"])}
    except AIRasterError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc


@router.post("/local/maxar/{upload_id}/complete", response_model=AIRasterPrepareResponse)
async def complete_maxar_upload(
    upload_id: str,
    service: AIRasterService = Depends(get_ai_raster_service),
) -> AIRasterPrepareResponse:
    try:
        state = service.get_large_upload(upload_id)
        path = service.large_upload_path(upload_id)
        if int(state["received_bytes"]) != int(state["size_bytes"]) or path.stat().st_size != int(state["size_bytes"]):
            raise AIRasterError("UPLOAD_INCOMPLETE", "L’upload Maxar est incomplet.")
        result = service.prepare_maxar_local(path, original_filename=str(state["filename"]))
        return result
    except AIRasterError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc
    finally:
        try:
            service.cleanup_large_upload(upload_id)
        except AIRasterError:
            pass


@router.post("/prepare", response_model=AIRasterPrepareResponse)
def prepare_ai_raster(
    request: AIRasterPrepareRequest,
    service: AIRasterService = Depends(get_ai_raster_service),
) -> AIRasterPrepareResponse:
    try:
        return service.prepare(request)
    except RasterValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GeeRasterDownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/local", response_model=AIRasterPrepareResponse)
async def prepare_local_ai_raster(
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
    red_band: int | None = Query(default=None, ge=1),
    green_band: int | None = Query(default=None, ge=1),
    blue_band: int | None = Query(default=None, ge=1),
    service: AIRasterService = Depends(get_ai_raster_service),
) -> AIRasterPrepareResponse:
    """Stream one GeoTIFF body into an isolated server-controlled staging file."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/tiff", "image/geotiff", "application/octet-stream"}:
        raise HTTPException(
            status_code=415,
            detail={"code": "LOCAL_RASTER_INVALID", "message": "Content-Type GeoTIFF non accepte."},
        )
    staged = None
    try:
        staged = service.allocate_local_upload(filename)
        maximum = service.local_upload_max_bytes()
        total = 0
        with staged.open("xb") as output:
            async for chunk in request.stream():
                total += len(chunk)
                if total > maximum:
                    raise AIRasterError(
                        "LOCAL_RASTER_INVALID",
                        f"Le GeoTIFF depasse la taille maximale autorisee ({maximum} octets).",
                    )
                output.write(chunk)
        if total == 0:
            raise AIRasterError("LOCAL_RASTER_INVALID", "Le GeoTIFF fourni est vide.")
        supplied = {"R": red_band, "G": green_band, "B": blue_band}
        band_mapping = None if all(value is None for value in supplied.values()) else supplied
        return service.prepare_local(
            staged,
            original_filename=filename,
            band_mapping=band_mapping,  # type: ignore[arg-type]
        )
    except AIRasterError as exc:
        status = 404 if exc.code == "LOCAL_RASTER_NOT_FOUND" else 422
        raise HTTPException(status_code=status, detail=exc.public_detail()) from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


@router.get("/{raster_id}/preview.png")
def preview_local_raster(
    raster_id: str,
    service: AIRasterService = Depends(get_ai_raster_service),
) -> Response:
    """Serve a bounded RGB preview without loading the full orthophoto."""
    try:
        raster_path, _sidecar = service.get_validated_artifact(raster_id)
        with rasterio.open(raster_path) as dataset:
            scale = min(1.0, 2048.0 / max(dataset.width, dataset.height))
            width = max(1, int(round(dataset.width * scale)))
            height = max(1, int(round(dataset.height * scale)))
            data = dataset.read(
                indexes=[1, 2, 3],
                out_shape=(3, height, width),
                resampling=rasterio.enums.Resampling.bilinear,
                masked=True,
            )
            rgb = np.ma.filled(data, 0).astype(np.uint8, copy=False)
            alpha = np.where(np.any(np.ma.getmaskarray(data), axis=0), 0, 255).astype(np.uint8)
            rgba = np.concatenate([np.moveaxis(rgb, 0, -1), alpha[..., None]], axis=-1)
        output = BytesIO()
        Image.fromarray(rgba, mode="RGBA").save(output, format="PNG", optimize=True)
        return Response(content=output.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, rasterio.errors.RasterioIOError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tile", response_model=AITilingResponse)
def tile_ai_raster(
    request: AITilingRequest,
    raster_service: AIRasterService = Depends(get_ai_raster_service),
    tiling_service: TilingService = Depends(get_tiling_service),
) -> AITilingResponse:
    try:
        raster_path, sidecar = raster_service.get_validated_artifact(request.raster_id)
        profile, band_indexes = raster_service.get_preprocessing_context(sidecar)
        preprocessing, tiling, tiles = tiling_service.summarize(
            raster_path,
            raster_id=request.raster_id,
            tile_size=request.tile_size,
            overlap_ratio=request.overlap_ratio,
            min_valid_pixel_ratio=request.min_valid_pixel_ratio,
            max_tiles_metadata=request.max_tiles_metadata,
            preprocessing_profile=profile,
            band_indexes=band_indexes,
        )
        return AITilingResponse(
            raster_id=request.raster_id,
            preprocessing=preprocessing,
            tiling=tiling,
            tiles=tiles,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIRasterError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{raster_id}", response_model=AIRasterCleanupResponse)
def cleanup_ai_raster(
    raster_id: str,
    service: AIRasterService = Depends(get_ai_raster_service),
) -> AIRasterCleanupResponse:
    try:
        removed = service.cleanup_raster(raster_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AIRasterCleanupResponse(success=True, raster_id=raster_id, removed=removed)
