from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..schemas.export_schemas import BuildingExportFormat
from ..schemas.results_schemas import BuildingAnalysisResult


@dataclass(frozen=True)
class BuildingExportArtifact:
    filename: str
    media_type: str
    content: bytes


class BuildingExportService:
    """Serialize an already-built AI result without rerunning inference."""

    _FEATURE_PROPERTIES = (
        "object_id",
        "object_type",
        "area_m2",
        "perimeter_m",
        "pixel_count",
        "centroid_lon",
        "centroid_lat",
        "model_name",
        "model_id",
        "model_architecture",
        "preprocessing_profile",
        "tile_size",
        "model_version",
        "threshold",
        "model_status",
        "component_models",
        "fusion_method",
    )
    _FORBIDDEN_CONFIG_TOKENS = (
        "path",
        "checkpoint",
        "credential",
        "password",
        "secret",
        "token",
        "api_key",
    )

    def export(
        self,
        result: BuildingAnalysisResult,
        export_format: BuildingExportFormat,
    ) -> BuildingExportArtifact:
        token = self._analysis_token(result.analysis_id)
        if export_format == "geojson":
            return BuildingExportArtifact(
                filename=f"georaster_ai_building_candidates_{token}.geojson",
                media_type="application/geo+json; charset=utf-8",
                content=self.geojson_bytes(result),
            )
        if export_format == "csv":
            return BuildingExportArtifact(
                filename=f"georaster_ai_building_statistics_{token}.csv",
                media_type="text/csv; charset=utf-8",
                content=self.csv_bytes(result),
            )
        if export_format == "metadata":
            return BuildingExportArtifact(
                filename=f"georaster_ai_building_metadata_{token}.json",
                media_type="application/json; charset=utf-8",
                content=self.metadata_bytes(result),
            )
        return BuildingExportArtifact(
            filename=f"georaster_ai_building_candidates_{token}.zip",
            media_type="application/zip",
            content=self.zip_bytes(result),
        )

    def geojson_bytes(self, result: BuildingAnalysisResult) -> bytes:
        features = []
        for feature in result.feature_collection.features:
            properties = {
                key: feature.properties.get(key)
                for key in self._FEATURE_PROPERTIES
            }
            properties["scientific_accuracy_status"] = result.scientific_accuracy_status
            features.append(
                {
                    "type": "Feature",
                    "id": feature.id,
                    "geometry": feature.geometry,
                    "properties": properties,
                }
            )
        payload = {
            "type": "FeatureCollection",
            "features": features,
        }
        return self._strict_json_bytes(payload)

    def csv_bytes(self, result: BuildingAnalysisResult) -> bytes:
        fields = (
            "analysis_id",
            "candidate_count",
            "total_area_m2",
            "mean_area_m2",
            "median_area_m2",
            "min_area_m2",
            "max_area_m2",
            "total_perimeter_m",
            "mean_perimeter_m",
            "model_name",
            "model_id",
            "model_architecture",
            "model_checkpoint_hash",
            "preprocessing_profile",
            "tile_size",
            "model_version",
            "threshold",
            "quality_mode",
            "scientific_accuracy_status",
            "model_status",
            "fusion_method",
        )
        stats = result.statistics
        row = {
            "analysis_id": result.analysis_id,
            "candidate_count": result.candidate_count,
            "total_area_m2": stats.total_area_m2,
            "mean_area_m2": stats.mean_area_m2,
            "median_area_m2": stats.median_area_m2,
            "min_area_m2": stats.min_area_m2,
            "max_area_m2": stats.max_area_m2,
            "total_perimeter_m": stats.total_perimeter_m,
            "mean_perimeter_m": stats.mean_perimeter_m,
            "model_name": result.model_name,
            "model_id": result.model_id,
            "model_architecture": result.model_architecture,
            "model_checkpoint_hash": result.model_checkpoint_hash,
            "preprocessing_profile": result.preprocessing_profile,
            "tile_size": result.tile_size,
            "model_version": result.model_version,
            "threshold": result.probability_threshold,
            "quality_mode": result.quality_mode,
            "scientific_accuracy_status": result.scientific_accuracy_status,
            "model_status": result.model_metadata.get("status", result.model_mode) if result.model_metadata else result.model_mode,
            "fusion_method": result.model_metadata.get("fusion_method") if result.model_metadata else None,
        }
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerow({key: "" if value is None else value for key, value in row.items()})
        return ("\ufeff" + stream.getvalue()).encode("utf-8")

    def metadata_bytes(self, result: BuildingAnalysisResult) -> bytes:
        metadata = {
            "analysis_id": result.analysis_id,
            "analysis_type": result.analysis_type,
            "object_type": result.object_type,
            "source_type": result.source_type,
            "source_resolution": result.source_resolution,
            "source_crs": result.source_crs,
            "model_name": result.model_name,
            "model_id": result.model_id,
            "model_architecture": result.model_architecture,
            "model_checkpoint_hash": result.model_checkpoint_hash,
            "preprocessing_profile": result.preprocessing_profile,
            "tile_size": result.tile_size,
            "model_version": result.model_version,
            "model_mode": result.model_mode,
            "display_name": result.model_metadata.get("display_name", result.model_name),
            "engine": result.model_metadata.get("engine"),
            "status": result.model_metadata.get("status"),
            "processing_time": result.model_metadata.get("processing_time"),
            "threshold": result.probability_threshold,
            "postprocessing_config": self._safe_config(
                result.processing_metadata.postprocessing_config
            ),
            "polygonization_config": self._safe_config(
                result.processing_metadata.polygonization_config
            ),
            "result_schema_version": result.result_schema_version,
            "quality_mode": result.quality_mode,
            "scientific_accuracy_status": result.scientific_accuracy_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_metadata": result.model_metadata,
            "processing_time_c": result.model_metadata.get("processing_time_c") if result.model_metadata else None,
            "processing_time_d": result.model_metadata.get("processing_time_d") if result.model_metadata else None,
            "fusion_time": result.model_metadata.get("fusion_time") if result.model_metadata else None,
            "polygonization_time": result.processing_metadata.polygonization_time_ms / 1000.0,
            "total_processing_time": (
                result.processing_metadata.total_processing_time_ms / 1000.0
                if result.processing_metadata.total_processing_time_ms is not None else None
            ),
        }
        return self._strict_json_bytes(metadata)

    def zip_bytes(self, result: BuildingAnalysisResult) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("building_candidates.geojson", self.geojson_bytes(result))
            archive.writestr("building_statistics.csv", self.csv_bytes(result))
            archive.writestr("building_metadata.json", self.metadata_bytes(result))
        return stream.getvalue()

    @classmethod
    def _safe_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        def clean(item: Any) -> Any:
            if isinstance(item, dict):
                return {
                    str(key): clean(child)
                    for key, child in item.items()
                    if not any(token in str(key).lower() for token in cls._FORBIDDEN_CONFIG_TOKENS)
                }
            if isinstance(item, (list, tuple)):
                return [clean(child) for child in item]
            if isinstance(item, str):
                if re.match(r"^[A-Za-z]:[\\/]", item) or item.startswith(("/", "\\\\")):
                    return None
                return item
            if isinstance(item, (int, float, bool)) or item is None:
                return item
            return str(item)

        return clean(value)

    @staticmethod
    def _analysis_token(analysis_id: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", analysis_id)

    @staticmethod
    def _strict_json_bytes(value: Any) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
