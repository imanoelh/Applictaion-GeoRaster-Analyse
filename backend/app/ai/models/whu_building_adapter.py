from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..config.building_model_catalog import model_identity
from ..services.tiling_service import PreparedTile
from .base_model_adapter import AIModelError, BaseModelAdapter, ModelOutput


logger = logging.getLogger(__name__)


class WHUBuildingModelAdapter(BaseModelAdapter):
    """Experimental adapter for the official WHU U-Net++ EfficientNet-B4 weights."""

    preferred_tile_size = 512
    preferred_overlap_ratio = 0.5
    preferred_batch_size = 1

    MODEL_ID = "whu_unetplusplus_effb4"
    MODEL_NAME = "WHU U-Net++ EfficientNet-B4"
    MODEL_VERSION = "whu-building-unetplusplus-efficientnet-b4"
    MODEL_ARCHITECTURE = "U-Net++ EfficientNet-B4"
    MODEL_SOURCE = "https://huggingface.co/giswqs/whu-building-unetplusplus-efficientnet-b4"
    MODEL_LICENSE = "Apache-2.0"
    EXPECTED_SHA256 = "922af7c96c0dc44256ab8b4d1a071f2151e0a921c997af80b55bb766bcc30dc6"

    def __init__(self, checkpoint_path: Path | None = None) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else (
            backend_dir / "data/models/building/experimental/whu_unetplusplus_effb4/model.pth"
        )
        self._model: Any | None = None
        self._torch: Any | None = None
        self._device = "cpu"
        self._load_time_ms = 0.0
        self._load_count = 0
        self._lock = threading.Lock()

    def load(self) -> None:
        if self.is_loaded():
            return
        with self._lock:
            if self.is_loaded():
                return
            if not self.checkpoint_path.is_file():
                raise AIModelError("MODEL_FILE_NOT_FOUND", "The experimental WHU checkpoint is missing.")
            self._validate_checksum()
            try:
                import torch
                import segmentation_models_pytorch as smp
            except Exception as exc:
                raise AIModelError("MODEL_LOAD_FAILED", "PyTorch/SMP sont requis pour WHU.", technical_detail=str(exc)) from exc

            started = time.perf_counter()
            try:
                model = smp.UnetPlusPlus(
                    encoder_name="efficientnet-b4",
                    encoder_weights=None,
                    in_channels=3,
                    classes=2,
                ).to(self._device)
                state_dict = torch.load(self.checkpoint_path, map_location=self._device, weights_only=True)
                if not isinstance(state_dict, dict) or not state_dict:
                    raise TypeError("WHU checkpoint must contain a non-empty state_dict.")
                model.load_state_dict(state_dict, strict=True)
                model.eval()
                self._model = model
                self._torch = torch
                self._load_count += 1
                self._load_time_ms = (time.perf_counter() - started) * 1000.0
                logger.info("[AI-MODEL] experimental WHU model loaded on %s", self._device)
            except Exception as exc:
                self._model = None
                self._torch = None
                logger.exception("[AI-MODEL] WHU strict load failed")
                raise AIModelError(
                    "MODEL_LOAD_FAILED",
                    "The experimental WHU checkpoint is invalid or incompatible.",
                    technical_detail=str(exc),
                ) from exc

    def is_loaded(self) -> bool:
        return self._model is not None

    def predict(self, tile: PreparedTile) -> ModelOutput:
        self._validate_tile(tile)
        if not self.is_loaded():
            self.load()
        tensor = self._torch.from_numpy(np.ascontiguousarray(tile.image)).unsqueeze(0).to(
            device=self._device, dtype=self._torch.float32
        )
        started = time.perf_counter()
        try:
            with self._torch.inference_mode():
                logits = self._model(tensor)
                if not hasattr(logits, "shape") or tuple(logits.shape) != (1, 2, 512, 512):
                    raise ValueError(f"Expected logits [1,2,512,512], got {getattr(logits, 'shape', None)}")
                probability = self._torch.softmax(logits, dim=1)[0, 1].cpu().numpy().astype(np.float32, copy=False)
            probability = np.ascontiguousarray(probability)
            probability[~tile.valid_mask] = np.float32(0.0)
            return ModelOutput(probability, (time.perf_counter() - started) * 1000.0)
        except AIModelError:
            raise
        except Exception as exc:
            logger.exception("[AI-INFERENCE] WHU inference failed tile=%s", tile.metadata.tile_id)
            raise AIModelError(
                "INFERENCE_FAILED",
                "Experimental WHU inference failed.",
                technical_detail=str(exc),
            ) from exc

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_id": self.MODEL_ID,
            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "model_architecture": self.MODEL_ARCHITECTURE,
            "checkpoint_sha256": self.EXPECTED_SHA256,
            "checkpoint_id": f"sha256:{self.EXPECTED_SHA256[:12]}",
            "checkpoint_format": "state_dict",
            "checkpoint_source": self.MODEL_SOURCE,
            "weights_license": self.MODEL_LICENSE,
            "training_dataset": "WHU Building Dataset",
            "preferred_tile_size": self.preferred_tile_size,
            "preferred_overlap_ratio": self.preferred_overlap_ratio,
            "input_size": 512,
            "input_channels": 3,
            "input_layout": "NCHW",
            "class_count": 2,
            "building_class_index": 1,
            "output_kind": "two_class_logits_softmax_building_probability",
            "preprocessing_profile": "rgb_orthophoto_uint8_v1",
            "training_normalization": "RGB float32 divided by 255 to [0,1]; no ImageNet mean/std",
            "runtime": "pytorch",
            "device": self._device,
            "loaded": self.is_loaded(),
            "model_mode": "EXPERIMENTAL" if self.is_loaded() else "NOT_LOADED",
            "experimental_only": True,
            "threshold_status": "NOT_CALIBRATED",
            "model_load_time_ms": round(self._load_time_ms, 3),
            "load_count": self._load_count,
            **model_identity("whu_unetplusplus_effb4", "pytorch"),
        }

    def close(self) -> None:
        self._model = None
        self._torch = None

    def _validate_checksum(self) -> None:
        digest = hashlib.sha256()
        with self.checkpoint_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != self.EXPECTED_SHA256:
            raise AIModelError("MODEL_LOAD_FAILED", "The WHU checkpoint SHA-256 does not match the expected model.")

    @staticmethod
    def _validate_tile(tile: PreparedTile) -> None:
        if not isinstance(tile.image, np.ndarray) or tile.image.shape != (3, 512, 512):
            raise AIModelError("MODEL_INPUT_INVALID", "WHU exige une tuile RGB float32 de forme (3,512,512).")
        if tile.image.dtype != np.float32 or not np.isfinite(tile.image).all():
            raise AIModelError("MODEL_INPUT_INVALID", "WHU RGB pixels must be finite float32 values.")
        if float(tile.image.min()) < 0.0 or float(tile.image.max()) > 1.0:
            raise AIModelError("MODEL_INPUT_INVALID", "WHU input values must be in [0,1].")
        if tile.valid_mask.shape != (512, 512) or tile.valid_mask.dtype != np.bool_:
            raise AIModelError("MODEL_INPUT_INVALID", "The WHU valid mask must be a 512x512 boolean array.")

