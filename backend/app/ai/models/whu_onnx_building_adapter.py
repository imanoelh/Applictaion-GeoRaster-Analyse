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
from .whu_building_adapter import WHUBuildingModelAdapter


logger = logging.getLogger(__name__)


class WHUOnnxBuildingModelAdapter(BaseModelAdapter):
    """Experimental ONNX Runtime CPU engine for the original WHU MODEL_D weights."""

    preferred_tile_size = 512
    preferred_overlap_ratio = 0.5
    preferred_batch_size = 1

    MODEL_ID = "whu_unetplusplus_effb4_onnx"
    MODEL_NAME = "WHU U-Net++ EfficientNet-B4 (ONNX Runtime CPU)"
    MODEL_VERSION = "whu-building-unetplusplus-efficientnet-b4-onnx-v1"
    MODEL_ARCHITECTURE = "U-Net++ / EfficientNet-B4 (ONNX)"
    ONNX_SHA256 = "62170133dac13124ee7297f592e024026ba9ccc66a102b07f5368d8abea3a0b6"
    ONNX_THREADS = 4

    def __init__(self, onnx_path: Path | None = None, checkpoint_path: Path | None = None) -> None:
        backend_dir = Path(__file__).resolve().parents[3]
        model_dir = backend_dir / "data/models/building/experimental/whu_unetplusplus_effb4"
        self.onnx_path = Path(onnx_path) if onnx_path else model_dir / "onnx/model.onnx"
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else model_dir / "model.pth"
        self._session: Any | None = None
        self._ort: Any | None = None
        self._load_time_ms = 0.0
        self._load_count = 0
        self._lock = threading.Lock()

    def load(self) -> None:
        if self.is_loaded():
            return
        with self._lock:
            if self.is_loaded():
                return
            if not self.onnx_path.is_file():
                raise AIModelError("MODEL_FILE_NOT_FOUND", "The experimental WHU ONNX model is missing.")
            if not self.checkpoint_path.is_file():
                raise AIModelError("MODEL_FILE_NOT_FOUND", "The original experimental WHU checkpoint is missing.")
            self._validate_sha256(self.onnx_path, self.ONNX_SHA256, "ONNX model")
            self._validate_sha256(
                self.checkpoint_path, WHUBuildingModelAdapter.EXPECTED_SHA256, "WHU source checkpoint"
            )
            try:
                import onnxruntime as ort
            except Exception as exc:
                raise AIModelError(
                    "MODEL_LOAD_FAILED", "ONNX Runtime est requis pour le moteur WHU expérimental.",
                    technical_detail=str(exc),
                ) from exc

            started = time.perf_counter()
            try:
                options = ort.SessionOptions()
                options.intra_op_num_threads = self.ONNX_THREADS
                options.inter_op_num_threads = 1
                options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                session = ort.InferenceSession(
                    str(self.onnx_path), sess_options=options, providers=["CPUExecutionProvider"]
                )
                inputs = session.get_inputs()
                outputs = session.get_outputs()
                if len(inputs) != 1 or inputs[0].name != "image" or len(outputs) != 1 or outputs[0].name != "logits":
                    raise ValueError("Unexpected ONNX input/output contract.")
                if inputs[0].shape[1:] != [3, 512, 512] or outputs[0].shape[1:] != [2, 512, 512]:
                    raise ValueError("Unexpected ONNX tensor shape.")
                self._session = session
                self._ort = ort
                self._load_count += 1
                self._load_time_ms = (time.perf_counter() - started) * 1000.0
                logger.info("[AI-MODEL] experimental WHU ONNX model loaded on CPU")
            except Exception as exc:
                self._session = None
                self._ort = None
                raise AIModelError(
                    "MODEL_LOAD_FAILED", "The experimental WHU ONNX model is invalid or incompatible.",
                    technical_detail=str(exc),
                ) from exc

    def is_loaded(self) -> bool:
        return self._session is not None

    def predict(self, tile: PreparedTile) -> ModelOutput:
        WHUBuildingModelAdapter._validate_tile(tile)
        if not self.is_loaded():
            self.load()
        image = np.ascontiguousarray(tile.image[None, ...], dtype=np.float32)
        started = time.perf_counter()
        try:
            logits = self._session.run(["logits"], {"image": image})[0]
            if not isinstance(logits, np.ndarray) or logits.shape != (1, 2, 512, 512):
                raise ValueError(f"Expected logits [1,2,512,512], got {getattr(logits, 'shape', None)}")
            logits = logits[0]
            logits -= logits.max(axis=0, keepdims=True)
            exp_logits = np.exp(logits)
            probability = exp_logits[1] / exp_logits.sum(axis=0)
            probability = np.ascontiguousarray(probability, dtype=np.float32)
            probability[~tile.valid_mask] = np.float32(0.0)
            return ModelOutput(probability, (time.perf_counter() - started) * 1000.0)
        except Exception as exc:
            logger.exception("[AI-INFERENCE] WHU ONNX inference failed tile=%s", tile.metadata.tile_id)
            raise AIModelError(
                "INFERENCE_FAILED", "Experimental WHU ONNX inference failed.", technical_detail=str(exc)
            ) from exc

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_id": self.MODEL_ID,
            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "model_architecture": self.MODEL_ARCHITECTURE,
            "checkpoint_sha256": WHUBuildingModelAdapter.EXPECTED_SHA256,
            "checkpoint_id": f"sha256:{WHUBuildingModelAdapter.EXPECTED_SHA256[:12]}",
            "onnx_sha256": self.ONNX_SHA256,
            "checkpoint_format": "state_dict_exported_to_onnx",
            "weights_license": WHUBuildingModelAdapter.MODEL_LICENSE,
            "training_dataset": "WHU Building Dataset",
            "preferred_tile_size": self.preferred_tile_size,
            "preferred_overlap_ratio": self.preferred_overlap_ratio,
            "preferred_batch_size": self.preferred_batch_size,
            "input_size": 512,
            "input_channels": 3,
            "input_layout": "NCHW",
            "class_count": 2,
            "building_class_index": 1,
            "output_kind": "two_class_logits_softmax_building_probability",
            "preprocessing_profile": "rgb_orthophoto_uint8_v1",
            "training_normalization": "RGB float32 divided by 255 to [0,1]; no ImageNet mean/std",
            "runtime": "onnxruntime",
            "device": "cpu",
            "intra_op_threads": self.ONNX_THREADS,
            "loaded": self.is_loaded(),
            "model_mode": "EXPERIMENTAL" if self.is_loaded() else "NOT_LOADED",
            "experimental_only": True,
            "threshold_status": "NOT_CALIBRATED",
            "model_load_time_ms": round(self._load_time_ms, 3),
            "load_count": self._load_count,
            **model_identity("whu_unetplusplus_effb4_onnx", "onnxruntime"),
        }

    def close(self) -> None:
        self._session = None
        self._ort = None

    @staticmethod
    def _validate_sha256(path: Path, expected: str, description: str) -> None:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != expected.lower():
            raise AIModelError("MODEL_LOAD_FAILED", f"{description} SHA-256 does not match the expected artifact.")
