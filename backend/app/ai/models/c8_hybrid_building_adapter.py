from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from ..config.building_model_catalog import model_identity
from .spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter


class C8HybridBuildingAdapter(SpaceNet2DeepLabAdapter):
    """MODEL_C8 adapter using the validated C8 PyTorch weights.

    C8 deliberately reuses the strict torchvision DeepLabV3 loader and the
    MODEL_C global RGB min-max preparation.
    """

    MODEL_ID = "model_c8_hybrid"
    CHECKPOINT_SHA256 = "32f48ba94385206ed3e1cc8a156b73ac33810525f05a6bb3fd51b16c486a7576"
    MODEL_VERSION = "MODEL_C8_HYBRID_epoch2"
    MODEL_ARCHITECTURE = "torchvision_deeplabv3_resnet50"
    preferred_tile_size = 512
    preferred_batch_size = 1
    preferred_overlap_ratio = 0.0
    torch_threads_env = "C8_TORCH_THREADS"
    default_torch_threads = 2

    def __init__(self, checkpoint_path: Path) -> None:
        # C8 is a PyTorch checkpoint even when the production MODEL_C runtime
        # is configured for ONNX. Keep the two engine choices isolated.
        super().__init__(checkpoint_path, expected_sha256=self.CHECKPOINT_SHA256, engine="pytorch")
        self.application_config_path = checkpoint_path.parents[2] / "14A15_application_precision_refinement" / "14A15_C8_REFINED_CONFIG.json"

    def get_application_config(self) -> dict[str, Any]:
        """Return the frozen application refinement, or safe C8 baseline."""
        baseline = {
            "enabled": False,
            "threshold": 0.50,
            "min_component": 32,
            "connectivity": 4,
            "morphology": "NONE",
        }
        try:
            config = json.loads(self.application_config_path.read_text(encoding="utf-8"))
            if (
                str(config.get("model", "")).lower() == self.MODEL_ID
                and config.get("checkpoint_sha256", "").lower() == self.CHECKPOINT_SHA256
                and bool(config.get("enabled"))
                and 0.0 < float(config["threshold"]) <= 1.0
                and int(config["min_component"]) > 0
            ):
                return {
                    "enabled": True,
                    "threshold": float(config["threshold"]),
                    "min_component": int(config["min_component"]),
                    "connectivity": 4,
                    "morphology": "NONE",
                }
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            pass
        return baseline

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_id": self.MODEL_ID,
            "model_name": "MODEL_C8 Hybrid Building Detection",
            "model_version": self.MODEL_VERSION,
            "model_architecture": self._architecture or self.MODEL_ARCHITECTURE,
            "checkpoint_sha256": self.CHECKPOINT_SHA256,
            "checkpoint_id": f"sha256:{self.CHECKPOINT_SHA256[:12]}",
            "checkpoint_format": "state_dict",
            "preferred_tile_size": 512,
            "input_size": 512,
            "model_input_size": 512,
            "input_layout": "NCHW",
            "input_channels": 3,
            "runtime": "pytorch",
            "device": self._device,
            "inference_threads": self._inference_threads,
            "loaded": self.is_loaded(),
            "model_mode": "EXPERIMENTAL",
            "preprocessing_profile": "c8_rgb_global_patch_minmax_v1",
            "training_normalization": "global_patch_rgb_minmax_to_0_1",
            "model_normalization": "global_patch_rgb_minmax_to_0_1",
            "source_normalization": "float32_0_1",
            "output_kind": "logits_sigmoid",
            "threshold_status": "FIXED_0_50",
            "weights_license": "Internal GeoRaster experimental weights",
            "experimental_only": True,
            "encoder": self._encoder_name or "resnet50",
            "output_channels": self._output_channels or 1,
            "aux_output_channels": self._aux_output_channels or 21,
            "preprocessing_status": "CONFIRMED_RGB_GLOBAL_MINMAX_NATIVE_512",
            "min_component_pixels": 32,
            "morphology": "NONE",
            "connectivity": 4,
            **model_identity(self.MODEL_ID, "pytorch"),
        }

