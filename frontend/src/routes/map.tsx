import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Image as ImageIcon,
  Layers as LayersIcon,
  Map as MapIcon,
  Wrench,
  Square,
  Hexagon,
  Upload,
  Trash2,
  Ruler,
  Maximize,
  Play,
  Loader2,
  CheckCircle2,
  Download,
  FileImage,
  FileText,
  Sigma,
  RotateCcw,
  Plus,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  indices,
  ndviStats,
  ndviClasses,
  ndviHistogram,
  type SatImage,
  type SpectralIndex,
} from "@/data/mock";
import {
  createAnalysis as createBackendAnalysis,
  createExport as createBackendExport,
  createMapLayoutPngExport,
  createMapPdfExport,
  deleteResultCache,
  downloadApiFile,
  downloadExport,
  getGeeStatus,
  getGeeScenePreview,
  getLandcoverClasses,
  getRunResult,
  getRunTiles,
  renameUnsupervisedCluster,
  updateUnsupervisedCluster,
  runAnalysis as runBackendAnalysis,
  createLandcoverClass,
  createTrainingSample,
  deleteTrainingSample,
  deleteTrainingSamplesForClass,
  getTrainingSamples,
  updateTrainingSample,
  getGeeCatalogJobStatus,
  getAnalysisJob,
  getPlatformSettings,
  readCachedPlatformSettings,
  searchResultCache,
  startGeeCatalogJob,
  startAnalysisJob,
  splitAoi,
  prepareGeeBuildingRaster,
  uploadLocalBuildingRaster,
  runBuildingDetection,
  downloadBuildingExport,
  API_BASE_URL,
} from "@/lib/georaster-api";
import type { AoiSplitPart, BuildingExportFormat } from "@/lib/georaster-api";
import { analysisTypeForIndex, supportedSensorsForIndex } from "@/lib/georaster-contract";
import type { ImageMethod, ResolutionId, SensorId } from "@/lib/georaster-contract";
import {
  AoiImportError,
  aoiGeometryAreaKm2,
  aoiImportUserMessage,
  importAoiFromFiles,
  type AoiGeometry,
} from "@/lib/aoi-import";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { useI18n } from "@/lib/i18n";
import { localizeResultLegendText, normalizeResultLegendText } from "@/lib/result-legend-i18n";
import { LocalizedDatePicker } from "@/components/LocalizedDatePicker";
import { BuildingDetectionPanel } from "@/features/ai-building/BuildingDetectionPanel";
import {
  DEFAULT_BUILDING_PARAMETERS,
  buildingErrorMessage,
  type AIRasterPrepareResult,
  type BuildingAnalysisResult,
  type BuildingDetectionParameters,
  type BuildingSourceMode,
} from "@/features/ai-building/model";

export const Route = createFileRoute("/map")({
  validateSearch: (search: Record<string, unknown>) => ({
    run_id: typeof search.run_id === "string" ? search.run_id : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Map & Analysis - GeoRaster Analytics" },
      { name: "description", content: "Interactive map and multispectral raster analysis." },
    ],
  }),
  component: MapPage,
  ssr: false,
});

type TabKey = "images" | "layers" | "basemap" | "tools";
type BasemapKey = "osm" | "satellite" | "googleSatellite" | "terrain" | "light";
type Step = "idle" | "clip" | "compute" | "render" | "done";
type SupervisedAlgorithm = "random_forest" | "cart" | "svm";
type SupervisedWorkflowStep = 1 | 2 | 3;
type UnsupervisedMode = "simple" | "expert";

const SENSOR_OPTIONS: { value: SensorId; label: string }[] = [
  { value: "sentinel-2", label: "Sentinel-2" },
  { value: "landsat-8-9", label: "Landsat 8/9" },
  { value: "dynamic-world", label: "Dynamic World" },
  { value: "esa-worldcover", label: "ESA WorldCover" },
  { value: "sentinel-1", label: "Sentinel-1 (advanced)" },
];

const RESOLUTION_OPTIONS: { value: ResolutionId; label: string }[] = [
  { value: "auto", label: "Automatic" },
  { value: "10m", label: "10 m" },
  { value: "20m", label: "20 m" },
  { value: "30m", label: "30 m" },
];

function nativeOutputResolution(indexId: string | undefined, sensor: string) {
  if (sensor === "landsat-8-9") return "30 m";
  const index = String(indexId || "").toUpperCase();
  if (index === "OSI_SAR") return "10 m";
  if (index.includes("NDBI") || index.includes("BSI")) return "20 m";
  return "10 m";
}

/** Resolve class legend text by label name — never by array index (class order ≠ mock legend order). */
function legendMeaningForClass(
  item: { name?: string; label?: string; meaning?: string; description?: string },
  legend: Array<{ label?: string; meaning?: string }> | undefined,
): string {
  if (item.meaning) return String(item.meaning);
  if (item.description) return String(item.description);
  if (!legend?.length) return "";
  const label = String(item.label ?? item.name ?? "")
    .trim()
    .toLowerCase();
  if (!label) return "";
  const exact = legend.find((entry) => String(entry.label ?? "").trim().toLowerCase() === label);
  if (exact?.meaning) return String(exact.meaning);
  const partial = legend.find((entry) => {
    const entryLabel = String(entry.label ?? "")
      .trim()
      .toLowerCase();
    return Boolean(entryLabel) && (label.includes(entryLabel) || entryLabel.includes(label));
  });
  return partial?.meaning ? String(partial.meaning) : "";
}

const SUPERVISED_CLASSIFICATION_ID = "SUPERVISED_CLASSIFICATION";
const UNSUPERVISED_CLASSIFICATION_ID = "UNSUPERVISED_CLASSIFICATION";
const OSI_SAR_ID = "OSI_SAR";
const CHANGE_DETECTION_IDS = [
  "CHANGE_NDVI",
  "CHANGE_NDWI",
  "CHANGE_NDBI",
  "CHANGE_BSI",
  "CHANGE_SAVI",
];
const CLASSIFICATION_IDS = [SUPERVISED_CLASSIFICATION_ID, UNSUPERVISED_CLASSIFICATION_ID];

function sampleIntersectsAoi(sample: any, aoi: [[number, number], [number, number]] | null) {
  if (!aoi) return false;
  const geometry = sample?.geometry;
  const coordinates = geometry?.coordinates;
  if (!geometry || !coordinates) return false;
  const points: Array<[number, number]> = [];
  const collect = (value: any) => {
    if (
      Array.isArray(value) &&
      value.length >= 2 &&
      Number.isFinite(Number(value[0])) &&
      Number.isFinite(Number(value[1]))
    ) {
      points.push([Number(value[0]), Number(value[1])]);
      return;
    }
    if (Array.isArray(value)) value.forEach(collect);
  };
  collect(coordinates);
  if (points.length === 0) return false;
  const [[south, west], [north, east]] = aoi;
  const longitudes = points.map(([longitude]) => longitude);
  const latitudes = points.map(([, latitude]) => latitude);
  const sampleWest = Math.min(...longitudes);
  const sampleEast = Math.max(...longitudes);
  const sampleSouth = Math.min(...latitudes);
  const sampleNorth = Math.max(...latitudes);
  return !(sampleEast < west || sampleWest > east || sampleNorth < south || sampleSouth > north);
}

function sampleCentroid(sample: any): [number, number] | null {
  const geometry = sample?.geometry;
  const coordinates = geometry?.coordinates;
  if (!geometry || !coordinates) return null;
  const points: Array<[number, number]> = [];
  const collect = (value: any) => {
    if (
      Array.isArray(value) &&
      value.length >= 2 &&
      Number.isFinite(Number(value[0])) &&
      Number.isFinite(Number(value[1]))
    ) {
      points.push([Number(value[0]), Number(value[1])]);
      return;
    }
    if (Array.isArray(value)) value.forEach(collect);
  };
  collect(coordinates);
  if (points.length === 0) return null;
  const lon = points.reduce((sum, [x]) => sum + x, 0) / points.length;
  const lat = points.reduce((sum, [, y]) => sum + y, 0) / points.length;
  return [lon, lat];
}

/** Rough AOI area in km² from Leaflet-style [[S,W],[N,E]] bbox. */
function estimateAoiAreaKm2(aoi: [[number, number], [number, number]] | null) {
  if (!aoi) return 0;
  const [[south, west], [north, east]] = aoi;
  const meanLat = (((south + north) / 2) * Math.PI) / 180;
  const widthKm = Math.abs(east - west) * 111.32 * Math.max(Math.cos(meanLat), 0.25);
  const heightKm = Math.abs(north - south) * 110.57;
  return Math.max(0, widthKm * heightKm);
}

/** Count how many AOI quadrants contain at least one sample centroid. */
function supervisedSampleQuadrantCoverage(
  samples: any[],
  aoi: [[number, number], [number, number]] | null,
) {
  if (!aoi || samples.length === 0) return { occupied: 0, ratio: 0 };
  const [[south, west], [north, east]] = aoi;
  const midLat = (south + north) / 2;
  const midLon = (west + east) / 2;
  const occupied = new Set<string>();
  for (const sample of samples) {
    const centroid = sampleCentroid(sample);
    if (!centroid) continue;
    const [lon, lat] = centroid;
    const key = `${lon >= midLon ? 1 : 0}:${lat >= midLat ? 1 : 0}`;
    occupied.add(key);
  }
  return { occupied: occupied.size, ratio: occupied.size / 4 };
}
const UNSUPERVISED_BANDS_BY_SENSOR: Record<"sentinel-2" | "landsat-8-9", string[]> = {
  "sentinel-2": ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"],
  "landsat-8-9": [
    "SR_B2",
    "SR_B3",
    "SR_B4",
    "SR_B5",
    "SR_B6",
    "SR_B7",
    "NDVI",
    "NDWI",
    "NDBI",
    "BSI",
    "SAVI",
  ],
};

const RESULT_STATUS_LABELS: Record<string, string> = {
  not_calculated: "Not calculated",
  running: "Running",
  calculated: "Calculated",
  error: "Error",
  available_from_cache: "Available from cache",
};

type GeeProgressState = {
  visible: boolean;
  percent: number;
  message: string;
  error: boolean;
};

type AnalysisProgressState = {
  visible: boolean;
  percent: number;
  message: string;
  error: boolean;
  cached: boolean;
};

const ANALYSIS_PROGRESS_STEPS = [
  { percent: 0, message: "Initializing processing..." },
  { percent: 10, message: "Validating parameters..." },
  { percent: 20, message: "Preparing analysis data..." },
  { percent: 35, message: "Preparing the Sentinel-2 mosaic..." },
  { percent: 50, message: "Computing the selected index..." },
  { percent: 65, message: "Classifying values..." },
  { percent: 80, message: "Computing statistics..." },
  { percent: 90, message: "Preparing the map layer..." },
];

const MAP_AR_TEXT: Record<string, string> = {
  AOI: "منطقة الاهتمام",
  "AOI changed: run the analysis again for the new selection.":
    "تغيّرت منطقة الاهتمام؛ أعد تشغيل التحليل للتحديد الجديد.",
  "Select an individual acquisition from the catalogue.":
    "اختر مرئية فردية من الكتالوج.",
  "The period mosaic cannot be used in Selected scene mode.":
    "لا يمكن استخدام موزاييك الفترة في وضع المرئية المحددة.",
  "Export resolution": "دقة التصدير",
  "Analysis source": "مصدر التحليل",
  "Temporal composite (median)": "مركب زمني (الوسيط)",
  "Selected scene": "المرئية المحددة",
  "Change Detection uses one temporal composite for each period.":
    "يستخدم كشف التغير مركباً زمنياً واحداً لكل فترة.",
  "The analysis will use only the selected catalogue acquisition.":
    "سيستخدم التحليل المرئية المحددة من الكتالوج فقط.",
  "The analysis will use the median of all valid images in the period.":
    "سيستخدم التحليل وسيط جميع الصور الصالحة خلال الفترة.",
  "Native analysis resolution": "الدقة الأصلية للتحليل",
  "Statistics adapt to AOI size": "تتكيف الإحصاءات مع حجم منطقة الاهتمام",
  "Continuous export: bilinear; classes: nearest neighbour":
    "التصدير المستمر: ثنائي الخط؛ الفئات: أقرب جار",
  standard: "قياسية",
  large: "كبيرة",
  "very large": "كبيرة جداً",
  "NDBI result layers": "طبقات نتائج NDBI",
  "OSI-SAR result layers": "طبقات نتائج OSI-SAR",
  "NDBI - Raw index": "NDBI - المؤشر الخام",
  "NDBI - Built-up classes": "NDBI - فئات العمران",
  "Built-up detection": "كشف المناطق المبنية",
  "Sentinel-1 VV": "Sentinel-1 VV",
  "Sentinel-1 VH": "Sentinel-1 VH",
  "Local contrast VV": "التباين المحلي لـ VV",
  "OSI-SAR raw candidates": "مرشحات OSI-SAR الأولية",
  "OSI-SAR final candidates": "مرشحات OSI-SAR النهائية",
  "Scenes found": "المشاهد الموجودة",
  "Scenes used": "المشاهد المستخدمة",
  "Selected Sentinel-1 VV in dB": "قناة VV للمشهد Sentinel-1 المحدد بالديسيبل",
  "Selected Sentinel-1 VH in dB": "قناة VH للمشهد Sentinel-1 المحدد بالديسيبل",
  "localMeanVV minus VV": "المتوسط المحلي لـ VV ناقص VV",
  "AND mask before connected-pixel filter": "قناع AND قبل مرشح البكسلات المتصلة",
  "Oil-spill suspect after connected-pixel filter": "اشتباه انسكاب نفطي بعد مرشح البكسلات المتصلة",
  "NDBI continuous result": "نتيجة NDBI المستمرة",
  "Continuous map stretch; class areas below are statistics only":
    "امتداد خريطة مستمر؛ مساحات الفئات أدناه إحصاءات فقط",
  "Value classes aligned with the legend; bare soil can also be positive in arid areas":
    "فئات قيم متوافقة مع المفتاح؛ قد تكون التربة العارية موجبة أيضاً في المناطق الجافة",
  "Classified built-up map (diagnostic)": "خريطة مصنفة للمناطق المبنية (تشخيصية)",
  "Continuous NDBI is displayed by default. Built-up interpretation remains a separate diagnostic layer.":
    "يتم عرض فئات NDBI افتراضياً، ويبقى التفسير العمراني الصارم طبقة تشخيصية منفصلة.",
  "Continuous NDBI is the default map. Class hectares are value-range statistics. Choose Built-up detection for a classified built-up map.":
    "فئات NDBI هي الخريطة الافتراضية. الهكتارات إحصاءات حسب نطاق القيمة. اختر كشف المناطق المبنية لخريطة عمرانية أكثر صرامة، أو المؤشر الخام للامتداد المستمر.",
  "Built-up evidence area": "مساحة دلائل المناطق المبنية",
  "Built-up evidence": "دلائل المناطق المبنية",
  "No evidence": "لا توجد دلائل",
  "Potential road": "طريق محتمل",
  Detected: "مكتشف",
  "High confidence": "ثقة عالية",
  "Pure continuous NDBI response": "استجابة طيفية مستمرة لمؤشر NDBI",
  "Separate built-up interpretation": "تفسير مستقل للمناطق المبنية",
  "Searching Sentinel-2 for the selected area...":
    "جاري البحث عن صور Sentinel-2 داخل المنطقة المحددة...",
  "Fallback catalog loaded because the online service is unavailable":
    "تم تحميل كتالوج احتياطي لأن الخدمة عبر الإنترنت غير متاحة",
  "No live image to display": "لا توجد صورة مباشرة للعرض",
  "Draw an area to search for live Sentinel-2 images.":
    "ارسم منطقة اهتمام للبحث عن صور Sentinel-2 مباشرة.",
  "Image detection error": "خطأ في اكتشاف الصور",
  "Searching satellite images...": "جاري البحث عن الصور الفضائية...",
  Automatic: "تلقائي",
  "10 m": "10 م",
  "20 m": "20 م",
  "30 m": "30 م",
  OpenStreetMap: "خريطة OpenStreetMap",
  "ESRI Imagery": "صور ESRI الفضائية",
  "Google Satellite": "صور Google الفضائية",
  Terrain: "خريطة التضاريس",
  "Light gray": "خريطة رمادية فاتحة",
  "Initializing processing...": "جاري تهيئة المعالجة...",
  "Validating parameters...": "جاري التحقق من المعاملات...",
  "Preparing analysis data...": "جاري تحضير بيانات التحليل...",
  "Initializing request...": "جاري تهيئة طلب البحث...",
  "Initializing request": "جاري تهيئة طلب البحث",
  "Initializing processing": "جاري تهيئة المعالجة",
  "Validating parameters": "جاري التحقق من المعاملات",
  "Reading area of interest": "جاري قراءة منطقة الاهتمام",
  "Preparing analysis data": "جاري تحضير بيانات التحليل",
  "Filtering by date and sensor": "جاري تصفية الصور حسب التاريخ والمستشعر",
  "Filtering by cloud coverage": "جاري تصفية الصور حسب نسبة الغيوم",
  "Detecting available scenes": "جاري التحقق من المشاهد المتاحة",
  "Preparing the catalog or mosaic": "جاري إعداد الكتالوج أو الصورة المجمعة",
  "Preparing image previews": "جاري إعداد معاينات الصور",
  "Images ready for display": "الصور جاهزة للعرض",
  "Images ready for display.": "الصور جاهزة للعرض.",
  "Satellite images detected successfully": "تم اكتشاف الصور الفضائية بنجاح",
  "Image detection error.": "حدث خطأ أثناء اكتشاف الصور",
  "Image detection error. Please widen the period, increase the cloud threshold, or reduce the area.":
    "تعذّر اكتشاف الصور. يُرجى توسيع الفترة الزمنية أو زيادة الحد الأقصى للغيوم أو تقليص مساحة المنطقة.",
  "Request queued": "تم وضع طلب البحث في قائمة الانتظار",
  "Image processing in progress...": "جاري معالجة الصور...",
  "Raster processing in progress": "جاري معالجة البيانات النقطية",
  "Preparing the Sentinel-2 mosaic...": "جاري تحضير موزاييك Sentinel-2...",
  "Computing the selected index...": "جاري حساب المؤشر المحدد...",
  "Classifying values...": "جاري تصنيف القيم...",
  "Computing statistics...": "جاري حساب الإحصاءات...",
  "Preparing the map layer...": "جاري تحضير طبقة الخريطة...",
  "Map is ready; exact statistics are updating in the background.":
    "الخريطة جاهزة، ويجري تحديث الإحصاءات الدقيقة في الخلفية.",
  "Statistics updated": "تم تحديث الإحصاءات",
  "The exact GEE statistics are now available.": "أصبحت إحصاءات GEE الدقيقة متاحة الآن.",
  "Map ready; statistics updating": "الخريطة جاهزة؛ جارٍ تحديث الإحصاءات",
  "Recenter map": "إعادة تمركز الخريطة",
  "Index calculation error. Please check the area, period, sensor, or try again later.":
    "خطأ في حساب المؤشر. تحقق من المنطقة أو الفترة أو الحساس، ثم حاول مرة أخرى لاحقا.",
  Level: "المستوى",
  comfortable: "مريح",
  possible: "ممكن",
  risky: "بحاجة إلى انتباه",
  "too large": "كبيرة جدا",
  Res: "الدقة",
  Clouds: "السحب",
  "Show on map": "عرض على الخريطة",
  "Multispectral image": "الصورة متعددة الأطياف",
  "Area of interest": "منطقة الاهتمام",
  "Analysis result": "نتيجة التحليل",
  Opacity: "الشفافية",
  "Administrative boundaries": "الحدود الإدارية",
  "Orthophoto ready for AI analysis": "الصورة الجوية جاهزة لتحليل الذكاء الاصطناعي",
  "Orthophoto upload failed": "فشل رفع الصورة الجوية",
  "building candidates vectorized": "مبانٍ مرشحة محولة إلى متجهات",
  "Analysis complete. No building candidates detected with the current parameters.":
    "اكتمل التحليل. لم يتم اكتشاف مبانٍ مرشحة بالإعدادات الحالية.",
  "Building analysis failed": "فشل تحليل المباني",
  "AI Building candidates": "المباني المرشحة بالذكاء الاصطناعي",
  objects: "عناصر",
  "Remove AI Building layer": "إزالة طبقة المباني بالذكاء الاصطناعي",
  "Raster analyses": "تحليلات الراستر",
  "AI Object Detection": "كشف الأجسام بالذكاء الاصطناعي",
  "AI Building export generated": "تم إنشاء تصدير المباني المرشحة",
  "AI Building export failed": "فشل تصدير المباني المرشحة",
  "The AI Building export could not be generated. Please try again.":
    "تعذر إنشاء تصدير المباني المرشحة. يرجى المحاولة مرة أخرى.",
  "Cached layers are loaded instantly from saved results.":
    "يتم تحميل الطبقات المحفوظة فوريا من النتائج المخزنة.",
  "One visual layer is active at a time. Statistics and legend follow the selected sub-layer.":
    "تكون طبقة مرئية واحدة نشطة في كل مرة. تتبع الإحصاءات ووسيلة الإيضاح الطبقة الفرعية المختارة.",
  "Draw rectangle": "رسم مستطيل",
  "Draw polygon": "رسم مضلع",
  "Draw point": "رسم نقطة",
  "Import GeoJSON": "استيراد GeoJSON",
  "Import area of interest": "استيراد منطقة الاهتمام",
  "Clear selection": "مسح التحديد",
  "Measure distance": "قياس المسافة",
  "Measure area": "قياس المساحة",
  "No image": "لا توجد صورة",
  "Sentinel-1 SAR AOI/date search": "بحث Sentinel-1 SAR حسب المنطقة والتاريخ",
  "No area drawn": "لم يتم رسم منطقة",
  "Mosaic quality": "جودة الموزاييك",
  Images: "الصور",
  Tiles: "البلاطات",
  Valid: "صالحة",
  Empty: "فارغة",
  Coverage: "التغطية",
  Quality: "الجودة",
  good: "جيدة",
  Good: "جيدة",
  a_evaluer: "بحاجة إلى تقييم",
  "Detailed coverage omitted to speed up processing of the large AOI.":
    "تم تخطي حساب التغطية التفصيلية لتسريع معالجة منطقة الاهتمام الكبيرة.",
  "Detailed coverage deferred to speed up processing of the large AOI.":
    "تم تأجيل حساب التغطية التفصيلية لتسريع معالجة منطقة الاهتمام الكبيرة.",
  "Low Sentinel-2 coverage: widen the period, raise the cloud threshold, or use a median composite.":
    "تغطية Sentinel-2 منخفضة: وسّع الفترة، أو ارفع حد الغيوم، أو استخدم مركّب الوسيط.",
  scene: "مشهد",
  vide: "فارغة",
  erreur: "خطأ",
  faible_couverture: "تغطية ضعيفة",
  moyenne: "متوسطة",
  faible: "ضعيفة",
  Area: "المساحة",
  "Bands used": "النطاقات المستخدمة",
  "Change Detection periods": "فترات كشف التغير",
  "Compare the same AOI using matched mosaics: Delta = Period 2 index - Period 1 index.":
    "مقارنة منطقة الاهتمام نفسها باستخدام موزاييك متطابق: الفرق = مؤشر الفترة 2 ناقص مؤشر الفترة 1.",
  "Period 1 start": "بداية الفترة 1",
  "Period 1 end": "نهاية الفترة 1",
  "Period 2 start": "بداية الفترة 2",
  "Period 2 end": "نهاية الفترة 2",
  "Use comparable seasons when possible. Seasonal differences can look like real change.":
    "استخدم مواسم قابلة للمقارنة قدر الإمكان، لأن الاختلافات الموسمية قد تبدو كتغير حقيقي.",
  "OSI-SAR parameters": "إعدادات OSI-SAR",
  "Sentinel-1 VV/VH dark-target detection for marine AOIs.":
    "اكتشاف الأهداف الداكنة VV/VH من Sentinel-1 لمناطق الاهتمام البحرية.",
  "VV dark threshold": "عتبة VV الداكنة",
  "VH dark threshold": "عتبة VH الداكنة",
  "Local contrast": "التباين المحلي",
  "Contrast radius": "نصف قطر التباين",
  "Minimum connected pixels": "الحد الأدنى للبكسلات المتصلة",
  "Removes isolated radar noise smaller than the selected connected-pixel count.":
    "يزيل ضوضاء الرادار المعزولة الأصغر من عدد البكسلات المتصلة المحدد.",
  "Acquisition date": "تاريخ الاكتساب",
  "Relative orbit": "المدار النسبي",
  "OSI-SAR uses one Sentinel-1 scene, not a long mosaic.":
    "يستخدم OSI-SAR مشهد Sentinel-1 واحدا وليس موزاييكا طويل المدة.",
  "Latest Sentinel-1 scene in the period": "أحدث مشهد Sentinel-1 في الفترة",
  "Selecting the Sentinel-1 acquisition...": "جارٍ اختيار اكتساب Sentinel-1...",
  "Sentinel-1 acquisition": "اكتساب Sentinel-1",
  "Scene ID": "معرف المشهد",
  "Orbit pass": "مسار المدار",
  "Any pass": "أي مسار",
  Ascending: "صاعد",
  Descending: "نازل",
  "Water/sea mask": "قناع المياه/البحر",
  "ERA5 wind validation": "تحقق الرياح ERA5",
  "Sentinel-2 visual validation": "تحقق بصري Sentinel-2",
  "Min wind": "أدنى سرعة رياح",
  "Max wind": "أقصى سرعة رياح",
  "OSI-SAR returns suspects, not confirmed pollution. Validate detections with wind, maritime context, and optical evidence when available.":
    "يعرض OSI-SAR مناطق مشتبه بها وليس تلوثا مؤكدا. تحقق من النتائج بالرياح والسياق البحري والأدلة البصرية عند توفرها.",
  "Supervised training": "إعداد التصنيف الموجَّه",
  "WorldCover reference, train/validation split, RF/CART/SVM comparison.":
    "مرجع WorldCover، وتقسيم التدريب والتحقق، ومقارنة خوارزميات التصنيف.",
  Compare: "مقارنة",
  Algorithm: "الخوارزمية",
  Trees: "الأشجار",
  "Samples per class": "عينات لكل فئة",
  "Training split": "تقسيم التدريب",
  "Interactive samples": "عينات تفاعلية",
  "Choose a class and sample role before drawing points or polygons on the map.":
    "اختر الفئة ودور العينة قبل رسم النقاط أو المضلعات على الخريطة.",
  training: "تدريب",
  validation: "تحقق",
  "Show saved training samples on map": "عرض عينات التدريب المحفوظة على الخريطة",
  "Active class": "الفئة النشطة",
  "Sample role": "دور العينة",
  Training: "تدريب",
  Validation: "تحقق",
  "Land-cover classes": "فئات غطاء الأرض",
  "Automatic clustering": "التجميع غير الموجَّه",
  "Automatic grouping of similar spectral patterns without training samples.":
    "تجميع غير موجَّه للأنماط الطيفية المتشابهة دون استخدام عينات تدريب.",
  Mode: "نمط التشغيل",
  Simple: "مبسّط",
  Expert: "متقدم",
  Clusters: "العناقيد",
  "Sampling pixels": "عدد بكسلات العيّنة",
  "Input bands": "النطاقات الطيفية المدخلة",
  "Guided user-sample workflow. WorldCover fallback is disabled for analyses launched here.":
    "سير عمل موجَّه يعتمد على عينات المستخدم. تم تعطيل الرجوع إلى مرجع WorldCover للتحليلات المشغَّلة من هنا.",
  Classes: "الفئات",
  Samples: "العينات",
  Review: "المراجعة",
  "Step 1 — Choose and configure classes": "الخطوة 1 — اختيار الفئات وإعدادها",
  "Select at least two classes that will be represented by user samples.":
    "اختر فئتين على الأقل لتمثيلهما بعينات المستخدم.",
  "Create a class": "إنشاء فئة",
  "Class name": "اسم الفئة",
  "Continue to samples": "الانتقال إلى العينات",
  "Step 2 — Create training samples": "الخطوة 2 — إنشاء عينات التدريب",
  "Choose the active class, then draw directly on the map.":
    "اختر الفئة النشطة، ثم ارسم العينات مباشرة على الخريطة.",
  "Training samples": "عينات التدريب",
  "Validation samples": "عينات التحقق",
  "Tr.": "تد.",
  "Val.": "تح.",
  Point: "نقطة",
  Polygon: "مضلع",
  "Click at least three vertices, then double-click to finish the polygon.":
    "انقر لتحديد ثلاثة رؤوس على الأقل، ثم انقر نقراً مزدوجاً لإتمام المضلع.",
  "Click once on the map to save a point sample.": "انقر مرة واحدة على الخريطة لحفظ عينة نقطية.",
  "Delete class samples": "حذف عينات الفئة",
  "Delete sample": "حذف العينة",
  "Missing training samples": "عينات التدريب الناقصة",
  Back: "رجوع",
  "Step 3 — Review and run": "الخطوة 3 — المراجعة والتشغيل",
  "Only samples inside the current AOI are included in the supervised classification workflow.":
    "لا تُدرج في سير عمل التصنيف الموجَّه إلا العينات الواقعة داخل منطقة الاهتمام الحالية.",
  "Selected classes": "الفئات المختارة",
  "Training geometries": "هندسيات التدريب",
  "Validation geometries": "هندسيات التحقق",
  "Random Forest": "الغابة العشوائية",
  "Decision Tree (CART)": "شجرة القرار (CART)",
  "Support Vector Machine (SVM)": "آلة المتجهات الداعمة (SVM)",
  "Pixels are sampled from these geometries. At least 40 training pixels and 10 validation pixels are required; when no validation geometry is provided, the validation set is created automatically. Point-only datasets usually require dozens of points.":
    "تُستخلص بكسلات العيّنة من هذه الهندسيات. يلزم ما لا يقل عن 40 بكسلاً للتدريب و10 بكسلات للتحقق؛ وعند عدم توفير هندسيات للتحقق، تُنشأ مجموعة التحقق تلقائياً. تتطلب مجموعات البيانات المعتمدة على النقاط فقط عشرات النقاط عادةً.",
  "Run classification": "تشغيل التصنيف",
  "Supervised classification": "تصنيف موجَّه",
  "Unsupervised classification": "تصنيف غير موجَّه",
  "Overall accuracy": "الدقة الكلية",
  "Kappa coefficient": "معامل كابا",
  "User accuracy": "دقة المستخدم",
  "Producer accuracy": "دقة المنتج",
  "Select a land-cover class before drawing a sample.": "اختر فئة لغطاء الأرض قبل رسم عينة.",
  "The active class must be selected in step 1.": "يجب اختيار الفئة النشطة في الخطوة الأولى.",
  "Training sample created": "تم إنشاء عينة تدريب.",
  "Validation sample created": "تم إنشاء عينة تحقق.",
  "Failed to save sample": "تعذر حفظ العينة",
  "Enter a class name.": "أدخل اسم الفئة.",
  "Class already exists": "الفئة موجودة بالفعل",
  "was selected instead of creating a duplicate.": "تم اختيارها بدلاً من إنشاء فئة مكررة.",
  "Land-cover class created.": "تم إنشاء فئة غطاء الأرض.",
  "Unable to create class": "تعذر إنشاء الفئة",
  "Backend error": "خطأ في الخادم الخلفي",
  "Training sample deleted.": "تم حذف عينة التدريب.",
  "Unable to delete sample": "تعذر حذف العينة",
  "sample(s) deleted for this class.": "عينة/عينات حُذفت لهذه الفئة.",
  "Unable to delete class samples": "تعذر حذف عينات الفئة",
  "Sample class updated.": "تم تحديث فئة العينة.",
  "Unable to update sample class": "تعذر تحديث فئة العينة",
  "Select at least two land-cover classes before running the classification.":
    "اختر فئتين لغطاء الأرض على الأقل قبل تشغيل التصنيف.",
  "Draw training samples inside the current area of interest.":
    "ارسم عينات تدريب داخل منطقة الاهتمام الحالية.",
  "Each selected class needs a training sample inside the AOI.":
    "تحتاج كل فئة مختارة إلى عينة تدريب داخل منطقة الاهتمام.",
  "Large AOI: spread training samples across more of the area for a reliable classification.":
    "منطقة كبيرة: وزّع عينات التدريب على أجزاء أكثر من المنطقة للحصول على تصنيف موثوق.",
  "Add points or polygons in different parts of the AOI for each class.":
    "أضف نقاطًا أو مضلعات في أجزاء مختلفة من منطقة الاهتمام لكل فئة.",
  "Samples are concentrated in one part of the AOI. Add samples elsewhere before trusting the map.":
    "العينات مركّزة في جزء واحد من المنطقة. أضف عينات في مواضع أخرى قبل الاعتماد على الخريطة.",
  "Clipping...": "جاري القص...",
  "Computing change...": "جاري حساب التغير...",
  "Classifying...": "جاري التصنيف...",
  "Preparation...": "التحضير...",
  "Sampling...": "أخذ العينات...",
  "Training / Clustering...": "التدريب / التجميع...",
  "Classification...": "التصنيف...",
  "Rendering...": "العرض...",
  "Completed": "اكتمل",
  "Computing index...": "جاري حساب المؤشر...",
  "Generating...": "جاري توليد الطبقة...",
  "Analysis error": "خطأ في التحليل",
  "Cache result": "نتيجة من الذاكرة المؤقتة",
  "Raster processing": "معالجة الراستر",
  "Draw a marine area of interest, then run Sentinel-1 OSI-SAR.":
    "ارسم منطقة اهتمام بحرية، ثم شغل Sentinel-1 OSI-SAR.",
  "Select an image, then draw an area of interest.": "اختر صورة، ثم ارسم منطقة اهتمام.",
  "Before / After summary": "ملخص قبل / بعد",
  "Visual reading workflow for P1, P2, NDVI P1, NDVI P2, and Delta NDVI.":
    "سير قراءة بصري للفترة P1 والفترة P2 و NDVI P1 و NDVI P2 و Delta NDVI.",
  "Period 1": "الفترة 1",
  "Period 2": "الفترة 2",
  "Reference vegetation state for the first period.": "حالة الغطاء النباتي المرجعية للفترة الأولى.",
  "Observed vegetation state for the second period.":
    "حالة الغطاء النباتي المرصودة للفترة الثانية.",
  "Computed as NDVI period 2 minus NDVI period 1.":
    "يحسب كالتالي: NDVI الفترة 2 ناقص NDVI الفترة 1.",
  Loss: "الفقدان",
  Stable: "مستقر",
  Gain: "الزيادة",
  "Loss %": "نسبة الفقدان",
  "Stable %": "نسبة الاستقرار",
  "Gain %": "نسبة الزيادة",
  "Dominant class": "الفئة الغالبة",
  "Period comparability warning.": "تنبيه قابلية مقارنة الفترات.",
  "Overall quality": "الجودة الإجمالية",
  "Training source": "مصدر التدريب",
  "User samples": "عينات المستخدم",
  "Fallback applied": "تم تطبيق البديل",
  "Algorithm comparison": "مقارنة الخوارزميات",
  Method: "الطريقة",
  "Cluster interpretation": "تفسير المجموعات",
  "Probable interpretation": "التفسير المحتمل",
  "Reference validation unavailable": "التحقق المرجعي غير متاح",
  "No independent reference dataset was supplied. Evaluate these clusters through spectral coherence, spatial coherence and stability.":
    "لم تُوفَّر بيانات مرجعية مستقلة. قيّم هذه المجموعات من خلال الاتساق الطيفي والمكاني والاستقرار.",
  "Classified area": "المساحة المصنفة",
  "Classified AOI": "نسبة المنطقة المصنفة",
  "Sample scale": "دقة أخذ العينات",
  "Light spatial filter": "مرشح مكاني خفيف",
  Enabled: "مفعّل",
  Disabled: "غير مفعّل",
  "Clusters are spectral groups, not validated land-cover classes. Labels shown below are probable interpretations only.":
    "المجموعات أنماط طيفية وليست فئات غطاء أرضي متحققاً منها. التسميات أدناه تفسيرات محتملة فقط.",
  "Validation by class": "التحقق حسب الفئة",
  "Suspect area": "المساحة المشتبه بها",
  "Suspect %": "نسبة الاشتباه",
  High: "مرتفع",
  Wind: "الرياح",
  "Mean VV": "متوسط VV",
  "Mean VH": "متوسط VH",
  "Map PNG": "خريطة PNG",
  "PDF Report": "تقرير PDF",
  "CSV stats": "إحصاءات CSV",
  Available: "متاح",
  Mosaic: "موزاييك",
  valid: "صالح",
  empty: "فارغ",
  "No or very sparse vegetation cover": "غطاء نباتي معدوم أو متناثر جدا",
  "Sparse vegetation cover": "غطاء نباتي متناثر",
  "Moderate vegetation cover": "غطاء نباتي متوسط الكثافة",
  "Dense vegetation cover": "غطاء نباتي كثيف",
  "Very dense vegetation cover": "غطاء نباتي كثيف جدا",
  "Bare or non-vegetated surfaces with very sparse vegetation.":
    "أسطح عارية أو غير مغطاة بالنباتات مع وجود غطاء نباتي متناثر جدا.",
  "Sparse or potentially stressed vegetation.": "غطاء نباتي متناثر أو يحتمل تعرضه للإجهاد.",
  "Moderate vegetation density.": "كثافة نباتية متوسطة.",
  "Dense vegetation cover.": "غطاء نباتي كثيف.",
  "Very dense and vigorous vegetation cover.": "غطاء نباتي كثيف جدا وعالي الحيوية.",
  "Large decrease in vegetation response.": "انخفاض كبير في استجابة الغطاء النباتي.",
  "Moderate decrease in vegetation cover or vigor.": "انخفاض متوسط في الغطاء النباتي أو حيويته.",
  "Limited NDVI change between periods.": "تغير محدود في NDVI بين الفترتين.",
  "Moderate increase in vegetation response.": "زيادة متوسطة في استجابة الغطاء النباتي.",
  "Large increase in vegetation cover or vigor.": "زيادة كبيرة في الغطاء النباتي أو حيويته.",
  "Dry / non-water": "جاف / غير مائي",
  "Low moisture": "رطوبة منخفضة",
  "Medium moisture": "رطوبة متوسطة",
  "High moisture": "رطوبة مرتفعة",
  "Likely water": "مياه محتملة",
  "Water/moisture disappearance": "اختفاء المياه/الرطوبة",
  "Moisture decrease": "انخفاض الرطوبة",
  "Moisture increase": "زيادة الرطوبة",
  "Probable water appearance": "ظهور مياه محتمل",
  "Strong decrease of water or moisture signal.": "انخفاض قوي في إشارة المياه أو الرطوبة.",
  "Moderate decrease of humidity or water response.":
    "انخفاض متوسط في الرطوبة أو الاستجابة المائية.",
  "Limited NDWI change between periods.": "تغير محدود في NDWI بين الفترتين.",
  "Moderate increase of humidity or water response.":
    "زيادة متوسطة في الرطوبة أو الاستجابة المائية.",
  "Strong increase suggesting new or expanded water.": "زيادة قوية تشير إلى مياه جديدة أو متوسعة.",
  "Non-built-up": "غير عمراني",
  "Low artificialization": "عمران منخفض",
  "Moderate built-up": "عمران متوسط",
  "High built-up": "عمران مرتفع",
  "Very high built-up": "عمران مرتفع جدا",
  "Built-up decrease": "انخفاض العمران",
  "Low built-up decrease": "انخفاض عمراني محدود",
  "New artificialization": "توسع عمراني جديد",
  "Strong built-up expansion": "توسع عمراني قوي",
  "Strong decrease of built-up spectral response.": "انخفاض قوي في الاستجابة الطيفية العمرانية.",
  "Moderate decrease of built-up response.": "انخفاض متوسط في الاستجابة العمرانية.",
  "Limited NDBI change between periods.": "تغير محدود في NDBI بين الفترتين.",
  "Moderate increase of built-up response.": "زيادة متوسطة في الاستجابة العمرانية.",
  "Strong increase suggesting urban or impervious expansion.":
    "زيادة قوية تشير إلى توسع عمراني أو أسطح غير نفاذة.",
  "Very low bare-soil exposure": "تعرض منخفض جدا للتربة المكشوفة",
  "Low bare-soil exposure": "تعرض منخفض للتربة المكشوفة",
  "Moderate bare-soil exposure": "تعرض متوسط للتربة المكشوفة",
  "High bare-soil exposure": "تعرض مرتفع للتربة المكشوفة",
  "Very high bare-soil exposure": "تعرض مرتفع جدا للتربة المكشوفة",
  "Preparing the Sentinel-1 SAR mosaic...": "جارٍ إعداد الفسيفساء الرادارية Sentinel-1 SAR...",
  "Result ready.": "النتيجة جاهزة.",
  "Result loaded from cache.": "تم تحميل النتيجة من الذاكرة المؤقتة.",
  "Loading result from cache...": "جارٍ تحميل النتيجة من الذاكرة المؤقتة...",
  "Draw an area of interest first.": "ارسم منطقة الاهتمام أولاً.",
  "Invalid period": "فترة زمنية غير صالحة",
  "The start date must be before the end date.": "يجب أن يسبق تاريخ البداية تاريخ النهاية.",
  "Fallback catalog loaded": "تم تحميل الكتالوج البديل",
  "The online service is unavailable. Fallback catalog loaded.":
    "الخدمة الإلكترونية غير متاحة حالياً؛ تم تحميل الكتالوج البديل.",
  "The app is temporarily using local catalog images.":
    "يستخدم التطبيق مؤقتاً صور الكتالوج المحلي.",
  "Please widen the period, increase the cloud threshold, or reduce the area.":
    "يرجى توسيع الفترة الزمنية أو رفع الحد الأقصى للغطاء السحابي أو تقليص منطقة الاهتمام.",
  "Analysis restored from History": "تمت استعادة التحليل من السجل",
  "Result loaded from the stored analysis without recalculation.":
    "تم تحميل نتيجة التحليل المحفوظ دون إعادة الحساب.",
  "Unable to restore analysis": "تعذرت استعادة التحليل",
  "Multispectral image loaded": "تم تحميل الصورة متعددة الأطياف",
  "Area of interest selected": "تم تحديد منطقة الاهتمام",
  "Result loaded from history; no recalculation required.":
    "تم تحميل النتيجة من السجل دون الحاجة إلى إعادة الحساب.",
  "Analysis not compatible with this sensor": "التحليل غير متوافق مع هذا المستشعر",
  "Invalid Change Detection periods": "فترات كشف التغير غير صالحة",
  "Each period must have a valid start date before its end date.":
    "يجب أن تتضمن كل فترة تاريخ بداية صالحاً يسبق تاريخ النهاية.",
  "Preparing raster analysis...": "جارٍ إعداد التحليل الراستري...",
  "Recalculation in progress...": "جارٍ إعادة الحساب...",
  "Classification in progress...": "جارٍ تنفيذ التصنيف...",
  "Analysis processing in progress...": "جارٍ تنفيذ التحليل...",
  "Analysis completed": "اكتمل التحليل",
  "Raster analysis failed": "تعذر تنفيذ التحليل الراستري",
  "Unable to refresh the stored map tile": "تعذر تحديث بلاطة الخريطة المحفوظة",
  "The run is restored, but the visual tile could not be regenerated.":
    "تمت استعادة عملية التنفيذ، لكن تعذر إعادة توليد البلاطة المرئية.",
  "Google Earth Engine is unavailable. Mock analysis is blocked.":
    "محرك Google Earth Engine غير متاح. التحليل التجريبي محظور.",
  "Connect Earth Engine and search live images before running an analysis.":
    "اتصل بـ Earth Engine وابحث عن صور حية قبل تشغيل التحليل.",
  "This stored result is a mock. It is not an operational GEE analysis.":
    "هذه النتيجة المخزنة تجريبية وليست تحليلاً تشغيلياً من Earth Engine.",
  "Select a cached result layer first.": "اختر أولاً طبقة نتائج محفوظة في الذاكرة المؤقتة.",
  "Cached result deleted": "تم حذف النتيجة المحفوظة مؤقتاً",
  "Unable to delete cached result": "تعذر حذف النتيجة المحفوظة مؤقتاً",
  "No result to export": "لا توجد نتيجة متاحة للتصدير",
  "Export generated": "تم إنشاء ملف التصدير",
  "Export failed": "تعذر إنشاء ملف التصدير",
  "Preparing Map PDF report...": "جارٍ إعداد تقرير الخريطة بصيغة PDF...",
  "Map PDF generated": "تم إنشاء تقرير الخريطة بصيغة PDF",
  "Download started": "بدأ التنزيل",
  "Map PDF export failed": "تعذر تصدير تقرير الخريطة بصيغة PDF",
  "Map capture unavailable": "التقاط الخريطة غير متاح",
  "Preparing cartographic layout...": "جارٍ إعداد الإخراج الخرائطي...",
  "Layout PNG generated": "تم إنشاء الإخراج الخرائطي بصيغة PNG",
  "PNG export failed": "تعذر تصدير الخريطة بصيغة PNG",
  "Cluster label updated": "تم تحديث اسم المجموعة",
  "Unable to rename cluster": "تعذر تغيير اسم المجموعة",
  "Import a .geojson file": "استورد ملفاً بصيغة GeoJSON.",
  "Import a GeoJSON, Shapefile, KML or KMZ file":
    "استورد ملفاً بصيغة GeoJSON أو Shapefile أو KML أو KMZ.",
  "Split area of interest": "تقسيم منطقة الاهتمام",
  "Split automatically": "تقسيم تلقائي",
  parts: "أجزاء",
  "Aligned grid, 4 cells along the longest side": "شبكة منتظمة، 4 خلايا على الضلع الأطول",
  "Area of interest small enough: no split needed":
    "منطقة الاهتمام صغيرة بما يكفي؛ لا حاجة للتقسيم",
  "Splitting the area of interest...": "جاري تقسيم منطقة الاهتمام...",
  "Area of interest split into equivalent parts": "تم تقسيم منطقة الاهتمام إلى أجزاء متكافئة",
  "Split failed": "فشل التقسيم",
  "Full area of interest": "منطقة الاهتمام الكاملة",
  "Draw or import an area of interest first": "ارسم أو استورد منطقة اهتمام أولا",
  "Click the cells on the map to analyse them together": "اضغط على الخلايا في الخريطة لتحليلها معا",
  "Run the image search again so the source image matches the selection":
    "أعد البحث عن الصور لتطابق الصورة المصدرية مع التحديد",
  "parts selected": "أجزاء محددة",
  All: "الكل",
  None: "لا شيء",
  "Area of interest imported": "تم استيراد منطقة الاهتمام",
  "Unsupported file format. Use GeoJSON, Shapefile, KML or KMZ.":
    "صيغة الملف غير مدعومة. استخدم GeoJSON أو Shapefile أو KML أو KMZ.",
  "The selected file is invalid or could not be read.": "الملف المحدد غير صالح أو تعذر قراءته.",
  "The file does not contain a valid polygon geometry.": "لا يحتوي الملف على هندسة مضلع صالحة.",
  "Incomplete Shapefile. Select the .shp with .shx and .dbf, or import a .zip. A .prj is required only when coordinates are not geographic WGS84.":
    "ملف Shapefile غير مكتمل. حدد ملف .shp مع .shx و.dbf، أو استورد ملفاً مضغوطاً zip. ملف .prj مطلوب فقط إذا لم تكن الإحداثيات جغرافية WGS84.",
  "Unable to determine or convert the file projection to WGS84.":
    "تعذر تحديد إسقاط الملف أو تحويله إلى WGS84.",
  "Reading area of interest...": "جارٍ قراءة منطقة الاهتمام...",
  "Selection cleared": "تم مسح التحديد",
  "Distance measurement enabled": "تم تفعيل قياس المسافة",
  "Area measurement enabled": "تم تفعيل قياس المساحة",
  "GeoTIFF map": "خريطة بصيغة GeoTIFF",
  "Statistics CSV": "إحصاءات بصيغة CSV",
  "Exact class areas are still being computed.": "ما زالت مساحات الفئات الدقيقة قيد الحساب.",
  "The map is a continuous index stretch, not a classified land-cover layer. Class areas in hectares are statistics; classes below 1% of the AOI are usually not visible at this zoom.":
    "الخريطة امتداد مستمر للمؤشر وليست طبقة تصنيف غطاء أرضي. المساحات بالهكتار إحصاءات؛ الفئات دون 1% من منطقة الاهتمام غالباً غير مرئية عند هذا التكبير.",
  "Area by value range": "المساحة حسب نطاق القيمة",
  "Surfaces in hectares come from index value ranges. They do not paint separate classified polygons on the continuous map.":
    "المساحات بالهكتار ناتجة عن نطاقات قيم المؤشر. وهي لا ترسم مضلعات مصنفة منفصلة على الخريطة المستمرة.",
  "Rarely visible on the continuous map at this zoom.":
    "نادراً ما تظهر على الخريطة المستمرة عند هذا التكبير.",
  "Native sensor scale; the dropdown does not resample GEE rasters.":
    "مقياس الحساس الأصلي؛ القائمة لا تعيد أخذ عينات الراستر من GEE.",
  "Automatic follows the native band scale. Chosen resolution is kept in metadata; GEE still uses native bands for index formulas.":
    "التلقائي يتبع مقياس النطاق الأصلي. الدقة المختارة تُحفظ في البيانات الوصفية؛ GEE ما زال يستخدم النطاقات الأصلية لصيغ المؤشرات.",
  "Sensor not available for this analysis": "الحساس غير متاح لهذا التحليل",
  unavailable: "غير متاح",
  "OSI-SAR requires Sentinel-1.": "OSI-SAR يتطلب Sentinel-1.",
  "Sentinel-2 and Landsat 8/9 are available for spectral indices. Dynamic World / WorldCover stay listed but disabled.":
    "Sentinel-2 و Landsat 8/9 متاحان للمؤشرات الطيفية. Dynamic World / WorldCover يظهران في القائمة لكنهما معطّلان.",
  "Available only for optical spectral analyses.": "متاح فقط للتحليلات الطيفية البصرية.",
  "Reserved for OSI-SAR analysis.": "مخصص لتحليل OSI-SAR.",
  "Reference land-cover product; not used to compute spectral indices.":
    "منتج مرجعي لغطاء الأرض؛ لا يُستخدم لحساب المؤشرات الطيفية.",
  "Not compatible with the selected analysis.": "غير متوافق مع التحليل المحدد.",
  "source image(s) found": "صورة مصدرية متاحة",
  "Land cover classified over": "تم تصنيف غطاء الأرض على مساحة",
  "OSI-SAR detected suspect slick candidates over": "رصد OSI-SAR مناطق مشتبه بها على مساحة",
  "calculated over": "تم حسابه على مساحة",
  "Strong reduction of exposed bare soil.": "انخفاض قوي في التربة المكشوفة.",
  "Moderate reduction of bare-soil response.": "انخفاض متوسط في استجابة التربة المكشوفة.",
  "Limited BSI change between periods.": "تغير محدود في BSI بين الفترتين.",
  "Moderate increase of exposed soil.": "زيادة متوسطة في التربة المكشوفة.",
  "Strong increase of bare or exposed mineral surface.":
    "زيادة قوية في الأسطح المعدنية العارية أو المكشوفة.",
  "Class color": "لون الفئة",
  "Change class color": "تغيير لون الفئة",
  "Cluster color updated": "تم تحديث لون المجموعة",
  "Unable to update cluster color": "تعذر تحديث لون المجموعة",
};

const MAP_INDEX_AR: Record<
  string,
  { name: string; topic: string; description: string; bands?: string }
> = {
  NDBI_RAW: {
    name: "NDBI - المؤشر الخام",
    topic: "الاستجابة الطيفية الخام",
    description:
      "يعرض الاستجابة الخام لمؤشر NDBI المحسوبة من نطاقي SWIR وNIR دون تحويلها مباشرة إلى فئات غطاء أرضي.",
    bands: "النطاقات المستخدمة: SWIR وNIR",
  },
  BUILT_DETECTION: {
    name: "كشف المناطق المبنية",
    topic: "المناطق المبنية والأسطح غير المنفذة",
    description:
      "طبقة تفسير مستقلة تجمع عدة أرصاد لتمييز المناطق المبنية والطرق عن التربة العارية.",
    bands: "النطاقات والمؤشرات المستخدمة: SWIR، NIR، NDVI، NDWI، BSI ومراجع الغطاء الأرضي",
  },
  NDVI: {
    name: "NDVI",
    topic: "الغطاء النباتي",
    description:
      "يقيم مستويات الغطاء النباتي وكثافته اعتمادا على نطاقي الأشعة القريبة من تحت الحمراء والأحمر.",
    bands: "النطاقات المستخدمة: NIR، الأحمر",
  },
  NDWI: {
    name: "NDWI",
    topic: "المياه والرطوبة",
    description: "يكشف المياه السطحية والمناطق الرطبة ومؤشرات الرطوبة داخل منطقة الاهتمام.",
    bands: "النطاقات المستخدمة: الأخضر، NIR",
  },
  NDBI: {
    name: "NDBI",
    topic: "العمران والمناطق الحضرية",
    description: "يميز المناطق العمرانية والأسطح غير النفاذة اعتمادا على SWIR و NIR.",
    bands: "النطاقات المستخدمة: SWIR، NIR",
  },
  BSI: {
    name: "BSI",
    topic: "التربة المكشوفة",
    description: "يبرز التربة العارية والأسطح الجافة والمناطق ذات الغطاء النباتي الضعيف.",
    bands: "النطاقات المستخدمة: SWIR، الأحمر، NIR، الأزرق",
  },
  SAVI: {
    name: "SAVI",
    topic: "الغطاء النباتي شبه الجاف",
    description: "يقيم الغطاء النباتي في المناطق شبه الجافة مع تقليل تأثير خلفية التربة.",
    bands: "النطاقات المستخدمة: NIR، الأحمر",
  },
  OSI_SAR: {
    name: "OSI-SAR",
    topic: "اشتباه الانسكابات النفطية",
    description:
      "يكشف المرشحات المحتملة للبقع النفطية فوق المياه باستخدام إشارات الرادار Sentinel-1 الداكنة.",
    bands: "النطاقات المستخدمة: Sentinel-1 VV, Sentinel-1 VH, التباين المحلي",
  },
  CHANGE_NDVI: {
    name: "CHANGE_NDVI",
    topic: "تغير الغطاء النباتي",
    description: "يقارن NDVI بين فترتين لرصد فقدان الغطاء النباتي أو استقراره أو زيادته.",
    bands: "النطاقات المستخدمة: NDVI الفترة 1, NDVI الفترة 2, فرق NDVI",
  },
  CHANGE_NDWI: {
    name: "CHANGE_NDWI",
    topic: "تغير المياه والرطوبة",
    description: "يقارن NDWI بين فترتين لرصد انخفاض الرطوبة أو استقرارها أو زيادتها.",
    bands: "النطاقات المستخدمة: NDWI الفترة 1, NDWI الفترة 2, فرق NDWI",
  },
  CHANGE_NDBI: {
    name: "CHANGE_NDBI",
    topic: "تغير العمران",
    description:
      "يقارن NDBI المستمر بين فترتين (NDBI_P2 ناقص NDBI_P1). زيادة NDBI ليست إثباتاً لعمران جديد.",
    bands: "النطاقات المستخدمة: NDBI الفترة 1, NDBI الفترة 2, فرق NDBI",
  },
  CHANGE_BSI: {
    name: "CHANGE_BSI",
    topic: "تغير التربة المكشوفة",
    description: "يقارن BSI بين فترتين لرصد انخفاض تعرض التربة أو استقراره أو زيادته.",
    bands: "النطاقات المستخدمة: BSI الفترة 1, BSI الفترة 2, فرق BSI",
  },
  CHANGE_SAVI: {
    name: "CHANGE_SAVI",
    topic: "تغير الغطاء النباتي شبه الجاف",
    description:
      "يقارن SAVI بين فترتين لرصد فقدان الغطاء النباتي أو استقراره أو تحسنه في المناطق شبه الجافة.",
    bands: "النطاقات المستخدمة: SAVI الفترة 1, SAVI الفترة 2, فرق SAVI",
  },
  SUPERVISED_CLASSIFICATION: {
    name: "التصنيف الموجَّه",
    topic: "تصنيف غطاء الأرض الموجه",
    description: "ينتج تصنيفا موجها لغطاء الأرض اعتمادا على منطقة الدراسة والعينات المختارة.",
    bands: "النطاقات المستخدمة: النطاقات الطيفية و NDVI, NDWI, NDBI, BSI, SAVI",
  },
  UNSUPERVISED_CLASSIFICATION: {
    name: "التصنيف غير الموجَّه",
    topic: "تجميع غطاء الأرض غير الموجه",
    description:
      "ينشئ تصنيفا تلقائيا لغطاء الأرض في المنطقة المحددة اعتمادا على أوجه التشابه الطيفي وتفسير المؤشرات.",
    bands: "النطاقات المستخدمة: النطاقات الطيفية و NDVI, NDWI, NDBI, BSI, SAVI",
  },
};

function mapText(value: string, language: string) {
  return language === "ar" ? (MAP_AR_TEXT[value] ?? value) : value;
}

function formatAreaHa(value: unknown, language: string, maximumFractionDigits = 2) {
  if (value == null || value === "") return "-";
  const numeric = Number(value);
  const formatted = Number.isFinite(numeric)
    ? numeric.toLocaleString(language === "ar" ? "ar-SA-u-nu-latn" : "en-US", {
        maximumFractionDigits,
      })
    : String(value);
  return language === "ar" ? `${formatted} هكتار` : `${formatted} ha`;
}

function mapErrorDescription(error: unknown, language: string) {
  return language === "ar"
    ? mapText("Backend error", language)
    : error instanceof Error
      ? error.message
      : "Backend error";
}

function resultHasDeferredStatistics(result: any) {
  const stats = result?.stats ?? {};
  const quality = result?.quality_summary ?? {};
  const performance = result?.performance ?? {};
  const isDeferredFlag = (value: unknown) => {
    if (value === true) return true;
    const text = String(value ?? "").trim().toLowerCase();
    return text === "deferred_for_first_map" || text === "deferred" || text.startsWith("deferred");
  };
  return Boolean(
    performance.stats_deferred === true ||
    stats.statistics_deferred === true ||
    isDeferredFlag(stats.statistics_status) ||
    isDeferredFlag(quality.statistics_status),
  );
}

function formatClassPct(pct: unknown, surfaceHa: unknown) {
  const area = Number(surfaceHa);
  const value = Number(pct);
  if (Number.isFinite(area) && area > 0 && (!Number.isFinite(value) || value === 0)) {
    return "<0.1%";
  }
  if (Number.isFinite(value) && value > 0 && value < 0.1) return "<0.1%";
  if (!Number.isFinite(value)) return "0%";
  return `${value}%`;
}

function classIsBelowMapVisibility(pct: unknown, surfaceHa: unknown) {
  const area = Number(surfaceHa);
  const value = Number(pct);
  if (Number.isFinite(area) && area > 0 && (!Number.isFinite(value) || value < 1)) return true;
  return Number.isFinite(value) && value > 0 && value < 1;
}

function mapBackendText(value: unknown, language: string) {
  const normalized = normalizeResultLegendText(displayBackendText(value));
  if (normalized === "a_evaluer") {
    return language === "ar" ? mapText("a_evaluer", language) : "To be evaluated";
  }
  const localizedLegendText = localizeResultLegendText(normalized, language);
  if (language !== "ar" || localizedLegendText !== normalized) return localizedLegendText;

  const mapped = mapText(normalized, language);
  if (mapped !== normalized) return mapped;

  const periodLayer = normalized.match(/^(NDVI|NDWI|NDBI|BSI|SAVI) - Period ([12])$/);
  if (periodLayer) return `${periodLayer[1]} - الفترة ${periodLayer[2]}`;
  const changeLayer = normalized.match(
    /^(NDVI|NDWI|NDBI|BSI|SAVI) Change - Period 2 minus Period 1$/,
  );
  if (changeLayer) return `تغير ${changeLayer[1]} - الفترة 2 ناقص الفترة 1`;

  return normalized
    .replace(/^Mosaic\b/, "موزاييك")
    .replace(/\bSaudi Arabia\b/g, "المملكة العربية السعودية")
    .replace(/\bAnalysis\b/g, "تحليل");
}

function supervisedResultSummary(
  interpretation: unknown,
  accuracy: any,
  classes: any[],
  algorithm: SupervisedAlgorithm,
  language: string,
) {
  if (language !== "ar") return displayBackendText(interpretation);

  const classItems = Array.isArray(classes) ? classes : [];
  const dominant = classItems.reduce<any | null>((best, item) => {
    const itemShare = Number(item?.pct ?? item?.percentage ?? item?.surface_ha ?? 0);
    const bestShare = Number(best?.pct ?? best?.percentage ?? best?.surface_ha ?? -1);
    return !best || itemShare > bestShare ? item : best;
  }, null);
  const overall = Number(accuracy?.overall_accuracy);
  const kappa = Number(accuracy?.kappa);
  const algorithmLabel = mapText(
    algorithm === "random_forest"
      ? "Random Forest"
      : algorithm === "cart"
        ? "Decision Tree (CART)"
        : "Support Vector Machine (SVM)",
    language,
  );

  let quality =
    "مقاييس التحقق غير متاحة؛ يُرجى مراجعة عينات التدريب والتحقق قبل الاستخدام التشغيلي.";
  if (Number.isFinite(overall)) {
    if (overall >= 0.85 && Number.isFinite(kappa) && kappa >= 0.8) {
      quality = "جودة التحقق مرتفعة، والنتيجة ملائمة لتفسير غطاء الأرض.";
    } else if (overall >= 0.7) {
      quality = "جودة التحقق مقبولة، مع ضرورة مراجعة الفئات التي قد يحدث بينها التباس طيفي.";
    } else {
      quality =
        "جودة التحقق منخفضة؛ يُنصح بتحسين العينات أو اختيار منطقة الاهتمام والفترة الزمنية قبل اعتماد الخريطة.";
    }
  }

  const dominantShare = Number(dominant?.pct ?? dominant?.percentage);
  const dominantText = dominant
    ? ` الفئة الغالبة: ${mapBackendText(dominant.name, language)}${Number.isFinite(dominantShare) ? ` (${dominantShare.toFixed(1)}%)` : ""}.`
    : "";
  return `اكتمل التصنيف باستخدام خوارزمية ${algorithmLabel}. ${quality}${dominantText}`;
}

function unsupervisedResultSummary(quality: any, classes: any[], language: string) {
  const classItems = Array.isArray(classes) ? classes : [];
  const clusterCount = Number(quality?.clusters_count) || classItems.length;
  const bandCount = Array.isArray(quality?.input_bands) ? quality.input_bands.length : 0;
  const dominant = classItems.reduce<any | null>((best, item) => {
    const itemShare = Number(item?.pct ?? item?.percentage ?? item?.surface_ha ?? 0);
    const bestShare = Number(best?.pct ?? best?.percentage ?? best?.surface_ha ?? -1);
    return !best || itemShare > bestShare ? item : best;
  }, null);
  const dominantShare = Number(dominant?.pct ?? dominant?.percentage);
  const rawDominantName = String(dominant?.name ?? "");
  const dominantName =
    language === "ar"
      ? rawDominantName
          .replace(/Cluster\s+(\d+)/gi, "المجموعة $1")
          .replace(/Uninterpreted cluster/gi, "مجموعة غير مفسرة")
      : rawDominantName;

  if (language === "ar") {
    const number = new Intl.NumberFormat("ar-SA", { maximumFractionDigits: 1 });
    const bandsText = bandCount > 0 ? ` اعتمادا على ${number.format(bandCount)} نطاقا إدخاليا` : "";
    const dominantText = dominantName
      ? ` المجموعة السائدة: ${dominantName}${Number.isFinite(dominantShare) ? ` (${number.format(dominantShare)}٪)` : ""}.`
      : "";
    return `حدد التحليل ${number.format(clusterCount)} مجموعات طيفية${bandsText}.${dominantText} أرقام المجموعات أنماط طيفية وليست فئات غطاء أرضي مؤكدة، والتفسيرات الدلالية احتمالية وتتطلب مراجعة.`;
  }

  const bandsText = bandCount > 0 ? ` using ${bandCount} input bands` : "";
  const dominantText = dominantName
    ? ` Dominant group: ${dominantName}${Number.isFinite(dominantShare) ? ` (${dominantShare.toFixed(1)}%)` : ""}.`
    : "";
  return `The analysis identified ${clusterCount} spectral groups${bandsText}.${dominantText} Cluster IDs are spectral groups, not validated land-cover classes; semantic labels are probable interpretations that require review.`;
}

function mapIndexCopy(index: SpectralIndex, language: string) {
  return language === "ar"
    ? (MAP_INDEX_AR[index.id] ?? {
        name: index.name,
        topic: index.topic,
        description: index.description,
        bands: `النطاقات المستخدمة: ${index.bands.join(", ")}`,
      })
    : {
        name: index.name,
        topic: index.topic,
        description: index.description,
        bands: `Bands used: ${index.bands.join(", ")}`,
      };
}

function analysisShortLabel(index: string, language: string) {
  if (language === "ar") {
    if (index === SUPERVISED_CLASSIFICATION_ID) return "التصنيف الموجَّه";
    if (index === UNSUPERVISED_CLASSIFICATION_ID) return "التصنيف غير الموجَّه";
    if (index === OSI_SAR_ID) return "مناطق اشتباه OSI-SAR";
    if (index.startsWith("CHANGE_")) return `كشف تغير ${index.replace("CHANGE_", "")}`;
    if (index === "NDBI") return "تحليل NDBI";
    return `تصنيف ${index}`;
  }
  if (index === SUPERVISED_CLASSIFICATION_ID) return "SUPERVISED CLASSIFICATION";
  if (index === UNSUPERVISED_CLASSIFICATION_ID) return "UNSUPERVISED CLASSIFICATION";
  if (index === OSI_SAR_ID) return "OSI-SAR oil spill suspects";
  if (index.startsWith("CHANGE_")) return `${index.replace("CHANGE_", "")} Change Detection`;
  if (index === "NDBI") return "NDBI analysis";
  return `${index} classified`;
}

function changeComparisonBase(index?: string | null) {
  if (index === "CHANGE_NDVI") return "ndvi";
  if (index === "CHANGE_NDWI") return "ndwi";
  if (index === "CHANGE_NDBI") return "ndbi";
  if (index === "CHANGE_BSI") return "bsi";
  if (index === "CHANGE_SAVI") return "savi";
  return null;
}

const NDBI_BUILT_DETECTION_LAYER_KEY = "ndbi_built_detection";
const NDBI_RAW_LAYER_KEY = "ndbi_raw";
const NDBI_CLASSES_LAYER_KEY = "ndbi_classes";
const NDVI_CLASSES_LAYER_KEY = "ndvi_classes";
const NDVI_RAW_LAYER_KEY = "ndvi_raw";

function defaultComparisonLayerKey(index?: string | null) {
  if (index === "NDBI") return NDBI_BUILT_DETECTION_LAYER_KEY;
  if (index === "NDVI") return NDVI_CLASSES_LAYER_KEY;
  if (index === OSI_SAR_ID) return "osi_final_candidates";
  const base = changeComparisonBase(index);
  return base ? `${base}_change` : "ndvi_change";
}

function preferredComparisonLayerKey(index?: string | null, backendLayerKey?: string | null) {
  // User-facing NDBI result is only Built-up detection. Raw/classes stay internal.
  if (index === "NDBI") return NDBI_BUILT_DETECTION_LAYER_KEY;
  // User-facing NDVI result is discrete absolute classes (not continuous stretch).
  if (index === "NDVI") return NDVI_CLASSES_LAYER_KEY;
  return backendLayerKey ?? defaultComparisonLayerKey(index);
}

function comparisonLayerSecondaryLabel(layer: any) {
  if (layer?.key === "ndbi_classes")
    return "Value classes aligned with the legend; bare soil can also be positive in arid areas";
  if (layer?.key === "ndbi_raw") return "Continuous map stretch; class areas below are statistics only";
  if (layer?.key === "ndbi_built_detection") return "Classified built-up map";
  if (layer?.key === "ndvi_classes") return "Stable NDVI classes shared by every AOI size";
  if (layer?.key === "ndvi_raw") return "Continuous NDVI stretch; class areas below are statistics only";
  if (layer?.key === "osi_vv") return "Selected Sentinel-1 VV in dB";
  if (layer?.key === "osi_vh") return "Selected Sentinel-1 VH in dB";
  if (layer?.key === "osi_contrast") return "localMeanVV minus VV";
  if (layer?.key === "osi_raw_candidates") return "AND mask before connected-pixel filter";
  if (layer?.key === "osi_final_candidates")
    return "Oil-spill suspect after connected-pixel filter";
  if (String(layer?.key ?? "").endsWith("_change")) return "Period 2 minus Period 1";
  const start = layer?.period?.start_date ? displayBackendText(layer.period.start_date) : null;
  const end = layer?.period?.end_date ? displayBackendText(layer.period.end_date) : null;
  if (start && end) return `${start} -> ${end}`;
  return "Same AOI and base index palette";
}

function isUserVisibleComparisonLayer(index: string | null | undefined, layer: any) {
  if (index === "NDBI") return layer?.key === NDBI_BUILT_DETECTION_LAYER_KEY;
  if (index === "NDVI") return layer?.key === NDVI_CLASSES_LAYER_KEY;
  return true;
}

function analysisButtonLabel(index: string, language: string) {
  if (index === SUPERVISED_CLASSIFICATION_ID)
    return language === "ar" ? "التصنيف الموجَّه" : "SUPERVISED CLASSIFICATION";
  if (index === UNSUPERVISED_CLASSIFICATION_ID)
    return language === "ar" ? "التصنيف غير الموجَّه" : "UNSUPERVISED CLASSIFICATION";
  if (index === OSI_SAR_ID) return "OSI-SAR";
  if (index.startsWith("CHANGE_")) return index.replace("CHANGE_", "Δ ");
  return index;
}

function sensorLabel(sensor: SensorId) {
  return SENSOR_OPTIONS.find((item) => item.value === sensor)?.label ?? sensor;
}

function displayBackendText(value: unknown): string {
  if (value == null) return "-";
  return String(value)
    .replaceAll("Initialisation de la requete", "Initializing request")
    .replaceAll("Initialisation du traitement", "Initializing processing")
    .replaceAll("Validation des parametres", "Validating parameters")
    .replaceAll("Lecture de la zone d'interet", "Reading area of interest")
    .replaceAll("Connexion a Google Earth Engine", "Preparing analysis data")
    .replaceAll("Filtrage par date et capteur", "Filtering by date and sensor")
    .replaceAll("Filtrage par couverture nuageuse", "Filtering by cloud coverage")
    .replaceAll("Detection des scenes disponibles", "Detecting available scenes")
    .replaceAll("Preparation du catalogue ou de la mosaique", "Preparing the catalog or mosaic")
    .replaceAll("Preparation des apercus des images", "Preparing image previews")
    .replaceAll("Images pretes a l'affichage", "Images ready for display")
    .replaceAll("Images GEE detectees avec succes", "Satellite images detected successfully")
    .replaceAll("Erreur lors de la detection des images GEE.", "Image detection error.")
    .replaceAll("Requete en attente", "Request queued")
    .replaceAll("Traitement GEE en cours", "Raster processing in progress")
    .replaceAll("Calcul de l'indice selectionne", "Computing the selected index")
    .replaceAll("Calcul des statistiques", "Computing statistics")
    .replaceAll("Preparation de la couche cartographique", "Preparing the map layer")
    .replaceAll("Resultat charge depuis le cache", "Result loaded from cache")
    .replaceAll("Resultat pret", "Result ready")
    .replaceAll("Absence ou tres faible couverture vegetale", "No or very sparse vegetation cover")
    .replaceAll("Couverture vegetale tres forte", "Very dense vegetation cover")
    .replaceAll("Couverture vegetale moyenne", "Moderate vegetation cover")
    .replaceAll("Couverture vegetale faible", "Sparse vegetation cover")
    .replaceAll("Couverture vegetale forte", "Dense vegetation cover")
    .replaceAll("Couverture detaillee omise pour accelerer le traitement de la grande AOI.", "Detailed coverage omitted to speed up processing of the large AOI.")
    .replaceAll("Couverture detaillee differee pour accelerer le traitement de la grande AOI.", "Detailed coverage deferred to speed up processing of the large AOI.")
    .replaceAll("Couverture non calculee:", "Coverage could not be computed:")
    .replaceAll(
      "Couverture Sentinel-2 faible: elargir la periode, augmenter le seuil nuages, ou utiliser median composite.",
      "Low Sentinel-2 coverage: widen the period, raise the cloud threshold, or use a median composite.",
    )
    .replaceAll("preparee sur toute la zone d'interet.", "prepared over the full area of interest.")
    .replaceAll("generee sur la zone d'interet.", "generated over the area of interest.")
    .replaceAll("finale generee sur toute la zone d'interet.", "generated over the full area of interest.")
    .replaceAll("Absence or very low vegetation cover", "No or very sparse vegetation cover")
    .replaceAll("Very high vegetation cover", "Very dense vegetation cover")
    .replaceAll("Medium vegetation cover", "Moderate vegetation cover")
    .replaceAll("Low vegetation cover", "Sparse vegetation cover")
    .replaceAll("High vegetation cover", "Dense vegetation cover")
    .replaceAll(
      "No vegetation or very sparse vegetation cover.",
      "Bare or non-vegetated surfaces with very sparse vegetation.",
    )
    .replaceAll("Weak or sparse vegetation cover.", "Sparse or potentially stressed vegetation.")
    .replaceAll("Moderate vegetation cover.", "Moderate vegetation density.")
    .replaceAll("Sec / non eau", "Dry / non-water")
    .replaceAll("Humidite faible", "Low moisture")
    .replaceAll("Humidite moyenne", "Medium moisture")
    .replaceAll("Eau probable", "Likely water")
    .replaceAll("Non bati", "Non-built-up")
    .replaceAll("Faible artificialisation", "Low artificialization")
    .replaceAll("Bati probable", "Likely built-up")
    .replaceAll("Bati dense", "Dense built-up")
    .replaceAll("Mosaique", "Mosaic")
    .replaceAll("mosaique", "mosaic")
    .replaceAll("Disponible", "Available")
    .replaceAll("disponible", "available")
    .replaceAll("valide", "valid")
    .replaceAll("Valide", "Valid")
    .replaceAll("bonne", "good")
    .replaceAll("Bonne", "Good")
    .replaceAll("terminee", "completed")
    .replaceAll("termine", "completed")
    .replaceAll("Connecting to Google Earth Engine", "Preparing analysis data")
    .replaceAll("Google Earth Engine", "online processing service")
    .replaceAll("GEE", "online service");
}

async function waitForVisibleMapImages(container: HTMLElement, timeoutMs = 3500) {
  const images = Array.from(container.querySelectorAll<HTMLImageElement>("img"));
  const pending = images.filter((img) => !img.complete || img.naturalWidth === 0);
  if (pending.length > 0) {
    await Promise.all(
      pending.map(
        (img) =>
          new Promise<void>((resolve) => {
            const timer = window.setTimeout(resolve, timeoutMs);
            const done = () => {
              window.clearTimeout(timer);
              resolve();
            };
            img.addEventListener("load", done, { once: true });
            img.addEventListener("error", done, { once: true });
          }),
      ),
    );
  }
  await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
  await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
}

function loadCanvasImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Unable to load map tile"));
    img.src = src;
  });
}

function canDrawImageSafely(img: HTMLImageElement) {
  try {
    const test = document.createElement("canvas");
    test.width = 1;
    test.height = 1;
    const testCtx = test.getContext("2d");
    if (!testCtx) return false;
    testCtx.drawImage(img, 0, 0, 1, 1);
    test.toDataURL("image/png");
    return true;
  } catch {
    return false;
  }
}

function canvasRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  radius: number,
) {
  const r = Math.min(radius, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function canvasWrappedLines(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  maxLines = 2,
) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (ctx.measureText(candidate).width <= maxWidth) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = word;
    if (lines.length >= maxLines) break;
  }
  if (current && lines.length < maxLines) lines.push(current);
  if (lines.length === maxLines && words.join(" ").length > lines.join(" ").length) {
    lines[maxLines - 1] = `${lines[maxLines - 1].replace(/\.+$/, "")}...`;
  }
  return lines;
}

function drawCanvasWrappedText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines = 2,
) {
  for (const line of canvasWrappedLines(ctx, text, maxWidth, maxLines)) {
    ctx.fillText(line, x, y);
    y += lineHeight;
  }
  return y;
}

async function drawLeafletSvgOverlays(
  ctx: CanvasRenderingContext2D,
  map: HTMLElement,
  mapRect: DOMRect,
  options?: { aoiOnly?: boolean },
) {
  const svgs = Array.from(map.querySelectorAll<SVGSVGElement>(".leaflet-overlay-pane svg"));
  for (const svg of svgs) {
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    const clone = svg.cloneNode(true) as SVGSVGElement;
    if (options?.aoiOnly) {
      const keep = Array.from(
        clone.querySelectorAll<SVGGraphicsElement>("path, rect, polygon, polyline"),
      ).filter((element) => {
        const stroke =
          `${element.getAttribute("stroke") ?? ""} ${element.getAttribute("style") ?? ""}`.toLowerCase();
        return stroke.includes("#f59e0b") || stroke.includes("245, 158, 11");
      });
      if (keep.length === 0) continue;
      Array.from(
        clone.querySelectorAll<SVGGraphicsElement>("path, rect, polygon, polyline"),
      ).forEach((element) => {
        if (!keep.includes(element)) element.remove();
      });
    }
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.setAttribute("width", String(rect.width));
    clone.setAttribute("height", String(rect.height));
    const src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(clone))}`;
    try {
      const img = await loadCanvasImage(src);
      ctx.drawImage(img, rect.left - mapRect.left, rect.top - mapRect.top, rect.width, rect.height);
    } catch {
      // Vector overlays are helpful for AOI borders, but the export should still continue if one cannot be serialized.
    }
  }
}

function drawMapScaleAndAttribution(
  ctx: CanvasRenderingContext2D,
  map: HTMLElement,
  mapRect: DOMRect,
) {
  ctx.save();
  ctx.font = "12px Arial, sans-serif";
  ctx.textBaseline = "top";

  for (const scale of Array.from(
    map.querySelectorAll<HTMLElement>(".leaflet-control-scale-line"),
  )) {
    const rect = scale.getBoundingClientRect();
    const x = rect.left - mapRect.left;
    const y = rect.top - mapRect.top;
    ctx.fillStyle = "rgba(255, 255, 255, 0.88)";
    ctx.fillRect(x, y, Math.max(rect.width, 50), Math.max(rect.height, 18));
    ctx.strokeStyle = "#111827";
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, Math.max(rect.width, 50), Math.max(rect.height, 18));
    ctx.fillStyle = "#111827";
    ctx.fillText(scale.textContent?.trim() ?? "", x + 4, y + 2);
  }

  const attribution = map.querySelector<HTMLElement>(".leaflet-control-attribution");
  if (attribution?.textContent) {
    const text = attribution.textContent.replace(/\s+/g, " ").trim();
    ctx.font = "11px Arial, sans-serif";
    const width = Math.min(ctx.measureText(text).width + 14, mapRect.width - 24);
    const x = mapRect.width - width - 8;
    const y = mapRect.height - 24;
    ctx.fillStyle = "rgba(255, 255, 255, 0.86)";
    ctx.fillRect(x, y, width, 18);
    ctx.fillStyle = "#334155";
    ctx.fillText(text.slice(0, 120), x + 7, y + 4);
  }

  ctx.restore();
}

function findAoiCropRect(map: HTMLElement, mapRect: DOMRect) {
  const overlays = Array.from(
    map.querySelectorAll<SVGGraphicsElement>(
      ".leaflet-overlay-pane path, .leaflet-overlay-pane rect",
    ),
  );
  const orange = overlays
    .map((element) => ({
      element,
      rect: element.getBoundingClientRect(),
      stroke:
        `${element.getAttribute("stroke") ?? ""} ${window.getComputedStyle(element).stroke}`.toLowerCase(),
    }))
    .filter(
      ({ rect, stroke }) =>
        rect.width > 10 &&
        rect.height > 10 &&
        (stroke.includes("#f59e0b") || stroke.includes("245, 158, 11")),
    );
  const candidates =
    orange.length > 0
      ? orange
      : overlays
          .map((element) => ({ element, rect: element.getBoundingClientRect(), stroke: "" }))
          .filter(({ rect }) => rect.width > 10 && rect.height > 10);
  if (candidates.length === 0) return null;
  const target = candidates.reduce((best, item) => {
    const area = item.rect.width * item.rect.height;
    const bestArea = best.rect.width * best.rect.height;
    return area > bestArea ? item : best;
  });
  const padding = 18;
  const left = Math.max(0, target.rect.left - mapRect.left - padding);
  const top = Math.max(0, target.rect.top - mapRect.top - padding);
  const right = Math.min(mapRect.width, target.rect.right - mapRect.left + padding);
  const bottom = Math.min(mapRect.height, target.rect.bottom - mapRect.top + padding);
  if (right - left < 80 || bottom - top < 80) return null;
  return { left, top, width: right - left, height: bottom - top };
}

function cropCanvasToRect(
  canvas: HTMLCanvasElement,
  crop: { left: number; top: number; width: number; height: number },
  scale: number,
) {
  const output = document.createElement("canvas");
  output.width = Math.max(1, Math.round(crop.width * scale));
  output.height = Math.max(1, Math.round(crop.height * scale));
  const outputCtx = output.getContext("2d");
  if (!outputCtx) return canvas;
  outputCtx.drawImage(
    canvas,
    Math.round(crop.left * scale),
    Math.round(crop.top * scale),
    Math.round(crop.width * scale),
    Math.round(crop.height * scale),
    0,
    0,
    output.width,
    output.height,
  );
  return output;
}

function blankMapScreenshotDataUrl() {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 360;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#eef5f8";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
  return canvas.toDataURL("image/png");
}

async function captureLeafletMapImage(
  container: HTMLElement,
  options?: { cropToAoi?: boolean; basemapOnly?: boolean; resultOnly?: boolean },
) {
  await waitForVisibleMapImages(container);
  const map = container.querySelector<HTMLElement>(".leaflet-container") ?? container;
  const mapRect = map.getBoundingClientRect();
  const scale = Math.min(window.devicePixelRatio || 1, 2);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(mapRect.width * scale));
  canvas.height = Math.max(1, Math.round(mapRect.height * scale));
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas capture unavailable.");

  ctx.scale(scale, scale);
  ctx.fillStyle = "#eef5f8";
  ctx.fillRect(0, 0, mapRect.width, mapRect.height);

  const tiles = Array.from(map.querySelectorAll<HTMLImageElement>("img.leaflet-tile"));
  let drawnTiles = 0;
  for (const tile of tiles) {
    if (!tile.complete || tile.naturalWidth === 0 || tile.naturalHeight === 0) continue;
    const rect = tile.getBoundingClientRect();
    if (
      rect.right < mapRect.left ||
      rect.left > mapRect.right ||
      rect.bottom < mapRect.top ||
      rect.top > mapRect.bottom
    )
      continue;
    if (!canDrawImageSafely(tile)) continue;
    const layer = tile.closest<HTMLElement>(".leaflet-layer");
    const layerOpacity = layer ? Number(window.getComputedStyle(layer).opacity) : 1;
    const layerStyle = layer ? window.getComputedStyle(layer) : null;
    const layerZIndex = layerStyle ? Number(layerStyle.zIndex) : NaN;
    const isResultTile =
      tile.classList.contains("georaster-result-tile") ||
      Boolean(layer?.classList.contains("georaster-result-tile")) ||
      (Number.isFinite(layerZIndex) && layerZIndex >= 400);
    if (options?.resultOnly && !isResultTile) continue;
    if (options?.basemapOnly && Number.isFinite(layerOpacity) && layerOpacity < 0.99) continue;
    ctx.save();
    ctx.globalAlpha = Number.isFinite(layerOpacity) ? layerOpacity : 1;
    ctx.drawImage(tile, rect.left - mapRect.left, rect.top - mapRect.top, rect.width, rect.height);
    ctx.restore();
    drawnTiles += 1;
  }

  if (options?.resultOnly && drawnTiles === 0) {
    throw new Error(
      "The classified raster tiles are not ready for PNG export. Please wait for the map result to finish loading and try again.",
    );
  }

  if (!options?.resultOnly) {
    await drawLeafletSvgOverlays(ctx, map, mapRect, { aoiOnly: options?.basemapOnly });
    drawMapScaleAndAttribution(ctx, map, mapRect);
  }

  const crop = options?.cropToAoi === false ? null : findAoiCropRect(map, mapRect);
  const output = crop ? cropCanvasToRect(canvas, crop, scale) : canvas;
  return options?.resultOnly ? output.toDataURL("image/png") : output.toDataURL("image/jpeg", 0.92);
}

async function captureLeafletMapForPdf(container: HTMLElement) {
  return captureLeafletMapImage(container, { cropToAoi: true });
}

function bboxToGeometry(bbox: [[number, number], [number, number]]) {
  const [[south, west], [north, east]] = bbox;
  return {
    type: "Polygon",
    coordinates: [
      [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ],
    ],
  };
}

function bboxFromStoredAnalysis(analysis: any): [[number, number], [number, number]] | null {
  const bbox = analysis?.aoi?.bbox;
  if (Array.isArray(bbox) && bbox.length === 2) {
    return [
      [Number(bbox[0][0]), Number(bbox[0][1])],
      [Number(bbox[1][0]), Number(bbox[1][1])],
    ];
  }
  const coordinates = analysis?.geometry?.coordinates?.[0];
  if (Array.isArray(coordinates) && coordinates.length) {
    const lats = coordinates.map((item: any) => Number(item[1])).filter(Number.isFinite);
    const lons = coordinates.map((item: any) => Number(item[0])).filter(Number.isFinite);
    if (lats.length && lons.length) {
      return [
        [Math.min(...lats), Math.min(...lons)],
        [Math.max(...lats), Math.max(...lons)],
      ];
    }
  }
  return null;
}

function layerToRunResult(layer: any) {
  const layerTiles = layer.tiles ?? {};
  const indexTileUrl = layerTiles.index_tile_url ?? layer.index_tile_url ?? layer.tile_url ?? null;
  const rgbTileUrl = layerTiles.rgb_tile_url ?? layer.rgb_tile_url ?? null;
  return {
    stats: layer.stats ?? layer.statistics,
    histogram: layer.histogram ?? [],
    classes: layer.classes ?? layer.legend ?? [],
    tiles: {
      ...layerTiles,
      index_tile_url: indexTileUrl,
      rgb_tile_url: rgbTileUrl,
    },
    mosaic: layer.mosaic,
    quality: layer.quality,
    quality_summary: layer.quality_summary,
    accuracy: layer.accuracy,
    palette: layer.palette,
    tile_source_palette: layer.tile_source_palette,
    analysis_type: layer.analysis_type,
    algorithm_comparison: layer.algorithm_comparison,
    comparison_layers: layer.comparison_layers ?? [],
    active_comparison_layer: layer.active_comparison_layer ?? null,
    interpretation: layer.interpretation,
    cluster_interpretation: layer.cluster_interpretation,
    cached: true,
    mode: layer.mode,
    run_id: layer.run_id ?? layer.latest_run_id ?? null,
    latest_run_id: layer.latest_run_id ?? layer.run_id ?? null,
  };
}

function mergeComparisonLayerTiles(result: any, refreshedLayers: any[] | undefined) {
  if (!result || !Array.isArray(refreshedLayers) || refreshedLayers.length === 0) return result;
  const refreshedByKey = new Map(refreshedLayers.map((layer) => [layer.key, layer]));
  return {
    ...result,
    comparison_layers: (result.comparison_layers ?? []).map((layer: any) => {
      const refreshed = refreshedByKey.get(layer.key);
      if (!refreshed) return layer;
      return {
        ...layer,
        tiles: {
          ...(layer.tiles ?? {}),
          ...(refreshed.tiles ?? {}),
        },
      };
    }),
  };
}

function removeHistoryRunIdFromUrl() {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (!url.searchParams.has("run_id")) return;
  url.searchParams.delete("run_id");
  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState(window.history.state, "", nextUrl || "/map");
}

function runIdFromBrowserLocation() {
  if (typeof window === "undefined") return undefined;
  return new URLSearchParams(window.location.search).get("run_id") ?? undefined;
}

const HISTORY_RESTORE_STORAGE_KEY = "georaster:history-restore";

type LiveCatalogImage = SatImage & {
  gee_id?: string | null;
  mosaic?: boolean;
  date_mosaic?: boolean;
  acquisition_date?: string;
  tile_url?: string | null;
  quality?: Record<string, unknown>;
  orbit_pass?: string;
  relative_orbit?: string | number;
  acquisition_timestamp?: number;
  platform?: string;
  cloud_source?: string;
};

function consumeStoredHistoryResult(runId: string) {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(HISTORY_RESTORE_STORAGE_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw);
    if (stored?.run_id !== runId || !stored?.item) return null;
    sessionStorage.removeItem(HISTORY_RESTORE_STORAGE_KEY);
    return stored.item;
  } catch {
    sessionStorage.removeItem(HISTORY_RESTORE_STORAGE_KEY);
    return null;
  }
}

function MapPage() {
  const routeSearch = Route.useSearch();
  const { t, isRtl, language } = useI18n();
  const historyRunId = routeSearch.run_id ?? runIdFromBrowserLocation();
  const [tab, setTab] = useState<TabKey>("images");
  const [catalogImages, setCatalogImages] = useState<LiveCatalogImage[]>([]);
  const [selectedImage, setSelectedImage] = useState<LiveCatalogImage | null>(null);
  const [aoi, setAoi] = useState<[[number, number], [number, number]] | null>(null);
  const [aoiGeometry, setAoiGeometry] = useState<AoiGeometry | null>(null);
  const [aoiParts, setAoiParts] = useState<AoiSplitPart[]>([]);
  const [selectedPartIds, setSelectedPartIds] = useState<string[]>([]);
  const [aoiSource, setAoiSource] = useState<{
    bbox: [[number, number], [number, number]];
    geometry: AoiGeometry | null;
  } | null>(null);
  const [aoiFitNonce, setAoiFitNonce] = useState(0);
  const aoiFileInputRef = useRef<HTMLInputElement>(null);
  const [showAoi, setShowAoi] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState<SpectralIndex | null>(indices[0]);
  const [analysisFamily, setAnalysisFamily] = useState<"raster" | "ai_building">("raster");
  const [buildingSourceMode, setBuildingSourceMode] = useState<BuildingSourceMode>("sentinel2");
  const [buildingParameters, setBuildingParameters] = useState<BuildingDetectionParameters>({
    ...DEFAULT_BUILDING_PARAMETERS,
  });
  const [preparedBuildingRaster, setPreparedBuildingRaster] = useState<AIRasterPrepareResult | null>(null);
  const [buildingRasterPreviewUrl, setBuildingRasterPreviewUrl] = useState<string | null>(null);
  const [buildingUploadFileName, setBuildingUploadFileName] = useState<string | null>(null);
  const [buildingResult, setBuildingResult] = useState<BuildingAnalysisResult | null>(null);
  const [showBuildingLayer, setShowBuildingLayer] = useState(false);
  const [buildingFitNonce, setBuildingFitNonce] = useState(0);
  const [isBuildingUploading, setIsBuildingUploading] = useState(false);
  const [buildingUploadProgress, setBuildingUploadProgress] = useState<{ phase: "uploading" | "preparing"; ratio: number } | null>(null);
  const [isBuildingRunning, setIsBuildingRunning] = useState(false);
  const [buildingExportingFormat, setBuildingExportingFormat] = useState<BuildingExportFormat | null>(null);
  const [buildingError, setBuildingError] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState<"rectangle" | "point" | "polygon" | null>(null);
  const [basemap, setBasemap] = useState<BasemapKey>(
    () => readCachedPlatformSettings()?.default_basemap ?? "osm",
  );

  const [showRaster, setShowRaster] = useState(true);
  const [showResult, setShowResult] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [rasterOpacity, setRasterOpacity] = useState(0.8);
  const [resultOpacity, setResultOpacity] = useState(0.85);

  const [step, setStep] = useState<Step>("idle");
  const [hasResult, setHasResult] = useState(false);
  const [isSearchingImages, setIsSearchingImages] = useState(false);
  const [geeSearchProgress, setGeeSearchProgress] = useState<GeeProgressState>({
    visible: false,
    percent: 0,
    message: "Searching satellite images...",
    error: false,
  });
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgressState>({
    visible: false,
    percent: 0,
    message: "Initializing processing...",
    error: false,
    cached: false,
  });
  const geeSearchSeqRef = useRef(0);
  const analysisProgressTimerRef = useRef<number | null>(null);
  const analysisProgressSeqRef = useRef(0);
  const restoredHistoryRunRef = useRef<string | null>(null);
  const tileRefreshRunRef = useRef<string | null>(null);
  const tileRefreshAttemptedRunsRef = useRef<Set<string>>(new Set());
  const suppressAutoCatalogLoadRef = useRef(false);
  const supervisedClassesInitializedRef = useRef(false);
  const [catalogMode, setCatalogMode] = useState<"gee" | "unavailable" | "unknown">("unknown");
  const [geeEnabled, setGeeEnabled] = useState<boolean | null>(null);
  const [previewingImageId, setPreviewingImageId] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<any | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [liveRasterTileUrl, setLiveRasterTileUrl] = useState<string | null>(null);
  const [liveResultTileUrl, setLiveResultTileUrl] = useState<string | null>(null);
  const [resultLayers, setResultLayers] = useState<any[]>([]);
  const [activeComparisonLayerKey, setActiveComparisonLayerKey] = useState<string>("ndvi_change");
  const [activeResultCacheKey, setActiveResultCacheKey] = useState<string | null>(null);
  const [resultStatusByIndex, setResultStatusByIndex] = useState<Record<string, string>>({});
  const [dateStart, setDateStart] = useState("2025-01-01");
  const [dateEnd, setDateEnd] = useState(new Date().toISOString().slice(0, 10));
  const [changeDateStart1, setChangeDateStart1] = useState("2025-01-01");
  const [changeDateEnd1, setChangeDateEnd1] = useState("2025-03-31");
  const [changeDateStart2, setChangeDateStart2] = useState("2026-01-01");
  const [changeDateEnd2, setChangeDateEnd2] = useState(new Date().toISOString().slice(0, 10));
  const [maxCloudPct, setMaxCloudPct] = useState(25);
  const [sensor, setSensor] = useState<SensorId>("sentinel-2");
  const [resolution, setResolution] = useState<ResolutionId>("auto");
  const [imageMethod, setImageMethod] = useState<ImageMethod>("median_composite");
  const [supervisedAlgorithm, setSupervisedAlgorithm] =
    useState<SupervisedAlgorithm>("random_forest");
  const [supervisedTrees, setSupervisedTrees] = useState(150);
  const [supervisedSamplesPerClass, setSupervisedSamplesPerClass] = useState(160);
  const [supervisedTrainingPct, setSupervisedTrainingPct] = useState(70);
  const [compareSupervisedAlgorithms, setCompareSupervisedAlgorithms] = useState(true);
  const [landcoverClasses, setLandcoverClasses] = useState<any[]>([]);
  const [trainingSamples, setTrainingSamples] = useState<any[]>([]);
  const [activeSampleClassId, setActiveSampleClassId] = useState<string>("");
  const [activeSampleUsage, setActiveSampleUsage] = useState<"training" | "validation">("training");
  const [showSavedTrainingSamples, setShowSavedTrainingSamples] = useState(false);
  const [supervisedWorkflowStep, setSupervisedWorkflowStep] = useState<SupervisedWorkflowStep>(1);
  const [selectedSupervisedClassIds, setSelectedSupervisedClassIds] = useState<string[]>([]);
  const [newLandcoverClassName, setNewLandcoverClassName] = useState("");
  const [newLandcoverClassColor, setNewLandcoverClassColor] = useState("#7c3aed");
  const [isSavingSupervisedSample, setIsSavingSupervisedSample] = useState(false);
  const [unsupervisedMode, setUnsupervisedMode] = useState<UnsupervisedMode>("simple");
  const [unsupervisedClusters, setUnsupervisedClusters] = useState(6);
  const [unsupervisedSamplesCount, setUnsupervisedSamplesCount] = useState(5000);
  const [unsupervisedBands, setUnsupervisedBands] = useState<string[]>(
    UNSUPERVISED_BANDS_BY_SENSOR["sentinel-2"],
  );
  const [osiDarkThresholdDb, setOsiDarkThresholdDb] = useState(-18);
  const [osiVhDarkThresholdDb, setOsiVhDarkThresholdDb] = useState(-25);
  const [osiContrastThresholdDb, setOsiContrastThresholdDb] = useState(2.5);
  const [osiContrastRadiusM, setOsiContrastRadiusM] = useState(500);
  const [osiMinConnectedPixels, setOsiMinConnectedPixels] = useState(8);
  const [osiWaterMask, setOsiWaterMask] = useState(true);
  const [osiOrbitPass, setOsiOrbitPass] = useState<"ANY" | "ASCENDING" | "DESCENDING">("ANY");
  const [osiWindValidation, setOsiWindValidation] = useState(true);
  const [osiWindMinMs, setOsiWindMinMs] = useState(2);
  const [osiWindMaxMs, setOsiWindMaxMs] = useState(10);
  const [osiSentinel2Validation, setOsiSentinel2Validation] = useState(false);
  const [isMapLayoutExporting, setIsMapLayoutExporting] = useState(false);
  const [isMapPdfExporting, setIsMapPdfExporting] = useState(false);
  const mapCaptureRef = useRef<HTMLDivElement | null>(null);

  // Load MapView client-only (Leaflet uses window)
  const [MapComp, setMapComp] = useState<null | typeof import("@/components/MapView").MapView>(
    null,
  );
  useEffect(() => {
    import("@/components/MapView").then((m) => setMapComp(() => m.MapView));
  }, []);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 8;

    const probe = () => {
      attempts += 1;
      getGeeStatus()
        .then((res) => {
          if (cancelled) return;
          const enabled = Boolean(res.item.enabled);
          setGeeEnabled(enabled);
          if (!enabled && attempts < maxAttempts) {
            window.setTimeout(probe, 4000);
          }
        })
        .catch(() => {
          if (cancelled) return;
          setGeeEnabled(false);
          if (attempts < maxAttempts) {
            window.setTimeout(probe, 4000);
          }
        });
    };

    probe();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    getLandcoverClasses()
      .then((response) => setLandcoverClasses(response.items ?? []))
      .catch(() => setLandcoverClasses([]));
  }, []);

  useEffect(() => {
    if (!activeSampleClassId && landcoverClasses.length > 0) {
      setActiveSampleClassId(String(landcoverClasses[0].id ?? ""));
    }
  }, [activeSampleClassId, landcoverClasses]);

  useEffect(() => {
    if (supervisedClassesInitializedRef.current || landcoverClasses.length === 0) return;
    supervisedClassesInitializedRef.current = true;
    setSelectedSupervisedClassIds(
      landcoverClasses
        .slice(0, Math.min(2, landcoverClasses.length))
        .map((item) => String(item.id)),
    );
  }, [landcoverClasses]);

  useEffect(() => {
    getTrainingSamples()
      .then((res) => setTrainingSamples(res.items ?? []))
      .catch(() => setTrainingSamples([]));
  }, []);

  useEffect(() => {
    const supervisedSelected = selectedIndex?.id === SUPERVISED_CLASSIFICATION_ID;
    if (supervisedSelected) {
      setShowSavedTrainingSamples(true);
      return;
    }
    if (drawMode === "point" || drawMode === "polygon") setDrawMode(null);
    setShowSavedTrainingSamples(false);
  }, [selectedIndex?.id]);

  const handleSampleCreated = async (sample: { type: string; geometry: any; properties?: any }) => {
    try {
      if (!activeSampleClassId) {
        toast.warning(mapText("Select a land-cover class before drawing a sample.", language));
        return;
      }
      if (!selectedSupervisedClassIds.includes(activeSampleClassId)) {
        toast.warning(mapText("The active class must be selected in step 1.", language));
        return;
      }
      setIsSavingSupervisedSample(true);
      const payload = {
        project_id: "default",
        class_id: activeSampleClassId,
        geometry: sample.geometry,
        geometry_type: sample.type,
        usage: activeSampleUsage,
        source:
          sample.type === "Point"
            ? "draw_point"
            : sample.type === "Polygon"
              ? "draw_polygon"
              : "manual",
        properties: sample.properties || {},
      };
      const res = await createTrainingSample(payload);
      const item = res.item;
      setTrainingSamples((prev) => [item, ...prev]);
      setShowSavedTrainingSamples(true);
      toast.success(
        mapText(
          activeSampleUsage === "training"
            ? "Training sample created"
            : "Validation sample created",
          language,
        ),
      );
      setDrawMode(null);
    } catch (err: any) {
      toast.error(
        `${mapText("Failed to save sample", language)}: ${language === "ar" ? mapText("Backend error", language) : (err?.message ?? "")}`,
      );
    } finally {
      setIsSavingSupervisedSample(false);
    }
  };

  const handleCreateLandcoverClass = async () => {
    const name = newLandcoverClassName.trim();
    if (!name) {
      toast.warning(mapText("Enter a class name.", language));
      return;
    }
    const existingClass = landcoverClasses.find(
      (item) => String(item.name).trim().toLocaleLowerCase() === name.toLocaleLowerCase(),
    );
    if (existingClass) {
      const existingClassId = String(existingClass.id);
      setSelectedSupervisedClassIds((previous) =>
        previous.includes(existingClassId) ? previous : [...previous, existingClassId],
      );
      setActiveSampleClassId(existingClassId);
      setNewLandcoverClassName("");
      toast.info(mapText("Class already exists", language), {
        description: `${mapBackendText(existingClass.name, language)} ${mapText("was selected instead of creating a duplicate.", language)}`,
      });
      return;
    }
    const nextCode = Math.max(0, ...landcoverClasses.map((item) => Number(item.code) || 0)) + 1;
    try {
      const response = await createLandcoverClass({
        project_id: "default",
        code: nextCode,
        name,
        color: newLandcoverClassColor,
      });
      const created = response.item;
      setLandcoverClasses((previous) =>
        [...previous, created].sort((a, b) => Number(a.code) - Number(b.code)),
      );
      setSelectedSupervisedClassIds((previous) => [...previous, String(created.id)]);
      setActiveSampleClassId(String(created.id));
      setNewLandcoverClassName("");
      toast.success(mapText("Land-cover class created.", language));
    } catch (error) {
      toast.error(mapText("Unable to create class", language), {
        description:
          language === "ar"
            ? mapText("Backend error", language)
            : error instanceof Error
              ? error.message
              : "Backend error",
      });
    }
  };

  const handleDeleteTrainingSample = async (sampleId: string) => {
    try {
      await deleteTrainingSample(sampleId);
      setTrainingSamples((previous) => previous.filter((sample) => String(sample.id) !== sampleId));
      toast.success(mapText("Training sample deleted.", language));
    } catch (error) {
      toast.error(mapText("Unable to delete sample", language), {
        description:
          language === "ar"
            ? mapText("Backend error", language)
            : error instanceof Error
              ? error.message
              : "Backend error",
      });
    }
  };

  const handleDeleteClassSamples = async (classId: string) => {
    try {
      const response = await deleteTrainingSamplesForClass(classId);
      setTrainingSamples((previous) =>
        previous.filter((sample) => String(sample.class_id) !== classId),
      );
      toast.success(
        `${response.samples_deleted} ${mapText("sample(s) deleted for this class.", language)}`,
      );
    } catch (error) {
      toast.error(mapText("Unable to delete class samples", language), {
        description:
          language === "ar"
            ? mapText("Backend error", language)
            : error instanceof Error
              ? error.message
              : "Backend error",
      });
    }
  };

  const handleUpdateTrainingSampleClass = async (sampleId: string, classId: string) => {
    try {
      const response = await updateTrainingSample(sampleId, { class_id: classId });
      setTrainingSamples((previous) =>
        previous.map((sample) => (String(sample.id) === sampleId ? response.item : sample)),
      );
      toast.success(mapText("Sample class updated.", language));
    } catch (error) {
      toast.error(mapText("Unable to update sample class", language), {
        description:
          language === "ar"
            ? mapText("Backend error", language)
            : error instanceof Error
              ? error.message
              : "Backend error",
      });
    }
  };

  const toggleSupervisedClass = (classId: string) => {
    setSelectedSupervisedClassIds((previous) => {
      const next = previous.includes(classId)
        ? previous.filter((value) => value !== classId)
        : [...previous, classId];
      if (!next.includes(activeSampleClassId)) setActiveSampleClassId(next[0] ?? "");
      return next;
    });
  };

  const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const startGeeSearchProgress = () => {
    setGeeSearchProgress({
      visible: true,
      percent: 0,
      message: mapText("Initializing request...", language),
      error: false,
    });
  };

  const updateGeeSearchProgress = (percent: number, message?: string) => {
    const backendMessage = displayBackendText(message || "Image processing in progress...");
    const localizedMessage = mapText(backendMessage, language);
    setGeeSearchProgress({
      visible: true,
      percent: Math.max(0, Math.min(Math.round(percent), 100)),
      message:
        language === "ar" && localizedMessage === backendMessage
          ? mapText("Image processing in progress...", language)
          : localizedMessage,
      error: false,
    });
  };

  const completeGeeSearchProgress = () => {
    setGeeSearchProgress({
      visible: true,
      percent: 100,
      message: mapText("Images ready for display.", language),
      error: false,
    });
    window.setTimeout(() => {
      setGeeSearchProgress((prev) => (prev.error ? prev : { ...prev, visible: false }));
    }, 2000);
  };

  const failGeeSearchProgress = (message?: string) => {
    setGeeSearchProgress({
      visible: true,
      percent: 100,
      message:
        language === "ar"
          ? mapText(
              "Image detection error. Please widen the period, increase the cloud threshold, or reduce the area.",
              language,
            )
          : displayBackendText(
              message ||
                "Image detection error. Please widen the period, increase the cloud threshold, or reduce the area.",
            ),
      error: true,
    });
  };

  const stopAnalysisProgressTimer = () => {
    if (analysisProgressTimerRef.current != null) {
      window.clearInterval(analysisProgressTimerRef.current);
      analysisProgressTimerRef.current = null;
    }
  };

  const updateAnalysisProgress = (percent: number, message?: string) => {
    setAnalysisProgress((prev) => ({
      ...prev,
      visible: true,
      percent: Math.max(0, Math.min(Math.round(percent), 100)),
      message: message ? mapBackendText(message, language) : prev.message,
      error: false,
      cached: false,
    }));
  };

  const startAnalysisProgress = () => {
    stopAnalysisProgressTimer();
    analysisProgressSeqRef.current += 1;
    const seq = analysisProgressSeqRef.current;
    let stepIndex = 0;
    setAnalysisProgress({
      visible: true,
      percent: ANALYSIS_PROGRESS_STEPS[0].percent,
      message: mapText(ANALYSIS_PROGRESS_STEPS[0].message, language),
      error: false,
      cached: false,
    });

    analysisProgressTimerRef.current = window.setInterval(() => {
      if (seq !== analysisProgressSeqRef.current) {
        stopAnalysisProgressTimer();
        return;
      }
      stepIndex = Math.min(stepIndex + 1, ANALYSIS_PROGRESS_STEPS.length - 1);
      const next = ANALYSIS_PROGRESS_STEPS[stepIndex];
      setAnalysisProgress((prev) => {
        if (prev.error || prev.percent >= 100) return prev;
        return { ...prev, percent: next.percent, message: mapText(next.message, language) };
      });
      if (stepIndex >= ANALYSIS_PROGRESS_STEPS.length - 1) {
        stopAnalysisProgressTimer();
      }
    }, 1200);
  };

  const completeAnalysisProgress = (message = "Result ready.") => {
    stopAnalysisProgressTimer();
    const seq = analysisProgressSeqRef.current;
    setAnalysisProgress({
      visible: true,
      percent: 100,
      message: mapText(message, language),
      error: false,
      cached: false,
    });
    window.setTimeout(() => {
      if (seq === analysisProgressSeqRef.current) {
        setAnalysisProgress((prev) => (prev.error ? prev : { ...prev, visible: false }));
      }
    }, 2000);
  };

  const completeCachedAnalysisProgress = () => {
    stopAnalysisProgressTimer();
    analysisProgressSeqRef.current += 1;
    const seq = analysisProgressSeqRef.current;
    setAnalysisProgress({
      visible: true,
      percent: 0,
      message: mapText("Loading result from cache...", language),
      error: false,
      cached: true,
    });
    window.setTimeout(() => {
      if (seq === analysisProgressSeqRef.current) {
        setAnalysisProgress({
          visible: true,
          percent: 100,
          message: mapText("Result loaded from cache.", language),
          error: false,
          cached: true,
        });
      }
    }, 250);
    window.setTimeout(() => {
      if (seq === analysisProgressSeqRef.current) {
        setAnalysisProgress((prev) => (prev.error ? prev : { ...prev, visible: false }));
      }
    }, 2200);
  };

  const failAnalysisProgress = (message?: string) => {
    stopAnalysisProgressTimer();
    analysisProgressSeqRef.current += 1;
    const fallback = mapText(
      "Index calculation error. Please check the area, period, sensor, or try again later.",
      language,
    );
    const resolved =
      message && message.trim()
        ? mapBackendText(message, language)
        : fallback;
    setAnalysisProgress({
      visible: true,
      percent: 100,
      message: resolved,
      error: true,
      cached: false,
    });
  };

  useEffect(() => {
    return () => stopAnalysisProgressTimer();
  }, []);

  const buildRasterPayload = (index = selectedIndex?.id ?? "NDVI") => {
    if (!aoi) return null;
    const isSupervised = index === SUPERVISED_CLASSIFICATION_ID;
    const isUnsupervised = index === UNSUPERVISED_CLASSIFICATION_ID;
    const isOsiSar = index === OSI_SAR_ID;
    const isChangeDetection = index.startsWith("CHANGE_");
    const payloadSensor = isOsiSar ? "sentinel-1" : sensor;
    const payloadStart = isChangeDetection ? changeDateStart2 : dateStart;
    const payloadEnd = isChangeDetection ? changeDateEnd2 : dateEnd;
    const selectedSceneId =
      selectedImage && !(selectedImage as any).mosaic
        ? String((selectedImage as any).gee_id ?? selectedImage.id ?? "").trim() || undefined
        : undefined;
    const effectiveImageMethod: ImageMethod =
      isOsiSar ? "selected_scene" : isChangeDetection ? "median_composite" : imageMethod;
    return {
      geometry: aoiGeometry ?? bboxToGeometry(aoi),
      start_date: payloadStart,
      end_date: payloadEnd,
      sensor: payloadSensor,
      resolution,
      cloud_max: maxCloudPct,
      image_method: effectiveImageMethod,
      image_id: effectiveImageMethod === "selected_scene" ? selectedSceneId : undefined,
      index,
      analysis_type: analysisTypeForIndex(index),
      ...(isChangeDetection
        ? {
            period_1: { start_date: changeDateStart1, end_date: changeDateEnd1 },
            period_2: { start_date: changeDateStart2, end_date: changeDateEnd2 },
          }
        : {}),
      ...(isSupervised
        ? {
            supervised_options: {
              algorithm: supervisedAlgorithm,
              trees: supervisedTrees,
              samples_per_class: supervisedSamplesPerClass,
              training_split: supervisedTrainingPct / 100,
              compare_algorithms: compareSupervisedAlgorithms,
              project_id: "default",
              class_ids: selectedSupervisedClassIds,
              require_user_samples: true,
            },
          }
        : {}),
      ...(isUnsupervised
        ? {
            unsupervised_options: {
              mode: unsupervisedMode,
              clusters_count: unsupervisedClusters,
              samples_count: unsupervisedSamplesCount,
              input_bands: unsupervisedMode === "expert" ? unsupervisedBands : undefined,
              seed: 91,
            },
          }
        : {}),
      ...(isOsiSar
        ? {
            osi_sar_options: {
              dark_threshold_db: osiDarkThresholdDb,
              vh_dark_threshold_db: osiVhDarkThresholdDb,
              contrast_threshold_db: osiContrastThresholdDb,
              contrast_radius_m: osiContrastRadiusM,
              min_connected_pixels: osiMinConnectedPixels,
              water_mask: osiWaterMask,
              orbit_pass: osiOrbitPass,
              wind_validation: osiWindValidation,
              wind_min_m_s: osiWindMinMs,
              wind_max_m_s: osiWindMaxMs,
              sentinel2_validation: osiSentinel2Validation,
              scene_id: (selectedImage as any)?.mosaic
                ? undefined
                : ((selectedImage as any)?.gee_id ?? selectedImage?.id),
              relative_orbit: (selectedImage as any)?.relative_orbit,
              scene_orbit_pass: (selectedImage as any)?.orbit_pass,
              acquisition_timestamp: (selectedImage as any)?.acquisition_timestamp,
              platform: (selectedImage as any)?.platform,
              gee_strict_validation: true,
            },
          }
        : {}),
    };
  };

  const uploadBuildingOrthophoto = async (file: File) => {
    setIsBuildingUploading(true);
    setBuildingUploadProgress(null);
    setBuildingError(null);
    setPreparedBuildingRaster(null);
    setBuildingRasterPreviewUrl(null);
    setBuildingUploadFileName(file.name);
    try {
      const prepared = await uploadLocalBuildingRaster(file, setBuildingUploadProgress);
      setPreparedBuildingRaster(prepared);
      setBuildingRasterPreviewUrl(`${API_BASE_URL}/api/ai/raster/${encodeURIComponent(prepared.raster_id)}/preview.png`);
      toast.success(mapText("Orthophoto ready for AI analysis", language), {
        description: prepared.raster_id,
      });
    } catch (error) {
      const message = buildingErrorMessage(error, language);
      setBuildingError(message);
      toast.error(mapText("Orthophoto upload failed", language), { description: message });
    } finally {
      setIsBuildingUploading(false);
      setBuildingUploadProgress(null);
    }
  };

  const clearBuildingResult = () => {
    setBuildingResult(null);
    setShowBuildingLayer(false);
    setBuildingError(null);
  };

  const exportBuildingResult = async (format: BuildingExportFormat) => {
    if (!buildingResult || buildingExportingFormat) return;
    setBuildingExportingFormat(format);
    try {
      const filename = await downloadBuildingExport(buildingResult, format);
      toast.success(mapText("AI Building export generated", language), { description: filename });
    } catch {
      toast.error(mapText("AI Building export failed", language), {
        description: mapText(
          "The AI Building export could not be generated. Please try again.",
          language,
        ),
      });
    } finally {
      setBuildingExportingFormat(null);
    }
  };

  const runBuildingAnalysis = async () => {
    if (isBuildingRunning) return;
    setIsBuildingRunning(true);
    setBuildingError(null);
    try {
      let raster = preparedBuildingRaster;
      if (buildingSourceMode === "sentinel2") {
        const payload = buildRasterPayload("NDVI");
        if (!payload || !selectedImage) throw new Error("LOCAL_RASTER_INVALID");
        const { index: _index, supervised_options: _supervised, unsupervised_options: _unsupervised, osi_sar_options: _osi, period_1: _period1, period_2: _period2, ...rasterPayload } = payload;
        raster = await prepareGeeBuildingRaster({
          ...rasterPayload,
          sensor: "sentinel-2",
          analysis_type: "ai_object_detection",
        });
      }
      if (!raster) throw new Error("LOCAL_RASTER_INVALID");
      const rasterPixelCount = raster.validation.width * raster.validation.height;
      const buildingTimeoutMs = rasterPixelCount > 25_000_000 ? 60 * 60 * 1000 : 10 * 60 * 1000;
      const result = await runBuildingDetection(raster.raster_id, buildingParameters, buildingTimeoutMs);
      setBuildingResult(result);
      setShowBuildingLayer(true);
      if (result.candidate_count > 0) {
        setBuildingFitNonce((value) => value + 1);
        toast.success(
          `${result.candidate_count.toLocaleString()} ${mapText("building candidates vectorized", language)}`,
        );
      } else {
        toast.info(
          mapText(
            "Analysis complete. No building candidates detected with the current parameters.",
            language,
          ),
        );
      }
    } catch (error) {
      const message = buildingErrorMessage(error, language);
      setBuildingError(message);
      toast.error(mapText("Building analysis failed", language), { description: message });
    } finally {
      setIsBuildingRunning(false);
    }
  };

  const loadCatalogImages = async () => {
    if (!aoi) {
      toast.info(mapText("Draw an area of interest first.", language));
      return;
    }
    if (!dateStart || !dateEnd || dateStart > dateEnd) {
      toast.error(mapText("Invalid period", language), {
        description: mapText("The start date must be before the end date.", language),
      });
      return;
    }

    setIsSearchingImages(true);
    startGeeSearchProgress();
    setCatalogImages([]);
    setSelectedImage(null);
    setImageMethod("median_composite");
    setLiveRasterTileUrl(null);
    setLiveResultTileUrl(null);
    setHasResult(false);
    setShowResult(false);
    setRunResult(null);
    try {
      const payload = buildRasterPayload();
      if (!payload) return;
      const searchSeq = ++geeSearchSeqRef.current;
      const job = await startGeeCatalogJob(payload);
      updateGeeSearchProgress(job.progress_percent ?? 0, job.status_message ?? job.message);

      let response = null;
      while (searchSeq === geeSearchSeqRef.current) {
        await delay(1200);
        const status = await getGeeCatalogJobStatus(job.job_id);
        updateGeeSearchProgress(
          status.progress_percent ?? 0,
          status.status_message ?? status.message,
        );
        if (status.status === "completed") {
          response = status.result;
          break;
        }
        if (status.status === "error") {
          throw new Error(status.error || status.message || "Image detection error.");
        }
      }
      if (searchSeq !== geeSearchSeqRef.current || !response) return;

      const isLiveGeeCatalog = response.mode === "gee" && Boolean(response.gee?.enabled);
      setCatalogMode(isLiveGeeCatalog ? "gee" : "unavailable");
      setGeeEnabled(Boolean(response.gee?.enabled));
      const items = ((response.items ?? []) as LiveCatalogImage[]).filter(
        (item) => selectedIndex?.id !== OSI_SAR_ID || !(item as any).mosaic,
      );
      if (isLiveGeeCatalog) {
        const preferredImage = pickPreferredCatalogImage(items);
        setCatalogImages(items);
        if (preferredImage) {
          setSelectedImage(preferredImage);
          setImageMethod((preferredImage as any).mosaic ? "median_composite" : "selected_scene");
          setShowRaster(true);
        }
        completeGeeSearchProgress();
        toast.success(mapText("Satellite images detected successfully", language), {
          description:
            language === "ar"
              ? `${new Intl.NumberFormat("ar-SA").format(response.count ?? items.length)} ${mapText("source image(s) found", language)}`
              : `${response.count ?? items.length} source image(s) found`,
        });
      } else {
        setGeeSearchProgress({
          visible: true,
          percent: 100,
          message: displayBackendText(
            response.warning ??
              "Google Earth Engine is unavailable. No satellite images were loaded.",
          ),
          error: true,
        });
        toast.error(mapText("Image detection error.", language), {
          description: displayBackendText(
            response.warning ??
              "Google Earth Engine is unavailable. No satellite images were loaded.",
          ),
        });
      }
    } catch (error) {
      console.error(error);
      setCatalogImages([]);
      setCatalogMode("unknown");
      failGeeSearchProgress(error instanceof Error ? error.message : undefined);
      toast.error(mapText("Image detection error.", language), {
        description: mapText(
          "Please widen the period, increase the cloud threshold, or reduce the area.",
          language,
        ),
      });
    } finally {
      setIsSearchingImages(false);
    }
  };

  const loadResultLayers = async () => {
    if (!aoi) {
      setResultLayers([]);
      setResultStatusByIndex({});
      return;
    }
    const payload = buildRasterPayload(selectedIndex?.id ?? "NDVI");
    if (!payload) return;
    try {
      const response = await searchResultCache({
        ...payload,
        name: "Result cache lookup",
      });
      setResultLayers(response.items ?? []);
      const statuses: Record<string, string> = {};
      for (const layer of response.items ?? []) {
        statuses[layer.index] = layer.status ?? "available_from_cache";
      }
      setResultStatusByIndex(statuses);
    } catch (error) {
      console.error(error);
      setResultLayers([]);
      setResultStatusByIndex({});
    }
  };

  useEffect(() => {
    if (!aoi) return;
    const timer = window.setTimeout(() => {
      if (suppressAutoCatalogLoadRef.current) {
        suppressAutoCatalogLoadRef.current = false;
        return;
      }
      loadResultLayers();
    }, 500);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aoi, dateStart, dateEnd, maxCloudPct, sensor, resolution, imageMethod, selectedImage?.id]);

  useEffect(() => {
    const runId = historyRunId;
    if (!runId || restoredHistoryRunRef.current === runId) return;
    restoredHistoryRunRef.current = runId;
    let cancelled = false;

    const applyHistoryResult = (result: any) => {
      const analysis = result.analysis ?? {};
      const restoredAoi = bboxFromStoredAnalysis(analysis);
      const restoredIndex = indices.find(
        (item) => item.id === String(analysis.index ?? result.index ?? "NDVI"),
      );
      const restoredSensor = String(analysis.sensor ?? "sentinel-2") as SensorId;
      const restoredResolution = String(analysis.resolution ?? "auto") as ResolutionId;
      const restoredStart = String(analysis.date_start ?? analysis.start_date ?? dateStart);
      const restoredEnd = String(analysis.date_end ?? analysis.end_date ?? dateEnd);

      suppressAutoCatalogLoadRef.current = true;
      if (restoredAoi) setAoi(restoredAoi);
      const restoredGeometry = analysis.geometry ?? analysis.aoi?.geojson;
      if (restoredGeometry?.type === "Polygon" || restoredGeometry?.type === "MultiPolygon") {
        setAoiGeometry(restoredGeometry);
      } else {
        setAoiGeometry(null);
      }
      if (restoredIndex) setSelectedIndex(restoredIndex);
      const knownSensors = new Set(SENSOR_OPTIONS.map((option) => option.value));
      setSensor(knownSensors.has(restoredSensor) ? restoredSensor : "sentinel-2");
      setResolution(
        ["auto", "10m", "20m", "30m"].includes(restoredResolution) ? restoredResolution : "auto",
      );
      setDateStart(restoredStart);
      setDateEnd(restoredEnd);
      setMaxCloudPct(Number(analysis.max_cloud_pct ?? analysis.cloud_max ?? maxCloudPct));
      setImageMethod(
        analysis.image_method === "selected_scene" || analysis.image_method === "single_scene"
          ? "selected_scene"
          : "median_composite",
      );
      if (analysis.period_1) {
        setChangeDateStart1(String(analysis.period_1.start_date ?? changeDateStart1));
        setChangeDateEnd1(String(analysis.period_1.end_date ?? changeDateEnd1));
      }
      if (analysis.period_2) {
        setChangeDateStart2(String(analysis.period_2.start_date ?? changeDateStart2));
        setChangeDateEnd2(String(analysis.period_2.end_date ?? changeDateEnd2));
      }

      const syntheticImage = {
        id: String(analysis.image_id ?? `history-${runId}`),
        name: String(
          analysis.image_id
            ? analysis.image_id
            : `${restoredIndex?.name ?? "Raster"} restored result`,
        ),
        sensor: sensorLabel(restoredSensor),
        date: restoredEnd,
        resolution: restoredResolution === "auto" ? "Automatic" : restoredResolution,
        projection: "EPSG:4326",
        cloud: Number(analysis.max_cloud_pct ?? 0),
        bands: restoredIndex?.bands ?? [],
        size: "-",
        region: "Stored study area",
        status: "Available",
        bbox: restoredAoi
          ? [restoredAoi[0][0], restoredAoi[0][1], restoredAoi[1][0], restoredAoi[1][1]]
          : [0, 0, 0, 0],
        tile_url: null,
      } as any;

      setCatalogImages([syntheticImage]);
      setSelectedImage(syntheticImage);
      // History restore is optimized for instant review of the already computed result.
      // Avoid loading the reference RGB tile unless the user explicitly selects a source image later.
      setShowRaster(false);
      setRunResult(result);
      setActiveRunId(runId);
      setCatalogMode(result.mode === "gee" ? "gee" : result.mode === "mock" ? "unavailable" : "unknown");
      setGeeEnabled(Boolean(result.gee?.enabled));
      setLiveRasterTileUrl(null);
      setLiveResultTileUrl(null);
      setActiveComparisonLayerKey(
        preferredComparisonLayerKey(restoredIndex?.id, result.active_comparison_layer),
      );
      setActiveResultCacheKey(result.cache_key ?? null);
      setHasResult(true);
      setShowResult(true);
      if (restoredIndex) {
        setResultStatusByIndex((prev) => ({
          ...prev,
          [restoredIndex.id]: result.cached ? "available_from_cache" : "calculated",
        }));
      }
      setStep("done");
      setAnalysisProgress((prev) => ({ ...prev, visible: false, error: false, cached: false }));
      removeHistoryRunIdFromUrl();
      if (result.mode === "mock") {
        toast.warning(
          mapText("This stored result is a mock. It is not an operational GEE analysis.", language),
        );
      } else {
        toast.success(mapText("Analysis restored from History", language), {
          description: mapText(
            "Result loaded from the stored analysis without recalculation.",
            language,
          ),
        });
      }
    };

    const restoreHistoryRun = async () => {
      try {
        stopAnalysisProgressTimer();
        analysisProgressSeqRef.current += 1;
        setAnalysisProgress((prev) => ({ ...prev, visible: false, error: false, cached: false }));
        setStep("idle");
        const storedResult = consumeStoredHistoryResult(runId);
        if (storedResult) {
          if (!cancelled) applyHistoryResult(storedResult);
          return;
        }

        const response = await getRunResult(runId);
        if (cancelled) return;
        applyHistoryResult(response.item);
      } catch (error) {
        restoredHistoryRunRef.current = null;
        console.error(error);
        toast.error(mapText("Unable to restore analysis", language), {
          description: mapErrorDescription(error, language),
        });
      }
    };

    restoreHistoryRun();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyRunId]);

  const handleSelectImage = async (img: LiveCatalogImage) => {
    setSelectedImage(img);
    setImageMethod((img as any).mosaic ? "median_composite" : "selected_scene");
    setLiveRasterTileUrl(null);
    setShowRaster(true);
    if ((img as any).mosaic || img.tile_url) {
      if (img.tile_url) setLiveRasterTileUrl(img.tile_url);
      toast.success(mapText("Multispectral image loaded", language), {
        description: mapBackendText(img.name, language),
      });
      return;
    }
    if (catalogMode !== "gee") {
      toast.error(mapText("Image detection error.", language), {
        description: "Google Earth Engine is unavailable.",
      });
      return;
    }
    const payload = buildRasterPayload("NDVI");
    const rawDate = String((img as any).acquisition_date || img.date || "").trim();
    const singleDay = /^\d{4}-\d{2}-\d{2}$/.test(rawDate) ? rawDate : "";
    const isSentinel2 =
      String(img.sensor || "")
        .toLowerCase()
        .includes("sentinel-2") || String(img.source || "").includes("S2");
    // Available Sentinel-2 rows must preview the full-AOI day mosaic, never a lone granule.
    const sceneId = (img as any).date_mosaic
      ? String(img.gee_id ?? img.id ?? "")
      : isSentinel2 && singleDay
        ? `S2_DATE_MOSAIC_${singleDay}`
        : String(img.gee_id ?? img.id ?? "");
    if (!payload || !sceneId) {
      toast.error(mapText("Image detection error.", language), {
        description: "The selected satellite scene is incomplete.",
      });
      return;
    }
    setPreviewingImageId(img.id);
    try {
      const response = await getGeeScenePreview({ ...payload, scene_id: sceneId });
      const tileUrl = response.item?.preview?.tile_url;
      if (!tileUrl)
        throw new Error(response.item?.warning ?? "No live RGB tile was returned for this scene.");
      const loadedImage = {
        ...img,
        tile_url: tileUrl,
        date_mosaic: Boolean((img as any).date_mosaic || (isSentinel2 && singleDay)),
        acquisition_date: singleDay || (img as any).acquisition_date,
        cloud: response.item?.image?.cloud ?? img.cloud,
        cloud_source: response.item?.image?.cloud_source ?? (img as any).cloud_source,
      };
      setCatalogImages((current) =>
        current.map((item) => (item.id === img.id ? loadedImage : item)),
      );
      setSelectedImage(loadedImage);
      setLiveRasterTileUrl(tileUrl);
      toast.success(mapText("Multispectral image loaded", language), {
        description: mapBackendText(img.name, language),
      });
    } catch (error) {
      console.error(error);
      setLiveRasterTileUrl(null);
      toast.error(mapText("Image detection error.", language), {
        description:
          error instanceof Error ? error.message : "Unable to load the live satellite scene.",
      });
    } finally {
      setPreviewingImageId(null);
    }
  };

  const pickPreferredCatalogImage = (items: LiveCatalogImage[]) => {
    return items.find((item) => Boolean(item.mosaic)) ?? items[0] ?? null;
  };

  const applyAoi = (
    bbox: [[number, number], [number, number]],
    geometry: AoiGeometry | null,
    options?: { fit?: boolean; toastKey?: string },
  ) => {
    stopAnalysisProgressTimer();
    analysisProgressSeqRef.current += 1;
    setAnalysisProgress((prev) => ({ ...prev, visible: false, error: false, cached: false }));
    setStep("idle");
    setHasResult(false);
    setShowResult(false);
    setRunResult(null);
    setActiveRunId(null);
    setLiveRasterTileUrl(null);
    setLiveResultTileUrl(null);
    setActiveComparisonLayerKey(defaultComparisonLayerKey(selectedIndex?.id));
    setActiveResultCacheKey(null);
    setAoi(bbox);
    setAoiGeometry(geometry);
    setShowAoi(true);
    setDrawMode(null);
    setTab("images");
    if (options?.fit) setAoiFitNonce((value) => value + 1);
    toast.success(mapText(options?.toastKey ?? "Area of interest selected", language));
  };

  const resetAoiParts = () => {
    setAoiParts([]);
    setSelectedPartIds([]);
    setAoiSource(null);
  };

  const handleAoiDrawn = (bbox: [[number, number], [number, number]]) => {
    resetAoiParts();
    applyAoi(bbox, null);
  };

  const handleSplitAoi = async () => {
    const geometry = (aoiGeometry ?? (aoi ? bboxToGeometry(aoi) : null)) as AoiGeometry | null;
    if (!aoi || !geometry) {
      toast.error(mapText("Draw or import an area of interest first", language));
      return;
    }
    const toastId = toast.loading(mapText("Splitting the area of interest...", language));
    try {
      const response = await splitAoi(geometry);
      toast.dismiss(toastId);
      setAoiSource({ bbox: aoi, geometry: aoiGeometry });
      setAoiParts(response.items);
      setSelectedPartIds([]);
      toast.success(
        response.parts > 1
          ? mapText("Area of interest split into equivalent parts", language)
          : mapText("Area of interest small enough: no split needed", language),
        {
          description: `${response.grid.rows} x ${response.grid.columns} - ${response.parts} ${mapText("parts", language)} ${(response.total_area_km2 / response.parts).toFixed(2)} km2`,
        },
      );
    } catch (error) {
      toast.dismiss(toastId);
      toast.error(mapText("Split failed", language), {
        description: mapErrorDescription(error, language),
      });
    }
  };

  // A grid selection changes the scientific AOI. Keep the chosen source image,
  // but invalidate every result/statistic produced for the previous geometry.
  const applySelectionAoi = (
    bbox: [[number, number], [number, number]],
    geometry: AoiGeometry | null,
  ) => {
    const hadResult = hasResult || Boolean(runResult) || Boolean(activeRunId);
    stopAnalysisProgressTimer();
    analysisProgressSeqRef.current += 1;
    setAnalysisProgress((previous) => ({
      ...previous,
      visible: false,
      error: false,
      cached: false,
    }));
    setStep("idle");
    setHasResult(false);
    setShowResult(false);
    setRunResult(null);
    setActiveRunId(null);
    setLiveResultTileUrl(null);
    setActiveResultCacheKey(null);
    setResultLayers([]);
    setResultStatusByIndex({});
    setAoi(bbox);
    setAoiGeometry(geometry);
    setShowAoi(true);
    setDrawMode(null);
    if (hadResult) {
      toast.info(mapText("AOI changed: run the analysis again for the new selection.", language), {
        id: "aoi-result-invalidated",
      });
    }
  };

  // Ticked parts are analysed together: their union becomes the current AOI.
  const applyPartSelection = (partIds: string[]) => {
    setSelectedPartIds(partIds);
    if (!partIds.length) {
      if (aoiSource) applySelectionAoi(aoiSource.bbox, aoiSource.geometry);
      return;
    }
    const chosen = aoiParts.filter((part) => partIds.includes(part.part_id));
    const polygons: any[] = [];
    chosen.forEach((part) => {
      if (part.geojson.type === "Polygon") polygons.push(part.geojson.coordinates);
      else (part.geojson.coordinates as any[]).forEach((polygon) => polygons.push(polygon));
    });
    const geometry = (
      polygons.length === 1
        ? { type: "Polygon", coordinates: polygons[0] }
        : { type: "MultiPolygon", coordinates: polygons }
    ) as AoiGeometry;
    applySelectionAoi(
      [
        [
          Math.min(...chosen.map((part) => part.bbox[0])),
          Math.min(...chosen.map((part) => part.bbox[1])),
        ],
        [
          Math.max(...chosen.map((part) => part.bbox[2])),
          Math.max(...chosen.map((part) => part.bbox[3])),
        ],
      ],
      geometry,
    );
  };

  const toggleAoiPart = (partId: string) => {
    applyPartSelection(
      selectedPartIds.includes(partId)
        ? selectedPartIds.filter((id) => id !== partId)
        : [...selectedPartIds, partId],
    );
  };

  const handleRestoreFullAoi = () => {
    if (!aoiSource) return;
    setSelectedPartIds([]);
    applySelectionAoi(aoiSource.bbox, aoiSource.geometry);
    setAoiFitNonce((value) => value + 1);
  };

  const handleImportAoiFiles = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    const toastId = toast.loading(mapText("Reading area of interest...", language));
    try {
      const imported = await importAoiFromFiles(Array.from(fileList));
      toast.dismiss(toastId);
      applyAoi(imported.bbox, imported.geometry, {
        fit: true,
        toastKey: "Area of interest imported",
      });
    } catch (error) {
      toast.dismiss(toastId);
      resetAoiParts();
      toast.error(mapText(aoiImportUserMessage(error), language), {
        description:
          error instanceof AoiImportError && error.message !== aoiImportUserMessage(error)
            ? error.message.replace(aoiImportUserMessage(error), "").trim()
            : undefined,
      });
    } finally {
      if (aoiFileInputRef.current) aoiFileInputRef.current.value = "";
    }
  };

  const activateCachedLayer = (layer: any, showToast = true) => {
    const matchingIndex = indices.find((idx) => idx.id === layer.index);
    if (matchingIndex) setSelectedIndex(matchingIndex);
    if (layer.index === OSI_SAR_ID) setShowRaster(false);
    setRunResult(layerToRunResult(layer));
    setActiveRunId(layer.run_id ?? null);
    setLiveRasterTileUrl(null);
    setLiveResultTileUrl(null);
    setActiveComparisonLayerKey(
      preferredComparisonLayerKey(layer.index, layer.active_comparison_layer),
    );
    setActiveResultCacheKey(layer.cache_key);
    setHasResult(true);
    setShowResult(true);
    setStep("done");
    if (CLASSIFICATION_IDS.includes(layer.index)) {
      setShowSavedTrainingSamples(false);
    }
    if (showToast) {
      toast.success(mapText("Result loaded from history; no recalculation required.", language));
    }
  };

    const runAnalysis = async (force = false) => {
    if (!aoi || !selectedIndex) return;
    if (geeEnabled === false) {
      toast.error(mapText("Google Earth Engine is unavailable. Mock analysis is blocked.", language), {
        description: mapText(
          "Connect Earth Engine and search live images before running an analysis.",
          language,
        ),
      });
      return;
    }
    const isOsiSar = selectedIndex.id === OSI_SAR_ID;
    const imageForAnalysis = selectedImage ?? null;
    if (!isOsiSar && !imageForAnalysis) {
      toast.error(mapText("Select an image, then draw an area of interest.", language));
      return;
    }
    if (
      !isOsiSar &&
      !selectedIndex.id.startsWith("CHANGE_") &&
      imageMethod === "selected_scene" &&
      ((imageForAnalysis as any)?.mosaic ||
        !String((imageForAnalysis as any)?.gee_id ?? (imageForAnalysis as any)?.id ?? "").trim())
    ) {
      toast.error(mapText("Select an individual acquisition from the catalogue.", language), {
        description: mapText(
          "The period mosaic cannot be used in Selected scene mode.",
          language,
        ),
      });
      return;
    }
    const isClassification = CLASSIFICATION_IDS.includes(selectedIndex.id);
    if (selectedIndex.id === SUPERVISED_CLASSIFICATION_ID) {
      const selectedClasses = landcoverClasses.filter((item) =>
        selectedSupervisedClassIds.includes(String(item.id)),
      );
      const samplesInsideAoi = trainingSamples.filter((sample) => sampleIntersectsAoi(sample, aoi));
      const missingClasses = selectedClasses.filter(
        (item) =>
          !samplesInsideAoi.some(
            (sample) =>
              String(sample.class_id) === String(item.id) &&
              (sample.usage ?? "training") === "training",
          ),
      );
      if (selectedClasses.length < 2) {
        toast.error(
          mapText(
            "Select at least two land-cover classes before running the classification.",
            language,
          ),
        );
        setSupervisedWorkflowStep(1);
        return;
      }
      if (samplesInsideAoi.length === 0) {
        toast.error(
          mapText("Draw training samples inside the current area of interest.", language),
        );
        setSupervisedWorkflowStep(2);
        return;
      }
      if (missingClasses.length > 0) {
        toast.error(
          mapText("Each selected class needs a training sample inside the AOI.", language),
          {
            description: missingClasses
              .map((item) => mapBackendText(item.name, language))
              .join(", "),
          },
        );
        setSupervisedWorkflowStep(2);
        return;
      }
      const areaKm2 = estimateAoiAreaKm2(aoi);
      const coverage = supervisedSampleQuadrantCoverage(samplesInsideAoi, aoi);
      // Coverage warnings must never block execution — they are advisory only.
      try {
        if (areaKm2 >= 5000 && coverage.occupied < 3) {
          toast.warning(
            mapText(
              "Large AOI: spread training samples across more of the area for a reliable classification.",
              language,
            ),
            {
              description: mapText(
                "Add points or polygons in different parts of the AOI for each class.",
                language,
              ),
            },
          );
        } else if (areaKm2 >= 2000 && coverage.occupied < 2) {
          toast.warning(
            mapText(
              "Samples are concentrated in one part of the AOI. Add samples elsewhere before trusting the map.",
              language,
            ),
          );
        }
      } catch {
        // Ignore advisory coverage failures.
      }
    }
    const isChangeDetection = selectedIndex.id.startsWith("CHANGE_");
    const effectiveSensor = isOsiSar ? "sentinel-1" : sensor;
    const compatibleSensors = supportedSensorsForIndex(selectedIndex.id);
    if (!compatibleSensors.includes(effectiveSensor)) {
      toast.warning(mapText("Analysis not compatible with this sensor", language), {
        description:
          language === "ar"
            ? selectedIndex.id === OSI_SAR_ID
              ? `المستشعر ${sensorLabel(effectiveSensor)} غير مدعوم لتحليل OSI-SAR. استخدم Sentinel-1 SAR.`
              : `المستشعر ${sensorLabel(effectiveSensor)} غير مدعوم لهذا التحليل. استخدم Sentinel-2 أو Landsat 8/9.`
            : selectedIndex.id === OSI_SAR_ID
              ? `${sensorLabel(effectiveSensor)} is not supported for OSI-SAR. Use Sentinel-1 SAR.`
              : `${sensorLabel(effectiveSensor)} is not supported for this analysis. Use Sentinel-2 or Landsat 8/9.`,
      });
      return;
    }
    if (isChangeDetection) {
      if (
        !changeDateStart1 ||
        !changeDateEnd1 ||
        !changeDateStart2 ||
        !changeDateEnd2 ||
        changeDateStart1 > changeDateEnd1 ||
        changeDateStart2 > changeDateEnd2
      ) {
        toast.error(mapText("Invalid Change Detection periods", language), {
          description: mapText(
            "Each period must have a valid start date before its end date.",
            language,
          ),
        });
        return;
      }
    }

    if (isOsiSar && !selectedImage) {
      toast.info(mapText("Latest Sentinel-1 scene in the period", language), {
        description: mapText("OSI-SAR uses one Sentinel-1 scene, not a long mosaic.", language),
      });
    }

    startAnalysisProgress();
    try {
      setStep("clip");
      toast.info(mapText("Preparing raster analysis...", language));
      updateAnalysisProgress(10, "Validating parameters...");
      const payload = buildRasterPayload(selectedIndex.id);
      if (!payload) {
        failAnalysisProgress();
        return;
      }

      if (!force) {
        setResultStatusByIndex((prev) => ({ ...prev, [selectedIndex.id]: "running" }));
        const cached = await searchResultCache({
          ...payload,
          name: `${selectedIndex.name} cache lookup`,
        });
        setResultLayers(cached.items ?? []);
        if (cached.item) {
          activateCachedLayer(cached.item);
          completeCachedAnalysisProgress();
          setResultStatusByIndex((prev) => ({
            ...prev,
            [selectedIndex.id]: "available_from_cache",
          }));
          return;
        }
      }

      setHasResult(false);
      setShowResult(false);
      // Hide previous sampling overlays when a new classification starts; supervised
      // samples stay in the DB and are re-shown on error.
      setShowSavedTrainingSamples(false);
      setRunResult(null);
      setActiveRunId(null);
      setLiveRasterTileUrl(null);
      setLiveResultTileUrl(null);
      setActiveComparisonLayerKey(defaultComparisonLayerKey(selectedIndex.id));
      setActiveResultCacheKey(null);
      setResultStatusByIndex((prev) => ({ ...prev, [selectedIndex.id]: "running" }));
      updateAnalysisProgress(20, "Preparing analysis data...");

      const analysis = await createBackendAnalysis({
        ...payload,
        name: `${selectedIndex.name} - ${imageForAnalysis ? displayBackendText(imageForAnalysis.name) : mapText("Latest Sentinel-1 scene in the period", language)}`,
        objective: selectedIndex.topic,
        description: "GeoRaster MVP analysis from the frontend",
        image_id: payload.image_id,
      });

      setStep("compute");
      updateAnalysisProgress(
        35,
        isClassification
          ? "Preparation..."
          : isOsiSar
            ? "Selecting the Sentinel-1 acquisition..."
            : "Preparing the Sentinel-2 mosaic...",
      );
      toast.info(
        mapText(
          force
            ? "Recalculation in progress..."
            : isClassification
              ? "Classification in progress..."
              : "Analysis processing in progress...",
          language,
        ),
      );
      if (isClassification) {
        // Synchronous runs report a single honest waiting phase; async jobs stream real stages.
        updateAnalysisProgress(48, "Classification...");
      } else {
        updateAnalysisProgress(50, "Computing the selected index...");
      }
      let run: any;
      if (aoiAreaKm2 > 15000) {
        let job = await startAnalysisJob(analysis.item.id, force);
        updateAnalysisProgress(40, job.message ?? "Analysis queued...");
        while (job.status === "queued" || job.status === "processing") {
          await delay(1500);
          job = await getAnalysisJob(job.job_id);
          const backendProgress =
            job.status === "queued"
              ? 40
              : Math.max(40, Math.min(Number(job.progress_percent) || 50, 90));
          updateAnalysisProgress(
            backendProgress,
            job.message ??
              (isClassification
                ? "Classification..."
                : "Processing large AOI in adaptive chunks..."),
          );
        }
        if (job.status === "failed" || !job.run) {
          throw new Error(job.error || job.message || "Large AOI analysis failed.");
        }
        run = { item: job.run };
      } else {
        run = await runBackendAnalysis(analysis.item.id, force);
      }

      setStep("render");
      updateAnalysisProgress(80, isClassification ? "Rendering..." : "Preparing the first map layer...");
      const result = await getRunResult(run.item.id);
      const statsDeferred = resultHasDeferredStatistics(result.item);
      updateAnalysisProgress(
        90,
        statsDeferred
          ? "Map layer ready; statistics are updating..."
          : isClassification
            ? "Completed"
            : "Preparing the map layer...",
      );
      setRunResult(result.item);
      setActiveRunId(run.item.id);
      setLiveRasterTileUrl(null);
      setLiveResultTileUrl(null);
      setActiveComparisonLayerKey(
        preferredComparisonLayerKey(selectedIndex.id, result.item.active_comparison_layer),
      );
      setActiveResultCacheKey(null);
      setHasResult(true);
      setShowResult(true);
      // Successful classification: clear sampling geometries so the result is readable.
      if (isClassification) setShowSavedTrainingSamples(false);
      if (selectedIndex.id === OSI_SAR_ID) setShowRaster(false);
      setStep("done");
      setResultStatusByIndex((prev) => ({
        ...prev,
        [selectedIndex.id]: result.item.cached
          ? "available_from_cache"
          : statsDeferred
            ? "calculating_stats"
            : "calculated",
      }));
      await loadResultLayers();
      completeAnalysisProgress(
        result.item.cached
          ? "Result loaded from cache."
          : statsDeferred
            ? "Map ready. Exact statistics are updating."
            : "Result ready.",
      );
      const completedArea =
        result.item.stats?.surface_ha ?? result.item.stats?.total_area_ha ?? "-";
      const completionDescription =
        language === "ar"
          ? isClassification
            ? `${mapText("Land cover classified over", language)} ${completedArea} هكتار`
            : selectedIndex.id === OSI_SAR_ID
              ? `${mapText("OSI-SAR detected suspect slick candidates over", language)} ${result.item.stats?.suspect_surface_ha ?? 0} هكتار`
              : `${selectedIndex.id} ${mapText("calculated over", language)} ${result.item.stats?.surface_ha ?? "-"} هكتار`
          : isClassification
            ? `Land cover classified over ${completedArea} ha`
            : selectedIndex.id === OSI_SAR_ID
              ? `OSI-SAR detected ${result.item.stats?.suspect_surface_ha ?? 0} ha of suspect slick candidates`
              : selectedIndex.id.startsWith("CHANGE_")
                ? `${analysisShortLabel(selectedIndex.id, language)} calculated over ${result.item.stats?.surface_ha ?? "-"} ha`
                : `${selectedIndex.id} calculated over ${result.item.stats?.surface_ha ?? "-"} ha`;
      toast.success(mapText("Analysis completed", language), {
        description: statsDeferred
          ? mapText("Map is ready; exact statistics are updating in the background.", language)
          : completionDescription,
      });
    } catch (error) {
      console.error(error);
      setStep("idle");
      failAnalysisProgress(error instanceof Error ? error.message : undefined);
      // Keep training samples visible so the user can correct and re-run.
      if (selectedIndex?.id === SUPERVISED_CLASSIFICATION_ID) {
        setShowSavedTrainingSamples(true);
      }
      if (selectedIndex)
        setResultStatusByIndex((prev) => ({ ...prev, [selectedIndex.id]: "error" }));
      toast.error(mapText("Raster analysis failed", language), {
        description: mapErrorDescription(error, language),
      });
    }
  };

  useEffect(() => {
    let cancelled = false;
    if (!showResult || !activeRunId) {
      setLiveRasterTileUrl(null);
      setLiveResultTileUrl(null);
      return;
    }

    const hasStoredResultTile = Boolean(runResult?.tiles?.index_tile_url);
    const hasStoredRasterTile = Boolean(
      (selectedImage as any)?.tile_url ?? runResult?.tiles?.rgb_tile_url,
    );
    const hasComparisonLayers =
      Array.isArray(runResult?.comparison_layers) && runResult.comparison_layers.length > 0;
    const needsComparisonRefresh = hasComparisonLayers && !liveResultTileUrl;
    const needsStableClusterTile =
      runResult?.analysis_type === "unsupervised_classification" && !liveResultTileUrl;

    // GEE map URLs expire. Comparison analyses must refresh all three layers,
    // including the final change layer, even when an old URL is still stored.
    // Unsupervised layers are refreshed once so their deterministic cluster
    // ordering stays synchronized with the persisted class statistics.
    if (!hasStoredResultTile || needsComparisonRefresh || needsStableClusterTile) {
      getRunTiles(activeRunId, { refresh: true, includeRgb: !hasStoredRasterTile })
        .then((response) => {
          if (cancelled) return;
          setLiveRasterTileUrl(response.item.rgb_tile_url ?? null);
          setLiveResultTileUrl(response.item.index_tile_url ?? null);
          setRunResult((prev: any) =>
            prev
              ? {
                  ...mergeComparisonLayerTiles(prev, (response.item as any).comparison_layers),
                  tile_source_palette:
                    response.item.tile_source_palette ?? prev.tile_source_palette,
                }
              : prev,
          );
          if (response.item.source === "stored_fallback") {
            toast.error(mapText("Unable to refresh the stored map tile", language), {
              description:
                displayBackendText(response.item.refresh_error) ||
                mapText(
                  "The run is restored, but the visual tile could not be regenerated.",
                  language,
                ),
            });
          }
        })
        .catch((error) => {
          if (cancelled) return;
          setLiveRasterTileUrl(null);
          setLiveResultTileUrl(null);
          toast.error(mapText("Unable to refresh the stored map tile", language), {
            description:
              error instanceof Error
                ? error.message
                : mapText(
                    "The run is restored, but the visual tile could not be regenerated.",
                    language,
                  ),
          });
        });
      return () => {
        cancelled = true;
      };
    }

    return () => {
      cancelled = true;
    };
  }, [
    showResult,
    activeRunId,
    liveResultTileUrl,
    runResult?.analysis_type,
    runResult?.tiles?.index_tile_url,
    runResult?.tiles?.rgb_tile_url,
    selectedImage,
  ]);

  const runResultStatsDeferred = resultHasDeferredStatistics(runResult);
  const pendingStatsValue = runResultStatsDeferred ? "..." : null;

  useEffect(() => {
    let cancelled = false;
    if (!showResult || !activeRunId || !runResultStatsDeferred) {
      return () => {
        cancelled = true;
      };
    }

    const pollDeferredStatistics = async () => {
      for (let attempt = 0; attempt < 120 && !cancelled; attempt += 1) {
        await delay(2500);
        if (cancelled) return;
        try {
          const response = await getRunResult(activeRunId);
          if (cancelled) return;
          setRunResult(response.item);
          if (!resultHasDeferredStatistics(response.item)) {
            const resultIndex = String(response.item?.analysis?.index ?? selectedIndex?.id ?? "");
            if (resultIndex) {
              setResultStatusByIndex((prev) => ({ ...prev, [resultIndex]: "calculated" }));
            }
            toast.success(mapText("Statistics updated", language), {
              description: mapText("The exact GEE statistics are now available.", language),
            });
            return;
          }
        } catch (error) {
          console.error(error);
          return;
        }
      }
    };

    pollDeferredStatistics();
    return () => {
      cancelled = true;
    };
  }, [showResult, activeRunId, selectedIndex?.id, language, runResultStatsDeferred]);

  useEffect(() => {
    let active = true;
    getPlatformSettings()
      .then((settings) => {
        if (!active) return;
        if (settings.default_basemap) {
          setBasemap(settings.default_basemap as BasemapKey);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const refreshExpiredResultTile = () => {
    if (
      !activeRunId ||
      !showResult ||
      tileRefreshRunRef.current === activeRunId ||
      tileRefreshAttemptedRunsRef.current.has(activeRunId)
    )
      return;
    tileRefreshRunRef.current = activeRunId;
    tileRefreshAttemptedRunsRef.current.add(activeRunId);
    getRunTiles(activeRunId, { refresh: true, includeRgb: false })
      .then((response) => {
        if (response.item.index_tile_url) {
          setLiveResultTileUrl(response.item.index_tile_url);
          setRunResult((prev: any) =>
            prev
              ? {
                  ...mergeComparisonLayerTiles(prev, (response.item as any).comparison_layers),
                  tiles: {
                    ...(prev.tiles ?? {}),
                    index_tile_url: response.item.index_tile_url,
                  },
                  tile_source_palette:
                    response.item.tile_source_palette ?? prev.tile_source_palette,
                }
              : prev,
          );
        }
        if (response.item.source === "stored_fallback" || !response.item.index_tile_url) {
          toast.error(mapText("Unable to refresh the stored map tile", language), {
            description:
              displayBackendText(response.item.refresh_error) ||
              mapText(
                "The run is restored, but the visual tile could not be regenerated.",
                language,
              ),
          });
        }
      })
      .catch((error) => {
        console.error(error);
        toast.error(mapText("Unable to refresh the stored map tile", language), {
          description: mapText(
            "The run is restored, but the visual tile could not be regenerated.",
            language,
          ),
        });
      })
      .finally(() => {
        tileRefreshRunRef.current = null;
      });
  };

  const deleteActiveResult = async () => {
    if (!activeResultCacheKey) {
      toast.warning(mapText("Select a cached result layer first.", language));
      return;
    }
    try {
      await deleteResultCache(activeResultCacheKey);
      setResultLayers((prev) => prev.filter((layer) => layer.cache_key !== activeResultCacheKey));
      setRunResult(null);
      setActiveRunId(null);
      setLiveRasterTileUrl(null);
      setActiveResultCacheKey(null);
      setHasResult(false);
      setShowResult(false);
      if (selectedIndex)
        setResultStatusByIndex((prev) => ({ ...prev, [selectedIndex.id]: "not_calculated" }));
      toast.success(mapText("Cached result deleted", language));
    } catch (error) {
      console.error(error);
      toast.error(mapText("Unable to delete cached result", language), {
        description: mapErrorDescription(error, language),
      });
    }
  };

  const exportFile = async (
    kind: "stats_csv" | "stats_json" | "report_pdf" | "map_png" | "geotiff",
    label: string,
  ) => {
    if (!activeRunId) {
      toast.warning(mapText("No result to export", language));
      return;
    }
    try {
      const response = await createBackendExport(
        activeRunId,
        kind,
        activeComparisonLayer?.key ?? null,
        language === "ar" ? "ar" : "en",
      );
      downloadExport(response.item.id);
      toast.success(mapText("Export generated", language), {
        description: mapText(label, language),
      });
    } catch (error) {
      console.error(error);
      toast.error(mapText("Export failed", language), {
        description: mapErrorDescription(error, language),
      });
    }
  };

  const exportMapPdf = async () => {
    if (!hasResult || !runResult || !selectedIndex || !aoi) {
      toast.warning(mapText("No result to export", language));
      return;
    }
    setIsMapPdfExporting(true);
    try {
      toast.info(mapText("Preparing Map PDF report...", language));
      const runIdForPdf =
        activeRunId ?? runResult?.run?.id ?? runResult?.run_id ?? runResult?.latest_run_id;
      if (runIdForPdf) {
        const reportQuery = new URLSearchParams({ language: language === "ar" ? "ar" : "en" });
        if (activeComparisonLayer?.key) reportQuery.set("layer_key", activeComparisonLayer.key);
        downloadApiFile(
          `/api/runs/${encodeURIComponent(runIdForPdf)}/export/map-pdf?${reportQuery.toString()}`,
        );
        toast.success(mapText("Map PDF generated", language), {
          description: mapText("Download started", language),
        });
        return;
      }
      const [[south, west], [north, east]] = aoi;
      const exportLegend =
        (classes?.length
          ? classes.map((item: any) => ({
              label: item.name ?? item.label,
              meaning: legendMeaningForClass(item, selectedIndex.legend),
              color: item.color,
              surface_ha: item.surface_ha ?? item.surface,
              pct: item.pct ?? item.percentage,
              min: item.min,
              max: item.max,
              pixels: item.pixels,
            }))
          : selectedIndex.legend) ?? [];
      const qualityForReport = {
        ...(mosaicQuality ?? {}),
        ...(qualitySummary ?? {}),
        overall_accuracy: accuracy?.overall_accuracy,
        kappa: accuracy?.kappa,
        mode: runResult?.mode,
        source:
          selectedIndex.id === OSI_SAR_ID ? "COPERNICUS/S1_GRD" : "COPERNICUS/S2_SR_HARMONIZED",
        message:
          "The result is based on the current GeoRaster analysis view and the selected satellite imagery.",
      };
      const response = await createMapPdfExport({
        analysis_id:
          activeRunId ??
          runResult?.run?.id ??
          runResult?.run_id ??
          runResult?.latest_run_id ??
          activeResultCacheKey ??
          undefined,
        analysis_type: selectedIndex.id,
        language: language === "ar" ? "ar" : "en",
        geometry_info: {
          label: "Selected area of interest",
          bounds: aoi,
          bounds_text: `${south.toFixed(5)}, ${west.toFixed(5)} -> ${north.toFixed(5)}, ${east.toFixed(5)}`,
          area_ha: Number((aoiAreaKm2 * 100).toFixed(2)),
          area_km2: Number(aoiAreaKm2.toFixed(4)),
        },
        parameters: {
          sensor: sensorLabel(sensor),
          resolution,
          start_date: dateStart,
          end_date: dateEnd,
          cloud_max: maxCloudPct,
          processing_method:
            selectedIndex?.id === OSI_SAR_ID
              ? "selected_scene"
              : selectedIndex?.id?.startsWith("CHANGE_")
                ? "median_composite"
                : imageMethod,
          images_count:
            mosaicQuality?.images_count ??
            mosaicQuality?.available_images ??
            qualitySummary?.images_count ??
            "-",
          display_mode: (selectedImage as any)?.mosaic
            ? "Mosaic"
            : catalogMode === "gee"
              ? "Live catalog"
              : "Catalog",
          objective: selectedIndex.description,
        },
        map_screenshot:
          "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+l2kAAAAASUVORK5CYII=",
        legend: exportLegend,
        statistics: stats,
        histogram: runResult?.histogram ?? [],
        classes,
        quality_summary: qualityForReport,
        interpretation: runResult?.interpretation ?? null,
        user_name: window.localStorage.getItem("georaster.userName"),
        metadata: {
          source_data:
            selectedIndex.id === OSI_SAR_ID ? "COPERNICUS/S1_GRD" : "COPERNICUS/S2_SR_HARMONIZED",
          satellite: sensorLabel(sensor),
          acquisition_start: dateStart,
          acquisition_end: dateEnd,
          spatial_resolution: resolution,
          extent_coordinates: {
            south,
            west,
            north,
            east,
          },
          processing_version:
            (qualitySummary as any)?.processing_version ?? runResult?.mode ?? "default-v1",
          georasterportal_version: "0.2.0",
          analysis_name: selectedIndex.name,
          analysis_topic: selectedIndex.topic,
          spatial_reference:
            runResult?.analysis?.spatial_reference ?? runResult?.spatial_reference ?? null,
        },
      });
      downloadApiFile(response.pdf_url);
      toast.success(mapText("Map PDF generated", language), { description: response.filename });
    } catch (error) {
      console.error(error);
      toast.error(mapText("Map PDF export failed", language), {
        description: mapErrorDescription(error, language),
      });
    } finally {
      setIsMapPdfExporting(false);
    }
  };

  const exportMapLayoutPng = async () => {
    if (!hasResult || !runResult || !selectedIndex || !aoi) {
      toast.warning(mapText("No result to export", language));
      return;
    }
    const mapElement = mapCaptureRef.current;
    if (!mapElement) {
      toast.error(mapText("Map capture unavailable", language));
      return;
    }
    setIsMapLayoutExporting(true);
    try {
      toast.info(mapText("Preparing cartographic layout...", language));
      if (document.fonts?.ready) await document.fonts.ready;
      let mapScreenshot = blankMapScreenshotDataUrl();
      try {
        mapScreenshot = await captureLeafletMapImage(mapElement, {
          cropToAoi: true,
          resultOnly: true,
        });
      } catch (captureError) {
        console.warn(
          "Falling back to backend PNG reconstruction because map capture failed.",
          captureError,
        );
      }
      const [[south, west], [north, east]] = aoi;
      const exportLegend =
        (classes?.length
          ? classes.map((item: any) => ({
              label: item.name ?? item.label,
              meaning: legendMeaningForClass(item, selectedIndex.legend),
              color: item.color,
              surface_ha: item.surface_ha,
              pct: item.pct,
            }))
          : selectedIndex.legend) ?? [];
      const response = await createMapLayoutPngExport({
        analysis_id:
          activeRunId ??
          runResult?.run?.id ??
          runResult?.run_id ??
          runResult?.latest_run_id ??
          activeResultCacheKey ??
          undefined,
        analysis_type: selectedIndex.id,
        language: language === "ar" ? "ar" : "en",
        geometry_info: {
          label: "Selected area of interest",
          bounds: aoi,
          bounds_text: `${south.toFixed(5)}, ${west.toFixed(5)} -> ${north.toFixed(5)}, ${east.toFixed(5)}`,
          area_ha: Number((aoiAreaKm2 * 100).toFixed(2)),
          area_km2: Number(aoiAreaKm2.toFixed(4)),
        },
        parameters: {
          sensor: sensorLabel(sensor),
          resolution,
          start_date: dateStart,
          end_date: dateEnd,
          period_1_start: changeDateStart1,
          period_1_end: changeDateEnd1,
          period_2_start: changeDateStart2,
          period_2_end: changeDateEnd2,
          cloud_max: maxCloudPct,
          processing_method:
            selectedIndex?.id === OSI_SAR_ID
              ? "selected_scene"
              : selectedIndex?.id?.startsWith("CHANGE_")
                ? "median_composite"
                : imageMethod,
          images_count:
            mosaicQuality?.images_count ??
            mosaicQuality?.available_images ??
            qualitySummary?.images_count ??
            "-",
          display_mode: (selectedImage as any)?.mosaic
            ? "Mosaic"
            : catalogMode === "gee"
              ? "Live catalog"
              : "Catalog",
        },
        map_screenshot: mapScreenshot,
        legend: exportLegend,
        statistics: stats,
        classes,
        quality_summary: {
          ...(mosaicQuality ?? {}),
          ...(qualitySummary ?? {}),
          mode: runResult?.mode,
        },
        interpretation: runResult?.interpretation ?? null,
        user_name: window.localStorage.getItem("georaster.userName"),
        metadata: {
          layer_key: activeComparisonLayer?.key ?? null,
          spatial_reference:
            runResult?.analysis?.spatial_reference ?? runResult?.spatial_reference ?? null,
        },
      });
      downloadApiFile(response.image_url);
      toast.success(mapText("Layout PNG generated", language), { description: response.filename });
    } catch (error) {
      console.error(error);
      toast.error(mapText("PNG export failed", language), {
        description: mapErrorDescription(error, language),
      });
    } finally {
      setIsMapLayoutExporting(false);
    }
  };

  const activeChangeComparisonBase = changeComparisonBase(selectedIndex?.id);
  const isResultSubLayerRun = Boolean(
    activeChangeComparisonBase ||
      selectedIndex?.id === "NDBI" ||
      selectedIndex?.id === "NDVI" ||
      selectedIndex?.id === OSI_SAR_ID,
  );
  const comparisonLayers = useMemo(
    () =>
      isResultSubLayerRun && Array.isArray(runResult?.comparison_layers)
        ? runResult.comparison_layers
        : [],
    [isResultSubLayerRun, runResult?.comparison_layers],
  );
  const visibleComparisonLayers = useMemo(
    () =>
      comparisonLayers.filter((layer: any) =>
        isUserVisibleComparisonLayer(selectedIndex?.id, layer),
      ),
    [comparisonLayers, selectedIndex?.id],
  );
  const activeComparisonLayer = useMemo(() => {
    if (!comparisonLayers.length) return null;
    const preferredKey =
      selectedIndex?.id === "NDBI"
        ? NDBI_BUILT_DETECTION_LAYER_KEY
        : selectedIndex?.id === "NDVI"
          ? NDVI_CLASSES_LAYER_KEY
          : activeComparisonLayerKey;
    return (
      comparisonLayers.find((layer: any) => layer.key === preferredKey) ??
      comparisonLayers.find((layer: any) => layer.key === activeComparisonLayerKey) ??
      comparisonLayers.find((layer: any) => String(layer.key ?? "").endsWith("_change")) ??
      comparisonLayers[0]
    );
  }, [activeComparisonLayerKey, comparisonLayers, selectedIndex?.id]);
  const visualResult = activeComparisonLayer ?? runResult;
  const stats = visualResult?.stats ?? ndviStats;
  const formatNumericStat = (value: unknown, digits = 2) =>
    value == null || value === "" ? "-" : Number(value).toFixed(digits);
  const histogram = visualResult?.histogram ?? ndviHistogram;
  const classes = visualResult?.classes ?? visualResult?.legend ?? [];
  const mosaicQuality =
    selectedIndex?.id === OSI_SAR_ID
      ? (runResult?.quality_summary ?? runResult?.mosaic ?? runResult?.quality)
      : (runResult?.mosaic ?? runResult?.quality ?? (selectedImage as any)?.quality);
  const accuracy = runResult?.accuracy;
  const qualitySummary = runResult?.quality_summary;
  const isClassificationSelected = selectedIndex
    ? CLASSIFICATION_IDS.includes(selectedIndex.id)
    : false;
  const isSupervisedSelected = selectedIndex?.id === SUPERVISED_CLASSIFICATION_ID;
  const isUnsupervisedSelected = selectedIndex?.id === UNSUPERVISED_CLASSIFICATION_ID;
  const supervisedSamplesInsideAoi = useMemo(
    () => trainingSamples.filter((sample) => sample.class_id && sampleIntersectsAoi(sample, aoi)),
    [aoi, trainingSamples],
  );
  const selectedSupervisedClasses = useMemo(
    () => landcoverClasses.filter((item) => selectedSupervisedClassIds.includes(String(item.id))),
    [landcoverClasses, selectedSupervisedClassIds],
  );
  const supervisedSampleCountsByClass = useMemo(() => {
    const counts: Record<string, { training: number; validation: number; total: number }> = {};
    for (const item of landcoverClasses)
      counts[String(item.id)] = { training: 0, validation: 0, total: 0 };
    for (const sample of supervisedSamplesInsideAoi) {
      const classId = String(sample.class_id);
      if (!counts[classId]) counts[classId] = { training: 0, validation: 0, total: 0 };
      const usage = sample.usage === "validation" ? "validation" : "training";
      counts[classId][usage] += 1;
      counts[classId].total += 1;
    }
    return counts;
  }, [landcoverClasses, supervisedSamplesInsideAoi]);
  const selectedClassesMissingTraining = selectedSupervisedClasses.filter(
    (item) => (supervisedSampleCountsByClass[String(item.id)]?.training ?? 0) === 0,
  );
  const trainingSampleCount = supervisedSamplesInsideAoi.filter(
    (sample) => (sample.usage ?? "training") === "training",
  ).length;
  const validationSampleCount = supervisedSamplesInsideAoi.filter(
    (sample) => sample.usage === "validation",
  ).length;
  const supervisedWorkflowReady =
    selectedSupervisedClasses.length >= 2 && selectedClassesMissingTraining.length === 0;
  const classificationInterpretation = isUnsupervisedSelected
    ? unsupervisedResultSummary(qualitySummary, classes, language)
    : supervisedResultSummary(
        runResult?.interpretation,
        accuracy,
        classes,
        supervisedAlgorithm,
        language,
      );
  const isOsiSarSelected = selectedIndex?.id === OSI_SAR_ID;
  const isNdbiBuiltResult =
    selectedIndex?.id === "NDBI" && activeComparisonLayer?.key === NDBI_BUILT_DETECTION_LAYER_KEY;
  const isChangeDetectionSelected = selectedIndex?.id
    ? selectedIndex.id.startsWith("CHANGE_")
    : false;
  const canRunSelectedAnalysis = Boolean(
    selectedIndex &&
    aoi &&
    (isOsiSarSelected || selectedImage) &&
    (!isSupervisedSelected || (supervisedWorkflowReady && supervisedWorkflowStep === 3)),
  );
  const selectedIndexCopy = selectedIndex ? mapIndexCopy(selectedIndex, language) : null;
  const selectedSourceLabel =
    qualitySummary?.scene_id && isOsiSarSelected
      ? String(qualitySummary.scene_id)
      : selectedImage && !(selectedImage as any).mosaic
        ? mapBackendText(selectedImage.name, language)
        : isOsiSarSelected
          ? mapText("Latest Sentinel-1 scene in the period", language)
          : selectedImage
            ? mapBackendText(selectedImage.name, language)
            : mapText("No image", language);
  const isNdviChangeSelected = selectedIndex?.id === "CHANGE_NDVI";
  const visualResultIndex = useMemo(() => {
    if (!selectedIndex || !activeComparisonLayer) return selectedIndex;
    const isPeriodLayer = String(activeComparisonLayer.key ?? "").includes("_period_");
    const layerLegend =
      Array.isArray(activeComparisonLayer.legend) && activeComparisonLayer.legend.length > 0
        ? activeComparisonLayer.legend
        : Array.isArray(activeComparisonLayer.classes) && activeComparisonLayer.classes.length > 0
          ? activeComparisonLayer.classes
          : null;
    const baseLegend = indices.find(
      (item) => item.id === (activeComparisonLayer.index ?? selectedIndex.id),
    )?.legend;
    return {
      ...selectedIndex,
      id: activeComparisonLayer.index ?? selectedIndex.id,
      name: activeComparisonLayer.title ?? selectedIndex.name,
      topic: activeComparisonLayer.topic ?? selectedIndex.topic,
      palette: activeComparisonLayer.palette ?? selectedIndex.palette,
      legend:
        layerLegend ??
        (isPeriodLayer ? (baseLegend ?? selectedIndex.legend) : selectedIndex.legend),
    } as SpectralIndex;
  }, [activeComparisonLayer, selectedIndex]);
  const isContinuousResultMap =
    !isClassificationSelected &&
    !isChangeDetectionSelected &&
    !isOsiSarSelected &&
    activeComparisonLayer?.key !== NDBI_BUILT_DETECTION_LAYER_KEY &&
    activeComparisonLayer?.key !== NDBI_CLASSES_LAYER_KEY &&
    activeComparisonLayer?.key !== NDVI_CLASSES_LAYER_KEY &&
    activeComparisonLayer?.key !== NDVI_RAW_LAYER_KEY &&
    !["NDVI", "NDBI"].includes(String(visualResultIndex?.id ?? selectedIndex?.id ?? "").toUpperCase()) &&
    ["NDWI", "NDBI_RAW", "BSI", "SAVI"].includes(
      String(visualResultIndex?.id ?? selectedIndex?.id ?? "").toUpperCase(),
    );
  const resultLegendNote = !showResult
    ? undefined
    : runResultStatsDeferred
      ? mapText("Exact class areas are still being computed.", language)
      : isUnsupervisedSelected
        ? mapText(
            "Clusters are spectral groups, not validated land-cover classes. Labels shown below are probable interpretations only.",
            language,
          )
      : isContinuousResultMap
        ? mapText(
            "The map is a continuous index stretch, not a classified land-cover layer. Class areas in hectares are statistics; classes below 1% of the AOI are usually not visible at this zoom.",
            language,
          )
        : undefined;
  const continuousLegendStretch = isContinuousResultMap
    ? {
        min: Number(visualResult?.stats?.min ?? Number.NaN),
        max: Number(visualResult?.stats?.max ?? Number.NaN),
        palette: Array.isArray(visualResult?.palette)
          ? visualResult.palette.map(String)
          : Array.isArray(visualResultIndex?.palette)
            ? visualResultIndex.palette.map(String)
            : Array.isArray(selectedIndex?.palette)
              ? selectedIndex.palette.map(String)
              : [],
      }
    : null;
  const localizedResultClasses = useMemo(
    () =>
      Array.isArray(classes)
        ? classes.map((item: any, index: number) => {
            const rawLabel = item?.label ?? item?.name ?? `Class ${index + 1}`;
            const rawMeaning = legendMeaningForClass(item, visualResultIndex?.legend);
            const localizedLabel = mapBackendText(rawLabel, language);
            const localizedMeaning = rawMeaning ? mapBackendText(rawMeaning, language) : "";
            const areaSummary =
              isUnsupervisedSelected && !item?.deferred
                ? `${formatAreaHa(item?.surface_ha ?? item?.surface ?? 0, language)} · ${formatClassPct(item?.pct, item?.surface_ha ?? item?.surface)}`
                : "";
            return {
              ...item,
              name: localizedLabel,
              label: localizedLabel,
              meaning: [areaSummary, localizedMeaning].filter(Boolean).join(" — "),
              description: [areaSummary, localizedMeaning].filter(Boolean).join(" — "),
            };
          })
        : [],
    [classes, isUnsupervisedSelected, language, visualResultIndex],
  );
  const localizedVisualResultIndex = useMemo(() => {
    if (!visualResultIndex) return null;
    const copy = mapIndexCopy(visualResultIndex, language);
    return {
      ...visualResultIndex,
      name: copy.name,
      topic: copy.topic,
      description: copy.description,
      legend: localizedResultClasses.length > 0 ? localizedResultClasses : visualResultIndex.legend,
    } as SpectralIndex;
  }, [language, localizedResultClasses, visualResultIndex]);
  // Refreshed sub-layer URLs are merged into comparison_layers by the API.
  // The selected sub-layer must therefore take priority over the main run tile.
  const visualResultTileUrl =
    activeComparisonLayer?.tiles?.index_tile_url ??
    liveResultTileUrl ??
    runResult?.tiles?.index_tile_url ??
    null;
  const visualResultSourcePalette =
    runResult?.analysis_type === "unsupervised_classification"
      ? (runResult?.tile_source_palette ?? runResult?.palette ?? null)
      : null;
  const visualResultDisplayPalette =
    runResult?.analysis_type === "unsupervised_classification"
      ? [...classes]
          .sort((left: any, right: any) => Number(left?.code ?? 0) - Number(right?.code ?? 0))
          .map((item: any) => String(item?.color ?? ""))
      : null;
  const changePeriod1 = (qualitySummary as any)?.period_1 ??
    stats.period_1 ?? {
      start_date: changeDateStart1,
      end_date: changeDateEnd1,
    };
  const changePeriod2 = (qualitySummary as any)?.period_2 ??
    stats.period_2 ?? {
      start_date: changeDateStart2,
      end_date: changeDateEnd2,
    };
  const ndviChangeSummary = useMemo(() => {
    if (
      !isNdviChangeSelected ||
      (activeComparisonLayer && activeComparisonLayer.key !== "ndvi_change") ||
      !Array.isArray(classes) ||
      classes.length === 0
    )
      return null;
    const byKeyword = (keyword: string) =>
      classes
        .filter((item: any) =>
          String(item.name ?? "")
            .toLowerCase()
            .includes(keyword),
        )
        .reduce((sum: number, item: any) => sum + Number(item.surface_ha ?? item.surface ?? 0), 0);
    const byPct = (keyword: string) =>
      classes
        .filter((item: any) =>
          String(item.name ?? "")
            .toLowerCase()
            .includes(keyword),
        )
        .reduce((sum: number, item: any) => sum + Number(item.pct ?? 0), 0);
    const lossHa = byKeyword("loss");
    const stableHa = byKeyword("stable");
    const gainHa = byKeyword("gain");
    const lossPct = byPct("loss");
    const stablePct = byPct("stable");
    const gainPct = byPct("gain");
    const dominantClass =
      [...classes].sort(
        (a: any, b: any) =>
          Number(b.surface_ha ?? b.surface ?? 0) - Number(a.surface_ha ?? a.surface ?? 0),
      )[0] ?? null;
    let interpretation = "Vegetation change is mixed across the area of interest.";
    if (stablePct >= 60) {
      interpretation = "Most of the area remains stable, with localized vegetation changes.";
    } else if (lossHa > gainHa * 1.3) {
      interpretation = "Vegetation loss dominates over the selected period pair.";
    } else if (gainHa > lossHa * 1.3) {
      interpretation = "Vegetation gain dominates over the selected period pair.";
    } else if (lossHa > 0 || gainHa > 0) {
      interpretation = "The area shows a balanced mix of vegetation loss and gain.";
    }
    return {
      lossHa,
      stableHa,
      gainHa,
      lossPct,
      stablePct,
      gainPct,
      dominantClass,
      interpretation,
      warning: (qualitySummary as any)?.warning ?? null,
    };
  }, [
    activeComparisonLayer,
    classes,
    isNdviChangeSelected,
    qualitySummary,
    stats.period_1,
    stats.period_2,
  ]);
  const unsupervisedAvailableBands =
    sensor === "landsat-8-9"
      ? UNSUPERVISED_BANDS_BY_SENSOR["landsat-8-9"]
      : UNSUPERVISED_BANDS_BY_SENSOR["sentinel-2"];
  const toggleUnsupervisedBand = (band: string) => {
    setUnsupervisedBands((prev) => {
      if (prev.includes(band)) return prev.filter((item) => item !== band);
      return [...prev, band];
    });
  };

  const renameCluster = async (code: number, name: string) => {
    const clean = name.trim();
    if (!activeRunId || !clean) return;
    try {
      const response = await renameUnsupervisedCluster(activeRunId, code, clean);
      setRunResult((prev: any) => ({ ...(prev ?? {}), ...response.item }));
      toast.success(mapText("Cluster label updated", language));
      await loadResultLayers();
    } catch (error) {
      console.error(error);
      toast.error(mapText("Unable to rename cluster", language), {
        description: mapErrorDescription(error, language),
      });
    }
  };

  const changeClusterColor = async (code: number, color: string) => {
    if (!activeRunId || !/^#[0-9a-f]{6}$/i.test(color)) return;
    try {
      const response = await updateUnsupervisedCluster(activeRunId, code, { color });
      setRunResult((prev: any) => ({ ...(prev ?? {}), ...response.item }));
      toast.success(mapText("Cluster color updated", language));
      await loadResultLayers();
    } catch (error) {
      console.error(error);
      toast.error(mapText("Unable to update cluster color", language), {
        description: error instanceof Error ? error.message : "Backend error",
      });
    }
  };
  useEffect(() => {
    const available =
      sensor === "landsat-8-9"
        ? UNSUPERVISED_BANDS_BY_SENSOR["landsat-8-9"]
        : UNSUPERVISED_BANDS_BY_SENSOR["sentinel-2"];
    setUnsupervisedBands((prev) => {
      const kept = prev.filter((band) => available.includes(band));
      return kept.length >= 2 ? kept : available;
    });
  }, [sensor]);

  const resultLayersByIndex = useMemo(() => {
    const map = new Map<string, any>();
    for (const layer of resultLayers) map.set(layer.index, layer);
    return map;
  }, [resultLayers]);
  const currentResultStatus = selectedIndex
    ? (resultStatusByIndex[selectedIndex.id] ?? "not_calculated")
    : "not_calculated";
  const aoiAreaKm2 = useMemo(() => {
    if (!aoi) return 0;
    const geometryArea = aoiGeometryAreaKm2(aoiGeometry);
    if (geometryArea > 0) return geometryArea;
    const [[south, west], [north, east]] = aoi;
    const meanLat = (((south + north) / 2) * Math.PI) / 180;
    const widthKm = Math.abs(east - west) * 111.32 * Math.max(Math.cos(meanLat), 0.25);
    const heightKm = Math.abs(north - south) * 110.57;
    return Math.max(widthKm * heightKm, 0);
  }, [aoi, aoiGeometry]);
  const aoiSurfaceLevel =
    aoiAreaKm2 > 15000 ? "very large" : aoiAreaKm2 > 5000 ? "large" : "standard";
  const resultStatusLabel = (status: string) => {
    if (status === "not_calculated") return t("status.notCalculated");
    if (status === "running") return t("status.running");
    if (status === "calculating_stats") return mapText("Map ready; statistics updating", language);
    if (status === "calculated") return t("status.calculated");
    if (status === "error") return t("status.error");
    if (status === "available_from_cache") return t("status.availableFromCache");
    return RESULT_STATUS_LABELS[status] ?? status;
  };

  return (
    <div dir="ltr" className="h-[calc(100vh-3.5rem)] flex">
      {/* LEFT PANEL */}
      <aside
        dir={isRtl ? "rtl" : "ltr"}
        className="w-80 border-r bg-card flex flex-col shrink-0 overflow-hidden"
      >
        <div className="flex border-b text-xs">
          {(
            [
              { k: "images", l: t("map.tabs.images"), I: ImageIcon },
              { k: "layers", l: t("map.tabs.layers"), I: LayersIcon },
              { k: "basemap", l: t("map.tabs.basemap"), I: MapIcon },
              { k: "tools", l: t("map.tabs.tools"), I: Wrench },
            ] as const
          ).map(({ k, l, I }) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 border-b-2 transition-colors ${
                tab === k
                  ? "border-primary text-primary font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <I className="h-3.5 w-3.5" />
              {l}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-auto p-3 space-y-2">
          {tab === "images" && (
            <div className="mb-2 rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground space-y-3">
              <div>
                {aoi
                  ? isSearchingImages
                    ? mapText("Searching Sentinel-2 for the selected area...", language)
                    : catalogMode === "gee"
                      ? t("map.liveGeeCatalog")
                      : catalogMode === "unavailable"
                        ? "Google Earth Engine is unavailable. No mock images are displayed."
                        : mapText("No live image to display", language)
                  : mapText("Draw an area to search for live Sentinel-2 images.", language)}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <label className="space-y-1">
                  <span className="block text-[10px] font-semibold uppercase">
                    {t("map.startDate")}
                  </span>
                  <LocalizedDatePicker
                    value={dateStart}
                    onChange={setDateStart}
                    language={language}
                  />
                </label>
                <label className="space-y-1">
                  <span className="block text-[10px] font-semibold uppercase">
                    {t("map.endDate")}
                  </span>
                  <LocalizedDatePicker value={dateEnd} onChange={setDateEnd} language={language} />
                </label>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <label className="space-y-1">
                  <span className="block text-[10px] font-semibold uppercase">
                    {t("map.satelliteSensor")}
                  </span>
                  <select
                    value={sensor}
                    onChange={(e) => setSensor(e.target.value as SensorId)}
                    className="w-full rounded-md border bg-card px-2 py-1.5 text-xs text-foreground"
                  >
                    {SENSOR_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="block text-[10px] font-semibold uppercase">
                    {mapText("Export resolution", language)}
                  </span>
                  <select
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value as ResolutionId)}
                    className="w-full rounded-md border bg-card px-2 py-1.5 text-xs text-foreground"
                  >
                    {RESOLUTION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.value === "auto"
                          ? `${mapText("Automatic", language)} (${nativeOutputResolution(selectedIndex?.id, sensor)})`
                          : option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="space-y-1 block">
                <span className="block text-[10px] font-semibold uppercase">
                  {mapText("Analysis source", language)}
                </span>
                <select
                  value={
                    selectedIndex?.id === OSI_SAR_ID
                      ? "selected_scene"
                      : selectedIndex?.id?.startsWith("CHANGE_")
                        ? "median_composite"
                        : imageMethod
                  }
                  disabled={
                    selectedIndex?.id === OSI_SAR_ID ||
                    Boolean(selectedIndex?.id?.startsWith("CHANGE_"))
                  }
                  onChange={(event) => setImageMethod(event.target.value as ImageMethod)}
                  className="w-full rounded-md border bg-card px-2 py-1.5 text-xs text-foreground disabled:opacity-60"
                >
                  <option value="median_composite">
                    {mapText("Temporal composite (median)", language)}
                  </option>
                  <option value="selected_scene">
                    {mapText("Selected scene", language)}
                  </option>
                </select>
                <span className="block text-[10px] leading-4 text-muted-foreground">
                  {selectedIndex?.id?.startsWith("CHANGE_")
                    ? mapText("Change Detection uses one temporal composite for each period.", language)
                    : imageMethod === "selected_scene"
                      ? mapText("The analysis will use only the selected catalogue acquisition.", language)
                      : mapText("The analysis will use the median of all valid images in the period.", language)}
                </span>
              </label>
              <div className="rounded-md border bg-muted/30 px-2 py-1.5 text-[10px] leading-4 text-muted-foreground">
                {mapText("Native analysis resolution", language)}: {nativeOutputResolution(selectedIndex?.id, sensor)} · {mapText("Statistics adapt to AOI size", language)} · {mapText("Continuous export: bilinear; classes: nearest neighbour", language)}
              </div>
              <label className="space-y-1 block">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase">
                    {t("map.maxSceneClouds")}
                  </span>
                  <span className="font-mono">{maxCloudPct}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={maxCloudPct}
                  onChange={(e) => setMaxCloudPct(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </label>
              {geeSearchProgress.visible && (
                <div
                  className={`rounded-md border px-2 py-2 text-[11px] ${geeSearchProgress.error ? "border-destructive/40 bg-destructive/10 text-destructive" : "bg-card"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">
                      {geeSearchProgress.error
                        ? mapText("Image detection error", language)
                        : mapText("Searching satellite images...", language)}
                    </span>
                    <span className="font-mono font-semibold">{geeSearchProgress.percent}%</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${geeSearchProgress.error ? "bg-destructive" : "bg-primary"}`}
                      style={{ width: `${geeSearchProgress.percent}%` }}
                    />
                  </div>
                  <p className="mt-2 leading-snug text-muted-foreground">
                    {mapText(geeSearchProgress.message, language)}
                  </p>
                </div>
              )}
              {aoi && (
                <div className="rounded-md border bg-card px-2 py-2 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span>{t("map.aoiArea")}</span>
                    <b>{aoiAreaKm2.toFixed(0)} km2</b>
                  </div>
                  <div className="mt-1">
                    {mapText("Level", language)}: <b>{mapText(aoiSurfaceLevel, language)}</b>
                  </div>
                </div>
              )}
              <button
                onClick={loadCatalogImages}
                disabled={!aoi || isSearchingImages}
                className="w-full rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {isSearchingImages ? t("map.searching") : t("map.searchGeeImages")}
              </button>
            </div>
          )}
          {tab === "images" &&
            catalogImages.map((img) => (
              <div
                key={img.id}
                className={`rounded-lg border p-3 text-sm transition-colors ${
                  selectedImage?.id === img.id ? "border-primary bg-primary/5" : "hover:bg-muted/40"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium truncate">{mapBackendText(img.name, language)}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {img.sensor} - {img.date}
                    </p>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-success/15 text-success shrink-0">
                    {mapBackendText(img.status, language)}
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-1 text-[11px] text-muted-foreground">
                  <span>
                    {mapText("Res", language)}: {img.resolution}
                  </span>
                  {(img as any).orbit_pass ? (
                    <span>
                      {mapText("Orbit pass", language)}: {(img as any).orbit_pass}{" "}
                      {(img as any).relative_orbit ?? ""}
                    </span>
                  ) : (
                    <span>
                      {mapText("Clouds", language)}: {img.cloud}%
                      {(img as any).date_mosaic || (img as any).cloud_source === "scl_aoi"
                        ? ` (${mapText("AOI", language)})`
                        : ""}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => void handleSelectImage(img)}
                  disabled={previewingImageId === img.id}
                  className="mt-2 w-full text-xs py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                >
                  {previewingImageId === img.id
                    ? t("map.searching")
                    : mapText("Show on map", language)}
                </button>
              </div>
            ))}

          {tab === "layers" && (
            <>
              <LayerRow
                label={mapText("Multispectral image", language)}
                opacityLabel={mapText("Opacity", language)}
                enabled={showRaster}
                onToggle={setShowRaster}
                opacity={rasterOpacity}
                onOpacity={setRasterOpacity}
              />
              <LayerRow
                label={mapText("Area of interest", language)}
                opacityLabel={mapText("Opacity", language)}
                enabled={Boolean(aoi && showAoi)}
                onToggle={setShowAoi}
                opacity={1}
                onOpacity={() => {}}
                disabledOpacity
              />
              <div className="rounded-lg border p-3 text-sm space-y-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showResult && hasResult}
                    onChange={(e) => setShowResult(e.target.checked && hasResult)}
                  />
                  <span className="font-medium">{mapText("Analysis result", language)}</span>
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground w-12">
                    {mapText("Opacity", language)}
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={resultOpacity}
                    disabled={!hasResult}
                    onChange={(e) => setResultOpacity(parseFloat(e.target.value))}
                    className="flex-1 accent-primary"
                  />
                  <span className="text-[10px] tabular-nums w-8 text-right">
                    {Math.round(resultOpacity * 100)}%
                  </span>
                </div>
                <div className="space-y-1.5 border-t pt-2">
                  {indices.map((idx) => {
                    const layer = resultLayersByIndex.get(idx.id);
                    const active = Boolean(
                      layer &&
                      ((activeResultCacheKey && layer.cache_key === activeResultCacheKey) ||
                        (!activeResultCacheKey &&
                          showResult &&
                          hasResult &&
                          selectedIndex?.id === idx.id)),
                    );
                    const status = layer
                      ? "available_from_cache"
                      : (resultStatusByIndex[idx.id] ?? "not_calculated");
                    return (
                      <div
                        key={idx.id}
                        className={`rounded-md border px-2 py-1.5 ${active ? "border-primary bg-primary/5" : "bg-card"}`}
                      >
                        <label className="flex items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            checked={Boolean(active)}
                            disabled={!layer}
                            onChange={(event) => {
                              if (!layer) return;
                              if (!event.target.checked && active) {
                                setShowResult(false);
                                return;
                              }
                              activateCachedLayer(layer);
                            }}
                          />
                          <span className="flex-1 font-medium">
                            {analysisShortLabel(idx.id, language)}
                          </span>
                        </label>
                        <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
                          <span>{resultStatusLabel(status)}</span>
                          {layer && (
                            <button
                              className="text-primary hover:underline"
                              onClick={() => activateCachedLayer(layer)}
                            >
                              {mapText("Show on map", language)}
                            </button>
                          )}
                        </div>
                        {(changeComparisonBase(idx.id) ||
                          idx.id === OSI_SAR_ID) &&
                          layer &&
                          visibleComparisonLayers.length > 0 &&
                          active && (
                            <div className="mt-2 space-y-1.5 rounded-md border bg-background/80 p-2">
                              <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                                {idx.id === OSI_SAR_ID
                                  ? mapText("OSI-SAR result layers", language)
                                  : `${String(idx.id).replace("CHANGE_", "")} ${language === "ar" ? "طبقات المقارنة" : "comparison layers"}`}
                              </p>
                              {visibleComparisonLayers.map((comparisonLayer: any) => {
                                const comparisonActive =
                                  (activeComparisonLayer?.key ??
                                    defaultComparisonLayerKey(idx.id)) === comparisonLayer.key;
                                return (
                                  <label
                                    key={comparisonLayer.key}
                                    className={`ml-3 flex items-start gap-2 rounded border px-2 py-1.5 text-xs ${
                                      comparisonActive ? "border-primary bg-primary/5" : "bg-card"
                                    }`}
                                  >
                                    <input
                                      type="radio"
                                      name={`${idx.id.toLowerCase()}-comparison-layer`}
                                      checked={comparisonActive}
                                      onChange={() => {
                                        setActiveComparisonLayerKey(comparisonLayer.key);
                                        setShowResult(true);
                                      }}
                                    />
                                    <span className="min-w-0">
                                      <span className="block font-medium">
                                        {mapBackendText(
                                          comparisonLayer.title ?? comparisonLayer.key,
                                          language,
                                        )}
                                      </span>
                                      <span className="block text-[10px] text-muted-foreground">
                                        {mapText(
                                          comparisonLayerSecondaryLabel(comparisonLayer),
                                          language,
                                        )}
                                      </span>
                                    </span>
                                  </label>
                                );
                              })}
                              <p className="text-[10px] leading-snug text-muted-foreground">
                                {mapText(
                                  "One visual layer is active at a time. Statistics and legend follow the selected sub-layer.",
                                  language,
                                )}
                              </p>
                            </div>
                          )}
                      </div>
                    );
                  })}
                </div>
                {resultLayers.length > 0 && (
                  <p className="text-[11px] text-muted-foreground">
                    {mapText("Cached layers are loaded instantly from saved results.", language)}
                  </p>
                )}
                {buildingResult && (
                  <div className="rounded-md border border-violet-300/70 bg-violet-50/50 p-2 dark:bg-violet-950/20">
                    <div className="flex items-center gap-2">
                      <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-xs">
                        <input
                          type="checkbox"
                          checked={showBuildingLayer}
                          onChange={(event) => setShowBuildingLayer(event.target.checked)}
                        />
                        <span className="min-w-0">
                          <span className="block font-medium">
                            {mapText("AI Building candidates", language)}
                          </span>
                          <span className="block text-[10px] text-muted-foreground">
                            {buildingResult.candidate_count.toLocaleString()} {mapText("objects", language)}
                          </span>
                        </span>
                      </label>
                      <button
                        type="button"
                        onClick={clearBuildingResult}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        aria-label={mapText("Remove AI Building layer", language)}
                        title={mapText("Remove AI Building layer", language)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
              <LayerRow
                label={mapText("Administrative boundaries", language)}
                opacityLabel={mapText("Opacity", language)}
                enabled={showAdmin}
                onToggle={setShowAdmin}
                opacity={1}
                onOpacity={() => {}}
                disabledOpacity
              />
            </>
          )}

          {tab === "basemap" &&
            (
              [
                { k: "osm", l: "OpenStreetMap" },
                { k: "satellite", l: "ESRI Imagery" },
                { k: "googleSatellite", l: "Google Satellite" },
                { k: "terrain", l: "Terrain" },
                { k: "light", l: "Light gray" },
              ] as const
            ).map((b) => (
              <button
                key={b.k}
                onClick={() => setBasemap(b.k)}
                className={`w-full text-left text-sm rounded-md border px-3 py-2 transition-colors ${
                  basemap === b.k
                    ? "border-primary bg-primary/5 text-primary font-medium"
                    : "hover:bg-muted/40"
                }`}
              >
                {mapText(b.l, language)}
              </button>
            ))}

          {tab === "tools" && (
            <>
              <ToolBtn
                icon={Square}
                label={mapText("Draw rectangle", language)}
                active={drawMode === "rectangle"}
                onClick={() => setDrawMode(drawMode === "rectangle" ? null : "rectangle")}
              />
              <ToolBtn
                icon={Upload}
                label={mapText("Import area of interest", language)}
                onClick={() => aoiFileInputRef.current?.click()}
              />
              <input
                ref={aoiFileInputRef}
                type="file"
                hidden
                multiple
                accept=".geojson,.json,.zip,.shp,.shx,.dbf,.prj,.cpg,.kml,.kmz,application/geo+json,application/json,application/zip,application/vnd.google-earth.kml+xml,application/vnd.google-earth.kmz"
                onChange={(event) => {
                  void handleImportAoiFiles(event.target.files);
                }}
              />
              <p className="px-1 text-[11px] leading-snug text-muted-foreground">
                {mapText("Import a GeoJSON, Shapefile, KML or KMZ file", language)}
              </p>
              <div className="mt-1 space-y-2 rounded-md border px-3 py-2">
                <p className="text-[11px] font-medium">
                  {mapText("Split area of interest", language)}
                </p>
                <button
                  type="button"
                  onClick={() => void handleSplitAoi()}
                  disabled={!aoi}
                  className="w-full rounded-md border px-2 py-1 text-sm transition-colors hover:bg-muted/40 disabled:opacity-50"
                >
                  {mapText("Split automatically", language)}
                </button>
                <p className="text-[11px] leading-snug text-muted-foreground">
                  {mapText("Aligned grid, 4 cells along the longest side", language)}
                </p>
                {aoiParts.length > 0 && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] text-muted-foreground">
                        {selectedPartIds.length}/{aoiParts.length}{" "}
                        {mapText("parts selected", language)}
                      </p>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => applyPartSelection(aoiParts.map((part) => part.part_id))}
                          className="rounded-md border px-2 py-0.5 text-[11px] transition-colors hover:bg-muted/40"
                        >
                          {mapText("All", language)}
                        </button>
                        <button
                          type="button"
                          onClick={() => applyPartSelection([])}
                          className="rounded-md border px-2 py-0.5 text-[11px] transition-colors hover:bg-muted/40"
                        >
                          {mapText("None", language)}
                        </button>
                      </div>
                    </div>
                    <p className="text-[11px] leading-snug text-muted-foreground">
                      {selectedPartIds.length > 0
                        ? mapText(
                            "Run the image search again so the source image matches the selection",
                            language,
                          )
                        : mapText("Click the cells on the map to analyse them together", language)}
                    </p>
                    <button
                      type="button"
                      onClick={handleRestoreFullAoi}
                      className="w-full rounded-md border px-2 py-1 text-left text-xs transition-colors hover:bg-muted/40"
                    >
                      {mapText("Full area of interest", language)}
                    </button>
                  </div>
                )}
              </div>
              <ToolBtn
                icon={Trash2}
                label={mapText("Clear selection", language)}
                onClick={() => {
                  setAoi(null);
                  setAoiGeometry(null);
                  setShowAoi(false);
                  resetAoiParts();
                  toast(mapText("Selection cleared", language));
                }}
              />
              <ToolBtn
                icon={Ruler}
                label={mapText("Measure distance", language)}
                onClick={() => toast.info(mapText("Distance measurement enabled", language))}
              />
              <ToolBtn
                icon={Maximize}
                label={mapText("Measure area", language)}
                onClick={() => toast.info(mapText("Area measurement enabled", language))}
              />
            </>
          )}
        </div>
      </aside>

      {/* MAP */}
      <div ref={mapCaptureRef} data-map-pdf-capture="true" className="flex-1 relative bg-muted">
        {runResult?.mode === "mock" && showResult && hasResult ? (
          <div className="absolute top-3 left-1/2 z-[2000] -translate-x-1/2 max-w-md rounded-md border border-destructive/40 bg-background px-3 py-2 text-center text-xs text-destructive">
            {mapText(
              "This stored result is a mock. It is not an operational GEE analysis.",
              language,
            )}
          </div>
        ) : null}
        {MapComp ? (
          <MapComp
            selectedImage={selectedImage}
            aoi={aoi}
            aoiGeometry={aoiGeometry}
            aoiParts={aoiParts}
            selectedPartIds={selectedPartIds}
            onToggleAoiPart={toggleAoiPart}
            aoiFitNonce={aoiFitNonce}
            showAoi={showAoi}
            showRaster={showRaster}
            showResult={showResult && hasResult}
            rasterOpacity={rasterOpacity}
            resultOpacity={resultOpacity}
            drawMode={drawMode}
            basemap={basemap}
            onAoiDrawn={handleAoiDrawn}
            resultIndex={localizedVisualResultIndex}
            rasterTileUrl={liveRasterTileUrl ?? (selectedImage as any)?.tile_url ?? null}
            rasterImageUrl={buildingRasterPreviewUrl}
            rasterImageBounds={(() => {
              const bounds = preparedBuildingRaster?.metadata?.wgs84_bounds as
                | { left?: number; bottom?: number; right?: number; top?: number }
                | undefined;
              return bounds && [
                [Number(bounds.bottom), Number(bounds.left)],
                [Number(bounds.top), Number(bounds.right)],
              ] as [[number, number], [number, number]];
            })()}
            resultTileUrl={visualResultTileUrl}
            resultSourcePalette={visualResultSourcePalette}
            resultDisplayPalette={visualResultDisplayPalette}
            samples={showSavedTrainingSamples ? trainingSamples : []}
            classes={landcoverClasses}
            resultClasses={localizedResultClasses}
            legendTitle={language === "ar" ? "مفتاح الخريطة" : "Legend"}
            legendDirection={language === "ar" ? "rtl" : "ltr"}
            legendNote={resultLegendNote}
            continuousLegend={continuousLegendStretch}
            recenterTitle={mapText("Recenter map", language)}
            onSampleCreated={handleSampleCreated}
            onResultTileError={refreshExpiredResultTile}
            buildingResult={buildingResult}
            showBuildingLayer={showBuildingLayer}
            buildingFitNonce={buildingFitNonce}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
            <Loader2 className="h-4 w-4 mr-2 animate-spin" /> {t("map.loadingMap")}
          </div>
        )}
      </div>

      {/* RIGHT PANEL */}
      <aside
        dir={isRtl ? "rtl" : "ltr"}
        className="w-96 border-l bg-card flex flex-col shrink-0 overflow-hidden"
      >
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm">{t("map.rasterAnalysis")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{t("map.workflow")}</p>
        </div>
        <div className="flex-1 overflow-auto">
          <StepRow
            n={1}
            label={t("map.selectedImage")}
            ok={Boolean(selectedImage || (isOsiSarSelected && aoi))}
            value={selectedSourceLabel}
          />
          <StepRow
            n={2}
            label={t("map.areaOfInterest")}
            ok={!!aoi}
            value={
              aoi
                ? `${aoi[0][0].toFixed(3)},${aoi[0][1].toFixed(3)} -> ${aoi[1][0].toFixed(3)},${aoi[1][1].toFixed(3)}`
                : mapText("No area drawn", language)
            }
          />
          {isOsiSarSelected && (qualitySummary || mosaicQuality) ? (
            <div className="p-4 border-b bg-muted/20">
              <p className="text-xs font-semibold uppercase tracking-wide mb-2">
                {mapText("Sentinel-1 acquisition", language)}
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <MiniMetric
                  label={mapText("Acquisition date", language)}
                  value={String(
                    qualitySummary?.acquisition_date ?? mosaicQuality?.acquisition_date ?? "-",
                  )}
                />
                <MiniMetric
                  label={mapText("Orbit pass", language)}
                  value={String(qualitySummary?.orbit_pass ?? mosaicQuality?.orbit_pass ?? "-")}
                />
                <MiniMetric
                  label={mapText("Relative orbit", language)}
                  value={String(
                    qualitySummary?.relative_orbit ?? mosaicQuality?.relative_orbit ?? "-",
                  )}
                />
                <MiniMetric
                  label={mapText("Scenes found", language)}
                  value={String(
                    qualitySummary?.available_images ?? mosaicQuality?.available_images ?? "-",
                  )}
                />
                <MiniMetric
                  label={mapText("Scenes used", language)}
                  value={String(qualitySummary?.images_count ?? mosaicQuality?.images_count ?? 1)}
                />
              </div>
              {(qualitySummary?.scene_id || mosaicQuality?.scene_id) && (
                <p className="mt-2 break-all text-[10px] text-muted-foreground">
                  {mapText("Scene ID", language)}:{" "}
                  {String(qualitySummary?.scene_id ?? mosaicQuality?.scene_id)}
                </p>
              )}
              {(qualitySummary?.warning || mosaicQuality?.warning) && (
                <p className="mt-1 text-[11px] text-warning">
                  {mapBackendText(qualitySummary?.warning ?? mosaicQuality?.warning, language)}
                </p>
              )}
            </div>
          ) : mosaicQuality ? (
            <div className="p-4 border-b bg-muted/20">
              <p className="text-xs font-semibold uppercase tracking-wide mb-2">
                {mapText("Mosaic quality", language)}
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <MiniMetric
                  label={mapText("Images", language)}
                  value={String(
                    mosaicQuality.images_count ?? mosaicQuality.available_images ?? "-",
                  )}
                />
                <MiniMetric
                  label={mapText("Tiles", language)}
                  value={String(mosaicQuality.tiles_count ?? "-")}
                />
                <MiniMetric
                  label={mapText("Valid", language)}
                  value={String(mosaicQuality.valid_tiles_count ?? "-")}
                />
                <MiniMetric
                  label={mapText("Empty", language)}
                  value={String(mosaicQuality.empty_tiles_count ?? "-")}
                />
                <MiniMetric
                  label={mapText("Coverage", language)}
                  value={`${mosaicQuality.coverage_percent ?? "-"}%`}
                />
                <MiniMetric
                  label={mapText("Quality", language)}
                  value={mapBackendText(mosaicQuality.quality, language)}
                />
              </div>
              {mosaicQuality.area_km2 && (
                <p className="mt-2 text-[11px] text-muted-foreground">
                  {mapText("Area", language)}: {Number(mosaicQuality.area_km2).toFixed(0)}{" "}
                  {language === "ar" ? "كم²" : "km²"}
                </p>
              )}
              {mosaicQuality.warning && (
                <p className="mt-1 text-[11px] text-warning">
                  {mapBackendText(mosaicQuality.warning, language)}
                </p>
              )}
              {Array.isArray(mosaicQuality.tile_reports) &&
                mosaicQuality.tile_reports.length > 0 && (
                  <div className="mt-3 max-h-40 overflow-auto rounded-md border bg-card text-[11px]">
                    {mosaicQuality.tile_reports.slice(0, 12).map((tile: any) => (
                      <div
                        key={tile.tile_id}
                        className="flex items-center justify-between gap-2 border-b px-2 py-1 last:border-b-0"
                      >
                        <span className="font-mono">{tile.tile_id}</span>
                        <span>
                          {tile.images_count} {language === "ar" ? "صورة" : "img"}
                        </span>
                        <span>{tile.coverage_percent}%</span>
                        <span
                          className={
                            displayBackendText(tile.status).toLowerCase() === "valid"
                              ? "text-success"
                              : "text-warning"
                          }
                        >
                          {mapBackendText(tile.status, language)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          ) : null}
          <div className="p-4 border-b">
            <div className="flex items-center gap-2 mb-3">
              <span className="h-5 w-5 rounded-full bg-primary text-primary-foreground text-[11px] flex items-center justify-center font-semibold">
                3
              </span>
              <p className="text-xs font-semibold uppercase tracking-wide">{t("map.analysis")}</p>
            </div>
            <div className="mb-3 grid grid-cols-2 gap-2 rounded-lg bg-muted/50 p-1">
              <button
                type="button"
                aria-pressed={analysisFamily === "raster"}
                onClick={() => setAnalysisFamily("raster")}
                className={`rounded-md px-2 py-2 text-[11px] font-semibold ${analysisFamily === "raster" ? "bg-card shadow-sm" : "text-muted-foreground"}`}
              >
                {mapText("Raster analyses", language)}
              </button>
              <button
                type="button"
                aria-pressed={analysisFamily === "ai_building"}
                onClick={() => setAnalysisFamily("ai_building")}
                className={`rounded-md px-2 py-2 text-[11px] font-semibold ${analysisFamily === "ai_building" ? "bg-violet-600 text-white shadow-sm" : "text-muted-foreground"}`}
              >
                {mapText("AI Object Detection", language)}
              </button>
            </div>
            {analysisFamily === "raster" ? (
              <>
            <div className="grid grid-cols-2 gap-1">
              {indices.map((idx) => (
                <button
                  key={idx.id}
                  onClick={() => setSelectedIndex(idx)}
                  className={`min-h-9 px-1.5 py-1.5 text-[11px] font-semibold rounded-md border leading-tight ${
                    selectedIndex?.id === idx.id
                      ? "bg-primary text-primary-foreground border-primary"
                      : "hover:bg-muted"
                  }`}
                >
                  {analysisButtonLabel(idx.id, language)}
                </button>
              ))}
            </div>
            {selectedIndex && (
              <div className="mt-3 rounded-md bg-muted/50 p-3 space-y-1.5">
                <p className="text-sm font-medium">
                  {selectedIndexCopy?.name} -{" "}
                  <span className="font-normal text-muted-foreground">
                    {selectedIndexCopy?.topic}
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">{selectedIndexCopy?.description}</p>
                {!isClassificationSelected && (
                  <p className="text-[11px] text-muted-foreground">{selectedIndexCopy?.bands}</p>
                )}
              </div>
            )}
            {isChangeDetectionSelected && (
              <div className="mt-3 rounded-md border bg-card p-3 text-xs space-y-3">
                <div>
                  <p className="font-semibold">{mapText("Change Detection periods", language)}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {mapText(
                      "Compare the same AOI using matched mosaics: Delta = Period 2 index - Period 1 index.",
                      language,
                    )}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <label className="block space-y-1">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Period 1 start", language)}
                    </span>
                    <LocalizedDatePicker
                      value={changeDateStart1}
                      onChange={setChangeDateStart1}
                      language={language}
                      className="bg-background"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Period 1 end", language)}
                    </span>
                    <LocalizedDatePicker
                      value={changeDateEnd1}
                      onChange={setChangeDateEnd1}
                      language={language}
                      className="bg-background"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Period 2 start", language)}
                    </span>
                    <LocalizedDatePicker
                      value={changeDateStart2}
                      onChange={setChangeDateStart2}
                      language={language}
                      className="bg-background"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Period 2 end", language)}
                    </span>
                    <LocalizedDatePicker
                      value={changeDateEnd2}
                      onChange={setChangeDateEnd2}
                      language={language}
                      className="bg-background"
                    />
                  </label>
                </div>
                <p className="rounded-md bg-warning/10 p-2 text-[11px] text-muted-foreground">
                  {mapText(
                    "Use comparable seasons when possible. Seasonal differences can look like real change.",
                    language,
                  )}
                </p>
              </div>
            )}
            {selectedIndex?.id === OSI_SAR_ID && (
              <div className="mt-3 rounded-md border bg-card p-3 text-xs space-y-3">
                <div>
                  <p className="font-semibold">{mapText("OSI-SAR parameters", language)}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {mapText("Sentinel-1 VV/VH dark-target detection for marine AOIs.", language)}
                  </p>
                </div>
                <label className="block space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("VV dark threshold", language)}
                    </span>
                    <span className="font-mono">{osiDarkThresholdDb} dB</span>
                  </div>
                  <input
                    type="range"
                    min={-24}
                    max={-12}
                    step={1}
                    value={osiDarkThresholdDb}
                    onChange={(event) => setOsiDarkThresholdDb(Number(event.target.value))}
                    className="w-full accent-primary"
                  />
                </label>
                <label className="block space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("VH dark threshold", language)}
                    </span>
                    <span className="font-mono">{osiVhDarkThresholdDb} dB</span>
                  </div>
                  <input
                    type="range"
                    min={-32}
                    max={-18}
                    step={1}
                    value={osiVhDarkThresholdDb}
                    onChange={(event) => setOsiVhDarkThresholdDb(Number(event.target.value))}
                    className="w-full accent-primary"
                  />
                </label>
                <label className="block space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Local contrast", language)}
                    </span>
                    <span className="font-mono">{osiContrastThresholdDb.toFixed(1)} dB</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={6}
                    step={0.5}
                    value={osiContrastThresholdDb}
                    onChange={(event) => setOsiContrastThresholdDb(Number(event.target.value))}
                    className="w-full accent-primary"
                  />
                </label>
                <label className="block space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Contrast radius", language)}
                    </span>
                    <span className="font-mono">{osiContrastRadiusM} m</span>
                  </div>
                  <input
                    type="range"
                    min={100}
                    max={1500}
                    step={100}
                    value={osiContrastRadiusM}
                    onChange={(event) => setOsiContrastRadiusM(Number(event.target.value))}
                    className="w-full accent-primary"
                  />
                </label>
                <label className="block space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Minimum connected pixels", language)}
                    </span>
                    <span className="font-mono">{osiMinConnectedPixels}</span>
                  </div>
                  <input
                    type="range"
                    min={4}
                    max={64}
                    step={1}
                    value={osiMinConnectedPixels}
                    onChange={(event) => setOsiMinConnectedPixels(Number(event.target.value))}
                    className="w-full accent-primary"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    {mapText(
                      "Removes isolated radar noise smaller than the selected connected-pixel count.",
                      language,
                    )}
                  </p>
                </label>
                <label className="block space-y-1">
                  <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                    {mapText("Orbit pass", language)}
                  </span>
                  <select
                    value={osiOrbitPass}
                    onChange={(event) =>
                      setOsiOrbitPass(event.target.value as "ANY" | "ASCENDING" | "DESCENDING")
                    }
                    className="w-full rounded-md border bg-background px-2 py-1.5"
                  >
                    <option value="ANY">{mapText("Any pass", language)}</option>
                    <option value="ASCENDING">{mapText("Ascending", language)}</option>
                    <option value="DESCENDING">{mapText("Descending", language)}</option>
                  </select>
                </label>
                <div className="grid grid-cols-1 gap-2">
                  <label className="flex items-center gap-2 rounded border px-2 py-1.5">
                    <input
                      type="checkbox"
                      checked={osiWaterMask}
                      onChange={(event) => setOsiWaterMask(event.target.checked)}
                    />
                    <span>{mapText("Water/sea mask", language)}</span>
                  </label>
                  <label className="flex items-center gap-2 rounded border px-2 py-1.5">
                    <input
                      type="checkbox"
                      checked={osiWindValidation}
                      onChange={(event) => setOsiWindValidation(event.target.checked)}
                    />
                    <span>{mapText("ERA5 wind validation", language)}</span>
                  </label>
                  <label className="flex items-center gap-2 rounded border px-2 py-1.5">
                    <input
                      type="checkbox"
                      checked={osiSentinel2Validation}
                      onChange={(event) => setOsiSentinel2Validation(event.target.checked)}
                    />
                    <span>{mapText("Sentinel-2 visual validation", language)}</span>
                  </label>
                </div>
                {osiWindValidation && (
                  <div className="grid grid-cols-2 gap-2">
                    <label className="block space-y-1">
                      <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                        {mapText("Min wind", language)}
                      </span>
                      <input
                        type="number"
                        min={0}
                        max={20}
                        step={0.5}
                        value={osiWindMinMs}
                        onChange={(event) => setOsiWindMinMs(Number(event.target.value))}
                        className="w-full rounded-md border bg-background px-2 py-1.5"
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                        {mapText("Max wind", language)}
                      </span>
                      <input
                        type="number"
                        min={0}
                        max={25}
                        step={0.5}
                        value={osiWindMaxMs}
                        onChange={(event) => setOsiWindMaxMs(Number(event.target.value))}
                        className="w-full rounded-md border bg-background px-2 py-1.5"
                      />
                    </label>
                  </div>
                )}
                <p className="rounded-md bg-warning/10 p-2 text-[11px] text-muted-foreground">
                  {mapText(
                    "OSI-SAR returns suspects, not confirmed pollution. Validate detections with wind, maritime context, and optical evidence when available.",
                    language,
                  )}
                </p>
              </div>
            )}
            {selectedIndex?.id === SUPERVISED_CLASSIFICATION_ID && (
              <div className="mt-3 rounded-md border bg-card p-3 text-xs space-y-3">
                <div>
                  <p className="font-semibold">{mapText("Supervised training", language)}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {mapText(
                      "Guided user-sample workflow. WorldCover fallback is disabled for analyses launched here.",
                      language,
                    )}
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-1">
                  {([1, 2, 3] as SupervisedWorkflowStep[]).map((workflowStep) => (
                    <button
                      key={workflowStep}
                      type="button"
                      onClick={() => {
                        if (workflowStep === 2 && selectedSupervisedClasses.length < 2) return;
                        if (workflowStep === 3 && !supervisedWorkflowReady) return;
                        setSupervisedWorkflowStep(workflowStep);
                        if (workflowStep !== 2 && (drawMode === "point" || drawMode === "polygon"))
                          setDrawMode(null);
                      }}
                      className={`rounded-md border px-1 py-1.5 text-[10px] font-semibold ${
                        supervisedWorkflowStep === workflowStep
                          ? "border-primary bg-primary text-primary-foreground"
                          : "bg-background"
                      }`}
                    >
                      {workflowStep}.{" "}
                      {mapText(
                        workflowStep === 1 ? "Classes" : workflowStep === 2 ? "Samples" : "Review",
                        language,
                      )}
                    </button>
                  ))}
                </div>

                {supervisedWorkflowStep === 1 && (
                  <div className="space-y-3">
                    <div>
                      <p className="mb-1 font-semibold">
                        {mapText("Step 1 — Choose and configure classes", language)}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {mapText(
                          "Select at least two classes that will be represented by user samples.",
                          language,
                        )}
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-1">
                      {landcoverClasses.map((item) => {
                        const classId = String(item.id);
                        const selected = selectedSupervisedClassIds.includes(classId);
                        const count = supervisedSampleCountsByClass[classId]?.total ?? 0;
                        return (
                          <label
                            key={classId}
                            className={`flex items-center gap-1.5 rounded border px-1.5 py-1.5 text-[10px] ${selected ? "border-primary bg-primary/5" : ""}`}
                          >
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => toggleSupervisedClass(classId)}
                            />
                            <span
                              className="h-2.5 w-2.5 rounded-full border"
                              style={{ background: item.color }}
                            />
                            <span className="min-w-0 flex-1 truncate">
                              {mapBackendText(item.name, language)}
                            </span>
                            <span className="font-mono text-muted-foreground">{count}</span>
                          </label>
                        );
                      })}
                    </div>
                    <div className="rounded-md border bg-muted/30 p-2 space-y-2">
                      <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                        {mapText("Create a class", language)}
                      </p>
                      <div className="flex gap-1">
                        <input
                          value={newLandcoverClassName}
                          onChange={(event) => setNewLandcoverClassName(event.target.value)}
                          placeholder={mapText("Class name", language)}
                          className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1.5"
                        />
                        <input
                          type="color"
                          value={newLandcoverClassColor}
                          onChange={(event) => setNewLandcoverClassColor(event.target.value)}
                          className="h-8 w-10 rounded border bg-background p-1"
                          aria-label={mapText("Class color", language)}
                        />
                        <button
                          type="button"
                          onClick={handleCreateLandcoverClass}
                          className="rounded-md border bg-background px-2"
                          title={mapText("Create a class", language)}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <label className="block space-y-1">
                        <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                          {mapText("Algorithm", language)}
                        </span>
                        <select
                          value={supervisedAlgorithm}
                          onChange={(event) =>
                            setSupervisedAlgorithm(event.target.value as SupervisedAlgorithm)
                          }
                          className="w-full rounded-md border bg-background px-2 py-1.5"
                        >
                          <option value="random_forest">
                            {mapText("Random Forest", language)}
                          </option>
                          <option value="cart">{mapText("Decision Tree (CART)", language)}</option>
                          <option value="svm">
                            {mapText("Support Vector Machine (SVM)", language)}
                          </option>
                        </select>
                      </label>
                      <label className="flex items-end gap-1.5 pb-1.5 text-[11px]">
                        <input
                          type="checkbox"
                          checked={compareSupervisedAlgorithms}
                          onChange={(event) => setCompareSupervisedAlgorithms(event.target.checked)}
                        />
                        {mapText("Compare", language)}
                      </label>
                    </div>
                    {supervisedAlgorithm === "random_forest" && (
                      <label className="block space-y-1">
                        <div className="flex justify-between">
                          <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                            {mapText("Trees", language)}
                          </span>
                          <span>{supervisedTrees}</span>
                        </div>
                        <input
                          type="range"
                          min={50}
                          max={300}
                          step={25}
                          value={supervisedTrees}
                          onChange={(event) => setSupervisedTrees(Number(event.target.value))}
                          className="w-full accent-primary"
                        />
                      </label>
                    )}
                    <button
                      type="button"
                      disabled={selectedSupervisedClasses.length < 2}
                      onClick={() => {
                        setSupervisedWorkflowStep(2);
                        setActiveSampleClassId(String(selectedSupervisedClasses[0]?.id ?? ""));
                        setShowSavedTrainingSamples(true);
                      }}
                      className="w-full inline-flex items-center justify-center gap-1 rounded-md bg-primary px-2 py-2 font-medium text-primary-foreground disabled:opacity-50"
                    >
                      {mapText("Continue to samples", language)}{" "}
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}

                {supervisedWorkflowStep === 2 && (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold">
                          {mapText("Step 2 — Create training samples", language)}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {mapText(
                            "Choose the active class, then draw directly on the map.",
                            language,
                          )}
                        </p>
                      </div>
                      <div className="text-right text-[10px]">
                        <div>
                          <b>{trainingSampleCount}</b> {mapText("Training samples", language)}
                        </div>
                        <div>
                          <b>{validationSampleCount}</b> {mapText("Validation samples", language)}
                        </div>
                      </div>
                    </div>
                    <label className="block space-y-1">
                      <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                        {mapText("Active class", language)}
                      </span>
                      <select
                        value={activeSampleClassId}
                        onChange={(event) => setActiveSampleClassId(event.target.value)}
                        className="w-full rounded-md border bg-background px-2 py-1.5"
                      >
                        {selectedSupervisedClasses.map((item) => (
                          <option key={item.id} value={item.id}>
                            {mapBackendText(item.name, language)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block space-y-1">
                      <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                        {mapText("Sample role", language)}
                      </span>
                      <select
                        value={activeSampleUsage}
                        onChange={(event) =>
                          setActiveSampleUsage(event.target.value as "training" | "validation")
                        }
                        className="w-full rounded-md border bg-background px-2 py-1.5"
                      >
                        <option value="training">{mapText("Training", language)}</option>
                        <option value="validation">{mapText("Validation", language)}</option>
                      </select>
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        disabled={!activeSampleClassId || isSavingSupervisedSample}
                        onClick={() => setDrawMode(drawMode === "point" ? null : "point")}
                        className={`inline-flex items-center justify-center gap-1 rounded-md border px-2 py-2 font-medium ${drawMode === "point" ? "border-primary bg-primary text-primary-foreground" : "bg-background"}`}
                      >
                        <Sigma className="h-3.5 w-3.5" /> {mapText("Draw point", language)}
                      </button>
                      <button
                        type="button"
                        disabled={!activeSampleClassId || isSavingSupervisedSample}
                        onClick={() => setDrawMode(drawMode === "polygon" ? null : "polygon")}
                        className={`inline-flex items-center justify-center gap-1 rounded-md border px-2 py-2 font-medium ${drawMode === "polygon" ? "border-primary bg-primary text-primary-foreground" : "bg-background"}`}
                      >
                        <Hexagon className="h-3.5 w-3.5" /> {mapText("Draw polygon", language)}
                      </button>
                    </div>
                    {drawMode === "polygon" && (
                      <p className="rounded bg-primary/5 p-2 text-[10px]">
                        {mapText(
                          "Click at least three vertices, then double-click to finish the polygon.",
                          language,
                        )}
                      </p>
                    )}
                    {drawMode === "point" && (
                      <p className="rounded bg-primary/5 p-2 text-[10px]">
                        {mapText("Click once on the map to save a point sample.", language)}
                      </p>
                    )}
                    <label className="flex items-center justify-between rounded-md border bg-background px-2 py-1.5 text-[11px]">
                      <span>{mapText("Show saved training samples on map", language)}</span>
                      <input
                        type="checkbox"
                        checked={showSavedTrainingSamples}
                        onChange={(event) => setShowSavedTrainingSamples(event.target.checked)}
                      />
                    </label>
                    <div className="max-h-56 space-y-1 overflow-auto">
                      {selectedSupervisedClasses.map((item) => {
                        const classId = String(item.id);
                        const classSamples = supervisedSamplesInsideAoi.filter(
                          (sample) => String(sample.class_id) === classId,
                        );
                        const counts = supervisedSampleCountsByClass[classId] ?? {
                          training: 0,
                          validation: 0,
                          total: 0,
                        };
                        return (
                          <div key={classId} className="rounded-md border bg-background p-2">
                            <div className="flex items-center gap-1.5">
                              <span
                                className="h-3 w-3 rounded-full border"
                                style={{ background: item.color }}
                              />
                              <span className="min-w-0 flex-1 truncate font-medium">
                                {mapBackendText(item.name, language)}
                              </span>
                              <span
                                className={
                                  counts.training > 0 ? "text-success" : "text-destructive"
                                }
                              >
                                {counts.training} {mapText("Tr.", language)}
                              </span>
                              <span className="text-muted-foreground">
                                {counts.validation} {mapText("Val.", language)}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleDeleteClassSamples(classId)}
                                disabled={counts.total === 0}
                                className="rounded p-1 text-destructive disabled:opacity-30"
                                title={mapText("Delete class samples", language)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </div>
                            {classSamples.map((sample) => (
                              <div
                                key={sample.id}
                                className="mt-1 flex items-center gap-1 border-t pt-1 text-[10px]"
                              >
                                <span className="w-14 truncate">
                                  {mapText(
                                    String(sample.geometry_type ?? sample.geometry?.type ?? ""),
                                    language,
                                  )}
                                </span>
                                <span className="w-12 text-muted-foreground">
                                  {mapText(String(sample.usage ?? "training"), language)}
                                </span>
                                <select
                                  value={sample.class_id}
                                  onChange={(event) =>
                                    handleUpdateTrainingSampleClass(
                                      String(sample.id),
                                      event.target.value,
                                    )
                                  }
                                  className="min-w-0 flex-1 rounded border bg-background px-1 py-0.5"
                                >
                                  {selectedSupervisedClasses.map((targetClass) => (
                                    <option key={targetClass.id} value={targetClass.id}>
                                      {mapBackendText(targetClass.name, language)}
                                    </option>
                                  ))}
                                </select>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteTrainingSample(String(sample.id))}
                                  className="rounded p-1 text-destructive"
                                  title={mapText("Delete sample", language)}
                                >
                                  <Trash2 className="h-3 w-3" />
                                </button>
                              </div>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                    {selectedClassesMissingTraining.length > 0 && (
                      <p className="rounded-md bg-destructive/10 p-2 text-[11px] text-destructive">
                        {mapText("Missing training samples", language)}:{" "}
                        {selectedClassesMissingTraining
                          .map((item) => mapBackendText(item.name, language))
                          .join(", ")}
                      </p>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setDrawMode(null);
                          setSupervisedWorkflowStep(1);
                        }}
                        className="inline-flex items-center justify-center gap-1 rounded-md border px-2 py-2"
                      >
                        <ChevronLeft className="h-3.5 w-3.5" /> {mapText("Back", language)}
                      </button>
                      <button
                        type="button"
                        disabled={!supervisedWorkflowReady}
                        onClick={() => {
                          setDrawMode(null);
                          setSupervisedWorkflowStep(3);
                        }}
                        className="inline-flex items-center justify-center gap-1 rounded-md bg-primary px-2 py-2 text-primary-foreground disabled:opacity-50"
                      >
                        {mapText("Review", language)} <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                )}

                {supervisedWorkflowStep === 3 && (
                  <div className="space-y-3">
                    <div>
                      <p className="font-semibold">
                        {mapText("Step 3 — Review and run", language)}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {mapText(
                          "Only samples inside the current AOI are included in the supervised classification workflow.",
                          language,
                        )}
                      </p>
                    </div>
                    <div className="rounded-md border bg-muted/30 p-2 space-y-1 text-[11px]">
                      <div className="flex justify-between">
                        <span>{mapText("Selected classes", language)}</span>
                        <b>{selectedSupervisedClasses.length}</b>
                      </div>
                      <div className="flex justify-between">
                        <span>{mapText("Training geometries", language)}</span>
                        <b>{trainingSampleCount}</b>
                      </div>
                      <div className="flex justify-between">
                        <span>{mapText("Validation geometries", language)}</span>
                        <b>{validationSampleCount}</b>
                      </div>
                      <div className="flex justify-between">
                        <span>{mapText("Algorithm", language)}</span>
                        <b>
                          {mapText(
                            supervisedAlgorithm === "random_forest"
                              ? "Random Forest"
                              : supervisedAlgorithm === "cart"
                                ? "Decision Tree (CART)"
                                : "Support Vector Machine (SVM)",
                            language,
                          )}
                        </b>
                      </div>
                    </div>
                    <p className="rounded-md bg-warning/10 p-2 text-[10px] text-muted-foreground">
                      {mapText(
                        "Pixels are sampled from these geometries. At least 40 training pixels and 10 validation pixels are required; when no validation geometry is provided, the validation set is created automatically. Point-only datasets usually require dozens of points.",
                        language,
                      )}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setSupervisedWorkflowStep(2)}
                        className="inline-flex items-center justify-center gap-1 rounded-md border px-2 py-2"
                      >
                        <ChevronLeft className="h-3.5 w-3.5" /> {mapText("Samples", language)}
                      </button>
                      <button
                        type="button"
                        disabled={!canRunSelectedAnalysis || (step !== "idle" && step !== "done")}
                        onClick={() => runAnalysis(false)}
                        className="inline-flex items-center justify-center gap-1 rounded-md bg-success px-2 py-2 font-medium text-success-foreground disabled:opacity-50"
                      >
                        <Play className="h-3.5 w-3.5" /> {mapText("Run classification", language)}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
            {selectedIndex?.id === UNSUPERVISED_CLASSIFICATION_ID && (
              <div className="mt-3 rounded-md border bg-card p-3 text-xs space-y-3">
                <div>
                  <p className="font-semibold">{mapText("Automatic clustering", language)}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {mapText(
                      "Automatic grouping of similar spectral patterns without training samples.",
                      language,
                    )}
                  </p>
                </div>

                <label className="block space-y-1">
                  <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                    {mapText("Mode", language)}
                  </span>
                  <select
                    value={unsupervisedMode}
                    onChange={(event) =>
                      setUnsupervisedMode(event.target.value as UnsupervisedMode)
                    }
                    className="w-full rounded-md border bg-background px-2 py-1.5"
                  >
                    <option value="simple">{mapText("Simple", language)}</option>
                    <option value="expert">{mapText("Expert", language)}</option>
                  </select>
                </label>

                <label className="block space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      {mapText("Clusters", language)}
                    </span>
                    <span className="font-mono">{unsupervisedClusters}</span>
                  </div>
                  <input
                    type="range"
                    min={2}
                    max={12}
                    step={1}
                    value={unsupervisedClusters}
                    onChange={(event) => setUnsupervisedClusters(Number(event.target.value))}
                    className="w-full accent-primary"
                  />
                </label>

                {unsupervisedMode === "expert" && (
                  <>
                    <label className="block space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                          {mapText("Sampling pixels", language)}
                        </span>
                        <span className="font-mono">{unsupervisedSamplesCount}</span>
                      </div>
                      <input
                        type="range"
                        min={1000}
                        max={15000}
                        step={1000}
                        value={unsupervisedSamplesCount}
                        onChange={(event) =>
                          setUnsupervisedSamplesCount(Number(event.target.value))
                        }
                        className="w-full accent-primary"
                      />
                    </label>

                    <div>
                      <p className="mb-1 text-[10px] font-semibold uppercase text-muted-foreground">
                        {mapText("Input bands", language)}
                      </p>
                      <div className="grid grid-cols-3 gap-1">
                        {unsupervisedAvailableBands.map((band) => (
                          <label
                            key={band}
                            className="flex items-center gap-1.5 rounded border px-1.5 py-1 text-[10px]"
                          >
                            <input
                              type="checkbox"
                              checked={unsupervisedBands.includes(band)}
                              onChange={() => toggleUnsupervisedBand(band)}
                              disabled={
                                unsupervisedBands.length <= 2 && unsupervisedBands.includes(band)
                              }
                            />
                            <span>{band}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
              </>
            ) : (
              <BuildingDetectionPanel
                language={language}
                sourceMode={buildingSourceMode}
                onSourceModeChange={(source) => {
                  setBuildingSourceMode(source);
                  setBuildingError(null);
                }}
                parameters={buildingParameters}
                onParametersChange={setBuildingParameters}
                preparedRaster={buildingSourceMode === "orthophoto" ? preparedBuildingRaster : null}
                uploadedFileName={buildingSourceMode === "orthophoto" ? buildingUploadFileName : null}
                canUseSentinel={Boolean(aoi && selectedImage && geeEnabled !== false)}
                isUploading={isBuildingUploading}
                uploadProgress={buildingUploadProgress}
                isRunning={isBuildingRunning}
                error={buildingError}
                result={buildingResult}
                layerVisible={showBuildingLayer}
                exportingFormat={buildingExportingFormat}
                onUpload={(file) => void uploadBuildingOrthophoto(file)}
                onRun={() => void runBuildingAnalysis()}
                onToggleLayer={setShowBuildingLayer}
                onExport={(format) => void exportBuildingResult(format)}
                onClear={clearBuildingResult}
              />
            )}
          </div>

          <div className={analysisFamily === "raster" ? "p-4 border-b" : "hidden"}>
            <div className="flex items-center gap-2 mb-3">
              <span className="h-5 w-5 rounded-full bg-primary text-primary-foreground text-[11px] flex items-center justify-center font-semibold">
                4
              </span>
              <p className="text-xs font-semibold uppercase tracking-wide">{t("map.run")}</p>
            </div>
            <button
              onClick={() => runAnalysis(false)}
              disabled={!canRunSelectedAnalysis || (step !== "idle" && step !== "done")}
              className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-success text-success-foreground py-2.5 text-sm font-medium hover:bg-success/90 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
              {step !== "idle" && step !== "done" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {step === "clip" && mapText("Clipping...", language)}
              {step === "compute" &&
                (isChangeDetectionSelected
                  ? mapText("Computing change...", language)
                  : isClassificationSelected
                    ? mapText("Classifying...", language)
                    : mapText("Computing index...", language))}
              {step === "render" && mapText("Generating...", language)}
              {(step === "idle" || step === "done") &&
                (isChangeDetectionSelected ? t("map.runChange") : t("map.runRaster"))}
            </button>
            {analysisProgress.visible && (
              <div
                className={`mt-2 rounded-md border px-2 py-2 text-[11px] ${analysisProgress.error ? "border-destructive/40 bg-destructive/10 text-destructive" : "border-success/30 bg-success/10 text-foreground"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">
                    {analysisProgress.error
                      ? mapText("Analysis error", language)
                      : analysisProgress.cached
                        ? mapText("Cache result", language)
                        : mapText("Raster processing", language)}
                  </span>
                  <span className="font-semibold tabular-nums">{analysisProgress.percent}%</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-background/80">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${analysisProgress.error ? "bg-destructive" : analysisProgress.cached ? "bg-primary" : "bg-success"}`}
                    style={{ width: `${analysisProgress.percent}%` }}
                  />
                </div>
                <p className="mt-1 leading-snug">{mapText(analysisProgress.message, language)}</p>
              </div>
            )}
            <div className="mt-2 grid grid-cols-2 gap-2">
              <button
                onClick={() => runAnalysis(true)}
                disabled={!canRunSelectedAnalysis || (step !== "idle" && step !== "done")}
                className="inline-flex items-center justify-center gap-1.5 rounded-md border px-2 py-2 text-xs font-medium hover:bg-muted disabled:opacity-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                {t("map.recalculate")}
              </button>
              <button
                onClick={deleteActiveResult}
                disabled={!activeResultCacheKey}
                className="inline-flex items-center justify-center gap-1.5 rounded-md border px-2 py-2 text-xs font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
                {t("map.deleteResult")}
              </button>
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground">
              {t("map.status")}: <b>{resultStatusLabel(currentResultStatus)}</b>
            </p>
            {!canRunSelectedAnalysis && (
              <p className="text-[11px] text-muted-foreground mt-2">
                {isOsiSarSelected
                  ? mapText(
                      "Draw a marine area of interest, then run Sentinel-1 OSI-SAR.",
                      language,
                    )
                  : mapText("Select an image, then draw an area of interest.", language)}
              </p>
            )}
          </div>

          <div className={analysisFamily === "raster" ? "p-4" : "hidden"}>
            <div className="flex items-center gap-2 mb-3">
              <span className="h-5 w-5 rounded-full bg-primary text-primary-foreground text-[11px] flex items-center justify-center font-semibold">
                5
              </span>
              <p className="text-xs font-semibold uppercase tracking-wide">{t("map.results")}</p>
            </div>
            {!hasResult ? (
              <p className="text-xs text-muted-foreground italic">{t("map.noResults")}</p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-2 text-center">
                  {isUnsupervisedSelected ? (
                    <>
                      <Stat
                        l={t("stats.area")}
                        v={formatAreaHa(stats.surface_ha ?? stats.total_area_ha ?? 0, language)}
                      />
                      <Stat
                        l={mapText("Classified area", language)}
                        v={formatAreaHa(stats.classified_surface_ha ?? 0, language)}
                      />
                      <Stat
                        l={mapText("Classified AOI", language)}
                        v={`${Number(stats.classified_pct_of_aoi ?? 0).toFixed(1)}%`}
                      />
                      <Stat
                        l={mapText("Clusters", language)}
                        v={String(stats.classes_count ?? classes.length)}
                      />
                      <Stat
                        l={mapText("Sampling pixels", language)}
                        v={Number(stats.samples_count ?? 0).toLocaleString()}
                      />
                      <Stat
                        l={mapText("Sample scale", language)}
                        v={`${qualitySummary?.sample_scale_m ?? "-"} m`}
                      />
                    </>
                  ) : isClassificationSelected ? (
                    <>
                      <Stat
                        l={t("stats.area")}
                        v={formatAreaHa(stats.surface_ha ?? stats.total_area_ha ?? 0, language)}
                      />
                      <Stat
                        l={t("map.classes")}
                        v={String(stats.classes_count ?? classes.length)}
                      />
                      <Stat
                        l={mapText("Training", language)}
                        v={String(
                          stats.training_samples_count ??
                            qualitySummary?.training_samples_count ??
                            "-",
                        )}
                      />
                      <Stat
                        l={mapText("Validation", language)}
                        v={String(
                          stats.validation_samples_count ??
                            qualitySummary?.validation_samples_count ??
                            "-",
                        )}
                      />
                      <Stat
                        l={mapText("Coverage", language)}
                        v={`${qualitySummary?.coverage_percent ?? mosaicQuality?.coverage_percent ?? "-"}%`}
                      />
                      <Stat
                        l={mapText("Overall accuracy", language)}
                        v={
                          accuracy?.overall_accuracy != null
                            ? `${Math.round(Number(accuracy.overall_accuracy) * 100)}%`
                            : "-"
                        }
                      />
                    </>
                  ) : isOsiSarSelected ? (
                    <>
                      <Stat
                        l={mapText("Suspect area", language)}
                        v={formatAreaHa(stats.suspect_surface_ha ?? 0, language)}
                      />
                      <Stat l={mapText("Suspect %", language)} v={`${stats.suspect_pct ?? 0}%`} />
                      <Stat
                        l={mapText("High", language)}
                        v={formatAreaHa(stats.high_suspicion_ha ?? 0, language)}
                      />
                      <Stat
                        l={mapText("Mean VV", language)}
                        v={`${Number(stats.mean_vv_db ?? 0).toFixed(1)} dB`}
                      />
                      <Stat
                        l={mapText("Mean VH", language)}
                        v={`${Number(stats.mean_vh_db ?? 0).toFixed(1)} dB`}
                      />
                      <Stat
                        l={mapText("Wind", language)}
                        v={
                          stats.mean_wind_m_s != null
                            ? `${Number(stats.mean_wind_m_s).toFixed(1)} m/s`
                            : "-"
                        }
                      />
                      <Stat
                        l={mapText("Acquisition date", language)}
                        v={String(
                          stats.acquisition_date ?? qualitySummary?.acquisition_date ?? "-",
                        )}
                      />
                      <Stat
                        l={mapText("Orbit pass", language)}
                        v={mapText(
                          String(stats.orbit_pass ?? qualitySummary?.orbit_pass ?? "-"),
                          language,
                        )}
                      />
                      <Stat
                        l={mapText("Relative orbit", language)}
                        v={String(stats.relative_orbit ?? qualitySummary?.relative_orbit ?? "-")}
                      />
                    </>
                  ) : isNdbiBuiltResult ? (
                    <>
                      <Stat
                        l={mapText("Built-up evidence area", language)}
                        v={formatAreaHa(stats.built_surface_ha ?? 0, language)}
                      />
                      <Stat
                        l={mapText("Built-up evidence", language)}
                        v={`${stats.built_pct ?? 0}%`}
                      />
                      <Stat l={mapText("No evidence", language)} v={`${classes[0]?.pct ?? 0}%`} />
                      <Stat
                        l={mapText("Potential road", language)}
                        v={`${classes[1]?.pct ?? 0}%`}
                      />
                      <Stat l={mapText("Detected", language)} v={`${classes[2]?.pct ?? 0}%`} />
                      <Stat
                        l={mapText("High confidence", language)}
                        v={`${classes[3]?.pct ?? 0}%`}
                      />
                    </>
                  ) : (
                    <>
                      <Stat
                        l={t("stats.min")}
                        v={pendingStatsValue ?? formatNumericStat(stats.min)}
                      />
                      <Stat
                        l={t("stats.max")}
                        v={pendingStatsValue ?? formatNumericStat(stats.max)}
                      />
                      <Stat
                        l={t("stats.mean")}
                        v={pendingStatsValue ?? formatNumericStat(stats.mean)}
                      />
                      <Stat
                        l={t("stats.stdDev")}
                        v={pendingStatsValue ?? formatNumericStat(stats.std)}
                      />
                      <Stat
                        l={t("stats.area")}
                        v={formatAreaHa(stats.surface_ha ?? stats.surface ?? 0, language)}
                      />
                      <Stat
                        l={t("stats.pixels")}
                        v={
                          pendingStatsValue ??
                          (stats.pixels == null ? "-" : Number(stats.pixels).toLocaleString())
                        }
                      />
                    </>
                  )}
                </div>

                {runResultStatsDeferred && (
                  <p className="text-[11px] text-muted-foreground">
                    {mapText("Map ready; statistics updating", language)}
                  </p>
                )}

                {isNdviChangeSelected && ndviChangeSummary && (
                  <div className="space-y-3 rounded-md border bg-muted/20 p-3">
                    <div>
                      <p className="text-xs font-semibold">
                        {mapText("Before / After summary", language)}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {mapText(
                          "Visual reading workflow for P1, P2, NDVI P1, NDVI P2, and Delta NDVI.",
                          language,
                        )}
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div className="rounded-md border bg-card px-2 py-2">
                        <div className="font-medium">{mapText("Period 1", language)}</div>
                        <div className="mt-1 text-muted-foreground">
                          {`${displayBackendText(changePeriod1.start_date)} -> ${displayBackendText(changePeriod1.end_date)}`}
                        </div>
                        <div className="mt-1 text-muted-foreground">
                          {language === "ar"
                            ? "خط أساس NDVI على نفس منطقة الاهتمام"
                            : "NDVI baseline over the same AOI"}
                        </div>
                      </div>
                      <div className="rounded-md border bg-card px-2 py-2">
                        <div className="font-medium">{mapText("Period 2", language)}</div>
                        <div className="mt-1 text-muted-foreground">
                          {`${displayBackendText(changePeriod2.start_date)} -> ${displayBackendText(changePeriod2.end_date)}`}
                        </div>
                        <div className="mt-1 text-muted-foreground">
                          {language === "ar"
                            ? "هدف مقارنة NDVI على نفس منطقة الاهتمام"
                            : "NDVI comparison target over the same AOI"}
                        </div>
                      </div>
                      <div className="rounded-md border bg-card px-2 py-2">
                        <div className="font-medium">NDVI P1</div>
                        <div className="mt-1 text-muted-foreground">
                          {mapText("Reference vegetation state for the first period.", language)}
                        </div>
                      </div>
                      <div className="rounded-md border bg-card px-2 py-2">
                        <div className="font-medium">NDVI P2</div>
                        <div className="mt-1 text-muted-foreground">
                          {mapText("Observed vegetation state for the second period.", language)}
                        </div>
                      </div>
                      <div className="col-span-2 rounded-md border bg-card px-2 py-2">
                        <div className="font-medium">Delta NDVI</div>
                        <div className="mt-1 text-muted-foreground">
                          {mapText("Computed as NDVI period 2 minus NDVI period 1.", language)}
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <Stat
                        l={mapText("Loss", language)}
                        v={formatAreaHa(ndviChangeSummary.lossHa, language)}
                      />
                      <Stat
                        l={mapText("Stable", language)}
                        v={formatAreaHa(ndviChangeSummary.stableHa, language)}
                      />
                      <Stat
                        l={mapText("Gain", language)}
                        v={formatAreaHa(ndviChangeSummary.gainHa, language)}
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <Stat
                        l={mapText("Loss %", language)}
                        v={`${ndviChangeSummary.lossPct.toFixed(1)}%`}
                      />
                      <Stat
                        l={mapText("Stable %", language)}
                        v={`${ndviChangeSummary.stablePct.toFixed(1)}%`}
                      />
                      <Stat
                        l={mapText("Gain %", language)}
                        v={`${ndviChangeSummary.gainPct.toFixed(1)}%`}
                      />
                    </div>
                    <div className="rounded-md border bg-card px-3 py-2 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <span>{mapText("Dominant class", language)}</span>
                        <b>
                          {mapBackendText(ndviChangeSummary.dominantClass?.name ?? "-", language)}
                        </b>
                      </div>
                      <p className="mt-2 leading-relaxed text-muted-foreground">
                        {ndviChangeSummary.interpretation}
                      </p>
                    </div>
                    {ndviChangeSummary.warning && (
                      <div className="rounded-md border bg-warning/10 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
                        <b>{mapText("Period comparability warning.", language)}</b>{" "}
                        {mapBackendText(ndviChangeSummary.warning, language)}
                      </div>
                    )}
                  </div>
                )}

                {!isClassificationSelected && (
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-semibold mb-1">
                      <Sigma className="h-3.5 w-3.5" /> {t("stats.histogram")}
                    </div>
                    <div className="h-32 rounded-md border bg-muted/30 p-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={histogram}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                          <XAxis dataKey="bin" tick={{ fontSize: 8 }} interval={3} />
                          <YAxis tick={{ fontSize: 8 }} width={28} />
                          <Tooltip contentStyle={{ fontSize: 11 }} />
                          {isChangeDetectionSelected && (
                            <ReferenceLine x={0} stroke="#111827" strokeDasharray="4 3" />
                          )}
                          <Bar dataKey="count" fill="#0f6f88" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {isOsiSarSelected && qualitySummary?.warning && (
                  <div className="rounded-md border bg-warning/10 p-2 text-xs leading-relaxed text-muted-foreground">
                    {mapBackendText(qualitySummary.warning, language)}
                  </div>
                )}

                {isClassificationSelected && accuracy?.kappa != null && (
                  <div className="rounded-md border bg-muted/30 p-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span>{mapText("Overall quality", language)}</span>
                      <b>
                        {accuracy.overall_accuracy != null
                          ? `${Math.round(Number(accuracy.overall_accuracy) * 100)}%`
                          : "-"}
                      </b>
                    </div>
                    <div className="mt-1 flex items-center justify-between">
                      <span>{mapText("Kappa coefficient", language)}</span>
                      <b>{Number(accuracy.kappa).toFixed(2)}</b>
                    </div>
                    {qualitySummary?.sample_source && (
                      <div className="mt-1 flex items-center justify-between">
                        <span>{mapText("Training source", language)}</span>
                        <b>
                          {qualitySummary.sample_source === "user_samples"
                            ? mapText("User samples", language)
                            : "WorldCover"}
                        </b>
                      </div>
                    )}
                    {qualitySummary?.warning && (
                      <p className="mt-2 text-warning">
                        {mapBackendText(qualitySummary.warning, language)}
                      </p>
                    )}
                    {qualitySummary?.fallback_reason && (
                      <p className="mt-1 text-muted-foreground">
                        {mapText("Fallback applied", language)}:{" "}
                        {mapBackendText(
                          qualitySummary.fallback_reason.replaceAll("_", " "),
                          language,
                        )}
                      </p>
                    )}
                  </div>
                )}

                {isClassificationSelected &&
                  Array.isArray(runResult?.algorithm_comparison) &&
                  runResult.algorithm_comparison.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold mb-1">
                        {mapText("Algorithm comparison", language)}
                      </p>
                      <div className="rounded-md border overflow-hidden text-[11px]">
                        {runResult.algorithm_comparison.map((item: any) => (
                          <div
                            key={item.algorithm}
                            className="grid grid-cols-3 gap-2 border-b px-2 py-1.5 last:border-b-0"
                          >
                            <span className="font-medium">
                              {mapText(
                                item.algorithm === "random_forest"
                                  ? "Random Forest"
                                  : item.algorithm === "cart"
                                    ? "Decision Tree (CART)"
                                    : "Support Vector Machine (SVM)",
                                language,
                              )}
                            </span>
                            <span>
                              {mapText("Overall accuracy", language)}{" "}
                              {item.overall_accuracy != null
                                ? `${Math.round(Number(item.overall_accuracy) * 100)}%`
                                : "-"}
                            </span>
                            <span>
                              {mapText("Kappa coefficient", language)}{" "}
                              {item.kappa != null ? Number(item.kappa).toFixed(2) : "-"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {isUnsupervisedSelected && qualitySummary && (
                  <div className="space-y-1 rounded-md border bg-muted/30 p-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span>{mapText("Clusters", language)}</span>
                      <b>{qualitySummary.clusters_count ?? classes.length}</b>
                    </div>
                    <div className="mt-1 flex items-center justify-between">
                      <span>{mapText("Input bands", language)}</span>
                      <b>
                        {Array.isArray(qualitySummary.input_bands)
                          ? qualitySummary.input_bands.length
                          : "-"}
                      </b>
                    </div>
                    {Array.isArray(qualitySummary.input_bands) && (
                      <p className="mt-2 text-[11px] text-muted-foreground">
                        {qualitySummary.input_bands.join(", ")}
                      </p>
                    )}
                    <div className="flex items-center justify-between">
                      <span>{mapText("Sampling pixels", language)}</span>
                      <b>{Number(qualitySummary.samples_count ?? 0).toLocaleString()}</b>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>{mapText("Light spatial filter", language)}</span>
                      <b>
                        {mapText(qualitySummary.apply_focal_mode ? "Enabled" : "Disabled", language)}
                      </b>
                    </div>
                    <div className="mt-2 rounded border border-amber-300/70 bg-amber-50 px-2 py-1.5 text-[11px] leading-snug text-amber-950">
                      <b>{mapText("Reference validation unavailable", language)}.</b>{" "}
                      {mapText(
                        "No independent reference dataset was supplied. Evaluate these clusters through spectral coherence, spatial coherence and stability.",
                        language,
                      )}
                    </div>
                  </div>
                )}

                {isUnsupervisedSelected &&
                  Array.isArray(runResult?.cluster_interpretation) &&
                  runResult.cluster_interpretation.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold mb-1">
                        {mapText("Cluster interpretation", language)}
                      </p>
                      <div className="max-h-40 overflow-auto rounded-md border text-[11px]">
                        {runResult.cluster_interpretation.map((item: any) => (
                          <div key={item.cluster} className="border-b px-2 py-1.5 last:border-b-0">
                            <div className="flex items-center gap-2">
                              <span
                                className="h-2.5 w-2.5 rounded-sm border"
                                style={{ background: item.color }}
                              />
                              <span className="font-medium">
                                {mapBackendText(item.name, language)}
                              </span>
                            </div>
                            {item.means && (
                              <p className="mt-1 text-muted-foreground">
                                NDVI {Number(item.means.NDVI ?? 0).toFixed(2)} | NDWI{" "}
                                {Number(item.means.NDWI ?? 0).toFixed(2)} | NDBI{" "}
                                {Number(item.means.NDBI ?? 0).toFixed(2)} | BSI{" "}
                                {Number(item.means.BSI ?? 0).toFixed(2)} | SAVI{" "}
                                {Number(item.means.SAVI ?? 0).toFixed(2)}
                              </p>
                            )}
                            {(item.probable_label || item.semantic_name) && (
                              <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
                                <b>{mapText("Probable interpretation", language)}:</b>{" "}
                                {mapBackendText(
                                  String(item.probable_label ?? item.semantic_name),
                                  language,
                                )}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {isClassificationSelected &&
                  Array.isArray(accuracy?.class_metrics) &&
                  accuracy.class_metrics.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold mb-1">
                        {mapText("Validation by class", language)}
                      </p>
                      <div className="max-h-36 overflow-auto rounded-md border text-[11px]">
                        {accuracy.class_metrics.map((item: any) => (
                          <div
                            key={item.code}
                            className="grid grid-cols-[1fr_76px_76px] gap-2 border-b px-2 py-1.5 last:border-b-0"
                          >
                            <span className="truncate">{mapBackendText(item.name, language)}</span>
                            <span>
                              {mapText("User accuracy", language)}{" "}
                              {item.user_accuracy != null
                                ? `${Math.round(Number(item.user_accuracy) * 100)}%`
                                : "-"}
                            </span>
                            <span>
                              {mapText("Producer accuracy", language)}{" "}
                              {item.producer_accuracy != null
                                ? `${Math.round(Number(item.producer_accuracy) * 100)}%`
                                : "-"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                <div>
                  <p className="text-xs font-semibold mb-1">
                    {isContinuousResultMap
                      ? mapText("Area by value range", language)
                      : t("map.classes")}
                  </p>
                  {isContinuousResultMap ? (
                    <p className="mb-1.5 text-[10px] leading-snug text-muted-foreground">
                      {mapText(
                        "Surfaces in hectares come from index value ranges. They do not paint separate classified polygons on the continuous map.",
                        language,
                      )}
                    </p>
                  ) : null}
                  <div className="rounded-md border overflow-hidden text-xs">
                    {classes.map((c: any, idx: number) => (
                      <div key={c.name} className="flex gap-2 px-2 py-1.5 border-b last:border-b-0">
                        {isUnsupervisedSelected && activeRunId ? (
                          <input
                            type="color"
                            className="mt-0.5 h-6 w-7 shrink-0 cursor-pointer rounded border bg-background p-0.5"
                            value={
                              /^#[0-9a-f]{6}$/i.test(String(c.color ?? ""))
                                ? String(c.color)
                                : "#000000"
                            }
                            aria-label={`${mapText("Class color", language)}: ${mapBackendText(c.name, language)}`}
                            title={mapText("Change class color", language)}
                            onChange={(event) => {
                              if (
                                event.currentTarget.value.toLowerCase() !==
                                String(c.color ?? "").toLowerCase()
                              ) {
                                void changeClusterColor(Number(c.code), event.currentTarget.value);
                              }
                            }}
                          />
                        ) : (
                          <span
                            className="mt-1 h-3 w-3 shrink-0 rounded-sm"
                            style={{ background: c.color }}
                          />
                        )}
                        <div className="min-w-0 flex-1">
                          {isUnsupervisedSelected && activeRunId ? (
                            <input
                              className="min-w-0 w-full rounded border bg-background px-1.5 py-1 text-xs"
                              defaultValue={mapBackendText(c.name, language)}
                              onBlur={(event) => {
                                if (
                                  event.currentTarget.value.trim() !==
                                  mapBackendText(c.name, language).trim()
                                ) {
                                  renameCluster(Number(c.code), event.currentTarget.value);
                                }
                              }}
                            />
                          ) : (
                            <div className="font-medium">{mapBackendText(c.name, language)}</div>
                          )}
                          {(c.description ||
                            c.meaning ||
                            legendMeaningForClass(c, selectedIndex?.legend)) && (
                            <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
                              {mapBackendText(
                                c.description ||
                                  c.meaning ||
                                  legendMeaningForClass(c, selectedIndex?.legend),
                                language,
                              )}
                            </p>
                          )}
                          {isContinuousResultMap &&
                          !runResultStatsDeferred &&
                          !c.deferred &&
                          classIsBelowMapVisibility(c.pct, c.surface_ha ?? c.surface) ? (
                            <p className="mt-0.5 text-[10px] text-amber-800">
                              {mapText("Rarely visible on the continuous map at this zoom.", language)}
                            </p>
                          ) : null}
                        </div>
                        <div className="shrink-0 text-right">
                          <div className="text-muted-foreground">
                            {c.deferred || runResultStatsDeferred
                              ? "..."
                              : formatAreaHa(c.surface_ha ?? c.surface, language)}
                          </div>
                          <div className="font-medium tabular-nums">
                            {c.deferred || runResultStatsDeferred
                              ? "..."
                              : formatClassPct(c.pct, c.surface_ha ?? c.surface)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {isClassificationSelected && classificationInterpretation && (
                  <div className="rounded-md border bg-muted/30 p-2 text-xs leading-relaxed text-muted-foreground">
                    {classificationInterpretation}
                  </div>
                )}

                <div>
                  <p className="text-xs font-semibold mb-1">{t("map.exports")}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <ExportBtn
                      icon={LayersIcon}
                      label="GeoTIFF"
                      onClick={() => exportFile("geotiff", "GeoTIFF map")}
                    />
                    <ExportBtn
                      icon={isMapLayoutExporting ? Loader2 : FileImage}
                      label={isMapLayoutExporting ? "PNG..." : mapText("Map PNG", language)}
                      onClick={exportMapLayoutPng}
                      disabled={isMapLayoutExporting}
                    />
                    <ExportBtn
                      icon={isMapPdfExporting ? Loader2 : FileText}
                      label={isMapPdfExporting ? "PDF..." : mapText("PDF Report", language)}
                      onClick={exportMapPdf}
                      disabled={isMapPdfExporting}
                    />
                    <ExportBtn
                      icon={Download}
                      label={mapText("CSV stats", language)}
                      onClick={() => exportFile("stats_csv", "Statistics CSV")}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}

function LayerRow({
  label,
  opacityLabel = "Opacity",
  enabled,
  onToggle,
  opacity,
  onOpacity,
  disabledOpacity,
}: {
  label: string;
  opacityLabel?: string;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  opacity: number;
  onOpacity: (v: number) => void;
  disabledOpacity?: boolean;
}) {
  return (
    <div className="rounded-lg border p-3 text-sm space-y-2">
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
        <span className="font-medium">{label}</span>
      </label>
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground w-12">{opacityLabel}</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={opacity}
          disabled={disabledOpacity || !enabled}
          onChange={(e) => onOpacity(parseFloat(e.target.value))}
          className="flex-1 accent-primary"
        />
        <span className="text-[10px] tabular-nums w-8 text-right">
          {Math.round(opacity * 100)}%
        </span>
      </div>
    </div>
  );
}

function ToolBtn({
  icon: Icon,
  label,
  onClick,
  active,
}: {
  icon: typeof Square;
  label: string;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
        active ? "border-primary bg-primary/5 text-primary" : "hover:bg-muted/40"
      }`}
    >
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function StepRow({
  n,
  label,
  ok,
  value,
}: {
  n: number;
  label: string;
  ok: boolean;
  value: string;
}) {
  return (
    <div className="p-4 border-b flex items-start gap-3">
      <span
        className={`h-5 w-5 rounded-full text-[11px] flex items-center justify-center font-semibold shrink-0 ${
          ok ? "bg-success text-success-foreground" : "bg-muted text-muted-foreground"
        }`}
      >
        {ok ? <CheckCircle2 className="h-3 w-3" /> : n}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold uppercase tracking-wide">{label}</p>
        <p className="text-xs text-muted-foreground mt-1 truncate font-mono">{value}</p>
      </div>
    </div>
  );
}

function Stat({ l, v }: { l: string; v: string }) {
  return (
    <div className="rounded-md border bg-muted/30 p-2">
      <p className="text-[10px] uppercase text-muted-foreground">{l}</p>
      <p className="text-sm font-semibold tabular-nums">{v}</p>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-card px-2 py-1.5">
      <p className="text-[10px] uppercase text-muted-foreground">{label}</p>
      <p className="font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function ExportBtn({
  icon: Icon,
  label,
  onClick,
  disabled = false,
}: {
  icon: typeof Download;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center gap-1.5 rounded-md border bg-card px-2 py-2 text-xs hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Icon className={`h-3.5 w-3.5 ${disabled ? "animate-spin" : ""}`} /> {label}
    </button>
  );
}
