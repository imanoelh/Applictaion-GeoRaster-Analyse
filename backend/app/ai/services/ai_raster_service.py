from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from rasterio.crs import CRS
from rasterio.warp import transform_bounds

from ..errors import AIRasterError
from ..schemas.ai_raster_schemas import AIRasterPrepareRequest, AIRasterPrepareResponse
from ..sources.base_raster_source import RasterSource
from ..sources.gee_raster_source import GeeRasterSource
from ..sources.local_raster_source import LocalRasterSource
from .image_validator import ImageValidator
from .maxar_multispectral_profile import MaxarMultispectralProfile


logger = logging.getLogger(__name__)
AI_RESOLUTION_WARNING = (
    "Sentinel-2 10 m : resolution insuffisante pour garantir une detection "
    "individuelle fiable des petits batiments, arbres ou vehicules."
)
_SAFE_RASTER_ID = re.compile(
    r"^(?:ai-s2-[0-9]{8}-[0-9a-f]{12}-[0-9a-f]{12}"
    r"|ai-ortho-[0-9a-f]{12}-[0-9a-f]{12}-[0-9a-f]{12})$"
)
_SAFE_FILENAME = re.compile(r"^[^/\\\x00]+\.(?:tif|tiff)$", re.IGNORECASE)
_SAFE_UPLOAD_ID = re.compile(r"^[0-9a-f]{32}$")
RasterSourceFactory = Callable[[dict[str, Any], Path, str], RasterSource]


class AIRasterService:
    """Orchestrate source materialization, validation and isolated lifecycle."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        source_factory: RasterSourceFactory | None = None,
        validator: ImageValidator | None = None,
    ) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        self.cache_dir = Path(cache_dir or backend_dir / "data" / "cache" / "ai-raster")
        self.source_factory = source_factory or (
            lambda payload, directory, raster_id: GeeRasterSource(payload, directory, raster_id)
        )
        self.validator = validator or ImageValidator()

    def prepare(self, request: AIRasterPrepareRequest) -> AIRasterPrepareResponse:
        payload = request.model_dump(mode="python", exclude_none=True)
        aoi = payload.get("aoi") or {}
        bounds = self._validate_request(payload, aoi)
        aoi_hash = hashlib.sha256(
            json.dumps(aoi, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:12]
        date_tag = str(payload["date_start"]).replace("-", "")
        raster_id = f"ai-s2-{date_tag}-{aoi_hash}-{uuid.uuid4().hex[:12]}"
        source = self.source_factory(payload, self.cache_dir, raster_id)
        sidecar_path = self.cache_dir / f"{raster_id}.json"

        try:
            raster_path = source.get_raster()
            validation = self.validator.validate(raster_path, source=source.SOURCE if hasattr(source, "SOURCE") else "sentinel2")
            validation["aoi_match"] = self._raster_matches_aoi(validation, bounds)
            if not validation["aoi_match"]:
                raise ValueError(
                    "Les coordonnees du GeoTIFF ne correspondent pas a l'AOI demandee."
                )
            self._validate_expected_resolution(validation)

            source_metadata = source.get_metadata()
            metadata = {
                "source": "sentinel2",
                "source_type": "sentinel2_gee",
                "source_profile": "sentinel2_sr_v1",
                "preprocessing_profile": "sentinel2_sr_v1",
                "band_indexes": [1, 2, 3],
                "bands": ["B4", "B3", "B2"],
                "date_start": payload["date_start"],
                "date_end": payload["date_end"],
                "aoi_hash": aoi_hash,
                "image_method": payload.get("image_method"),
                "images_count": source_metadata.get("images_count"),
                "mosaic_method": source_metadata.get("mosaic_method"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "wgs84_bounds": self._wgs84_bounds(validation),
            }
            self._write_sidecar(sidecar_path, raster_id, metadata, validation)
            logger.info("[AI-RASTER] validation success raster_id=%s", raster_id)
            logger.info("[AI-RASTER] resolution=10m")
            return AIRasterPrepareResponse(
                source="sentinel2",
                raster_id=raster_id,
                validation=validation,
                warning=AI_RESOLUTION_WARNING,
                metadata=metadata,
            )
        except Exception:
            self.cleanup_raster(raster_id)
            raise

    def allocate_local_upload(self, filename: str) -> Path:
        """Allocate a server-controlled staging path; client paths are never accepted."""
        self._validate_local_filename(filename)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f".upload-{uuid.uuid4().hex}.tif.part"

    @staticmethod
    def local_upload_max_bytes() -> int:
        import os

        raw = os.getenv("AI_LOCAL_RASTER_MAX_BYTES", str(512 * 1024 * 1024))
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError("AI_LOCAL_RASTER_MAX_BYTES doit etre un entier.") from exc
        if value <= 0:
            raise RuntimeError("AI_LOCAL_RASTER_MAX_BYTES doit etre strictement positif.")
        return value

    @staticmethod
    def maxar_upload_max_bytes() -> int:
        import os

        raw = os.getenv("AI_MAXAR_MAX_UPLOAD_BYTES", str(MaxarMultispectralProfile.max_upload_bytes))
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError("AI_MAXAR_MAX_UPLOAD_BYTES doit etre un entier.") from exc
        if value <= 0:
            raise RuntimeError("AI_MAXAR_MAX_UPLOAD_BYTES doit etre strictement positif.")
        return value

    @staticmethod
    def large_upload_chunk_size() -> int:
        import os

        raw = os.getenv("AI_MAXAR_UPLOAD_CHUNK_BYTES", str(16 * 1024 * 1024))
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError("AI_MAXAR_UPLOAD_CHUNK_BYTES doit etre un entier.") from exc
        if value < 1024 * 1024:
            raise RuntimeError("AI_MAXAR_UPLOAD_CHUNK_BYTES doit etre au moins 1 MiB.")
        return value

    def create_large_upload(self, filename: str, size_bytes: int) -> dict[str, Any]:
        self._validate_local_filename(filename)
        if size_bytes <= 0 or size_bytes > self.maxar_upload_max_bytes():
            raise AIRasterError("MAXAR_UPLOAD_TOO_LARGE", "La taille du fichier Maxar dépasse la limite configurée.")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        upload_id = uuid.uuid4().hex
        state = {
            "upload_id": upload_id, "filename": filename, "size_bytes": int(size_bytes),
            "received_bytes": 0, "next_chunk": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._upload_part_path(upload_id).touch()
        self._upload_state_path(upload_id).write_text(json.dumps(state, indent=2), encoding="utf-8")
        return {"upload_id": upload_id, "chunk_size": self.large_upload_chunk_size(), "max_bytes": self.maxar_upload_max_bytes()}

    def get_large_upload(self, upload_id: str) -> dict[str, Any]:
        self._validate_upload_id(upload_id)
        path = self._upload_state_path(upload_id)
        if not path.is_file():
            raise AIRasterError("UPLOAD_NOT_FOUND", "Upload Maxar introuvable ou expiré.")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIRasterError("UPLOAD_INVALID", "L’état de l’upload Maxar est illisible.") from exc

    def save_large_upload_state(self, state: dict[str, Any]) -> None:
        self._upload_state_path(str(state["upload_id"])).write_text(json.dumps(state, indent=2), encoding="utf-8")

    def large_upload_path(self, upload_id: str) -> Path:
        self._validate_upload_id(upload_id)
        return self._upload_part_path(upload_id)

    def cleanup_large_upload(self, upload_id: str) -> bool:
        self._validate_upload_id(upload_id)
        removed = False
        for path in (self._upload_part_path(upload_id), self._upload_state_path(upload_id)):
            if path.is_file():
                path.unlink()
                removed = True
        return removed

    def prepare_maxar_local(self, staged_path: Path, *, original_filename: str) -> AIRasterPrepareResponse:
        """Convert an accepted Maxar Multi-8 source, then reuse prepare_local."""
        self._validate_local_filename(original_filename)
        identity = MaxarMultispectralProfile.identify(Path(staged_path))
        if identity is None:
            raise AIRasterError("MAXAR_PROFILE_NOT_MATCHED", "Le GeoTIFF ne correspond pas au profil Maxar Multi-8 attendu.")
        source_hash = self._sha256_file(Path(staged_path))
        derivative = self.cache_dir / f".maxar-{source_hash[:16]}-{MaxarMultispectralProfile.name}.tif"
        if not derivative.is_file():
            temporary = derivative.with_suffix(".tif.part")
            MaxarMultispectralProfile.convert_to_rgb(Path(staged_path), temporary)
            temporary.replace(derivative)
        prepared = self.prepare_local(derivative, original_filename=original_filename, band_mapping={"R": 1, "G": 2, "B": 3})
        prepared.source = "orthophoto_local"
        prepared.metadata.update({"input_source_profile": MaxarMultispectralProfile.name, "input_content_sha256": source_hash, "maxar_rgb_bands": {"R": 5, "G": 3, "B": 2}, "stretch": "p2-p98_per_channel", "automatic_preparation": True})
        return prepared

    def prepare_local(
        self,
        staged_path: Path,
        *,
        original_filename: str,
        band_mapping: dict[str, int] | None = None,
    ) -> AIRasterPrepareResponse:
        """Validate and isolate a local RGB orthophoto without changing Sentinel/GEE."""
        self._validate_local_filename(original_filename)
        staged = Path(staged_path)
        if not staged.is_file():
            raise AIRasterError("LOCAL_RASTER_NOT_FOUND", "Le GeoTIFF local temporaire est introuvable.")
        content_hash = self._sha256_file(staged)
        profile_document = {
            "source_profile": "rgb_orthophoto_uint8_v1",
            "band_mapping": band_mapping,
        }
        profile_hash = hashlib.sha256(
            json.dumps(profile_document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        raster_id = f"ai-ortho-{content_hash[:12]}-{profile_hash[:12]}-{uuid.uuid4().hex[:12]}"
        source = LocalRasterSource(
            staged,
            self.cache_dir,
            raster_id,
            original_filename=original_filename,
        )
        sidecar_path = self.cache_dir / f"{raster_id}.json"
        try:
            raster_path = source.get_raster()
            validation = self.validator.validate(
                raster_path,
                source="orthophoto_local",
                band_mapping=band_mapping,
            )
            source_metadata = source.get_metadata()
            metadata = {
                **source_metadata,
                "source": "orthophoto_local",
                "source_type": "orthophoto_local",
                "source_profile": validation["source_profile"],
                "preprocessing_profile": validation["source_profile"],
                "band_indexes": validation["band_indexes"],
                "content_sha256": content_hash,
                "profile_sha256": profile_hash,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "wgs84_bounds": self._wgs84_bounds(validation),
            }
            self._write_sidecar(sidecar_path, raster_id, metadata, validation)
            logger.info(
                "[AI-RASTER] validation success raster_id=%s source=orthophoto_local profile=%s",
                raster_id,
                validation["source_profile"],
            )
            resolution_class = validation.get("resolution_class")
            warning = (
                "Orthophoto RGB locale validee pour le pipeline IA; aucune reprojection n'a ete appliquee."
                if resolution_class in {"VERY_HIGH_RESOLUTION", "HIGH_RESOLUTION"}
                else "Orthophoto RGB validee; unite ou resolution spatiale a verifier pour la detection de batiments."
            )
            return AIRasterPrepareResponse(
                source="orthophoto_local",
                raster_id=raster_id,
                validation=validation,
                warning=warning,
                metadata=metadata,
            )

        except Exception:
            self.cleanup_raster(raster_id)
            raise

    @staticmethod
    def _wgs84_bounds(validation: dict[str, Any]) -> dict[str, float]:
        bounds = validation["bounds"]
        source_crs = str(validation["crs"])
        left, bottom, right, top = transform_bounds(
            source_crs,
            "EPSG:4326",
            float(bounds["left"]),
            float(bounds["bottom"]),
            float(bounds["right"]),
            float(bounds["top"]),
            densify_pts=21,
        )
        return {"left": left, "bottom": bottom, "right": right, "top": top}

    def cleanup_raster(self, raster_id: str) -> bool:
        """Remove only artifacts created by this isolated AI cache."""
        self._validate_raster_id(raster_id)
        removed = False
        for suffix in (".tif", ".tif.part", ".json", ".json.part"):
            path = self.cache_dir / f"{raster_id}{suffix}"
            if path.is_file():
                path.unlink()
                removed = True
        return removed

    def get_validated_artifact(self, raster_id: str) -> tuple[Path, dict[str, Any]]:
        """Resolve a validated stage-1 raster without exposing arbitrary paths."""
        self._validate_raster_id(raster_id)
        raster_path = self.cache_dir / f"{raster_id}.tif"
        sidecar_path = self.cache_dir / f"{raster_id}.json"
        if not raster_path.is_file() or not sidecar_path.is_file():
            raise FileNotFoundError("Raster IA valide introuvable ou deja nettoye.")
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Les metadonnees du raster IA sont illisibles.") from exc
        if sidecar.get("raster_id") != raster_id or not (sidecar.get("validation") or {}).get("valid"):
            raise ValueError("Le raster ne possede pas une validation d'etape 1 exploitable.")
        return raster_path, sidecar

    @staticmethod
    def get_preprocessing_context(sidecar: dict[str, Any]) -> tuple[str, tuple[int, int, int]]:
        """Resolve the persisted source contract, defaulting legacy sidecars to Sentinel."""
        metadata = sidecar.get("metadata") if isinstance(sidecar, dict) else None
        validation = sidecar.get("validation") if isinstance(sidecar, dict) else None
        metadata = metadata if isinstance(metadata, dict) else {}
        validation = validation if isinstance(validation, dict) else {}
        profile = str(
            metadata.get("preprocessing_profile")
            or metadata.get("source_profile")
            or validation.get("source_profile")
            or "sentinel2_sr_v1"
        )
        raw_indexes = metadata.get("band_indexes") or validation.get("band_indexes") or [1, 2, 3]
        try:
            indexes = tuple(int(value) for value in raw_indexes)
        except (TypeError, ValueError) as exc:
            raise AIRasterError("UNSUPPORTED_BAND_CONFIGURATION", "Mapping RGB stocke invalide.") from exc
        if len(indexes) != 3:
            raise AIRasterError("UNSUPPORTED_BAND_CONFIGURATION", "Mapping RGB stocke invalide.")
        return profile, indexes  # type: ignore[return-value]

    def cleanup_expired(self, max_age_seconds: int = 86_400) -> int:
        """Delete expired files from the AI raster folder, never other caches."""
        if max_age_seconds < 0:
            raise ValueError("max_age_seconds doit etre positif.")
        if not self.cache_dir.is_dir():
            return 0
        threshold = datetime.now(timezone.utc).timestamp() - max_age_seconds
        removed = 0
        for path in self.cache_dir.iterdir():
            raster_id = path.name.split(".tif", 1)[0].split(".json", 1)[0]
            if _SAFE_RASTER_ID.fullmatch(raster_id) and path.is_file() and path.stat().st_mtime < threshold:
                path.unlink()
                removed += 1
        return removed

    @staticmethod
    def _validate_request(payload: dict[str, Any], aoi: dict[str, Any]) -> list[float]:
        if str(payload.get("sensor")) != "sentinel-2" or str(payload.get("source")) != "S2_SR_HARMONIZED":
            raise ValueError("La preparation raster IA actuelle accepte uniquement Sentinel-2 SR Harmonized.")
        try:
            start = date.fromisoformat(str(payload.get("date_start")))
            end = date.fromisoformat(str(payload.get("date_end")))
        except (TypeError, ValueError) as exc:
            raise ValueError("Les dates doivent utiliser le format ISO YYYY-MM-DD.") from exc
        if start > end:
            raise ValueError("date_start doit etre anterieure ou egale a date_end.")

        bounds = AIRasterService._aoi_bounds(aoi)
        west, south, east, north = bounds
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("AOI invalide: limites geographiques incoherentes.")
        center_latitude = (south + north) / 2.0
        if center_latitude < -80 or center_latitude > 84:
            raise ValueError("L'AOI est hors de la couverture UTM supportee par ce prototype a 10 m.")
        return bounds

    @staticmethod
    def _aoi_bounds(aoi: dict[str, Any]) -> list[float]:
        bbox = aoi.get("bbox") if isinstance(aoi, dict) else None
        if isinstance(bbox, list) and len(bbox) == 2:
            try:
                (south, west), (north, east) = bbox
                values = [float(west), float(south), float(east), float(north)]
                if all(math.isfinite(item) for item in values):
                    return values
            except (TypeError, ValueError):
                pass

        geojson = aoi.get("geojson") if isinstance(aoi, dict) else None
        geometry = geojson.get("geometry", geojson) if isinstance(geojson, dict) else None
        geometry_type = str(geometry.get("type") or "") if isinstance(geometry, dict) else ""
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("AOI invalide: un Polygon ou MultiPolygon avec une surface est requis.")
        coordinates = geometry.get("coordinates")
        points: list[tuple[float, float]] = []

        def collect(value: Any) -> None:
            if (
                isinstance(value, (list, tuple))
                and len(value) >= 2
                and isinstance(value[0], (int, float))
                and isinstance(value[1], (int, float))
            ):
                longitude, latitude = float(value[0]), float(value[1])
                if math.isfinite(longitude) and math.isfinite(latitude):
                    points.append((longitude, latitude))
                return
            if isinstance(value, (list, tuple)):
                for item in value:
                    collect(item)

        collect(coordinates)
        if len(points) < 4:
            raise ValueError("AOI invalide: la geometrie ne contient pas assez de coordonnees.")
        longitudes = [point[0] for point in points]
        latitudes = [point[1] for point in points]
        return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]

    @staticmethod
    def _raster_matches_aoi(validation: dict[str, Any], aoi_bounds: list[float]) -> bool:
        bounds = validation["bounds"]
        try:
            raster_wgs84 = transform_bounds(
                validation["crs"],
                "EPSG:4326",
                bounds["left"],
                bounds["bottom"],
                bounds["right"],
                bounds["top"],
                densify_pts=21,
            )
        except Exception:
            return False
        west, south, east, north = aoi_bounds
        r_west, r_south, r_east, r_north = raster_wgs84
        intersection_width = max(0.0, min(east, r_east) - max(west, r_west))
        intersection_height = max(0.0, min(north, r_north) - max(south, r_south))
        aoi_area = (east - west) * (north - south)
        return aoi_area > 0 and (intersection_width * intersection_height / aoi_area) >= 0.90

    @staticmethod
    def _validate_expected_resolution(validation: dict[str, Any]) -> None:
        # GEE can snap the output grid by tiny floating-point amounts. One
        # centimetre tolerance still enforces the exact 10 m product contract.
        if not CRS.from_string(str(validation["crs"])).is_projected:
            raise ValueError("Le GeoTIFF IA doit utiliser un CRS projete en metres.")
        for key in ("resolution_x", "resolution_y"):
            if not math.isclose(float(validation[key]), 10.0, abs_tol=0.01):
                raise ValueError(
                    f"Resolution GeoTIFF inattendue ({validation[key]} m); 10 m requis."
                )

    @staticmethod
    def _write_sidecar(
        path: Path,
        raster_id: str,
        metadata: dict[str, Any],
        validation: dict[str, Any],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.part")
        document = {"raster_id": raster_id, "metadata": metadata, "validation": validation}
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _validate_local_filename(filename: str) -> None:
        value = str(filename or "")
        if not _SAFE_FILENAME.fullmatch(value) or Path(value).name != value:
            raise AIRasterError(
                "LOCAL_RASTER_INVALID",
                "Nom de fichier invalide; un nom simple termine par .tif ou .tiff est requis.",
            )

    @staticmethod
    def _validate_raster_id(raster_id: str) -> None:
        if not _SAFE_RASTER_ID.fullmatch(str(raster_id or "")):
            raise ValueError("Identifiant de raster IA invalide.")

    def _upload_part_path(self, upload_id: str) -> Path:
        self._validate_upload_id(upload_id)
        return self.cache_dir / f".maxar-upload-{upload_id}.tif.part"

    def _upload_state_path(self, upload_id: str) -> Path:
        self._validate_upload_id(upload_id)
        return self.cache_dir / f".maxar-upload-{upload_id}.json"

    @staticmethod
    def _validate_upload_id(upload_id: str) -> None:
        if not _SAFE_UPLOAD_ID.fullmatch(str(upload_id or "")):
            raise AIRasterError("UPLOAD_INVALID", "Identifiant d’upload Maxar invalide.")
