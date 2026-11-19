import {
  Archive,
  Bot,
  Building2,
  ChevronDown,
  FileJson,
  FileSpreadsheet,
  Loader2,
  Play,
  Trash2,
  Upload,
} from "lucide-react";
import type { BuildingExportFormat } from "@/lib/georaster-api";
import type {
  AIRasterPrepareResult,
  BuildingAnalysisResult,
  BuildingDetectionParameters,
  BuildingSourceMode,
} from "./model";
import { buildingQualityLabel, buildingSourceNotice } from "./model";

type Props = {
  language: "en" | "ar";
  sourceMode: BuildingSourceMode;
  onSourceModeChange: (source: BuildingSourceMode) => void;
  parameters: BuildingDetectionParameters;
  onParametersChange: (parameters: BuildingDetectionParameters) => void;
  preparedRaster: AIRasterPrepareResult | null;
  uploadedFileName: string | null;
  canUseSentinel: boolean;
  isUploading: boolean;
  uploadProgress?: { phase: "uploading" | "preparing"; ratio: number } | null;
  isRunning: boolean;
  error: string | null;
  result: BuildingAnalysisResult | null;
  layerVisible: boolean;
  exportingFormat: BuildingExportFormat | null;
  onUpload: (file: File) => void;
  onRun: () => void;
  onToggleLayer: (visible: boolean) => void;
  onExport: (format: BuildingExportFormat) => void;
  onClear: () => void;
};

const text = (language: "en" | "ar", en: string, ar: string) => (language === "ar" ? ar : en);

const numberText = (value: number | null, digits = 2) =>
  value == null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: digits });

export function BuildingDetectionPanel({
  language,
  sourceMode,
  onSourceModeChange,
  parameters,
  onParametersChange,
  preparedRaster,
  uploadedFileName,
  canUseSentinel,
  isUploading,
  uploadProgress,
  isRunning,
  error,
  result,
  layerVisible,
  exportingFormat,
  onUpload,
  onRun,
  onToggleLayer,
  onExport,
  onClear,
}: Props) {
  const canRun =
    !isRunning &&
    !isUploading &&
    (sourceMode === "sentinel2" ? canUseSentinel : Boolean(preparedRaster));
  const setParameter = <K extends keyof BuildingDetectionParameters>(
    key: K,
    value: BuildingDetectionParameters[K],
  ) => onParametersChange({ ...parameters, [key]: value });

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-violet-300/60 bg-violet-50/40 p-3 text-xs dark:bg-violet-950/10">
      <div className="flex items-start gap-2">
        <span className="rounded-md bg-violet-600 p-1.5 text-white">
          <Bot className="h-4 w-4" />
        </span>
        <div>
          <p className="font-semibold">
            {text(language, "AI Object Detection", "كشف الأجسام بالذكاء الاصطناعي")}
          </p>
          <p className="text-[11px] text-muted-foreground">
            {text(language, "Buildings", "المباني")}
          </p>
        </div>
      </div>

      <div
        className="grid grid-cols-2 gap-2"
        role="group"
        aria-label={text(language, "Raster source", "مصدر الراستر")}
      >
        <button
          type="button"
          aria-pressed={sourceMode === "sentinel2"}
          onClick={() => onSourceModeChange("sentinel2")}
          className={`rounded-md border px-2 py-2 text-left ${sourceMode === "sentinel2" ? "border-violet-600 bg-violet-600 text-white" : "bg-background"}`}
        >
          Sentinel-2 / GEE
        </button>
        <button
          type="button"
          aria-pressed={sourceMode === "orthophoto"}
          onClick={() => onSourceModeChange("orthophoto")}
          className={`rounded-md border px-2 py-2 text-left ${sourceMode === "orthophoto" ? "border-violet-600 bg-violet-600 text-white" : "bg-background"}`}
        >
          {text(language, "Local orthophoto", "صورة جوية محلية")}
        </button>
      </div>

      <p className="rounded-md border border-amber-300/70 bg-amber-50 px-2 py-2 text-[11px] leading-relaxed text-amber-950">
        {buildingSourceNotice(sourceMode, language)}
      </p>

      <div className="block space-y-1 rounded-md border bg-background p-2">
        <span className="font-medium">{text(language, "Building model", "نموذج المباني")}</span>
        <select
          aria-label={text(language, "Building model", "نموذج المباني")}
          className="w-full rounded-md border bg-background px-2 py-2"
          value={parameters.model_id}
          disabled={isRunning}
          onChange={(event) => {
            const model_id = event.target.value as BuildingDetectionParameters["model_id"];
            onParametersChange({
              ...parameters,
              model_id,
              probability_threshold: model_id === "model_c8_hybrid" ? 0.5 : parameters.probability_threshold,
              min_object_pixels: model_id === "model_c8_hybrid" ? 32 : parameters.min_object_pixels,
              opening_enabled: model_id === "model_c8_hybrid" ? false : parameters.opening_enabled,
              closing_enabled: model_id === "model_c8_hybrid" ? false : parameters.closing_enabled,
            });
          }}
        >
          <option value="spacenet2_deeplab">Standard Building Detection (MODEL_C)</option>
          <option value="model_c8_hybrid">Building AI v2 (MODEL_C8 Hybrid · experimental)</option>
        </select>
        {parameters.model_id === "model_c8_hybrid" && (
          <p className="rounded-md bg-amber-100 px-2 py-1.5 text-[11px] text-amber-950">
            {text(language, "Experimental staging engine. MODEL_C remains the production default.", "محرك تجريبي مرحلي. يبقى MODEL_C هو الافتراضي للإنتاج.")}
          </p>
        )}
      </div>

      <p className="rounded-md border bg-background px-2 py-2 text-[11px] leading-relaxed text-muted-foreground">
        {text(language, "Building Detection uses DeepLabV3 ResNet-50 with 512 px tiles. Candidate results are not scientifically validated.", "يستخدم كشف المباني DeepLabV3 ResNet-50 بفسيفساء 512 بكسل. النتائج المرشحة غير معتمدة علميًا.")}
      </p>

      {sourceMode === "orthophoto" && (
        <div className="space-y-2 rounded-md border bg-background p-2">
          <label className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-md border px-2 py-2 font-medium hover:bg-muted">
            {isUploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {isUploading
              ? text(language, "Uploading...", "جارٍ الرفع...")
              : text(language, "Upload GeoTIFF", "رفع GeoTIFF")}
            <input
              type="file"
              className="sr-only"
              accept=".tif,.tiff,image/tiff,image/geotiff"
              disabled={isUploading || isRunning}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onUpload(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
          {isUploading && uploadProgress && (
            <div className="space-y-1 text-[11px]" aria-live="polite">
              <div className="flex justify-between">
                <span>{uploadProgress.phase === "uploading" ? "Uploading" : "Preparing RGB"}</span>
                <span>{Math.round(uploadProgress.ratio * 100)}%</span>
              </div>
              <progress className="h-1.5 w-full" max={1} value={uploadProgress.ratio} />
            </div>
          )}
          {preparedRaster && (
            <div className="rounded bg-success/10 px-2 py-1.5 text-[11px]">
              {preparedRaster.metadata?.input_source_profile === "maxar_multispectral_p2p98_v1" && (
                <div className="mb-1 font-medium text-violet-700">Maxar multispectral detected · Preparing RGB input automatically</div>
              )}
              <b>{text(language, "Raster ready", "الراستر جاهز")}</b>
              {uploadedFileName && <div className="mt-0.5 break-all">{uploadedFileName}</div>}
              <div className="mt-0.5 break-all font-mono">{preparedRaster.raster_id}</div>
              <div>
                {preparedRaster.validation.width} × {preparedRaster.validation.height} ·{" "}
                {preparedRaster.validation.dtype}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="space-y-2 rounded-md border bg-background p-2">
        <div className="flex items-center justify-between">
          <label htmlFor="building-threshold" className="font-medium">
            {text(language, "Probability threshold", "عتبة الاحتمال")}
          </label>
          <span className="font-mono">{parameters.probability_threshold.toFixed(2)}</span>
        </div>
        <input
          id="building-threshold"
          type="range"
          min={0.05}
          max={0.95}
          step={0.05}
          value={parameters.probability_threshold}
              disabled={isRunning || parameters.model_id === "spacenet2_deeplab" || parameters.model_id === "model_c8_hybrid"}
          onChange={(event) => setParameter("probability_threshold", Number(event.target.value))}
          className="w-full accent-violet-600"
        />
        <details>
          <summary className="flex cursor-pointer list-none items-center justify-between font-medium">
            {text(language, "Advanced parameters", "إعدادات متقدمة")}
            <ChevronDown className="h-3.5 w-3.5" />
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <NumericField
              label="Tile size"
              value={parameters.tile_size}
              min={64}
              max={4096}
              step={64}
              disabled={isRunning || parameters.model_id === "spacenet2_deeplab" || parameters.model_id === "whu_unetplusplus_effb4" || parameters.model_id === "hybrid_model_c_model_d" || parameters.model_id === "model_c8_hybrid"}
              onChange={(value) => setParameter("tile_size", value)}
            />
            <NumericField
              label="Overlap %"
              value={Math.round(parameters.overlap_ratio * 100)}
              min={0}
              max={90}
              step={5}
              disabled={isRunning || parameters.model_id === "whu_unetplusplus_effb4" || parameters.model_id === "hybrid_model_c_model_d" || parameters.model_id === "model_c8_hybrid"}
              onChange={(value) => setParameter("overlap_ratio", value / 100)}
            />
            <NumericField
              label="Min object pixels"
              value={parameters.min_object_pixels}
              min={0}
              max={10000}
              step={1}
              disabled={isRunning}
              onChange={(value) => setParameter("min_object_pixels", value)}
            />
            <NumericField
              label="Max hole pixels"
              value={parameters.max_hole_pixels}
              min={0}
              max={10000}
              step={1}
              disabled={isRunning}
              onChange={(value) => setParameter("max_hole_pixels", value)}
            />
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Toggle
              label="Opening"
              checked={parameters.opening_enabled}
              disabled={isRunning}
              onChange={(value) => setParameter("opening_enabled", value)}
            />
            <Toggle
              label="Closing"
              checked={parameters.closing_enabled}
              disabled={isRunning}
              onChange={(value) => setParameter("closing_enabled", value)}
            />
            <NumericField
              label="Morphology kernel"
              value={parameters.morphology_kernel_size}
              min={1}
              max={15}
              step={2}
              disabled={isRunning}
              onChange={(value) => setParameter("morphology_kernel_size", value)}
            />
            <NumericField
              label="Morphology iterations"
              value={parameters.morphology_iterations}
              min={1}
              max={10}
              step={1}
              disabled={isRunning}
              onChange={(value) => setParameter("morphology_iterations", value)}
            />
          </div>
        </details>
      </div>

      <p className="rounded-md bg-violet-100/70 px-2 py-2 text-[11px] leading-relaxed text-violet-950 dark:bg-violet-950/30 dark:text-violet-100">
        {text(
          language,
          "These results are AI-generated building candidates. Scientific accuracy has not yet been validated on an annotated real orthophoto.",
          "نموذج الذكاء الاصطناعي يعمل، لكن دقته لم تُتحقق بعد على صورة جوية حقيقية مشروحة.",
        )}
      </p>

      <button
        type="button"
        onClick={onRun}
        disabled={!canRun}
        aria-busy={isRunning}
        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-violet-600 px-3 py-2.5 font-semibold text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {isRunning
          ? text(language, "AI analysis in progress...", "تحليل الذكاء الاصطناعي جارٍ...")
          : text(language, "Run Building detection", "تشغيل كشف المباني")}
      </button>
      {!canRun && !isRunning && (
        <p className="text-[11px] text-muted-foreground">
          {sourceMode === "sentinel2"
            ? text(
                language,
                "Select a Sentinel-2 image and an AOI first.",
                "اختر صورة Sentinel-2 ومنطقة اهتمام أولاً.",
              )
            : text(
                language,
                "Upload a compatible orthophoto first.",
                "ارفع صورة جوية متوافقة أولاً.",
              )}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-md bg-destructive/10 px-2 py-2 text-destructive">
          {error}
        </p>
      )}

      {result && (
        <div className="space-y-3 rounded-md border bg-card p-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-semibold">
                {result.candidate_count === 0
                  ? text(
                      language,
                      "Analysis complete. No building candidates detected with the current parameters.",
                      "اكتمل التحليل. لم يتم اكتشاف أي مبانٍ مرشحة بالإعدادات الحالية.",
                    )
                  : text(
                      language,
                      `${result.candidate_count.toLocaleString()} building candidates vectorized`,
                      `${result.candidate_count.toLocaleString()} مبنى مرشح`,
                    )}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {buildingQualityLabel(result.quality_mode, language)}
              </p>
            </div>
            <Building2 className="h-5 w-5 text-violet-600" />
          </div>
          <div className="grid grid-cols-2 gap-2 text-center">
            <Metric
              label={text(language, "Candidates", "المرشحون")}
              value={result.candidate_count.toLocaleString()}
            />
            <Metric
              label={text(language, "Total area", "المساحة الإجمالية")}
              value={
                result.statistics.total_area_m2 == null
                  ? numberText(result.statistics.total_area_map_units)
                  : `${numberText(result.statistics.total_area_m2)} m²`
              }
            />
            <Metric
              label={text(language, "Mean area", "متوسط المساحة")}
              value={
                result.statistics.mean_area_m2 == null
                  ? numberText(result.statistics.mean_area_map_units)
                  : `${numberText(result.statistics.mean_area_m2)} m²`
              }
            />
            <Metric
              label={text(language, "Median area", "وسيط المساحة")}
              value={
                result.statistics.median_area_m2 == null
                  ? numberText(result.statistics.median_area_map_units)
                  : `${numberText(result.statistics.median_area_m2)} m²`
              }
            />
            <Metric
              label={text(language, "Min area", "أدنى مساحة")}
              value={
                result.statistics.min_area_m2 == null
                  ? numberText(result.statistics.min_area_map_units)
                  : `${numberText(result.statistics.min_area_m2)} m²`
              }
            />
            <Metric
              label={text(language, "Max area", "أقصى مساحة")}
              value={
                result.statistics.max_area_m2 == null
                  ? numberText(result.statistics.max_area_map_units)
                  : `${numberText(result.statistics.max_area_m2)} m²`
              }
            />
          </div>
          <label className="flex items-center justify-between rounded-md border px-2 py-2">
            <span>{text(language, "AI Building Candidates layer", "طبقة المباني المرشحة")}</span>
            <input
              type="checkbox"
              checked={layerVisible}
              onChange={(event) => onToggleLayer(event.target.checked)}
            />
          </label>
          <details className="rounded-md border px-2 py-2">
            <summary className="cursor-pointer font-medium">
              {text(language, "Analysis metadata", "بيانات التحليل")}
            </summary>
            <dl className="mt-2 grid grid-cols-[90px_1fr] gap-1 text-[10px]">
              <dt>Source</dt>
              <dd>{result.source_type ?? "—"}</dd>
              <dt>Model</dt>
              <dd>{String(result.model_metadata.display_name ?? result.model_name)}</dd>
              <dt>Status</dt>
              <dd>{String(result.model_metadata.status ?? result.model_mode)}</dd>
              <dt>Tile size</dt>
              <dd>{result.tile_size ?? "—"}</dd>
              <dt>Preprocessing</dt>
              <dd>{result.preprocessing_profile ?? "—"}</dd>
              <dt>Version</dt>
              <dd>{result.model_version}</dd>
              <dt>Threshold</dt>
              <dd>{result.probability_threshold.toFixed(2)}</dd>
              <dt>Analysis ID</dt>
              <dd className="break-all font-mono">{result.analysis_id}</dd>
              <dt>Scientific accuracy</dt>
              <dd>{result.scientific_accuracy_status}</dd>
              {result.model_id === "hybrid_model_c_model_d" && (
                <>
                  <dt>Fusion</dt>
                  <dd>Binary mask union · HYBRID_EXPERIMENTAL</dd>
                  <dt>MODEL_C / D</dt>
                  <dd>{numberText(result.processing_metadata.model_c_inference_time_ms, 0)} / {numberText(result.processing_metadata.model_d_inference_time_ms, 0)} ms</dd>
                  <dt>Fusion time</dt>
                  <dd>{numberText(result.processing_metadata.fusion_time_ms, 2)} ms</dd>
                </>
              )}
            </dl>
          </details>
          <div className="space-y-2 rounded-md border p-2">
            <p className="font-medium">
              {text(language, "Export building candidates", "تصدير المباني المرشحة")}
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              <BuildingExportButton
                label="GeoJSON"
                icon={FileJson}
                format="geojson"
                exportingFormat={exportingFormat}
                onExport={onExport}
              />
              <BuildingExportButton
                label="CSV"
                icon={FileSpreadsheet}
                format="csv"
                exportingFormat={exportingFormat}
                onExport={onExport}
              />
              <BuildingExportButton
                label="Metadata JSON"
                icon={FileJson}
                format="metadata"
                exportingFormat={exportingFormat}
                onExport={onExport}
              />
              <BuildingExportButton
                label="ZIP"
                icon={Archive}
                format="zip"
                exportingFormat={exportingFormat}
                onExport={onExport}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={onClear}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md border px-2 py-2 text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="h-4 w-4" /> {text(language, "Remove result", "إزالة النتيجة")}
          </button>
        </div>
      )}
    </div>
  );
}

function BuildingExportButton({
  label,
  icon: Icon,
  format,
  exportingFormat,
  onExport,
}: {
  label: string;
  icon: typeof FileJson;
  format: BuildingExportFormat;
  exportingFormat: BuildingExportFormat | null;
  onExport: (format: BuildingExportFormat) => void;
}) {
  const isActive = exportingFormat === format;
  return (
    <button
      type="button"
      onClick={() => onExport(format)}
      disabled={exportingFormat !== null}
      aria-busy={isActive}
      className="inline-flex items-center justify-center gap-1 rounded-md border px-2 py-2 text-[11px] font-medium hover:bg-muted disabled:opacity-50"
    >
      {isActive ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Icon className="h-3.5 w-3.5" />
      )}
      {label}
    </button>
  );
}

function NumericField({
  label,
  value,
  min,
  max,
  step,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <label className="space-y-1">
      <span className="text-[10px] text-muted-foreground">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full rounded-md border bg-background px-2 py-1.5"
      />
    </label>
  );
}

function Toggle({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between rounded-md border px-2 py-1.5">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/50 p-2">
      <p className="text-[10px] uppercase text-muted-foreground">{label}</p>
      <p className="font-semibold tabular-nums">{value}</p>
    </div>
  );
}

