from pathlib import Path

import numpy as np
import torch

from backend.scripts.building_dataset.train_model_c9 import BuildingDataset, dice_loss, make_model, metrics, select_device


def test_c9_device_selection_falls_back_to_cpu_without_cuda() -> None:
    assert select_device("cpu").type == "cpu"
    if not torch.cuda.is_available():
        assert select_device("auto").type == "cpu"


def test_c9_dataset_mask_and_forward_shape() -> None:
    root = Path(r"D:\GeoRaster_AI_Datasets\SpaceNet\georaster_building_v1_khartoum")
    if not root.exists():
        return
    ds = BuildingDataset(root, "train", limit=1)
    image, mask = ds[0]
    assert image.shape == (3, 512, 512)
    assert mask.shape == (1, 512, 512)
    assert image.dtype == torch.float32 and mask.dtype == torch.float32
    assert set(torch.unique(mask).tolist()) <= {0.0, 1.0}
    model = make_model().eval()
    with torch.inference_mode():
        output = model(image.unsqueeze(0))["out"]
    assert output.shape == (1, 1, 512, 512)


def test_c9_loss_metrics_are_finite() -> None:
    logits = torch.zeros((1, 1, 4, 4), requires_grad=True)
    target = torch.zeros((1, 1, 4, 4))
    loss = 0.5 * torch.nn.functional.binary_cross_entropy_with_logits(logits, target) + 0.5 * dice_loss(logits, target)
    assert torch.isfinite(loss)
    loss.backward()
    result = metrics(logits.detach(), target)
    assert np.isfinite(result["f1"])
