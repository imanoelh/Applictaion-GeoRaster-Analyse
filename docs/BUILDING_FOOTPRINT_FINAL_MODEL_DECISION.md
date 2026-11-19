# GeoRaster — Final Building Footprint model decision

## Selected model

**MODEL_C — DeepLabV3 / ResNet-50, ONNX Runtime CPU** remains the general production model and the default Building Detection engine.

The independent TEST comparison confirms that MODEL_C is strongest for industrial roofs, large roofs, boundary quality and production stability. MODEL_F is retained as an experimental residential/high-recall alternative. MODEL_F2 is retained as an experimental fine-tuning artifact; it has lower false-positive component count and faster CPU inference, but it does not generalize better on the locked TEST set. MODEL_D and MODEL_D_ONNX remain experimental high-recall/slow engines. MODEL_E is benchmark-only.

## Production pipeline validated

Orthophoto ingestion, RGB preprocessing, 512-pixel tiling, MODEL_C ONNX inference, binary mask creation, overlap fusion, polygonization, georeferencing, statistics, map display and GeoJSON/CSV/metadata/ZIP export are connected through the existing production services. The 2048 and 4096 validation artifacts have valid non-empty polygons, no exact duplicate geometries, and matching source transforms and bounds.

## Strengths and limitations

- Strengths: industrial IoU and recall, boundary quality, stable production path, correct georeferencing, and deterministic exports.
- Limitations: residential performance is weaker than MODEL_F; boundaries can remain diffuse by a few pixels; full-raster CPU processing is slow (historical reference approximately 26 minutes).
- No model or registry change is made by this validation.

## Experimental alternatives

MODEL_F remains useful for residential/high-recall experiments. MODEL_F2 is not a general replacement after the independent TEST. MODEL_D/D_ONNX remain slow experimental alternatives, and MODEL_E remains benchmark-only.

The final user acceptance action is to run the normal Building Detection workflow with MODEL_C selected by default.
