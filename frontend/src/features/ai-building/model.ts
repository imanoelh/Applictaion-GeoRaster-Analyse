import { z } from "zod";

export type BuildingSourceMode = "sentinel2" | "orthophoto";
export type BuildingModelId = "unet_resnet34" | "spacenet2_deeplab" | "whu_unetplusplus_effb4" | "whu_unetplusplus_effb4_onnx" | "hybrid_model_c_model_d" | "model_c8_hybrid";

export type BuildingDetectionParameters = {
  model_id: BuildingModelId;
  probability_threshold: number;
  tile_size: number;
  overlap_ratio: number;
  min_object_pixels: number;
  max_hole_pixels: number;
  opening_enabled: boolean;
  closing_enabled: boolean;
  morphology_kernel_size: number;
  morphology_iterations: number;
};

export const DEFAULT_BUILDING_PARAMETERS: BuildingDetectionParameters = {
  model_id: "spacenet2_deeplab",
  probability_threshold: 0.5,
  tile_size: 512,
  overlap_ratio: 0.2,
  min_object_pixels: 4,
  max_hole_pixels: 0,
  opening_enabled: false,
  closing_enabled: false,
  morphology_kernel_size: 3,
  morphology_iterations: 1,
};

export type Wgs84Bounds = { left: number; bottom: number; right: number; top: number };

export type BuildingFeatureProperties = {
  object_id: string;
  object_type: "building_candidate";
  geometry_type: "Polygon" | "MultiPolygon";
  pixel_count: number;
  area_map_units: number;
  area_m2: number | null;
  perimeter_map_units: number;
  perimeter_m: number | null;
  centroid_native: { x: number; y: number };
  centroid_lon: number;
  centroid_lat: number;
  source: string | null;
  model_name: string;
  model_id?: BuildingModelId;
  model_architecture?: string | null;
  model_checkpoint_hash?: string | null;
  preprocessing_profile?: string | null;
  tile_size?: number | null;
  model_version: string;
  threshold: number;
};

export type GeoJSONGeometry = {
  type: "Polygon" | "MultiPolygon";
  coordinates: unknown;
};

export type BuildingGeoJSONFeature = {
  type: "Feature";
  id: string;
  geometry: GeoJSONGeometry;
  properties: BuildingFeatureProperties;
};

export type GeoJSONFeatureCollection = {
  type: "FeatureCollection";
  features: BuildingGeoJSONFeature[];
};

export type BuildingStatistics = {
  candidate_count: number;
  total_area_map_units: number;
  mean_area_map_units: number | null;
  median_area_map_units: number | null;
  min_area_map_units: number | null;
  max_area_map_units: number | null;
  total_perimeter_map_units: number;
  mean_perimeter_map_units: number | null;
  total_area_m2: number | null;
  mean_area_m2: number | null;
  median_area_m2: number | null;
  min_area_m2: number | null;
  max_area_m2: number | null;
  total_perimeter_m: number | null;
  mean_perimeter_m: number | null;
};

export type BuildingAnalysisResult = {
  success: boolean;
  result_schema_version: "1.0";
  analysis_id: string;
  analysis_type: "ai_object_detection";
  object_type: "building";
  raster_id: string;
  source_type: string | null;
  source_resolution: number[];
  source_crs: string;
  feature_collection_crs: "EPSG:4326";
  native_bounds: Wgs84Bounds;
  wgs84_bounds: Wgs84Bounds;
  model_name: string;
  model_id: BuildingModelId;
  model_architecture: string | null;
  model_checkpoint_hash: string | null;
  tile_size: number | null;
  preprocessing_profile: string | null;
  model_version: string;
  model_mode: string;
  probability_threshold: number;
  postprocessing_version: string;
  polygonization_version: string;
  quality_mode: "integration_test" | "real_model_unvalidated" | string;
  quality_note: string;
  scientific_accuracy_status: "NOT_VALIDATED";
  candidate_count: number;
  statistics: BuildingStatistics;
  feature_collection: GeoJSONFeatureCollection;
  processing_metadata: {
    postprocessing_time_ms: number;
    polygonization_time_ms: number;
    results_build_time_ms: number;
    geojson_serialization_time_ms: number;
    polygonization_config: Record<string, unknown>;
    postprocessing_config: Record<string, unknown>;
    model_c_inference_time_ms?: number | null;
    model_d_inference_time_ms?: number | null;
    fusion_time_ms?: number | null;
    total_processing_time_ms?: number | null;
  };
  model_metadata: Record<string, unknown>;
};

export type AIRasterPrepareResult = {
  success: boolean;
  source: string;
  raster_id: string;
  quality_mode: string;
  warning: string;
  metadata?: Record<string, unknown>;
  validation: {
    valid: boolean;
    source_type: string | null;
    source_profile: string | null;
    bands: number;
    crs: string;
    width: number;
    height: number;
    resolution_x: number;
    resolution_y: number;
    dtype: string;
  };
};

const nullableNumber = z.number().finite().nullable();
const boundsSchema = z.object({
  left: z.number().finite(),
  bottom: z.number().finite(),
  right: z.number().finite(),
  top: z.number().finite(),
});
const statisticsSchema = z.object({
  candidate_count: z.number().int().nonnegative(),
  total_area_map_units: z.number().finite(),
  mean_area_map_units: nullableNumber,
  median_area_map_units: nullableNumber,
  min_area_map_units: nullableNumber,
  max_area_map_units: nullableNumber,
  total_perimeter_map_units: z.number().finite(),
  mean_perimeter_map_units: nullableNumber,
  total_area_m2: nullableNumber,
  mean_area_m2: nullableNumber,
  median_area_m2: nullableNumber,
  min_area_m2: nullableNumber,
  max_area_m2: nullableNumber,
  total_perimeter_m: nullableNumber,
  mean_perimeter_m: nullableNumber,
});
const featureSchema = z.object({
  type: z.literal("Feature"),
  id: z.string().min(1),
  geometry: z.object({
    type: z.enum(["Polygon", "MultiPolygon"]),
    coordinates: z.unknown(),
  }),
  properties: z.object({
    object_id: z.string().min(1),
    object_type: z.literal("building_candidate"),
    geometry_type: z.enum(["Polygon", "MultiPolygon"]),
    pixel_count: z.number().int().nonnegative(),
    area_map_units: z.number().finite(),
    area_m2: nullableNumber,
    perimeter_map_units: z.number().finite(),
    perimeter_m: nullableNumber,
    centroid_native: z.object({ x: z.number().finite(), y: z.number().finite() }),
    centroid_lon: z.number().finite(),
    centroid_lat: z.number().finite(),
    source: z.string().nullable(),
    model_name: z.string(),
    model_id: z.enum(["unet_resnet34", "spacenet2_deeplab", "whu_unetplusplus_effb4", "whu_unetplusplus_effb4_onnx", "hybrid_model_c_model_d", "model_c8_hybrid"]).optional().default("unet_resnet34"),
    model_architecture: z.string().nullable().optional().default(null),
    model_checkpoint_hash: z.string().nullable().optional().default(null),
    preprocessing_profile: z.string().nullable().optional().default(null),
    tile_size: z.number().int().nullable().optional().default(null),
    model_version: z.string(),
    threshold: z.number().min(0).max(1),
  }),
});

export const buildingAnalysisResultSchema: z.ZodType<BuildingAnalysisResult> = z.object({
  success: z.boolean(),
  result_schema_version: z.literal("1.0"),
  analysis_id: z.string().min(1),
  analysis_type: z.literal("ai_object_detection"),
  object_type: z.literal("building"),
  raster_id: z.string().min(1),
  source_type: z.string().nullable(),
  source_resolution: z.array(z.number().positive()).min(2),
  source_crs: z.string().min(1),
  feature_collection_crs: z.literal("EPSG:4326"),
  native_bounds: boundsSchema,
  wgs84_bounds: boundsSchema,
  model_name: z.string(),
  model_id: z.enum(["unet_resnet34", "spacenet2_deeplab", "whu_unetplusplus_effb4", "whu_unetplusplus_effb4_onnx", "hybrid_model_c_model_d", "model_c8_hybrid"]).optional().default("unet_resnet34"),
  model_architecture: z.string().nullable().optional().default(null),
  model_checkpoint_hash: z.string().nullable().optional().default(null),
  tile_size: z.number().int().nullable().optional().default(null),
  preprocessing_profile: z.string().nullable().optional().default(null),
  model_version: z.string(),
  model_mode: z.string(),
  probability_threshold: z.number().min(0).max(1),
  postprocessing_version: z.string(),
  polygonization_version: z.string(),
  quality_mode: z.string(),
  quality_note: z.string(),
  scientific_accuracy_status: z.literal("NOT_VALIDATED"),
  candidate_count: z.number().int().nonnegative(),
  statistics: statisticsSchema,
  feature_collection: z.object({
    type: z.literal("FeatureCollection"),
    features: z.array(featureSchema),
  }),
  processing_metadata: z.object({
    postprocessing_time_ms: z.number().nonnegative(),
    polygonization_time_ms: z.number().nonnegative(),
    results_build_time_ms: z.number().nonnegative(),
    geojson_serialization_time_ms: z.number().nonnegative(),
    polygonization_config: z.record(z.string(), z.unknown()),
    postprocessing_config: z.record(z.string(), z.unknown()),
    model_c_inference_time_ms: z.number().nonnegative().nullable().optional(),
    model_d_inference_time_ms: z.number().nonnegative().nullable().optional(),
    fusion_time_ms: z.number().nonnegative().nullable().optional(),
    total_processing_time_ms: z.number().nonnegative().nullable().optional(),
  }),
  model_metadata: z.record(z.string(), z.unknown()).optional().default({}),
});

export function parseBuildingAnalysisResult(value: unknown): BuildingAnalysisResult {
  return buildingAnalysisResultSchema.parse(value);
}

export function isValidWgs84Bounds(bounds: Wgs84Bounds | null | undefined): bounds is Wgs84Bounds {
  return Boolean(
    bounds &&
    [bounds.left, bounds.bottom, bounds.right, bounds.top].every(Number.isFinite) &&
    bounds.left >= -180 &&
    bounds.right <= 180 &&
    bounds.bottom >= -90 &&
    bounds.top <= 90 &&
    bounds.left < bounds.right &&
    bounds.bottom < bounds.top,
  );
}

export function buildingQualityLabel(mode: string, language: "en" | "ar") {
  if (mode === "integration_test")
    return language === "ar" ? "وضع اختبار التكامل" : "Integration test mode";
  return language === "ar"
    ? "نموذج حقيقي — الدقة غير مُتحقق منها بعد"
    : "Real model — accuracy not yet validated";
}

export function buildingSourceNotice(source: BuildingSourceMode, language: "en" | "ar") {
  if (source === "sentinel2")
    return language === "ar"
      ? "تُستخدم Sentinel-2 بدقة 10 م هنا لاختبار التكامل. الدقة غير كافية لضمان كشف فردي موثوق للمباني."
      : "Sentinel-2 at 10 m is used here as an integration-test source. Its resolution is insufficient to guarantee reliable individual building detection.";
  return language === "ar"
    ? "يُنصح بمصدر عالي الدقة لكشف المباني. الصيغة الحالية: GeoTIFF RGB، ثلاث حزم، uint8، مع CRS وإسناد جغرافي."
    : "A high-resolution source is recommended for Building detection. Current format: RGB GeoTIFF, 3 bands, uint8, with CRS and georeferencing.";
}

export function buildingErrorMessage(error: unknown, language: "en" | "ar") {
  const raw = error instanceof Error ? error.message : String(error ?? "");
  const status = error instanceof Error && "status" in error ? Number(error.status) : NaN;
  if (import.meta.env?.DEV && Number.isInteger(status) && status > 0) {
    return `HTTP ${status}: ${raw}`;
  }
  const code = raw.match(/\b[A-Z][A-Z0-9_]{3,}\b/)?.[0] ?? "";
  const en: Record<string, string> = {
    MODEL_NOT_CONFIGURED: "The Building model is not configured on the server.",
    MODEL_NOT_FOUND: "The selected Building model is not available.",
    MODEL_FILE_NOT_FOUND: "The selected Building model checkpoint is missing on the server.",
    MODEL_LOAD_FAILED: "The Building model could not be loaded.",
    HYBRID_ALIGNMENT_ERROR: "The MODEL_C and MODEL_D raster masks do not align; the hybrid run was stopped.",
    HYBRID_INFERENCE_MODE_UNSUPPORTED: "The hybrid model supports the standard inference mode only.",
    LOCAL_RASTER_INVALID: "The local GeoTIFF is invalid or unsupported.",
    UNSUPPORTED_RASTER_DTYPE: "The raster must be an RGB uint8 GeoTIFF.",
    RASTER_CRS_MISSING: "The raster must include a valid CRS.",
    INFERENCE_FAILED: "The AI inference failed. Check the raster and try again.",
    POSTPROCESSING_RASTER_TOO_LARGE: "This raster is too large for the available processing strategy.",
    RASTER_TOO_LARGE_FOR_IN_MEMORY_PROCESSING: "This raster is too large for in-memory processing.",
    INSUFFICIENT_DISK_SPACE: "There is not enough temporary disk space to process this raster.",
    POSTPROCESSING_FAILED: "Building mask post-processing failed.",
    POLYGONIZATION_FAILED: "Building polygonization failed while creating map features.",
    ANALYSIS_TIMEOUT: "The Building analysis timed out. Try a smaller area.",
    AI_REQUEST_TIMEOUT: "The Building analysis exceeded its time limit. Try a smaller area.",
    INVALID_BUILDING_RESPONSE: "The server returned an invalid Building result.",
  };
  let message = en[code] ?? "The Building analysis could not be completed.";
  if (code === "LOCAL_RASTER_INVALID") {
    const normalized = raw.toLowerCase();
    if (normalized.includes("taille maximale") || normalized.includes("maximum") || normalized.includes("octets")) {
      message = "The selected GeoTIFF exceeds the 512 MiB upload limit. Use a 3-band RGB uint8 derivative or a smaller crop.";
    } else if (normalized.includes("exactement trois") || normalized.includes("8 bandes") || normalized.includes("bandes rgb")) {
      message = "The selected GeoTIFF is multispectral. Building import requires exactly 3 RGB uint8 bands.";
    } else if (normalized.includes("content-type")) {
      message = "The selected file was not sent as a GeoTIFF. Choose a .tif or .tiff file.";
    }
  }
  if (language === "en") return message;
  const ar: Record<string, string> = {
    MODEL_NOT_CONFIGURED: "نموذج المباني غير مُعدّ على الخادم.",
    MODEL_LOAD_FAILED: "تعذّر تحميل نموذج المباني.",
    LOCAL_RASTER_INVALID: "ملف GeoTIFF المحلي غير صالح أو غير مدعوم.",
    UNSUPPORTED_RASTER_DTYPE: "يجب أن يكون الراستر GeoTIFF RGB من نوع uint8.",
    RASTER_CRS_MISSING: "يجب أن يحتوي الراستر على نظام إحداثيات صالح.",
    INFERENCE_FAILED: "فشل استدلال الذكاء الاصطناعي. تحقق من الراستر وحاول مجددًا.",
    AI_REQUEST_TIMEOUT: "تجاوز تحليل المباني المهلة الزمنية. جرّب مساحة أصغر.",
    INVALID_BUILDING_RESPONSE: "أعاد الخادم نتيجة مبانٍ غير صالحة.",
  };
  return ar[code] ?? en[code] ?? "تعذّر إكمال تحليل المباني.";
}

export const BUILDING_LAYER_STYLE = {
  normal: { color: "#7c3aed", weight: 2, fillColor: "#c4b5fd", fillOpacity: 0.28 },
  hover: { color: "#5b21b6", weight: 3, fillColor: "#a78bfa", fillOpacity: 0.45 },
  selected: { color: "#f59e0b", weight: 4, fillColor: "#fbbf24", fillOpacity: 0.5 },
} as const;

export function buildingPopupFields(properties: BuildingFeatureProperties) {
  return [
    ["ID", properties.object_id],
    ["Type", properties.object_type],
    [
      "Area",
      properties.area_m2 == null
        ? `${properties.area_map_units.toFixed(2)} map units²`
        : `${properties.area_m2.toFixed(2)} m²`,
    ],
    [
      "Perimeter",
      properties.perimeter_m == null
        ? `${properties.perimeter_map_units.toFixed(2)} map units`
        : `${properties.perimeter_m.toFixed(2)} m`,
    ],
    ["Pixels", properties.pixel_count.toLocaleString()],
    ["Model", `${properties.model_name} ${properties.model_version}`.trim()],
    ["Threshold", properties.threshold.toFixed(2)],
  ] as const;
}
