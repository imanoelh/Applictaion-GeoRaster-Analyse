from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BuildingModelConfig:
    checkpoint_path: Path | None
    model_name: str = "building-segmentation"
    model_version: str = "v1"
    model_architecture: str = "torchscript"
    checkpoint_format: str = "torchscript"
    checkpoint_sha256: str | None = None
    checkpoint_source: str | None = None
    weights_license: str | None = None
    training_dataset: str | None = None
    runtime: str = "pytorch"
    allow_cuda: bool = False
    probability_threshold: float = 0.50
    input_size: int = 640
    model_input_size: int | None = None
    model_normalization: str = "none"
    output_kind: str = "logits"
    building_class_index: int = 0
    test_only: bool = False
    enforce_provenance: bool = False

    @property
    def effective_model_input_size(self) -> int:
        return int(self.model_input_size or self.input_size)

    @classmethod
    def from_env(cls) -> "BuildingModelConfig":
        configured_path = os.getenv("AI_BUILDING_MODEL_PATH", "").strip()
        backend_dir = Path(__file__).resolve().parents[3]
        default_path = backend_dir / "data" / "models" / "building" / "kastela-dof5" / "unet_best.pt"
        use_verified_default = not configured_path and default_path.is_file()
        selected_path = Path(configured_path) if configured_path else (default_path if use_verified_default else None)
        threshold = float(os.getenv("AI_BUILDING_PROBABILITY_THRESHOLD", "0.50"))
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("AI_BUILDING_PROBABILITY_THRESHOLD doit etre compris entre 0 et 1.")
        output_kind = os.getenv("AI_BUILDING_OUTPUT_KIND", "logits").strip().lower()
        if output_kind not in {"logits", "probabilities"}:
            raise ValueError("AI_BUILDING_OUTPUT_KIND doit etre logits ou probabilities.")
        checkpoint_format = os.getenv(
            "AI_BUILDING_CHECKPOINT_FORMAT",
            "state_dict" if use_verified_default else "torchscript",
        ).strip().lower()
        if checkpoint_format not in {"torchscript", "state_dict"}:
            raise ValueError("AI_BUILDING_CHECKPOINT_FORMAT doit etre torchscript ou state_dict.")
        model_input_size = int(os.getenv("AI_BUILDING_MODEL_INPUT_SIZE", "512" if use_verified_default else "640"))
        if model_input_size <= 0:
            raise ValueError("AI_BUILDING_MODEL_INPUT_SIZE doit etre strictement positif.")
        return cls(
            checkpoint_path=selected_path,
            model_name=os.getenv(
                "AI_BUILDING_MODEL_NAME",
                "kastela-dof5-unet-resnet34" if use_verified_default else "building-segmentation",
            ).strip(),
            model_version=os.getenv(
                "AI_BUILDING_MODEL_VERSION",
                "sha256-6cd2467e0636" if use_verified_default else "v1",
            ).strip(),
            model_architecture=os.getenv(
                "AI_BUILDING_MODEL_ARCH",
                "unet_resnet34" if use_verified_default else "torchscript",
            ).strip().lower(),
            checkpoint_format=checkpoint_format,
            checkpoint_sha256=os.getenv(
                "AI_BUILDING_CHECKPOINT_SHA256",
                "6cd2467e063696e9d41d409bda7751a9ccdb057d5adba251ab5a765d8d415987"
                if use_verified_default
                else "",
            ).strip().lower() or None,
            checkpoint_source=os.getenv(
                "AI_BUILDING_CHECKPOINT_SOURCE",
                "https://huggingface.co/dnovak232/kastela-dof5-building-segmentation"
                if use_verified_default
                else "",
            ).strip() or None,
            weights_license=os.getenv(
                "AI_BUILDING_WEIGHTS_LICENSE",
                "CC-BY-4.0" if use_verified_default else "",
            ).strip() or None,
            training_dataset=os.getenv(
                "AI_BUILDING_TRAINING_DATASET",
                "DGU DOF5 2023 orthophoto + DGU cadastral building polygons"
                if use_verified_default
                else "",
            ).strip() or None,
            allow_cuda=_env_bool("AI_ALLOW_CUDA", False),
            probability_threshold=threshold,
            model_input_size=model_input_size,
            model_normalization=os.getenv(
                "AI_BUILDING_MODEL_NORMALIZATION",
                "per_channel_zscore" if use_verified_default else "none",
            ).strip().lower(),
            output_kind=output_kind,
            building_class_index=int(os.getenv("AI_BUILDING_CLASS_INDEX", "0")),
            enforce_provenance=(
                selected_path is not None
                or _env_bool("AI_BUILDING_ENFORCE_PROVENANCE", False)
            ),
        )

