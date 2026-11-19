import type { CanonicalRasterPayload } from "@/lib/georaster-contract";
import {
  parseBuildingAnalysisResult,
  type AIRasterPrepareResult,
  type BuildingAnalysisResult,
  type BuildingDetectionParameters,
} from "@/features/ai-building/model";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8010";

export type AoiBBox = [[number, number], [number, number]];

export type SearchImagesPayload = CanonicalRasterPayload & {
  // Deprecated compatibility fields. Prefer the canonical fields above.
  source?: "S2_SR_HARMONIZED" | "S1_GRD";
  date_start?: string;
  date_end?: string;
  max_cloud_pct?: number;
  aoi?: { bbox: AoiBBox };
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    let message = detail;
    try {
      const parsed = JSON.parse(detail) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        message = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        message = parsed.detail
          .map((item) =>
            typeof item === "object" && item && "msg" in item
              ? String((item as any).msg)
              : String(item),
          )
          .join("; ");
      } else if (parsed.detail && typeof parsed.detail === "object") {
        const publicDetail = parsed.detail as { code?: unknown; message?: unknown };
        const code = typeof publicDetail.code === "string" ? publicDetail.code : "";
        const detailMessage = typeof publicDetail.message === "string" ? publicDetail.message : "";
        if (code || detailMessage) message = `${code}${code && detailMessage ? ": " : ""}${detailMessage}`;
      }
    } catch {
      // Keep raw response text when the body is not JSON.
    }
    const error = new Error(message || `API ${response.status} on ${path}`);
    Object.assign(error, { status: response.status });
    throw error;
  }

  return response.json() as Promise<T>;
}

export async function prepareGeeBuildingRaster(
  payload: Omit<CanonicalRasterPayload, "analysis_type"> & {
    analysis_type?: string;
    image_id?: string;
  },
) {
  return request<AIRasterPrepareResult>("/api/ai/raster/prepare", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadLocalBuildingRaster(
  file: File,
  onProgress?: (progress: { phase: "uploading" | "preparing"; ratio: number }) => void,
) {
  const standardLimit = 512 * 1024 * 1024;
  if (file.size > standardLimit) {
    const initResponse = await fetch(
      `${API_BASE_URL}/api/ai/raster/local/maxar/init?filename=${encodeURIComponent(file.name)}&size_bytes=${file.size}`,
      { method: "POST" },
    );
    if (!initResponse.ok) throw new Error(await parseRasterUploadError(initResponse));
    const upload = (await initResponse.json()) as { upload_id: string; chunk_size: number };
    const totalChunks = Math.ceil(file.size / upload.chunk_size);
    for (let index = 0; index < totalChunks; index += 1) {
      const start = index * upload.chunk_size;
      const chunk = file.slice(start, Math.min(file.size, start + upload.chunk_size));
      let response: Response | null = null;
      let body = "";
      for (let attempt = 0; attempt < 2; attempt += 1) {
        response = await fetch(
          `${API_BASE_URL}/api/ai/raster/local/maxar/${encodeURIComponent(upload.upload_id)}/chunk?index=${index}&total_chunks=${totalChunks}`,
          { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: chunk },
        );
        if (response.ok) break;
        body = await response.text();
      }
      if (!response?.ok) throw new Error(body || "UPLOAD_CHUNK_FAILED");
      onProgress?.({ phase: "uploading", ratio: (index + 1) / totalChunks });
    }
    onProgress?.({ phase: "preparing", ratio: 0 });
    const complete = await fetch(
      `${API_BASE_URL}/api/ai/raster/local/maxar/${encodeURIComponent(upload.upload_id)}/complete`,
      { method: "POST" },
    );
    if (!complete.ok) throw new Error(await parseRasterUploadError(complete));
    onProgress?.({ phase: "preparing", ratio: 1 });
    return complete.json() as Promise<AIRasterPrepareResult>;
  }
  const response = await fetch(
    `${API_BASE_URL}/api/ai/raster/local?filename=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      headers: { "Content-Type": file.type || "image/tiff" },
      body: file,
    },
  );
  if (!response.ok) {
    throw new Error(await parseRasterUploadError(response));
  }
  return response.json() as Promise<AIRasterPrepareResult>;
}

async function parseRasterUploadError(response: Response) {
  const body = await response.text();
  let message = body;
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    const detail = parsed.detail;
    if (detail && typeof detail === "object") {
      const code = "code" in detail ? String((detail as any).code ?? "") : "";
      const detailMessage = "message" in detail ? String((detail as any).message ?? "") : "";
      if (code || detailMessage) message = `${code}: ${detailMessage}`.replace(/: $/, "");
    } else if (typeof detail === "string" && detail.trim()) message = detail;
  } catch {
    // Preserve raw response text when the server did not return JSON.
  }
  return message || `LOCAL_RASTER_INVALID: API ${response.status}`;
}

export async function runBuildingDetection(
  rasterId: string,
  parameters: BuildingDetectionParameters,
  timeoutMs = 10 * 60 * 1000,
): Promise<BuildingAnalysisResult> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort("AI_REQUEST_TIMEOUT"), timeoutMs);
  try {
    const raw = await request<unknown>("/api/ai/results/building", {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({ raster_id: rasterId, ...parameters }),
    });
    try {
      return parseBuildingAnalysisResult(raw);
    } catch {
      throw new Error("INVALID_BUILDING_RESPONSE");
    }
  } catch (error) {
    if (controller.signal.aborted) throw new Error("AI_REQUEST_TIMEOUT");
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export type BuildingExportFormat = "geojson" | "csv" | "metadata" | "zip";

export async function downloadBuildingExport(
  result: BuildingAnalysisResult,
  format: BuildingExportFormat,
): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/ai/results/building/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, result }),
  });
  if (!response.ok) {
    const detail = await response.text();
    let message = detail;
    try {
      const parsed = JSON.parse(detail) as { detail?: unknown };
      if (typeof parsed.detail === "string") message = parsed.detail;
    } catch {
      // Preserve the response body when the server did not return JSON.
    }
    throw new Error(message || `AI_BUILDING_EXPORT_FAILED: API ${response.status}`);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const asciiName = disposition.match(/filename="([^"]+)"/i)?.[1];
  const fallback = `georaster_ai_building_candidates_${result.analysis_id}.${format}`;
  const filename = utf8Name ? decodeURIComponent(utf8Name) : asciiName || fallback;
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
  return filename;
}

export async function getGeeStatus() {
  return request<{
    item: {
      enabled: boolean;
      project: string | null;
      account: string | null;
      error: string | null;
    };
  }>("/api/gee/status");
}

export async function getCatalogImages(filters?: {
  sensor?: string;
  region?: string;
  max_cloud?: number;
  q?: string;
}) {
  const params = new URLSearchParams();
  if (filters?.sensor) params.set("sensor", filters.sensor);
  if (filters?.region) params.set("region", filters.region);
  if (filters?.max_cloud != null) params.set("max_cloud", String(filters.max_cloud));
  if (filters?.q) params.set("q", filters.q);
  const query = params.toString();
  return request<{ items: any[] }>(`/api/catalog/images${query ? `?${query}` : ""}`);
}

export async function searchImages(payload: SearchImagesPayload) {
  return request<{
    items: any[];
    scenes?: any[];
    mosaic?: any;
    mode?: string;
    gee?: any;
    warning?: string;
    count?: number;
  }>("/api/catalog/images/search?limit=12", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getGeeScenePreview(payload: SearchImagesPayload & { scene_id: string }) {
  return request<{
    item: { image?: any; preview?: { tile_url?: string | null }; warning?: string };
  }>("/api/gee/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type GeeCatalogJobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "error";
  progress_percent: number;
  current_step?: string;
  status_message?: string;
  message?: string;
  error?: string | null;
  result?: {
    items: any[];
    scenes?: any[];
    mosaic?: any;
    mode?: string;
    gee?: any;
    warning?: string;
    count?: number;
  } | null;
};

export async function startGeeCatalogJob(payload: SearchImagesPayload) {
  return request<GeeCatalogJobStatus>("/api/gee/jobs/catalog?limit=12", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getGeeCatalogJobStatus(jobId: string) {
  return request<GeeCatalogJobStatus>(`/api/gee/jobs/${encodeURIComponent(jobId)}/status`);
}

export type AoiSplitPart = {
  part_id: string;
  row: number;
  column: number;
  geojson: { type: "Polygon" | "MultiPolygon"; coordinates: any };
  bbox: [number, number, number, number];
  area_km2: number;
  area_share: number;
};

export type AoiSplitResponse = {
  parts: number;
  mode: "auto" | "manual";
  cells_along_length: number;
  grid: { rows: number; columns: number };
  total_area_km2: number;
  items: AoiSplitPart[];
};

// `parts` is optional: the backend lays `cells_along_length` cells (7 by
// default) along the longest side of the AOI and keeps the cells square.
export async function splitAoi(
  geometry: unknown,
  options?: { parts?: number | "auto"; cellsAlongLength?: number },
) {
  return request<AoiSplitResponse>("/api/aoi/split", {
    method: "POST",
    body: JSON.stringify({
      geometry,
      parts: options?.parts ?? "auto",
      cells_along_length: options?.cellsAlongLength,
    }),
  });
}

export async function createAnalysis(payload: any) {
  return request<{ item: any }>("/api/analyses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runAnalysis(analysisId: string, force = false) {
  return request<{ item: any }>(`/api/analyses/${analysisId}/run${force ? "?force=true" : ""}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export type AnalysisJobStatus = {
  job_id: string;
  analysis_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress_percent: number;
  message?: string;
  error?: string | null;
  run?: any | null;
  run_id?: string | null;
  processing_policy?: Record<string, any>;
};

export async function startAnalysisJob(analysisId: string, force = false) {
  return request<AnalysisJobStatus>(
    `/api/jobs/analyses?analysis_id=${encodeURIComponent(analysisId)}&force=${String(force)}`,
    {
      method: "POST",
      body: JSON.stringify({}),
    },
  );
}

export async function getAnalysisJob(jobId: string) {
  return request<AnalysisJobStatus>(`/api/jobs/analyses/${encodeURIComponent(jobId)}`);
}

export async function getRunResult(runId: string) {
  return request<{ item: any }>(`/api/runs/${runId}/result`);
}

export async function getRunTiles(
  runId: string,
  options?: { refresh?: boolean; includeRgb?: boolean },
) {
  const params = new URLSearchParams();
  if (options?.refresh != null) params.set("refresh", String(options.refresh));
  if (options?.includeRgb != null) params.set("include_rgb", String(options.includeRgb));
  const query = params.toString();
  return request<{
    item: {
      run_id: string;
      rgb_tile_url?: string | null;
      index_tile_url?: string | null;
      comparison_layers?: any[];
      tile_source_palette?: string[] | null;
      opacity?: number;
      mode?: string | null;
      source?: string | null;
      refreshed?: boolean;
      refresh_error?: string | null;
    };
  }>(`/api/runs/${runId}/tiles${query ? `?${query}` : ""}`);
}

export async function updateUnsupervisedCluster(
  runId: string,
  code: number,
  updates: { name?: string; color?: string },
) {
  return request<{ item: any }>(
    `/api/runs/${encodeURIComponent(runId)}/clusters/${encodeURIComponent(String(code))}/rename`,
    {
      method: "POST",
      body: JSON.stringify(updates),
    },
  );
}

export async function renameUnsupervisedCluster(runId: string, code: number, name: string) {
  return updateUnsupervisedCluster(runId, code, { name });
}

export async function searchResultCache(payload: any) {
  return request<{ items: any[]; item: any | null; context_key: string; cache_key: string }>(
    "/api/result-cache/search",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function deleteResultCache(cacheKey: string) {
  return request<{ deleted: boolean; cache_key: string }>(
    `/api/result-cache/${encodeURIComponent(cacheKey)}`,
    {
      method: "DELETE",
    },
  );
}

export async function getAnalysisHistory() {
  return request<{ items: any[] }>("/api/history");
}

export async function getLandcoverClasses(projectId = "default") {
  return request<{ items: any[] }>(
    `/api/classification/classes?project_id=${encodeURIComponent(projectId)}`,
  );
}

export async function createLandcoverClass(payload: {
  project_id?: string;
  code: number;
  name: string;
  color: string;
  description?: string;
}) {
  return request<{ item: any }>("/api/classification/classes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createTrainingSample(payload: any) {
  return request<{ item: any }>("/api/classification/samples", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTrainingSamples(projectId = "default") {
  return request<{ items: any[] }>(
    `/api/classification/samples?project_id=${encodeURIComponent(projectId)}`,
  );
}

export async function updateTrainingSample(
  sampleId: string,
  updates: { class_id?: string; usage?: "training" | "validation" },
) {
  return request<{ item: any }>(`/api/classification/samples/${encodeURIComponent(sampleId)}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteTrainingSample(sampleId: string) {
  return request<{ deleted: boolean; id: string }>(
    `/api/classification/samples/${encodeURIComponent(sampleId)}`,
    {
      method: "DELETE",
    },
  );
}

export async function deleteTrainingSamplesForClass(classId: string, projectId = "default") {
  return request<{ deleted: boolean; class_id: string; samples_deleted: number }>(
    `/api/classification/classes/${encodeURIComponent(classId)}/samples?project_id=${encodeURIComponent(projectId)}`,
    { method: "DELETE" },
  );
}

export async function deleteAnalysis(analysisId: string) {
  return request<{ deleted: boolean; id: string }>(
    `/api/analyses/${encodeURIComponent(analysisId)}`,
    {
      method: "DELETE",
    },
  );
}

export async function createExport(
  runId: string,
  kind: "stats_csv" | "stats_json" | "report_pdf" | "map_png" | "geotiff",
  layerKey?: string | null,
  language: "en" | "ar" = "en",
) {
  return request<{ item: { id: string; filename: string } }>(`/api/runs/${runId}/export`, {
    method: "POST",
    body: JSON.stringify({ kind, layer_key: layerKey ?? null, language }),
  });
}

export type MapPdfExportPayload = {
  analysis_id?: string | null;
  analysis_type: string;
  language?: "en" | "ar";
  geometry_info?: Record<string, any>;
  parameters?: Record<string, any>;
  map_screenshot: string;
  locator_screenshot?: string | null;
  legend?: any[];
  statistics?: Record<string, any>;
  histogram?: any[];
  classes?: any[];
  quality_summary?: Record<string, any>;
  interpretation?: string | null;
  user_name?: string | null;
  metadata?: Record<string, any>;
};

export async function createMapPdfExport(payload: MapPdfExportPayload) {
  return request<{ success: boolean; pdf_url: string; filename: string; message: string }>(
    "/api/export/map-pdf",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function createMapLayoutPngExport(payload: MapPdfExportPayload) {
  return request<{ success: boolean; image_url: string; filename: string; message: string }>(
    "/api/export/map-layout-png",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function downloadExport(exportId: string) {
  window.location.href = `${API_BASE_URL}/api/exports/${exportId}/download`;
}

export function downloadApiFile(url: string) {
  window.location.href = /^https?:\/\//i.test(url) ? url : `${API_BASE_URL}${url}`;
}

export type ProjectionMode = "automatic" | "manual";

export type CrsDescriptor = {
  code: string | null;
  name: string;
  unit: string | null;
  utm_zone: number | null;
  selection_mode?: string | null;
  type?: string;
  dimension?: number;
  horizontal_unit?: string | null;
  vertical_unit?: string | null;
  axes?: string[];
  status?: string;
  capabilities?: Record<string, boolean>;
};

export type SpatialReferenceSettings = {
  national_system?: string;
  reference_frame?: string;
  input_crs?: string;
  web_map_crs: string;
  analysis_crs: string | null;
  analysis_crs_name: string;
  utm_zone: number | null;
  unit: string | null;
  selection_mode: string;
  selection_method: string;
  projection_mode: ProjectionMode;
  configured_analysis_crs?: string | null;
  crosses_utm_zone?: boolean;
  warning?: string | null;
  center_longitude?: number | null;
  center_latitude?: number | null;
  grid_signature?: string | null;
  status?: string | null;
};

export type PlatformSettings = {
  platform_name: string;
  logo_url: string | null;
  user_profile: {
    name: string;
    email: string;
  };
  default_basemap: "osm" | "satellite" | "googleSatellite" | "terrain" | "light";
  export_format: "geotiff" | "png" | "pdf" | "csv";
  measurement_unit: "ha" | "km2" | "m2";
  backend_connection: {
    raster_server: string;
    endpoint: string;
    api_key: string;
  };
  projection_mode: ProjectionMode;
  web_map_crs: "EPSG:3857";
  analysis_crs: "AUTO_KSA_GRF17";
  manual_crs:
    | "EPSG:9333"
    | "EPSG:9356"
    | "EPSG:9357"
    | "EPSG:9358"
    | "EPSG:9359"
    | "EPSG:9360"
    | null;
  simulation_3d_enabled?: boolean;
  simulation_3d_crs?: "EPSG:9332";
  coordinate_reference?: {
    web_map_crs: CrsDescriptor;
    analysis_choices: CrsDescriptor[];
    simulation_3d?: CrsDescriptor;
    effective: SpatialReferenceSettings;
  };
};

const PLATFORM_SETTINGS_CACHE_KEY = "georaster.platformSettings";

function applyPlatformLogoCacheToDocument(settings: PlatformSettings) {
  if (typeof document === "undefined") return;
  const logoUrl = resolveApiAssetUrl(settings.logo_url);
  if (logoUrl) {
    document.documentElement.dataset.platformLogoCache = "true";
    document.documentElement.style.setProperty(
      "--georaster-platform-logo-url",
      `url("${logoUrl.replaceAll('"', '\\"')}")`,
    );
  } else {
    delete document.documentElement.dataset.platformLogoCache;
    document.documentElement.style.removeProperty("--georaster-platform-logo-url");
  }
}

export function readCachedPlatformSettings(): PlatformSettings | null {
  if (typeof window === "undefined") return null;
  try {
    const cached = window.localStorage.getItem(PLATFORM_SETTINGS_CACHE_KEY);
    return cached ? (JSON.parse(cached) as PlatformSettings) : null;
  } catch {
    return null;
  }
}

function cachePlatformSettings(settings: PlatformSettings) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PLATFORM_SETTINGS_CACHE_KEY, JSON.stringify(settings));
    applyPlatformLogoCacheToDocument(settings);
  } catch {
    // Ignore cache errors; backend settings remain the source of truth.
  }
}

export function resolveApiAssetUrl(url?: string | null) {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_BASE_URL}${url}`;
}

export async function getPlatformSettings() {
  const settings = await request<PlatformSettings>("/api/settings/platform");
  cachePlatformSettings(settings);
  return settings;
}

export async function updatePlatformSettings(payload: PlatformSettings) {
  const settings = await request<PlatformSettings>("/api/settings/platform", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  cachePlatformSettings(settings);
  return settings;
}

export async function uploadPlatformLogo(file: File) {
  const response = await fetch(`${API_BASE_URL}/api/settings/logo`, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-User-Role": "admin",
    },
    body: file,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`API ${response.status} on /api/settings/logo: ${detail}`);
  }
  const result = (await response.json()) as {
    success: boolean;
    logo_url: string | null;
    message: string;
  };
  const cached = readCachedPlatformSettings();
  cachePlatformSettings({
    ...(cached ?? (await getPlatformSettings())),
    logo_url: result.logo_url,
  });
  return result;
}

export async function resetPlatformLogo() {
  const result = await request<{ success: boolean; logo_url: string | null; message: string }>(
    "/api/settings/logo/reset",
    {
      method: "POST",
      headers: { "X-User-Role": "admin" },
      body: JSON.stringify({}),
    },
  );
  const cached = readCachedPlatformSettings();
  cachePlatformSettings({
    ...(cached ?? (await getPlatformSettings())),
    logo_url: result.logo_url,
  });
  return result;
}

export function notifyPlatformSettingsUpdated() {
  window.dispatchEvent(new Event("platform-settings-updated"));
}
