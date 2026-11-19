# MODEL_C9 GPU / Google Colab guide

MODEL_C9 is experimental only. MODEL_C8 and all production components remain
unchanged. This guide uses external dataset/checkpoint paths and never writes
to the C8 checkpoint.

## 1. Enable GPU

In Colab: **Runtime → Change runtime type → T4 GPU**. Then verify:

```bash
!nvidia-smi
```

## 2. Install dependencies and obtain the repository

```bash
!git clone <YOUR_REPOSITORY_URL> /content/georaster
%cd /content/georaster
!pip install -r backend/requirements.txt
```

The scripts require PyTorch, torchvision, rasterio, numpy and psutil.

## 3. Mount Google Drive and set external paths

```python
from google.colab import drive
drive.mount('/content/drive')

DATASET_ROOT = '/content/drive/MyDrive/GeoRaster/georaster_building_v1_khartoum'
C8_CHECKPOINT = '/content/drive/MyDrive/GeoRaster/MODEL_C8_HYBRID_epoch2.pth'
```

Alternatively, extract a ZIP/TAR under `/content/` and point
`--dataset-root` to that extracted directory. Do not hard-code a Windows path.

## 4. GPU benchmark (256/64/64, three epochs)

```bash
!python backend/scripts/building_dataset/benchmark_model_c9.py \
  --dataset-root "$DATASET_ROOT" \
  --c8-checkpoint "$C8_CHECKPOINT" \
  --output /content/model_c9_benchmark \
  --train-limit 256 \
  --val-limit 64 \
  --test-limit 64 \
  --epochs 3 \
  --batch-size 4 \
  --device cuda \
  --amp \
  --num-workers 2 \
  --pin-memory \
  --seed 42
```

The JSON report records device, CUDA version, GPU name, VRAM, AMP, epoch times,
RAM, validation threshold, and preliminary C8/C9 test metrics.

If VRAM is insufficient, retry with `--batch-size 2`, then `1`. Keep 512×512;
do not silently resize tiles. AMP is enabled only when CUDA is actually
available.

## 5. Full training (only after the benchmark is stable)

Do not run this automatically. After human review of the benchmark:

```bash
!python backend/scripts/building_dataset/train_model_c9.py \
  --dataset-root "$DATASET_ROOT" \
  --c8-checkpoint "$C8_CHECKPOINT" \
  --output /content/model_c9_final \
  --epochs 20 \
  --batch-size 4 \
  --device cuda \
  --amp \
  --num-workers 2 \
  --pin-memory \
  --seed 42
```

The output contains `MODEL_C9_epochXX.pth`, `MODEL_C9_best.pth`, history and a
JSON report. No file under the MODEL_C8 directory is ever written.

## 6. Retrieve artifacts

```bash
!cp -r /content/model_c9_benchmark /content/drive/MyDrive/GeoRaster/
!cp -r /content/model_c9_final /content/drive/MyDrive/GeoRaster/  # after approved full run
```

## 7. Safety checks

The scripts select `cuda` only when `torch.cuda.is_available()` is true and
otherwise fall back to CPU. `--amp` is ignored on CPU. The existing CPU tests
remain valid; current isolated MODEL_C9 tests pass.
