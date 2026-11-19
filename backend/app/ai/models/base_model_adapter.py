from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..services.tiling_service import PreparedTile


class AIModelError(RuntimeError):
    """Safe business error returned without exposing implementation traces."""

    def __init__(self, code: str, message: str, *, technical_detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.technical_detail = technical_detail

    def public_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ModelOutput:
    probability_map: np.ndarray
    inference_time_ms: float
    details: dict[str, Any] = field(default_factory=dict)


class BaseModelAdapter(ABC):
    preferred_tile_size: int | None = None
    preferred_batch_size = 1

    @abstractmethod
    def load(self) -> None:
        """Load and validate model resources once."""

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return whether the model is ready for inference."""

    @abstractmethod
    def predict(self, tile: PreparedTile) -> ModelOutput:
        """Return a standardized probability map for one prepared tile."""

    def predict_batch(self, tiles: list[PreparedTile]) -> list[ModelOutput]:
        """Predict a bounded batch; adapters can override for vectorized inference."""
        return [self.predict(tile) for tile in tiles]

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Return non-sensitive runtime/model metadata."""

    @abstractmethod
    def close(self) -> None:
        """Release model resources in a controlled way."""

