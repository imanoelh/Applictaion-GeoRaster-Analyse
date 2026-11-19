# SpaceNet 2 AOI_5_Khartoum — full dataset validation

## Scope and isolation

The complete experimental dataset was generated from the 1,012 Khartoum RGB
PanSharpen sources and 1,012 matching Building GeoJSON files. MODEL_C9 was not
trained. No production GeoRaster component was changed.

Output:

`D:\GeoRaster_AI_Datasets\SpaceNet\georaster_building_v1_khartoum`

## Generation parameters

- tile size: `512`
- seed: `42`
- pairing: canonical SpaceNet sample ID
- radiometry: `spacenet_rgb_percentile_uint8_v1`
- percentiles: p2 / p98 per RGB band and tile
- input: 3-band uint16 RGB
- output RGB: uint8
- mask: uint8, background `0`, building `255`
- source-level train/val/test split
- edge windows: controlled Rasterio boundless padding to 512×512
- negative tiles retained, subject only to the configured empty-tile ratio

## Final statistics

- images detected: **1012**
- labels detected: **1012**
- pairs: **1012**
- unmatched: **0**
- source rasters processed: **1012**
- total tiles: **4048**
- train / val / test: **2832 / 608 / 608**
- positive tiles: **3490**
- negative tiles: **558**
- rejected tiles: **0**
- total footprints: **25133**
- building pixels: **172634630**
- building pixel ratio: **0.1626849928**
- background pixel ratio: **0.8373150072**
- processing time: **1951.66 seconds** (about 32.5 minutes)
- disk usage: **2162919923 bytes** (about **2062.72 MiB**)
- previews: **20**

## Exhaustive QA

All **4048** manifest records and their image/mask files were checked:

- image and mask dimensions: 512×512;
- RGB: 3 bands, uint8;
- mask: uint8, values only `{0,255}`;
- image/mask transform, CRS and bounds aligned;
- no NaN values;
- no corrupted tile;
- no broken manifest path;
- 1,012 unique source rasters;
- source split leakage: **none**.

QA result: **0 errors, 0 NaN tiles, 0 split leaks**.

## Previews

Twenty RGB/mask overlays were generated at:

`D:\GeoRaster_AI_Datasets\SpaceNet\georaster_building_v1_khartoum\metadata\previews`

The preview set is seed-reproducible and includes train, validation and test
tiles. The full dataset contains 558 negative tiles; the generated preview
sample happened not to select a negative tile.

## Tests

Targeted pipeline suite: **8 passed**.

The full 1,012-source generation and QA completed. MODEL_C9 training was not
started.

MODEL_C8 unchanged  
GEE unchanged  
Indices unchanged (NDVI, NDWI, NDBI, BSI, SAVI)  
Classifications unchanged  
Exports unchanged  
Frontend unchanged  
Production API unchanged  
Offline mode unchanged  
Production cache unchanged

## Stop point

This step is complete. The pipeline is intentionally stopped here pending a
separate decision to train MODEL_C9.
