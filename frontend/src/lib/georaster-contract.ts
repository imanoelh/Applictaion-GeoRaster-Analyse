export type SensorId =
  | "sentinel-2"
  | "landsat-8-9"
  | "dynamic-world"
  | "esa-worldcover"
  | "sentinel-1";
export type ResolutionId = "10m" | "20m" | "30m" | "auto";
export type ImageMethod = "median_composite" | "selected_scene";
export type AnalysisType =
  | "spectral_index"
  | "supervised_classification"
  | "unsupervised_classification"
  | `change_detection_${string}`;

export type CanonicalRasterPayload = {
  geometry: Record<string, any>;
  start_date: string;
  end_date: string;
  sensor: SensorId;
  resolution: ResolutionId;
  cloud_max: number;
  image_method?: ImageMethod;
  image_id?: string;
  index?: string;
  analysis_type?: AnalysisType;
  supervised_options?: Record<string, any>;
  unsupervised_options?: Record<string, any>;
  osi_sar_options?: Record<string, any>;
  period_1?: { start_date: string; end_date: string };
  period_2?: { start_date: string; end_date: string };
};

export function analysisTypeForIndex(index: string): AnalysisType {
  if (index === "SUPERVISED_CLASSIFICATION") return "supervised_classification";
  if (index === "UNSUPERVISED_CLASSIFICATION") return "unsupervised_classification";
  if (index.startsWith("CHANGE_"))
    return `change_detection_${index.replace("CHANGE_", "").toLowerCase()}`;
  return "spectral_index";
}

export function supportedSensorsForIndex(index: string): SensorId[] {
  if (index === "OSI_SAR") return ["sentinel-1"];
  return ["sentinel-2", "landsat-8-9"];
}
