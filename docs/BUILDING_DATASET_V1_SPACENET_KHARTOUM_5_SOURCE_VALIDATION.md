# SpaceNet 2 AOI_5_Khartoum — 5-source dataset validation

## Scope

This validation is restricted to five SpaceNet Khartoum sources. The 1,012
source dataset was not generated and MODEL_C9 was not trained.

## Implemented experimental change

The isolated dataset script now uses the deterministic profile
`spacenet_rgb_percentile_uint8_v1`: each RGB tile is clipped at configurable
per-band p2/p98 percentiles and rescaled to uint8 `[0, 255]`. Constant bands use
a safe deterministic fallback. The default CLI parameters are
`--rgb-low-percentile 2` and `--rgb-high-percentile 98`.

## Generation command

```text
python backend/scripts/building_dataset/prepare_spacenet_building_dataset.py --imagery "D:\\GeoRaster_AI_Datasets\\SpaceNet\\SN2_Khartoum\\AOI_5_Khartoum_Train\\RGB-PanSharpen" --labels "D:\\GeoRaster_AI_Datasets\\SpaceNet\\SN2_Khartoum\\AOI_5_Khartoum_Train\\geojson\\buildings" --output "D:\\GeoRaster_AI_Datasets\\SpaceNet\\georaster_building_v1_test" --tile-size 512 --seed 42 --limit 5
```

## Results

- sources processed: **5**
- tiles generated: **20**
- train/val/test: **12 / 4 / 4**
- positive tiles: **20**
- negative tiles: **0** (none of the five selected sources produced an empty retained tile; negatives remain enabled)
- rejected tiles: **0**
- source footprints: **162** total (`26 + 69 + 15 + 15 + 37`)
- input dtype: **uint16**, 3 RGB bands
- output dtype: **uint8**, 3 RGB bands
- radiometric profile: **spacenet_rgb_percentile_uint8_v1**
- percentiles: **p2 / p98** per band and tile
- building pixel ratio: **0.1142879486**
- previews: **10**

Output dataset:

`D:\GeoRaster_AI_Datasets\SpaceNet\georaster_building_v1_test`

Previews:

`D:\GeoRaster_AI_Datasets\SpaceNet\georaster_building_v1_test\metadata\previews`

## QA

All 20 generated records passed automated checks:

- image and mask are 512×512;
- RGB has 3 bands and uint8 dtype;
- mask is uint8 with values only `{0, 255}`;
- image/mask CRS, transform, and bounds match;
- no NaN values;
- all five source rasters remain exclusively in one split;
- no source-level train/val/test leakage.

The source imagery is approximately 650×650, so edge windows are padded to the
configured 512×512 shape with Rasterio `boundless=True`; no resizing or building
geometry deformation is performed.

## Tests

Targeted pipeline suite: **8 passed**. This includes uint16 percentile scaling,
constant-band handling, clipping, mask values, alignment, deterministic output,
pairing, and nodata rejection.

Known non-fatal environment warnings were emitted by the local PostgreSQL/PROJ
database and GDAL block-size metadata. They did not produce rejected records or
alignment errors.

MODEL_C8, GEE, indices, classifications, exports, frontend, production API,
offline mode, and production cache are unchanged.

## Stop point

The requested five-source generation, previews, and QA are complete. The full
1,012-image generation and MODEL_C9 training were intentionally not started.
