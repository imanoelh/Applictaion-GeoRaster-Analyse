from __future__ import annotations

import numpy as np


def stretch_uint8(values: np.ndarray, low: float, high: float, valid_mask: np.ndarray) -> np.ndarray:
    values = np.asarray(values)
    valid_mask = np.asarray(valid_mask, dtype=bool)
    if values.shape != valid_mask.shape:
        raise ValueError("values et valid_mask doivent avoir les memes dimensions")
    if not np.isfinite(low) or not np.isfinite(high) or low >= high:
        raise ValueError("les bornes doivent etre strictement croissantes")
    scaled = (np.asarray(values, dtype=np.float32) - float(low)) * (255.0 / (float(high) - float(low)))
    return np.where(valid_mask, np.clip(np.rint(scaled), 0, 255), 0).astype(np.uint8)
