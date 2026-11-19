import type {
  BuildingAnalysisResult,
  BuildingGeoJSONFeature,
} from "../../src/features/ai-building/model.ts";

export function createBuildingAnalysisFixture(
  candidateCount = 2,
  qualityMode: "integration_test" | "real_model_unvalidated" = "integration_test",
): BuildingAnalysisResult {
  const features: BuildingGeoJSONFeature[] = Array.from({ length: candidateCount }, (_, index) => {
    const column = index % 50;
    const row = Math.floor(index / 50);
    const left = -6.85 + column * 0.0002;
    const bottom = 33.95 + row * 0.0002;
    const right = left + 0.00012;
    const top = bottom + 0.0001;
    const area = 96 + (index % 17);
    const perimeter = 40 + (index % 11);
    return {
      type: "Feature",
      id: `building-${index + 1}`,
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [left, bottom],
            [right, bottom],
            [right, top],
            [left, top],
            [left, bottom],
          ],
        ],
      },
      properties: {
        object_id: `building-${index + 1}`,
        object_type: "building_candidate",
        geometry_type: "Polygon",
        pixel_count: 24 + (index % 9),
        area_map_units: area,
        area_m2: area,
        perimeter_map_units: perimeter,
        perimeter_m: perimeter,
        centroid_native: { x: (left + right) / 2, y: (bottom + top) / 2 },
        centroid_lon: (left + right) / 2,
        centroid_lat: (bottom + top) / 2,
        source: qualityMode === "integration_test" ? "sentinel2" : "local",
        model_name: "unet_resnet34",
        model_version: "1.0.0",
        threshold: 0.5,
      },
    };
  });
  const areas = features.map((feature) => feature.properties.area_map_units);
  const perimeters = features.map((feature) => feature.properties.perimeter_map_units);
  const totalArea = areas.reduce((sum, value) => sum + value, 0);
  const totalPerimeter = perimeters.reduce((sum, value) => sum + value, 0);
  const sortedAreas = [...areas].sort((a, b) => a - b);
  const middle = Math.floor(sortedAreas.length / 2);
  const median =
    candidateCount === 0
      ? null
      : candidateCount % 2
        ? sortedAreas[middle]
        : (sortedAreas[middle - 1] + sortedAreas[middle]) / 2;

  return {
    success: true,
    result_schema_version: "1.0",
    analysis_id: `analysis-fixture-${candidateCount}`,
    analysis_type: "ai_object_detection",
    object_type: "building",
    raster_id: "raster-fixture-001",
    source_type: qualityMode === "integration_test" ? "sentinel2" : "local",
    source_resolution: qualityMode === "integration_test" ? [10, 10] : [0.2, 0.2],
    source_crs: "EPSG:32629",
    feature_collection_crs: "EPSG:4326",
    native_bounds: { left: 329000, bottom: 3757000, right: 329600, top: 3757600 },
    wgs84_bounds: { left: -6.85, bottom: 33.95, right: -6.83, top: 33.97 },
    model_name: "unet_resnet34",
    model_version: "1.0.0",
    model_mode: "REAL",
    probability_threshold: 0.5,
    postprocessing_version: "1.0",
    polygonization_version: "1.0",
    quality_mode: qualityMode,
    quality_note:
      qualityMode === "integration_test"
        ? "Sentinel-2 integration test; not suitable for individual-building validation."
        : "Real model output; scientific accuracy is not validated.",
    scientific_accuracy_status: "NOT_VALIDATED",
    candidate_count: candidateCount,
    statistics: {
      candidate_count: candidateCount,
      total_area_map_units: totalArea,
      mean_area_map_units: candidateCount ? totalArea / candidateCount : null,
      median_area_map_units: median,
      min_area_map_units: candidateCount ? Math.min(...areas) : null,
      max_area_map_units: candidateCount ? Math.max(...areas) : null,
      total_perimeter_map_units: totalPerimeter,
      mean_perimeter_map_units: candidateCount ? totalPerimeter / candidateCount : null,
      total_area_m2: totalArea,
      mean_area_m2: candidateCount ? totalArea / candidateCount : null,
      median_area_m2: median,
      min_area_m2: candidateCount ? Math.min(...areas) : null,
      max_area_m2: candidateCount ? Math.max(...areas) : null,
      total_perimeter_m: totalPerimeter,
      mean_perimeter_m: candidateCount ? totalPerimeter / candidateCount : null,
    },
    feature_collection: { type: "FeatureCollection", features },
    processing_metadata: {
      postprocessing_time_ms: 12.5,
      polygonization_time_ms: 18.25,
      results_build_time_ms: 3.1,
      geojson_serialization_time_ms: 2.4,
      polygonization_config: { connectivity: 8, simplify_tolerance: 0 },
      postprocessing_config: { min_object_pixels: 4, max_hole_pixels: 0 },
    },
  };
}
