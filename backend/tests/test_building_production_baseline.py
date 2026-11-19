from __future__ import annotations

import pytest

from app.ai.config.building_model_catalog import building_model_metadata
from app.ai.models.base_model_adapter import AIModelError
from app.ai.registry.model_registry import create_default_model_registry


def test_catalog_describes_all_five_engines_without_loading_them() -> None:
    registry = create_default_model_registry()
    try:
        models = registry.list_models("building")
        assert {m["role"]: m["status"] for m in models} == {
            "MODEL_A": "LEGACY", "MODEL_C": "PRODUCTION", "MODEL_D": "EXPERIMENTAL",
            "MODEL_D_ONNX": "EXPERIMENTAL", "MODEL_E": "BENCHMARK_ONLY",
        }
        assert [m["id"] for m in models if m["default"]] == ["spacenet2_deeplab"]
        for model in models:
            assert all(key in model for key in (
                "model_id", "display_name", "architecture", "engine", "status",
                "model_sources", "input_size", "threshold", "preprocessing", "availability",
            ))
        assert registry._named_instances == {}
    finally:
        registry.close_all()


@pytest.mark.parametrize("model_id", ["whu_unetplusplus_effb4", "whu_unetplusplus_effb4_onnx", "hybrid_model_c_model_d"])
def test_rd_engine_cannot_be_promoted_by_default_selection(model_id: str) -> None:
    registry = create_default_model_registry()
    try:
        with pytest.raises(AIModelError) as exc:
            registry.set_default_model("building", model_id)
        assert exc.value.code == "MODEL_DEFAULT_FORBIDDEN"
        assert registry.get_selected_model("building").get_model_info()["model_id"] == "spacenet2_deeplab"
    finally:
        registry.close_all()


def test_unavailable_experimental_engine_is_isolated_and_has_no_fallback(tmp_path) -> None:
    registry = create_default_model_registry()
    try:
        default = registry.get_selected_model("building")
        experimental = registry.get_selected_model("building", "whu_unetplusplus_effb4_onnx")
        experimental.onnx_path = tmp_path / "missing.onnx"
        with pytest.raises(AIModelError) as exc:
            experimental.load()
        assert exc.value.code == "MODEL_FILE_NOT_FOUND"
        assert registry.get_selected_model("building") is default
        assert not default.is_loaded()
        assert registry.get_selected_model("building", "whu_unetplusplus_effb4_onnx") is experimental
        assert building_model_metadata("whu_unetplusplus_effb4_onnx", tmp_path)["availability"] == "UNAVAILABLE"
    finally:
        registry.close_all()


def test_missing_production_engine_never_falls_back_to_rd(tmp_path) -> None:
    registry = create_default_model_registry()
    try:
        default = registry.get_selected_model("building")
        default.checkpoint_path = tmp_path / "missing.pth"
        with pytest.raises(AIModelError) as exc:
            default.load()
        assert exc.value.code == "MODEL_FILE_NOT_FOUND"
        assert registry.get_selected_model("building") is default
        assert set(registry._named_instances) == {("building", "spacenet2_deeplab")}
    finally:
        registry.close_all()
