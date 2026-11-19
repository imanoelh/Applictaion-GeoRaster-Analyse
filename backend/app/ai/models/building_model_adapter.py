from __future__ import annotations

import logging
import hashlib
import threading
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..config.ai_model_config import BuildingModelConfig
from ..services.tiling_service import PreparedTile
from .base_model_adapter import AIModelError, BaseModelAdapter, ModelOutput


logger = logging.getLogger(__name__)
ModelLoader = Callable[[Path, str], Any]


class BuildingModelAdapter(BaseModelAdapter):
    """PyTorch/TorchScript adapter for one-channel building segmentation."""

    def __init__(
        self,
        config: BuildingModelConfig | None = None,
        *,
        model_loader: ModelLoader | None = None,
    ) -> None:
        self.config = config or BuildingModelConfig.from_env()
        self._model_loader = model_loader
        self._model: Any | None = None
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
            checkpoint = self.config.checkpoint_path
            if checkpoint is None:
                raise AIModelError(
                    "MODEL_NOT_CONFIGURED",
                    "Aucun checkpoint de segmentation de batiments n'est configure.",
                )
            if not checkpoint.is_file():
                raise AIModelError(
                    "MODEL_FILE_NOT_FOUND",
                    "Le checkpoint de segmentation configure est introuvable.",
                )
            self._validate_provenance()
            self._validate_checkpoint_checksum(checkpoint)
            torch = self._torch()
            self._device = (
                "cuda"
                if self.config.allow_cuda and bool(torch.cuda.is_available())
                else "cpu"
            )
            logger.info("[AI-MODEL] loading building model")
            started = time.perf_counter()
            try:
                if self._model_loader is not None:
                    model = self._model_loader(checkpoint, self._device)
                elif self.config.checkpoint_format == "state_dict":
                    model = self._load_state_dict_model(checkpoint, self._device)
                else:
                    model = torch.jit.load(str(checkpoint), map_location=self._device)
                if not callable(model) or not hasattr(model, "eval"):
                    raise TypeError("Le checkpoint ne fournit pas un module PyTorch executable.")
                model.eval()
                self._model = model
                self._load_count += 1
                self._load_time_ms = (time.perf_counter() - started) * 1000.0
                logger.info("[AI-MODEL] model loaded device=%s", self._device)
            except AIModelError:
                raise
            except Exception as exc:
                self._model = None
                logger.exception("[AI-MODEL] building model load failed")
                raise AIModelError(
                    "MODEL_LOAD_FAILED",
                    "Le checkpoint de segmentation est invalide ou incompatible.",
                    technical_detail=str(exc),
                ) from exc

    def is_loaded(self) -> bool:
        return self._model is not None

    def predict(self, tile: PreparedTile) -> ModelOutput:
        self._validate_tile(tile)
        if not self.is_loaded():
            self.load()
        torch = self._torch()
        started = time.perf_counter()
        try:
            tensor = self.tile_to_tensor(tile)
            with torch.inference_mode():
                raw_output = self._model(tensor)
            output_tensor = self._extract_tensor(raw_output)
            if self.config.output_kind == "logits":
                output_tensor = torch.sigmoid(output_tensor)
            probability_map = self._to_probability_map(output_tensor, tile)
            return ModelOutput(
                probability_map=probability_map,
                inference_time_ms=(time.perf_counter() - started) * 1000.0,
            )
        except AIModelError:
            raise
        except Exception as exc:
            logger.exception("[AI-INFERENCE] building inference failed tile=%s", tile.metadata.tile_id)
            raise AIModelError(
                "INFERENCE_FAILED",
                "L'inference de segmentation a echoue.",
                technical_detail=str(exc),
            ) from exc

    def tile_to_tensor(self, tile: PreparedTile) -> Any:
        self._validate_tile(tile)
        torch = self._torch()
        contiguous = np.ascontiguousarray(tile.image)
        tensor = torch.from_numpy(contiguous).unsqueeze(0).to(
            device=self._device,
            dtype=torch.float32,
        )
        model_size = self.config.effective_model_input_size
        if tuple(tensor.shape[-2:]) != (model_size, model_size):
            tensor = torch.nn.functional.interpolate(
                tensor,
                size=(model_size, model_size),
                mode="bilinear",
                align_corners=False,
            )
        if self.config.model_normalization == "per_channel_zscore":
            mask = torch.from_numpy(np.ascontiguousarray(tile.valid_mask)).to(
                device=self._device,
                dtype=torch.float32,
            )[None, None]
            if tuple(mask.shape[-2:]) != (model_size, model_size):
                mask = torch.nn.functional.interpolate(mask, size=(model_size, model_size), mode="nearest")
            valid = mask[0, 0] > 0.5
            if not bool(valid.any()):
                self._input_error("La tuile ne contient aucun pixel valide pour la normalisation.")
            tensor = tensor * 255.0
            for channel in range(3):
                values = tensor[0, channel][valid]
                mean = values.mean()
                std = values.std(unbiased=False)
                tensor[0, channel] = (tensor[0, channel] - mean) / (std + 1e-6)
            tensor = tensor * valid[None, None].to(dtype=tensor.dtype)
        elif self.config.model_normalization != "none":
            self._input_error(
                f"Normalisation modele inconnue: {self.config.model_normalization}."
            )
        return tensor

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_id": "unet_resnet34",
            "display_name": "U-Net ResNet-34",
            "model_architecture_name": "UNet ResNet34",
            "checkpoint_sha256": self.config.checkpoint_sha256,
            "preferred_tile_size": None,
            "status": "stable",
            "recommended_usage": "Default production Building model.",
            "preprocessing_profile": "production_rgb_zscore_v1",
            "model_name": self.config.model_name,
            "model_version": self.config.model_version,
            "model_architecture": self.config.model_architecture,
            "checkpoint_id": (
                f"sha256:{self.config.checkpoint_sha256[:12]}"
                if self.config.checkpoint_sha256
                else None
            ),
            "checkpoint_format": self.config.checkpoint_format,
            "runtime": self.config.runtime,
            "device": self._device,
            "loaded": self.is_loaded(),
            "model_mode": (
                "TEST_ONLY"
                if self.config.test_only
                else ("REAL" if self.is_loaded() else "NOT_CONFIGURED")
            ),
            "model_load_time_ms": round(self._load_time_ms, 3),
            "load_count": self._load_count,
            "input_size": self.config.input_size,
            "model_input_size": self.config.effective_model_input_size,
            "input_layout": "NCHW",
            "input_channels": 3,
            "source_normalization": "float32_0_1",
            "model_normalization": self.config.model_normalization,
            "output_kind": self.config.output_kind,
            "threshold_status": "NOT_CALIBRATED",
            "weights_license": self.config.weights_license,
        }

    def close(self) -> None:
        self._model = None
        try:
            torch = self._torch()
            if self._device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except AIModelError:
            pass
        self._device = "cpu"

    def _validate_tile(self, tile: PreparedTile) -> None:
        image = tile.image
        expected_size = self.config.input_size
        if not isinstance(image, np.ndarray):
            self._input_error("L'image de tuile doit etre un tableau NumPy.")
        if image.dtype != np.float32:
            self._input_error("L'image de tuile doit utiliser float32.")
        if image.shape != (3, expected_size, expected_size):
            self._input_error(
                f"La tuile doit avoir la forme (3, {expected_size}, {expected_size})."
            )
        if not np.isfinite(image).all():
            self._input_error("La tuile contient NaN ou Inf.")
        if float(image.min()) < 0.0 or float(image.max()) > 1.0:
            self._input_error("Les valeurs normalisees doivent etre comprises entre 0 et 1.")
        if tile.valid_mask.shape != (expected_size, expected_size):
            self._input_error("Le valid_mask ne correspond pas aux dimensions de la tuile.")
        if tile.valid_mask.dtype != np.bool_:
            self._input_error("Le valid_mask doit etre booleen.")
        if tile.metadata.tile_size != expected_size:
            self._input_error("La metadata tile_size est incompatible avec le modele.")

    def _to_probability_map(self, tensor: Any, tile: PreparedTile) -> np.ndarray:
        torch = self._torch()
        if not isinstance(tensor, torch.Tensor):
            raise AIModelError("MODEL_OUTPUT_INVALID", "Le modele n'a pas retourne un Tensor.")
        while tensor.ndim > 2 and tensor.shape[0] == 1:
            tensor = tensor.squeeze(0)
        model_expected = (
            self.config.effective_model_input_size,
            self.config.effective_model_input_size,
        )
        if tuple(tensor.shape) != model_expected:
            raise AIModelError(
                "MODEL_OUTPUT_INVALID",
                f"La sortie brute du modele doit avoir la forme {model_expected}.",
            )
        expected = tuple(tile.valid_mask.shape)
        if model_expected != expected:
            tensor = torch.nn.functional.interpolate(
                tensor[None, None],
                size=expected,
                mode="bilinear",
                align_corners=False,
            )[0, 0]
        probability = tensor.detach().to(device="cpu", dtype=torch.float32).numpy().copy()
        if not np.isfinite(probability).all():
            raise AIModelError("MODEL_OUTPUT_INVALID", "La sortie contient NaN ou Inf.")
        if float(probability.min()) < 0.0 or float(probability.max()) > 1.0:
            raise AIModelError(
                "MODEL_OUTPUT_INVALID",
                "La carte de probabilite doit etre comprise entre 0 et 1.",
            )
        probability[~tile.valid_mask] = np.float32(0.0)
        return probability.astype(np.float32, copy=False)

    @staticmethod
    def _extract_tensor(output: Any) -> Any:
        if isinstance(output, dict):
            for key in ("out", "logits", "mask"):
                if key in output:
                    return output[key]
            raise AIModelError(
                "MODEL_OUTPUT_INVALID",
                "La sortie dictionnaire ne contient ni out, logits, ni mask.",
            )
        if isinstance(output, (tuple, list)):
            if not output:
                raise AIModelError("MODEL_OUTPUT_INVALID", "La sortie du modele est vide.")
            return output[0]
        return output

    def _load_state_dict_model(self, checkpoint: Path, device: str) -> Any:
        if self.config.model_architecture != "unet_resnet34":
            raise AIModelError(
                "MODEL_METADATA_INCOMPLETE",
                f"Architecture state_dict non supportee: {self.config.model_architecture}.",
            )
        try:
            import segmentation_models_pytorch as smp
        except Exception as exc:
            raise AIModelError(
                "MODEL_LOAD_FAILED",
                "La dependance segmentation-models-pytorch est indisponible.",
                technical_detail=str(exc),
            ) from exc
        torch = self._torch()
        state_dict = torch.load(str(checkpoint), map_location="cpu", weights_only=True)
        if not isinstance(state_dict, dict) or not state_dict:
            raise AIModelError(
                "MODEL_LOAD_FAILED",
                "Le checkpoint state_dict est vide ou invalide.",
            )
        model = smp.Unet(
            encoder_name="resnet34",
            encoder_weights=None,
            in_channels=3,
            classes=1,
        )
        model.load_state_dict(state_dict, strict=True)
        return model.to(device)

    def _validate_provenance(self) -> None:
        if self.config.test_only or not self.config.enforce_provenance:
            return
        if not self.config.weights_license or self.config.weights_license.upper() in {"UNKNOWN", "UNVERIFIED"}:
            raise AIModelError(
                "MODEL_LICENSE_UNVERIFIED",
                "La licence des poids du modele n'est pas verifiee.",
            )
        required = {
            "architecture": self.config.model_architecture,
            "checkpoint_source": self.config.checkpoint_source,
            "training_dataset": self.config.training_dataset,
            "checkpoint_sha256": self.config.checkpoint_sha256,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise AIModelError(
                "MODEL_METADATA_INCOMPLETE",
                "Les metadonnees obligatoires du modele sont incompletes.",
                technical_detail=", ".join(missing),
            )

    def _validate_checkpoint_checksum(self, checkpoint: Path) -> None:
        expected = self.config.checkpoint_sha256
        if not expected:
            return
        digest = hashlib.sha256()
        with checkpoint.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != expected.lower():
            raise AIModelError(
                "MODEL_LOAD_FAILED",
                "Le checksum du checkpoint ne correspond pas a la version configuree.",
            )

    @staticmethod
    def _torch() -> Any:
        try:
            import torch
        except Exception as exc:
            raise AIModelError(
                "MODEL_LOAD_FAILED",
                "Le runtime PyTorch n'est pas installe ou ne peut pas etre charge.",
                technical_detail=str(exc),
            ) from exc
        return torch

    @staticmethod
    def _input_error(message: str) -> None:
        raise AIModelError("MODEL_INPUT_INVALID", message)

