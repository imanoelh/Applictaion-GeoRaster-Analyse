# SpaceNet 2 AOI_5_Khartoum — pairing fix validation

## Scope

Only the experimental dataset-preparation pipeline was changed. No MODEL_C8,
production API, frontend, GEE, indices, classifications, exports, cache, or
offline behavior was changed. No tiles were generated and no MODEL_C9 training
was started.

## Root cause

The previous pairing code compared ad-hoc normalized filename strings. The
imagery prefix (`RGB-PanSharpen_`) and label prefix (`buildings_`) were not
converted to one stable sample key, so the two real names produced different
keys and every image was reported as `NO_MATCHING_LABEL`.

## Fix

`extract_spacenet_sample_id(path_or_filename)` now extracts the complete
collision-safe token `AOI_<id>_<city>_img<number>` from imagery, label, PAN and
MUL names. Pairing indexes both sides by this canonical key and explicitly
rejects missing, duplicate-image, and duplicate-label keys instead of choosing
silently. Generic synthetic names also retain a shared normalized stem for the
existing pipeline fixtures.

## Tests

Targeted pipeline tests: **6 passed**.

Covered cases include the real `img1` and `img1001` names, extension variants,
Windows paths, `img1`/`img10`/`img100` non-collision, multi-AOI non-collision,
missing labels, duplicate canonical IDs, raster-mask alignment, deterministic
dry-run behavior, and nodata rejection.

## Real dry-run

Command used (exact requested command):

```text
python backend/scripts/building_dataset/prepare_spacenet_building_dataset.py --imagery "D:\\GeoRaster_AI_Datasets\\SpaceNet\\SN2_Khartoum\\AOI_5_Khartoum_Train\\RGB-PanSharpen" --labels "D:\\GeoRaster_AI_Datasets\\SpaceNet\\SN2_Khartoum\\AOI_5_Khartoum_Train\\geojson\\buildings" --output "D:\\GeoRaster_AI_Datasets\\SpaceNet\\georaster_building_v1_test" --tile-size 512 --seed 42 --dry-run --limit 5
```

Results:

- images detected: **1012**
- labels detected: **1012**
- canonical pairs: **1012**
- sampled/inspected examples: **5**
- unmatched/rejected pairings: **0**
- dry-run: **true**
- tile generation: **not run**

The five inspected pairs were:

1. `AOI_5_Khartoum_img1` — 650×650, 3 bands, uint16, 26 clipped footprints
2. `AOI_5_Khartoum_img10` — 650×650, 3 bands, uint16, 69 clipped footprints
3. `AOI_5_Khartoum_img100` — 650×650, 3 bands, uint16, 15 clipped footprints
4. `AOI_5_Khartoum_img1001` — 650×650, 3 bands, uint16, 15 clipped footprints
5. `AOI_5_Khartoum_img1003` — 650×650, 3 bands, uint16, 37 clipped footprints

Each example reports the absolute image path, absolute GeoJSON path, canonical
sample ID, dimensions, bands, dtype, CRS, affine transform, and footprint count
in the command JSON output. The source CRS is geographic WGS84/CRS84 and the
pipeline treats the equivalent CRS84/WGS84 forms as already aligned. The local
GDAL/PROJ installation emits a known `proj.db` version warning, but it does not
prevent pairing or footprint inspection.

## Status

The pairing bug is fixed and the real Khartoum dry-run is successful. Stop here
until the 5 inspected associations and CRS/alignment output are approved; do not
run the full dataset generation yet.
