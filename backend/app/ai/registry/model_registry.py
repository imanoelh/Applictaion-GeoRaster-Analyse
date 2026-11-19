from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config.building_model_catalog import DEFAULT_BUILDING_MODEL_ID, building_model_metadata
from ..models.base_model_adapter import AIModelError, BaseModelAdapter
from ..models.building_model_adapter import BuildingModelAdapter
from ..models.hybrid_building_adapter import HybridBuildingModelAdapter
from ..models.c8_hybrid_building_adapter import C8HybridBuildingAdapter
from ..models.spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter
from ..models.whu_building_adapter import WHUBuildingModelAdapter
from ..models.whu_onnx_building_adapter import WHUOnnxBuildingModelAdapter


ModelFactory = Callable[[], BaseModelAdapter]


class ModelRegistry:
    """Create one adapter instance per registered object type, on demand."""

    def __init__(self) -> None:
        self._factories: dict[str, ModelFactory] = {}
        self._instances: dict[str, BaseModelAdapter] = {}
        self._named_factories: dict[tuple[str, str], ModelFactory] = {}
        self._named_instances: dict[tuple[str, str], BaseModelAdapter] = {}
        self._model_metadata: dict[tuple[str, str], dict[str, Any]] = {}
        self._default_model_ids: dict[str, str] = {}
        self._lock = threading.RLock()

    def register(self, object_type: str, factory: ModelFactory, *, replace: bool = False) -> None:
        key = str(object_type).strip().lower()
        if not key:
            raise ValueError("object_type ne peut pas etre vide.")
        with self._lock:
            if key in self._factories and not replace:
                raise ValueError(f"Un modele est deja enregistre pour {key}.")
            previous = self._instances.pop(key, None)
            if previous is not None:
                previous.close()
            self._factories[key] = factory

    def get_model(self, object_type: str) -> BaseModelAdapter:
        key = str(object_type).strip().lower()
        with self._lock:
            if key not in self._factories:
                raise AIModelError(
                    "MODEL_NOT_CONFIGURED",
                    f"Aucun adaptateur n'est enregistre pour le type {key or 'inconnu'}.",
                )
            if key not in self._instances:
                self._instances[key] = self._factories[key]()
            return self._instances[key]

    def register_model(
        self,
        object_type: str,
        model_id: str,
        factory: ModelFactory,
        *,
        metadata: dict[str, Any],
    ) -> None:
        object_key = str(object_type).strip().lower()
        model_key = str(model_id).strip().lower()
        if not object_key or not model_key:
            raise ValueError("object_type et model_id doivent etre renseignes.")
        if metadata.get("id") != model_key:
            raise ValueError("Les metadata du modele doivent contenir le meme id.")
        with self._lock:
            key = (object_key, model_key)
            if key in self._named_factories:
                raise ValueError(f"Un modele {model_key} est deja enregistre.")
            self._named_factories[key] = factory
            self._model_metadata[key] = dict(metadata)

    def set_default_model(self, object_type: str, model_id: str) -> None:
        object_key = str(object_type).strip().lower()
        model_key = str(model_id).strip().lower()
        with self._lock:
            key = (object_key, model_key)
            if key not in self._named_factories:
                raise AIModelError("MODEL_NOT_FOUND", f"Le modele par defaut {model_key} n'est pas enregistre.")
            status = self._model_metadata[key].get("status")
            if object_key == "building" and status in {"LEGACY", "EXPERIMENTAL", "BENCHMARK_ONLY"}:
                raise AIModelError("MODEL_DEFAULT_FORBIDDEN", "Ce moteur ne peut pas devenir le modele Building standard.")
            self._default_model_ids[object_key] = model_key
            for (kind, candidate_id), metadata in self._model_metadata.items():
                if kind == object_key:
                    metadata["default"] = candidate_id == model_key

    def get_selected_model(self, object_type: str, model_id: str | None = None) -> BaseModelAdapter:
        """Resolve an explicit model, or the configured object default when omitted."""
        object_key = str(object_type).strip().lower()
        if model_id is None or not str(model_id).strip():
            default_model_id = self._default_model_ids.get(object_key)
            if default_model_id is not None:
                return self.get_selected_model(object_key, default_model_id)
            return self.get_model(object_key)
        model_key = str(model_id).strip().lower()
        if object_key == "building" and model_key == "unet_resnet34":
            return self.get_model(object_key)
        with self._lock:
            named_key = (object_key, model_key)
            if named_key not in self._named_factories:
                raise AIModelError("MODEL_NOT_FOUND", f"Le modele {model_key} n'est pas disponible pour {object_key}.")
            if named_key not in self._named_instances:
                self._named_instances[named_key] = self._named_factories[named_key]()
            return self._named_instances[named_key]

    def list_models(self, object_type: str) -> list[dict[str, Any]]:
        object_key = str(object_type).strip().lower()
        with self._lock:
            values = [dict(value) for (kind, _model_id), value in self._model_metadata.items() if kind == object_key]
            if object_key == "building" and object_key in self._factories:
                values.insert(0, building_model_metadata("unet_resnet34"))
            return values

    def reload(self, object_type: str) -> BaseModelAdapter:
        key = str(object_type).strip().lower()
        with self._lock:
            if key not in self._factories:
                raise AIModelError("MODEL_NOT_CONFIGURED", "Modele non enregistre.")
            current = self._instances.pop(key, None)
            if current is not None:
                current.close()
            replacement = self._factories[key]()
            self._instances[key] = replacement
            return replacement

    def close_all(self) -> None:
        with self._lock:
            for model in self._instances.values():
                model.close()
            for model in self._named_instances.values():
                model.close()
            self._instances.clear()
            self._named_instances.clear()


def create_default_model_registry() -> ModelRegistry:
    registry = ModelRegistry()
    registry.register("building", BuildingModelAdapter)
    backend_dir = Path(__file__).resolve().parents[3]
    checkpoint = backend_dir / "data" / "models" / "building" / "experimental" / "spacenet2-deeplab" / "best_deeplab.pth"
    registry.register_model(
        "building",
        "spacenet2_deeplab",
        lambda: SpaceNet2DeepLabAdapter(
            checkpoint,
            expected_sha256="170c49e1f42737f5a4b3922b9fc58b25b6ba0a7dd7bf00b9186a92ccb84dc555",
        ),
        metadata=building_model_metadata("spacenet2_deeplab"),
    )
    whu_checkpoint = backend_dir / "data" / "models" / "building" / "experimental" / "whu_unetplusplus_effb4" / "model.pth"
    registry.register_model(
        "building",
        "whu_unetplusplus_effb4",
        lambda: WHUBuildingModelAdapter(whu_checkpoint),
        metadata=building_model_metadata("whu_unetplusplus_effb4"),
    )
    whu_onnx = backend_dir / "data" / "models" / "building" / "experimental" / "whu_unetplusplus_effb4" / "onnx" / "model.onnx"
    registry.register_model(
        "building",
        WHUOnnxBuildingModelAdapter.MODEL_ID,
        lambda: WHUOnnxBuildingModelAdapter(whu_onnx, whu_checkpoint),
        metadata=building_model_metadata("whu_unetplusplus_effb4_onnx"),
    )
    registry.register_model(
        "building",
        HybridBuildingModelAdapter.MODEL_ID,
        lambda: HybridBuildingModelAdapter(
            registry.get_selected_model("building", "spacenet2_deeplab"),
            registry.get_selected_model("building", "whu_unetplusplus_effb4"),
        ),
        metadata=building_model_metadata("hybrid_model_c_model_d"),
    )
    c8_checkpoint = backend_dir / "data" / "fine_tuning" / "buildings" / "maxar_v2_high_precision" / "14A11_hybrid_pipeline" / "models" / "MODEL_C8_HYBRID_epoch2.pth"
    registry.register_model(
        "building",
        C8HybridBuildingAdapter.MODEL_ID,
        lambda: C8HybridBuildingAdapter(c8_checkpoint),
        metadata=building_model_metadata(C8HybridBuildingAdapter.MODEL_ID),
    )
    registry.set_default_model("building", DEFAULT_BUILDING_MODEL_ID)
    return registry

