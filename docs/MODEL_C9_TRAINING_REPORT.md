# MODEL_C9 experimental training report

## Status

MODEL_C9 is implemented in an isolated script and remains **EXPERIMENTAL**.
MODEL_C8 remains the production/default model and was loaded read-only.

The host has PyTorch **2.8.0+cpu** and no CUDA device. A controlled smoke run
was completed to validate the complete training/evaluation path. A full 20-epoch
run over all 2,832 training tiles was not started because the CPU-only runtime
would require an impractically long execution window; the smoke result must not
be interpreted as a scientific C8/C9 benchmark.

## Implementation

- script: `backend/scripts/building_dataset/train_model_c9.py`
- architecture: torchvision DeepLabV3 / ResNet50, one-channel main output;
- initialization: compatible C8 weights loaded read-only (backbone and main
  classifier); C9 auxiliary head initialized independently;
- preprocessing: RGB uint8 → float32 `[0,1]`, 512×512;
- augmentations: horizontal/vertical flips and 90° rotations, nearest-neighbor
  mask semantics;
- loss: 0.5 BCEWithLogits + 0.5 Dice;
- optimizer: AdamW, learning rate `1e-4`, weight decay `1e-4`;
- seed: `42`;
- threshold candidates: `0.30` through `0.70`, selected on validation only;
- test split was not used for threshold selection.

## Smoke run

Output: `backend/data/fine_tuning/buildings/model_c9_smoke/`  
Samples: 8 train / 4 validation / 4 test  
Device: CPU  
Epochs: 1  
Training time: approximately 365 seconds

Validation-selected threshold: **0.70**  
Validation F1 at that threshold: **0.4639**  
Smoke test F1 at the fixed run configuration: **0.6895**

This run produced `MODEL_C9_best.pth`, `MODEL_C9_epoch01.pth`,
`training_history.json`, and `MODEL_C9_TRAINING_REPORT.json` in the smoke output
directory.

## Tests

MODEL_C9 isolated tests: **2 passed**.

They cover dataset tensor/mask shape, binary mask values, DeepLab forward output,
finite loss, and metric calculation.

## Production protection

MODEL_C8 unchanged  
MODEL_C9 experimental only  
GEE unchanged  
Indices unchanged  
Classifications unchanged  
Exports unchanged  
Frontend unchanged  
Production API unchanged  
Offline mode unchanged  
Production cache unchanged

## Recommendation

No promotion decision is possible from the smoke subset. Run the same script with
the full dataset and 20 epochs on a suitable GPU/long-running training host,
then compare C8 and C9 once on the locked test split.
