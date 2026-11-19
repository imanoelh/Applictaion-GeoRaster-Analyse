# MODEL_C9 intermediate benchmark

## Scope

Controlled benchmark target: 256 train tiles, 64 validation tiles, 64 test
tiles, seed 42, three epochs, CPU-only. The experiment is isolated under
`backend/data/fine_tuning/buildings/model_c9_benchmark/` and does not modify
MODEL_C8 or production.

## Configuration

- architecture: torchvision DeepLabV3 / ResNet50;
- initialization: compatible MODEL_C8 weights, read-only;
- batch size: 2;
- DataLoader workers: 0;
- PyTorch threads: 2;
- loss: BCEWithLogits + Dice, 0.5/0.5;
- epoch threshold metrics: 0.50;
- final validation threshold candidates: 0.30–0.70;
- fixed split selection: first sorted records within existing train/val/test
  splits; no tile moved between splits.

## Execution result

The benchmark was started but stopped before the first epoch completed because
the CPU-only runtime was too slow and memory-intensive for this host. During the
run, the Python process reached approximately **5.2 GiB working set** and more
than **17 minutes CPU time** without producing an epoch result. No three-epoch
metrics, threshold, C8 comparison, or benchmark checkpoint can therefore be
reported honestly.

The earlier C9 smoke-test remains valid only as a pipeline smoke-test (8/4/4
tiles, one epoch); it is not a scientific benchmark.

## Decision

**B. TRAINING_COMPLET_CPU_TROP_LENT**

A GPU or substantially larger CPU host is required for the requested 256/64/64
three-epoch benchmark. Do not launch the full 20-epoch training on this machine.

MODEL_C8 unchanged  
MODEL_C9 experimental  
Production unchanged  
GEE unchanged  
Indices unchanged  
Classifications unchanged  
Exports unchanged  
Frontend unchanged  
API unchanged  
Offline unchanged
