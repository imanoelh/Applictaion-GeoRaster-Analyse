from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import Window

from ..config.building_model_catalog import model_identity
from ..services.tiling_service import PreparedTile
from .base_model_adapter import AIModelError, BaseModelAdapter, ModelOutput


class SpaceNet2DeepLabAdapter(BaseModelAdapter):
    """Standard Building engine for the audited torchvision MODEL_C checkpoint."""

    preferred_tile_size = 512
    preferred_batch_size = 4
    torch_threads_env = "SPACENET2_TORCH_THREADS"
    default_torch_threads = 4

    def __init__(
        self,
        checkpoint_path: Path,
        *,
        expected_sha256: str | None = None,
        engine: str | None = None,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.expected_sha256 = expected_sha256
        self._model: Any | None = None
        self._onnx_session: Any | None = None
        self._engine = (engine or os.getenv("SPACENET2_ENGINE", "onnxruntime")).strip().lower()
        self.onnx_path = self.checkpoint_path.parent / "onnx" / "spacenet2_deeplab_main.onnx"
        self._device = "cpu"
        self._load_time_ms = 0.0
        self._load_count = 0
        self._architecture: str | None = None
        self._encoder_name: str | None = None
        self._output_channels: int | None = None
        self._aux_output_channels: int | None = None
        self._inference_threads: int | None = None
        self._lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._image_stats_cache: dict[tuple[str, str, int, int, tuple[int, int, int]], tuple[float, float]] = {}

    def load(self) -> None:
        if self.is_loaded():
            return
        with self._lock:
            if self.is_loaded():
                return
            if not self.checkpoint_path.is_file():
                raise AIModelError("MODEL_FILE_NOT_FOUND", "The experimental MODEL_C checkpoint is missing.")
            self._validate_checksum()
            if self._engine == "onnxruntime":
                self._load_onnx()
                return
            if self._engine != "pytorch":
                raise AIModelError("MODEL_CONFIGURATION_INVALID", "SPACENET2_ENGINE must be pytorch or onnxruntime.")
            torch = self._torch()
            try:
                requested_threads = int(os.getenv(self.torch_threads_env, str(self.default_torch_threads)))
            except ValueError as exc:
                raise AIModelError(
                    "MODEL_CONFIGURATION_INVALID",
                    f"{self.torch_threads_env} must be a positive integer.",
                    technical_detail=str(exc),
                ) from exc
            if requested_threads <= 0:
                raise AIModelError(
                    "MODEL_CONFIGURATION_INVALID",
                    f"{self.torch_threads_env} must be a positive integer.",
                )
            torch.set_num_threads(min(requested_threads, os.cpu_count() or requested_threads))
            self._inference_threads = torch.get_num_threads()
            started = time.perf_counter()
            try:
                checkpoint = torch.load(str(self.checkpoint_path), map_location="cpu", weights_only=True)
                state_dict = self._extract_state_dict(checkpoint)
                model, architecture, encoder_name, output_channels, aux_output_channels = (
                    self._build_strict_model(state_dict)
                )
                model.eval().to(self._device)
                self._model = model
                self._architecture = architecture
                self._encoder_name = encoder_name
                self._output_channels = output_channels
                self._aux_output_channels = aux_output_channels
                self._load_count += 1
                self._load_time_ms = (time.perf_counter() - started) * 1000.0
            except AIModelError:
                raise
            except Exception as exc:
                self._model = None
                raise AIModelError("MODEL_LOAD_FAILED", "The MODEL_C checkpoint could not be strictly loaded.", technical_detail=str(exc)) from exc

    def is_loaded(self) -> bool:
        return self._model is not None or self._onnx_session is not None

    def predict(self, tile: PreparedTile) -> ModelOutput:
        self._validate_tile(tile)
        if not self.is_loaded():
            self.load()
        if self._engine == "onnxruntime":
            return self._predict_batch_onnx([tile])[0]
        torch = self._torch()
        started = time.perf_counter()
        try:
            image = tile.image if (tile.image.flags.c_contiguous and tile.image.dtype == np.float32) else np.ascontiguousarray(tile.image, dtype=np.float32)
            tensor = torch.from_numpy(image).unsqueeze(0)
            with torch.inference_mode():
                raw_output = self._model(tensor)
            output = self._extract_output(raw_output)
            if output.ndim != 4 or output.shape[0] != 1 or output.shape[1] != 1:
                raise AIModelError("MODEL_OUTPUT_INVALID", "The main output must be one-channel logits.")
            probability = torch.sigmoid(output[:, 0])[0]
            result = probability.detach().to(device="cpu", dtype=torch.float32).numpy().copy()
            if not np.isfinite(result).all() or float(result.min()) < 0.0 or float(result.max()) > 1.0:
                raise AIModelError("MODEL_OUTPUT_INVALID", "The probability map is outside [0, 1].")
            result[~tile.valid_mask] = np.float32(0.0)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            del tensor, raw_output, output, probability
            return ModelOutput(result, elapsed_ms)
        except AIModelError:
            raise
        except Exception as exc:
            raise AIModelError("INFERENCE_FAILED", "MODEL_C inference failed.", technical_detail=str(exc)) from exc

    def predict_batch(self, tiles: list[PreparedTile]) -> list[ModelOutput]:
        if not tiles:
            return []
        for tile in tiles:
            self._validate_tile(tile)
        if not self.is_loaded():
            self.load()
        if self._engine == "onnxruntime":
            return self._predict_batch_onnx(tiles)
        if len(tiles) == 1:
            return [self.predict(tiles[0])]
        torch = self._torch()
        started = time.perf_counter()
        try:
            batch = np.stack(
                [np.ascontiguousarray(tile.image, dtype=np.float32) for tile in tiles],
                axis=0,
            )
            tensor = torch.from_numpy(batch).to(device=self._device, dtype=torch.float32)
            with torch.inference_mode():
                raw_output = self._model(tensor)
            output = self._extract_output(raw_output)
            if output.ndim != 4 or output.shape[0] != len(tiles) or output.shape[1] != 1:
                raise AIModelError("MODEL_OUTPUT_INVALID", "The batch main output must have shape [B, 1, H, W].")
            probabilities = torch.sigmoid(output[:, 0]).detach().to(device="cpu", dtype=torch.float32).numpy()
            if probabilities.shape != (len(tiles), 512, 512) or not np.isfinite(probabilities).all():
                raise AIModelError("MODEL_OUTPUT_INVALID", "The batch probability output is invalid.")
            elapsed_ms_per_tile = (time.perf_counter() - started) * 1000.0 / len(tiles)
            results = []
            for tile, probability in zip(tiles, probabilities, strict=True):
                result = np.asarray(probability, dtype=np.float32).copy()
                result[~tile.valid_mask] = np.float32(0.0)
                results.append(ModelOutput(result, elapsed_ms_per_tile))
            return results
        except AIModelError:
            raise
        except Exception as exc:
            raise AIModelError("INFERENCE_FAILED", "MODEL_C batch inference failed.", technical_detail=str(exc)) from exc

    def prepare_inference_tiles(
        self,
        tiles: Iterable[PreparedTile],
        raster_path: Path,
        *,
        raster_id: str,
        band_indexes: tuple[int, int, int],
    ) -> Iterator[PreparedTile]:
        """Apply training-compatible full-raster RGB min-max to each tile."""
        image_min, image_max = self._image_minmax(
            Path(raster_path), raster_id=raster_id, band_indexes=band_indexes
        )
        for tile in tiles:
            yield self.normalize_tile(tile, image_min=image_min, image_max=image_max)

    @staticmethod
    def normalize_tile(
        tile: PreparedTile, *, image_min: float, image_max: float
    ) -> PreparedTile:
        source = tile.source_rgb
        if source.shape != tile.image.shape or source.ndim != 3 or source.shape[0] != 3:
            raise AIModelError("MODEL_INPUT_INVALID", "MODEL_C source RGB data is invalid.")
        source_float = source.astype(np.float32, copy=False)
        if image_max == image_min:
            normalized = np.zeros(source.shape, dtype=np.float32)
        else:
            normalized = (source_float - np.float32(image_min)) / np.float32(image_max - image_min)
        normalized[~np.isfinite(normalized)] = np.float32(0.0)
        normalized[:, ~tile.valid_mask] = np.float32(0.0)
        return replace(tile, image=normalized.astype(np.float32, copy=False))

    def _image_minmax(
        self, raster_path: Path, *, raster_id: str, band_indexes: tuple[int, int, int]
    ) -> tuple[float, float]:
        stat = raster_path.stat()
        key = (raster_id, str(raster_path.resolve()), stat.st_mtime_ns, stat.st_size, tuple(band_indexes))
        with self._stats_lock:
            cached = self._image_stats_cache.get(key)
            if cached is not None:
                return cached
        minimum = float("inf")
        maximum = float("-inf")
        with rasterio.open(raster_path) as dataset:
            for row in range(0, dataset.height, 1024):
                for col in range(0, dataset.width, 1024):
                    height = min(1024, dataset.height - row)
                    width = min(1024, dataset.width - col)
                    data = dataset.read(
                        indexes=band_indexes,
                        window=Window(col, row, width, height),
                        masked=True,
                    )
                    valid = ~np.any(np.ma.getmaskarray(data), axis=0)
                    if not valid.any():
                        continue
                    values = np.asarray(data.data)[:, valid]
                    finite = np.isfinite(values)
                    if not finite.any():
                        continue
                    minimum = min(minimum, float(values[finite].min()))
                    maximum = max(maximum, float(values[finite].max()))
        if not np.isfinite(minimum) or not np.isfinite(maximum):
            raise AIModelError("MODEL_INPUT_INVALID", "MODEL_C raster contains no valid RGB pixels.")
        stats = (minimum, maximum)
        with self._stats_lock:
            self._image_stats_cache[key] = stats
            while len(self._image_stats_cache) > 32:
                self._image_stats_cache.pop(next(iter(self._image_stats_cache)))
        return stats

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_id": "spacenet2_deeplab",
            "model_architecture_name": "DeepLabV3 ResNet-50",
            "checkpoint_sha256": self.expected_sha256,
            "preferred_tile_size": self.preferred_tile_size,
            "recommended_usage": "High-resolution aerial and orthophoto imagery.",
            "preprocessing_profile": "full_raster_global_rgb_minmax_v1",
            "model_name": "spacenet2-deeplabv3-experimental",
            "model_version": "best_deeplab.pth",
            "model_architecture": self._architecture or "torchvision_deeplabv3",
            "checkpoint_id": f"sha256:{self.expected_sha256[:12]}" if self.expected_sha256 else None,
            "checkpoint_format": "state_dict",
            "runtime": "onnxruntime" if self._engine == "onnxruntime" else "pytorch",
            "device": self._device,
            "inference_threads": self._inference_threads,
            "loaded": self.is_loaded(),
            "model_mode": model_identity("spacenet2_deeplab")["status"] if self.is_loaded() else "NOT_CONFIGURED",
            "model_load_time_ms": round(self._load_time_ms, 3),
            "load_count": self._load_count,
            "input_size": 512,
            "model_input_size": 512,
            "input_layout": "NCHW",
            "input_channels": 3,
            "source_normalization": "float32_0_1",
            "training_normalization": "full_image_global_rgb_minmax_to_0_1",
            "training_mean": None,
            "training_std": None,
            "model_normalization": "full_raster_global_rgb_minmax_to_0_1",
            "output_kind": "logits",
            "threshold_status": "NOT_CALIBRATED",
            "weights_license": "MIT (source declaration)",
            "experimental_only": False,
            "encoder": self._encoder_name,
            "output_channels": self._output_channels,
            "aux_output_channels": self._aux_output_channels,
            "preprocessing_status": "CONFIRMED_MINMAX;RESIZE_INTERPOLATION_PARTIAL",
            **model_identity("spacenet2_deeplab", "onnxruntime" if self._engine == "onnxruntime" else "pytorch"),
        }

    def close(self) -> None:
        self._model = None
        self._onnx_session = None
        self._device = "cpu"

    def _load_onnx(self) -> None:
        if not self.onnx_path.is_file():
            raise AIModelError("MODEL_FILE_NOT_FOUND", "The experimental MODEL_C ONNX artifact is missing.")
        try:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            options.intra_op_num_threads = int(os.getenv("SPACENET2_ORT_INTRA_THREADS", "8"))
            options.inter_op_num_threads = int(os.getenv("SPACENET2_ORT_INTER_THREADS", "2"))
            started = time.perf_counter()
            session = ort.InferenceSession(
                str(self.onnx_path), sess_options=options, providers=["CPUExecutionProvider"]
            )
            inputs = session.get_inputs()
            outputs = session.get_outputs()
            if len(inputs) != 1 or inputs[0].name != "image" or len(outputs) != 1 or outputs[0].name != "out":
                raise ValueError("Unexpected MODEL_C ONNX input/output signature.")
            self._onnx_session = session
            self._architecture = "torchvision_deeplabv3_resnet50_onnx"
            self._encoder_name = "resnet50"
            self._output_channels = 1
            self._aux_output_channels = 21
            self._inference_threads = options.intra_op_num_threads
            self._load_count += 1
            self._load_time_ms = (time.perf_counter() - started) * 1000.0
        except Exception as exc:
            self._onnx_session = None
            raise AIModelError("MODEL_LOAD_FAILED", "The MODEL_C ONNX artifact could not be loaded.", technical_detail=str(exc)) from exc

    def _predict_batch_onnx(self, tiles: list[PreparedTile]) -> list[ModelOutput]:
        started = time.perf_counter()
        try:
            batch = np.stack([np.ascontiguousarray(tile.image, dtype=np.float32) for tile in tiles], axis=0)
            outputs = self._onnx_session.run(["out"], {"image": batch})
            logits = outputs[0]
            if logits.shape != (len(tiles), 1, 512, 512) or not np.isfinite(logits).all():
                raise AIModelError("MODEL_OUTPUT_INVALID", "The ONNX main output must have shape [B, 1, 512, 512].")
            # ONNX graph exports logits; retain the PyTorch adapter's sigmoid contract.
            clipped = np.clip(logits[:, 0], -80.0, 80.0)
            probabilities = (1.0 / (1.0 + np.exp(-clipped))).astype(np.float32, copy=False)
            elapsed_ms_per_tile = (time.perf_counter() - started) * 1000.0 / len(tiles)
            results = []
            for tile, probability in zip(tiles, probabilities, strict=True):
                result = probability.copy()
                result[~tile.valid_mask] = np.float32(0.0)
                results.append(ModelOutput(result, elapsed_ms_per_tile))
            return results
        except AIModelError:
            raise
        except Exception as exc:
            raise AIModelError("INFERENCE_FAILED", "MODEL_C ONNX batch inference failed.", technical_detail=str(exc)) from exc

    def _validate_tile(self, tile: PreparedTile) -> None:
        if not isinstance(tile.image, np.ndarray) or tile.image.shape != (3, 512, 512):
            raise AIModelError("MODEL_INPUT_INVALID", "MODEL_C tiles must be float32 with shape (3, 512, 512).")
        if tile.image.dtype != np.float32 or not np.isfinite(tile.image).all():
            raise AIModelError("MODEL_INPUT_INVALID", "MODEL_C tile values are invalid.")
        if float(tile.image.min()) < 0.0 or float(tile.image.max()) > 1.0:
            raise AIModelError("MODEL_INPUT_INVALID", "MODEL_C pixels must be in [0, 1].")
        if tile.valid_mask.shape != (512, 512) or tile.valid_mask.dtype != np.bool_:
            raise AIModelError("MODEL_INPUT_INVALID", "The MODEL_C valid_mask is incompatible.")

    def _validate_checksum(self) -> None:
        if not self.expected_sha256:
            return
        digest = hashlib.sha256()
        with self.checkpoint_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != self.expected_sha256.lower():
            raise AIModelError("MODEL_LOAD_FAILED", "The MODEL_C checkpoint checksum is incorrect.")

    @staticmethod
    def _extract_state_dict(checkpoint: Any) -> dict[str, Any]:
        if not isinstance(checkpoint, dict):
            raise AIModelError("MODEL_LOAD_FAILED", "The MODEL_C checkpoint is not a weight dictionary.")
        candidates = [checkpoint]
        for key in ("state_dict", "model_state_dict", "model"):
            value = checkpoint.get(key)
            if isinstance(value, dict):
                candidates.insert(0, value)
        for candidate in candidates:
            if candidate and all(hasattr(value, "shape") for value in candidate.values()):
                keys = list(candidate)
                for prefix in ("module.", "model."):
                    if keys and all(key.startswith(prefix) for key in keys):
                        candidate = {key[len(prefix):]: value for key, value in candidate.items()}
                        keys = list(candidate)
                return candidate
        raise AIModelError("MODEL_LOAD_FAILED", "No tensor state_dict was found.")

    @classmethod
    def _build_strict_model(cls, state_dict: dict[str, Any]) -> tuple[Any, str, str, int, int]:
        """Rebuild the exact torchvision model represented by MODEL_C."""
        try:
            from torchvision.models.segmentation import deeplabv3_resnet50
            from torchvision.models.segmentation.deeplabv3 import DeepLabHead
        except Exception as exc:
            raise AIModelError("MODEL_LOAD_FAILED", "torchvision is unavailable.", technical_detail=str(exc)) from exc
        classifier_weight = state_dict.get("classifier.4.weight")
        aux_classifier_weight = state_dict.get("aux_classifier.4.weight")
        if classifier_weight is None or aux_classifier_weight is None:
            raise AIModelError("MODEL_LOAD_FAILED", "Expected torchvision classifiers are missing.")
        output_channels = int(classifier_weight.shape[0])
        aux_output_channels = int(aux_classifier_weight.shape[0])
        if output_channels != 1:
            raise AIModelError("MODEL_LOAD_FAILED", f"Unexpected main output channels: {output_channels}.")
        if aux_output_channels != 21:
            raise AIModelError("MODEL_LOAD_FAILED", f"Unexpected auxiliary output channels: {aux_output_channels}.")
        model = deeplabv3_resnet50(weights=None, weights_backbone=None, aux_loss=True)
        model.classifier = DeepLabHead(2048, output_channels)
        try:
            model.load_state_dict(state_dict, strict=True)
        except RuntimeError as exc:
            raise AIModelError("MODEL_LOAD_FAILED", "The strict torchvision MODEL_C load failed.", technical_detail=str(exc)) from exc
        return model, "torchvision_deeplabv3", "resnet50", output_channels, aux_output_channels

    @staticmethod
    def _extract_output(output: Any) -> Any:
        if isinstance(output, dict) and "out" in output:
            return output["out"]
        raise AIModelError("MODEL_OUTPUT_INVALID", "The torchvision output does not contain the out key.")

    @staticmethod
    def _torch() -> Any:
        try:
            import torch
        except Exception as exc:
            raise AIModelError("MODEL_LOAD_FAILED", "PyTorch is unavailable.", technical_detail=str(exc)) from exc
        return torch
