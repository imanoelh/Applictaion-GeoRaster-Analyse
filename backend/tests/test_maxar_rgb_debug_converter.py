from __future__ import annotations

import numpy as np
import pytest

from scripts.maxar_rgb_debug_converter import stretch_uint8


def test_stretch_uint8_maps_bounds_and_preserves_mask() -> None:
    values = np.array([[0, 100, 200], [50, 150, 250]], dtype=np.uint16)
    valid = np.array([[True, True, True], [False, True, True]])

    output = stretch_uint8(values, 50.0, 200.0, valid)

    assert output.dtype == np.uint8
    assert output.tolist() == [[0, 85, 255], [0, 170, 255]]


def test_stretch_uint8_rejects_invalid_bounds() -> None:
    values = np.ones((2, 2), dtype=np.uint16)
    with pytest.raises(ValueError, match="strictement croissantes"):
        stretch_uint8(values, 2.0, 2.0, np.ones((2, 2), dtype=bool))


def test_stretch_uint8_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="memes dimensions"):
        stretch_uint8(np.ones((2, 2)), 0.0, 1.0, np.ones((1, 2), dtype=bool))
