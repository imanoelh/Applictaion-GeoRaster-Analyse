# ÉTAPE 13R — Targeted industrial fine-tuning dataset for MODEL_F

## Scope

The dataset was prepared in the isolated experimental directory:

`backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R/`

No fine-tuning was run. MODEL_F, MODEL_C, the model registry, the frontend, the API, the TEST split and production processing were not modified.

## Source and leakage control

New 512×512 windows were sampled from the cached orthophoto source `ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif`, outside the six locked TEST footprints. The six TEST RGB SHA-256 values were loaded into the exclusion check and every generated RGB hash was compared with them. Spatial intersection with the transformed TEST bounds was also checked.

Result: 36 new windows, with `test_leakage = 0`. Train and validation are assigned by geographic macro-zone; no zone identifier occurs in both splits. The split is 31 train / 5 validation. The target was 80/20; the available valid windows produced a slightly larger train share.

## Labels and QA state

MODEL_C ONNX was used only on these new, non-overlapping windows to create pseudo probability maps and binary masks. The unchanged production RGB min/max preprocessing was used. Small artifact filtering was applied before rasterizing masks. Every mask is GeoTIFF, 512×512, `uint8`, with values exactly `{0, 1}`, and the source transform/CRS/bounds are preserved. A contact sheet is available at `qa_contact_sheet_rgb_model_c_pseudo.png`.

The scene labels are dataset sampling labels, not human truth: 24 industrial and 12 residential/urban companion patches. All patches remain `NEEDS_CORRECTION`; no human review was performed. Therefore the dataset is technically validated for structure and leakage, but it is not ready for fine-tuning until the pseudo-label contact sheet is reviewed and corrections are persisted.

## Files

- `manifest.csv` — patch metadata, split, zone, source, label source, review state and RGB/mask hashes.
- `qa_summary.json` — counts and leakage result.
- `images/{train,val}` — RGB tiles.
- `probability/{train,val}` — MODEL_C pseudo probability maps.
- `masks/{train,val}` — binary pseudo-label masks.
- `overlays/{train,val}` — RGB plus pseudo-mask QA overlays.
- `qa_contact_sheet_rgb_model_c_pseudo.png` — contact sheet for human review.

## Review gate

No TEST patch was used. No model was trained. The next controlled action is human review of these 36 pseudo-labels, with explicit ACCEPTED/REJECTED/NEEDS_CORRECTION decisions and correction masks before any 13R.1 fine-tuning.

TEST PATCHES USED FOR TRAINING :
0
TEST LEAKAGE :
0
TRAIN PATCHES :
31
VAL PATCHES :
5
INDUSTRIAL PATCHES :
24
RESIDENTIAL PATCHES :
12
DARK ROOF PATCHES :
0 (not separately verified)
LARGE ROOF PATCHES :
24 (sampling subtype proxy)
LOW CONTRAST PATCHES :
0 (not separately verified)
MODEL_C PSEUDO LABELS :
36
HUMAN ACCEPTED :
0
HUMAN REJECTED :
0
HUMAN CORRECTED :
0
TRAIN MASKS :
31
VAL MASKS :
5
DATASET QA :
VALIDATED
MODEL_F ORIGINAL :
UNCHANGED
MODEL_C :
PRODUCTION UNCHANGED
READY_FOR_FINE_TUNING :
NO
NEXT STEP :
13R.1 MODEL_F TARGETED INDUSTRIAL FINE-TUNING /
CORRECT DATASET
