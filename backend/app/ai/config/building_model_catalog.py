"""Building engine lifecycle policy. No model is loaded by this catalogue."""
from __future__ import annotations

import importlib.util
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_BUILDING_MODEL_ID = "model_c8_hybrid"
_MODEL_DIR = "data/models/building/"
_C_DIR = _MODEL_DIR + "experimental/spacenet2-deeplab/"
_D_DIR = _MODEL_DIR + "experimental/whu_unetplusplus_effb4/"
_C8_DIR = "data/fine_tuning/buildings/maxar_v2_high_precision/14A11_hybrid_pipeline/models/"

BUILDING_MODEL_CATALOG = {
    "unet_resnet34": {
        "role": "MODEL_A", "display_name": "Legacy Building Detection",
        "architecture": "U-Net / ResNet-34", "status": "LEGACY",
        "engine": "PYTORCH_CPU", "input_size": 640, "threshold": 0.5,
        "preprocessing": "production_rgb_zscore_v1",
        "model_sources": [_MODEL_DIR + "kastela-dof5/unet_best.pt"],
        "dependencies": ["torch", "segmentation_models_pytorch"],
        "recommended_usage": "Legacy reference; explicit API selection only.",
    },
    "spacenet2_deeplab": {
        "role": "MODEL_C", "display_name": "Standard Building Detection",
        "architecture": "DeepLabV3 / ResNet-50", "status": "PRODUCTION",
        "engine": "ONNX_RUNTIME_CPU", "input_size": 512, "threshold": 0.5,
        "preprocessing": "full_raster_global_rgb_minmax_v1",
        "model_sources": [_C_DIR + "best_deeplab.pth", _C_DIR + "onnx/spacenet2_deeplab_main.onnx"],
        "dependencies": ["onnxruntime"],
        "recommended_usage": "Standard production engine; footprint accuracy is not a scientific guarantee.",
    },
    "whu_unetplusplus_effb4": {
        "role": "MODEL_D", "display_name": "Experimental WHU Reference (PyTorch)",
        "architecture": "WHU U-Net++ / EfficientNet-B4", "status": "EXPERIMENTAL",
        "engine": "PYTORCH_CPU", "input_size": 512, "threshold": 0.5,
        "preprocessing": "rgb_orthophoto_uint8_v1",
        "model_sources": [_D_DIR + "model.pth"],
        "dependencies": ["torch", "segmentation_models_pytorch"],
        "recommended_usage": "Reference, debugging and ONNX equivalence checks; explicit API selection only.",
    },
    "whu_unetplusplus_effb4_onnx": {
        "role": "MODEL_D_ONNX", "display_name": "Experimental High-Recall Detection",
        "architecture": "WHU U-Net++ / EfficientNet-B4", "status": "EXPERIMENTAL",
        "engine": "ONNX_RUNTIME_CPU", "input_size": 512, "threshold": 0.5,
        "preprocessing": "rgb_orthophoto_uint8_v1",
        "model_sources": [_D_DIR + "model.pth", _D_DIR + "onnx/model.onnx"],
        "dependencies": ["onnxruntime"],
        "recommended_usage": "Experimental CPU engine; high-recall is a role label, not a scientific accuracy claim.",
    },
    "hybrid_model_c_model_d": {
        "role": "MODEL_E", "display_name": "Benchmark C + D Binary Union",
        "architecture": "DeepLabV3 ResNet-50 + WHU U-Net++ EfficientNet-B4",
        "status": "BENCHMARK_ONLY", "engine": "COMPOSITE", "input_size": 512,
        "threshold": 0.5, "preprocessing": "component_specific:C_full_raster_minmax;D_rgb_0_1",
        "model_sources": [_C_DIR + "best_deeplab.pth", _C_DIR + "onnx/spacenet2_deeplab_main.onnx", _D_DIR + "model.pth"],
        "dependencies": ["onnxruntime", "torch", "segmentation_models_pytorch"],
        "recommended_usage": "Benchmark/R&D only; both passes must be explicitly requested.",
    },
    "model_c8_hybrid": {
        "role": "MODEL_C8", "display_name": "Building AI v2 (MODEL_C8 Hybrid)",
        "architecture": "DeepLabV3 / ResNet-50 (C8 fine-tuned)", "status": "PRODUCTION",
        "engine": "PYTORCH_CPU", "input_size": 512, "threshold": 0.5,
        "preprocessing": "c8_rgb_global_patch_minmax_v1",
        "model_sources": [_C8_DIR + "MODEL_C8_HYBRID_epoch2.pth"],
        "dependencies": ["torch", "torchvision"],
        "recommended_usage": "Stable Building V2 CPU engine; MODEL_C remains available as fallback.",
    },
}


def model_identity(model_id: str, runtime: str | None = None) -> dict[str, Any]:
    """Canonical public identity, with the actual runtime when supplied."""
    entry = BUILDING_MODEL_CATALOG.get(model_id)
    if entry is None:
        return {}
    engine = entry["engine"]
    if runtime:
        engine = {"onnxruntime": "ONNX_RUNTIME_CPU", "pytorch": "PYTORCH_CPU", "composite": "COMPOSITE"}.get(runtime, runtime)
    return {"display_name": entry["display_name"], "status": entry["status"], "engine": engine}


def building_model_metadata(model_id: str, backend_dir: Path | None = None) -> dict[str, Any]:
    entry = deepcopy(BUILDING_MODEL_CATALOG[model_id])
    backend_dir = backend_dir or Path(__file__).resolve().parents[3]
    # Keep supported diagnostic overrides visible without changing inference.
    c_engine = os.getenv("SPACENET2_ENGINE", "onnxruntime").strip().lower()
    if model_id == DEFAULT_BUILDING_MODEL_ID and c_engine == "pytorch":
        entry.update(engine="PYTORCH_CPU", dependencies=["torch", "torchvision"])
        entry["model_sources"] = entry["model_sources"][:1]
    if model_id == "hybrid_model_c_model_d" and c_engine == "pytorch":
        entry["dependencies"] = ["torch", "torchvision", "segmentation_models_pytorch"]
        entry["model_sources"].remove(_C_DIR + "onnx/spacenet2_deeplab_main.onnx")
    if model_id == "unet_resnet34":
        from .ai_model_config import BuildingModelConfig
        config = BuildingModelConfig.from_env()
        path = config.checkpoint_path
        entry.update(input_size=config.input_size, model_input_size=config.effective_model_input_size,
                     threshold=config.probability_threshold, preprocessing=config.model_normalization)
        entry["model_sources"] = [str(path)] if path else []
    missing_files = [path for path in entry["model_sources"] if not (backend_dir / path).is_file()]
    missing_dependencies = [name for name in entry.pop("dependencies") if importlib.util.find_spec(name) is None]
    available = bool(entry["model_sources"]) and not missing_files and not missing_dependencies
    # Public descriptions identify artifacts without disclosing external paths.
    def public_source(value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            return path.as_posix()
        try:
            return path.relative_to(backend_dir).as_posix()
        except ValueError:
            return path.name
    entry["model_sources"] = [public_source(value) for value in entry["model_sources"]]
    return {
        **entry, "id": model_id, "model_id": model_id, "name": entry["display_name"],
        "default": model_id == DEFAULT_BUILDING_MODEL_ID,
        "availability": "AVAILABLE" if available else "UNAVAILABLE",
        "available": available,
        "availability_checks": "Files and installed modules only; strict load validates checksums and runtime.",
        "missing_sources": [public_source(value) for value in missing_files], "missing_dependencies": missing_dependencies,
    }
