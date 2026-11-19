import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  Download,
  Droplets,
  Layers as LayersIcon,
  Leaf,
  Mountain,
  Radar,
  Satellite,
  Sprout,
} from "lucide-react";
import {
  analyses as mockAnalyses,
  dashboardStats,
  images,
  indices,
  type Analysis,
  type SpectralIndex,
} from "@/data/mock";
import { API_BASE_URL } from "@/lib/georaster-api";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard - GeoRaster Analytics" },
      { name: "description", content: "Operational overview of multispectral raster analyses." },
    ],
  }),
  component: DashboardPage,
});

type DashboardResponse = {
  stats?: {
    images?: number;
    analyses?: number;
    indices?: number;
    exports?: number;
  };
  recent_analyses?: any[];
  indices?: any[];
};

type DashboardAnalysis = {
  id: string;
  name: string;
  date: string;
  image: string;
  index: string;
  area: string;
  status: string;
};

const ICONS: Record<string, typeof Sprout> = {
  NDVI: Sprout,
  NDBI: Building2,
  NDWI: Droplets,
  BSI: Mountain,
  SAVI: Leaf,
  SUPERVISED_CLASSIFICATION: Radar,
  UNSUPERVISED_CLASSIFICATION: Radar,
};

const INDEX_TONES: Record<string, string> = {
  NDVI: "bg-emerald-500/15 text-emerald-700",
  NDBI: "bg-orange-500/15 text-orange-700",
  NDWI: "bg-sky-500/15 text-sky-700",
  BSI: "bg-amber-500/15 text-amber-700",
  SAVI: "bg-lime-500/15 text-lime-700",
  SUPERVISED_CLASSIFICATION: "bg-violet-500/15 text-violet-700",
  UNSUPERVISED_CLASSIFICATION: "bg-fuchsia-500/15 text-fuchsia-700",
};

const AR_INDEX_COPY: Record<
  string,
  { label: string; name: string; topic: string; description: string; bands: string[] }
> = {
  NDVI: {
    label: "NDVI",
    name: "تحليل مؤشر الغطاء النباتي NDVI",
    topic: "الغطاء النباتي",
    description:
      "يقيم مستويات الغطاء النباتي وكثافته اعتمادا على نطاقي الأشعة القريبة من تحت الحمراء والأحمر.",
    bands: ["الأشعة القريبة من تحت الحمراء", "الأحمر"],
  },
  NDWI: {
    label: "NDWI",
    name: "تحليل مؤشر المياه والرطوبة NDWI",
    topic: "المياه والرطوبة",
    description: "يكشف المياه السطحية والمناطق الرطبة ومؤشرات الرطوبة في التربة والغطاء النباتي.",
    bands: ["الأخضر", "الأشعة القريبة من تحت الحمراء"],
  },
  NDBI: {
    label: "NDBI",
    name: "تحليل مؤشر العمران NDBI",
    topic: "العمران والمناطق الحضرية",
    description: "يميز المناطق المبنية والأسطح الاصطناعية والطرق والأسطح غير النفاذة.",
    bands: ["الأشعة قصيرة الموجة تحت الحمراء", "الأشعة القريبة من تحت الحمراء"],
  },
  BSI: {
    label: "BSI",
    name: "تحليل مؤشر التربة المكشوفة BSI",
    topic: "التربة المكشوفة",
    description: "يبرز التربة العارية والأسطح الجافة والمناطق ذات الغطاء النباتي الضعيف.",
    bands: ["الأشعة قصيرة الموجة تحت الحمراء", "الأحمر", "الأشعة القريبة من تحت الحمراء", "الأزرق"],
  },
  SAVI: {
    label: "SAVI",
    name: "تحليل مؤشر الغطاء النباتي المعدل للتربة SAVI",
    topic: "النباتات في البيئات شبه الجافة",
    description: "يقيم الغطاء النباتي في المناطق شبه الجافة مع تقليل تأثير خلفية التربة.",
    bands: ["الأشعة القريبة من تحت الحمراء", "الأحمر"],
  },
  OSI_SAR: {
    label: "OSI-SAR",
    name: "تحليل الاشتباه في الانسكابات النفطية OSI-SAR",
    topic: "اشتباه الانسكابات النفطية",
    description:
      "يكشف المرشحات المحتملة للبقع النفطية فوق المياه باستخدام إشارات الرادار Sentinel-1 الداكنة.",
    bands: ["Sentinel-1 VV", "Sentinel-1 VH", "التباين المحلي"],
  },
  CHANGE_NDVI: {
    label: "CHANGE_NDVI",
    name: "CHANGE_NDVI - كشف تغير الغطاء النباتي",
    topic: "تغير الغطاء النباتي",
    description: "يقارن NDVI بين فترتين لرصد فقدان الغطاء النباتي أو استقراره أو زيادته.",
    bands: ["NDVI الفترة 1", "NDVI الفترة 2", "فرق NDVI"],
  },
  CHANGE_NDWI: {
    label: "CHANGE_NDWI",
    name: "CHANGE_NDWI - كشف تغير المياه والرطوبة",
    topic: "تغير المياه والرطوبة",
    description: "يقارن NDWI بين فترتين لرصد انخفاض الرطوبة أو استقرارها أو زيادتها.",
    bands: ["NDWI الفترة 1", "NDWI الفترة 2", "فرق NDWI"],
  },
  CHANGE_NDBI: {
    label: "CHANGE_NDBI",
    name: "CHANGE_NDBI - كشف تغير العمران",
    topic: "تغير العمران",
    description:
      "يقارن NDBI بين فترتين لرصد انخفاض الاستجابة العمرانية أو الاستقرار أو التوسع العمراني الجديد.",
    bands: ["NDBI الفترة 1", "NDBI الفترة 2", "فرق NDBI"],
  },
  CHANGE_BSI: {
    label: "CHANGE_BSI",
    name: "CHANGE_BSI - كشف تغير التربة المكشوفة",
    topic: "تغير التربة المكشوفة",
    description: "يقارن BSI بين فترتين لرصد انخفاض تعرض التربة أو استقراره أو زيادة انكشافها.",
    bands: ["BSI الفترة 1", "BSI الفترة 2", "فرق BSI"],
  },
  CHANGE_SAVI: {
    label: "CHANGE_SAVI",
    name: "CHANGE_SAVI - كشف تغير الغطاء النباتي",
    topic: "تغير الغطاء النباتي شبه الجاف",
    description:
      "يقارن SAVI بين فترتين لرصد فقدان الغطاء النباتي أو استقراره أو تحسنه في المناطق شبه الجافة.",
    bands: ["SAVI الفترة 1", "SAVI الفترة 2", "فرق SAVI"],
  },
  SUPERVISED_CLASSIFICATION: {
    label: "SUPERVISED",
    name: "SUPERVISED - تصنيف غطاء الأرض الموجه",
    topic: "غطاء الأرض",
    description: "ينشئ تصنيفا آليا موجها لغطاء الأرض اعتمادا على منطقة الدراسة والعينات المختارة.",
    bands: ["النطاقات الطيفية", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"],
  },
  UNSUPERVISED_CLASSIFICATION: {
    label: "UNSUPERVISED",
    name: "UNSUPERVISED - تجميع غطاء الأرض غير الموجه",
    topic: "تجميع غطاء الأرض",
    description:
      "ينشئ تصنيفا آليا لغطاء الأرض في المنطقة المحددة اعتمادا على أوجه التشابه الطيفي وتفسير المؤشرات.",
    bands: ["النطاقات الطيفية", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"],
  },
};

const EN_INDEX_COPY: Record<string, { topic: string; description: string; bands: string[] }> = {
  NDVI: {
    topic: "Vegetation",
    description: "Assesses vegetation cover and vigor using near-infrared and red bands.",
    bands: ["NIR", "Red"],
  },
  NDWI: {
    topic: "Water / Moisture",
    description: "Detects surface water, wet areas, and moisture indicators in vegetation or soil.",
    bands: ["Green", "NIR"],
  },
  NDBI: {
    topic: "Built-up / Urban Areas",
    description:
      "Highlights built-up, artificial, road, and impervious surfaces using SWIR and NIR bands.",
    bands: ["SWIR", "NIR"],
  },
};

function normalizeStatus(status: string | undefined) {
  const value = String(status || "Unknown").toLowerCase();
  if (["completed", "termine", "terminé", "succeeded"].some((item) => value.includes(item)))
    return "Completed";
  if (["running", "en cours", "queued"].some((item) => value.includes(item))) return "Running";
  if (["failed", "error", "erreur"].some((item) => value.includes(item))) return "Failed";
  return status || "Unknown";
}

function compactIndexLabel(index: string, language: string) {
  if (language === "ar" && AR_INDEX_COPY[index]) return AR_INDEX_COPY[index].label;
  if (index === "SUPERVISED_CLASSIFICATION") return "SUPERVISED";
  if (index === "UNSUPERVISED_CLASSIFICATION") return "UNSUPERVISED";
  return index;
}

function displayIndexName(index: string, fallback: string, language: string) {
  if (language === "ar" && AR_INDEX_COPY[index]) return AR_INDEX_COPY[index].name;
  return fallback;
}

function displayIndexTopic(index: string, fallback: string, language: string) {
  if (language === "ar" && AR_INDEX_COPY[index]) return AR_INDEX_COPY[index].topic;
  if (language === "en" && EN_INDEX_COPY[index]) return EN_INDEX_COPY[index].topic;
  return fallback;
}

function displayIndexDescription(index: string, fallback: string, language: string) {
  if (language === "ar" && AR_INDEX_COPY[index]) return AR_INDEX_COPY[index].description;
  if (language === "en" && EN_INDEX_COPY[index]) return EN_INDEX_COPY[index].description;
  return fallback;
}

function displayIndexBands(index: string, fallback: string[] | undefined, language: string) {
  if (language === "ar" && AR_INDEX_COPY[index]) return AR_INDEX_COPY[index].bands;
  if (language === "en" && EN_INDEX_COPY[index]) return EN_INDEX_COPY[index].bands;
  return fallback ?? [];
}

function displaySourceText(value: string, language: string) {
  if (language !== "ar") return value;
  return value
    .replaceAll("Sentinel-2 Surface Reflectance", "انعكاسية سطح Sentinel-2")
    .replaceAll("Satellite raster", "راستر فضائي")
    .replaceAll("Mosaic", "موزاييك")
    .replaceAll("Saudi Arabia", "السعودية")
    .replaceAll("Riyadh", "الرياض")
    .replaceAll("Jeddah", "جدة")
    .replaceAll("Medina", "المدينة المنورة");
}

function displayAreaText(value: string, language: string) {
  if (language !== "ar") return value;
  return value.replaceAll(" ha", " هكتار").replaceAll("kmÂ²", "كم²").replaceAll("km²", "كم²");
}

function normalizeBackendAnalysis(item: any, fallbackIndex: number): DashboardAnalysis {
  return {
    id: String(item?.id ?? `analysis-${fallbackIndex}`),
    name: String(item?.name ?? `${item?.index ?? "Raster"} analysis`),
    date: String(item?.date ?? item?.created_at ?? "-").slice(0, 10),
    image: String(item?.image ?? item?.source ?? "Satellite raster"),
    index: String(item?.index ?? "NDVI"),
    area: String(item?.area ?? (item?.area_km2 ? `${Number(item.area_km2).toFixed(0)} km²` : "-")),
    status: normalizeStatus(item?.status),
  };
}

function mockToDashboardAnalysis(item: Analysis): DashboardAnalysis {
  return {
    id: item.id,
    name: item.name,
    date: item.date,
    image: item.image,
    index: item.index,
    area: item.area,
    status: item.status,
  };
}

function statusClasses(status: string) {
  if (status === "Completed") return "bg-success/15 text-success";
  if (status === "Running") return "bg-warning/20 text-warning-foreground";
  if (status === "Failed") return "bg-destructive/15 text-destructive";
  return "bg-muted text-muted-foreground";
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string | number;
  hint: string;
  icon: typeof Satellite;
  tone: string;
}) {
  return (
    <div className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
        </div>
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${tone}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b p-4">
      <h2 className="font-semibold">{title}</h2>
      {action}
    </div>
  );
}

function DashboardPage() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const { t, language } = useI18n();

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE_URL}/api/dashboard`)
      .then((response) => {
        if (!response.ok) throw new Error(`Dashboard API ${response.status}`);
        return response.json() as Promise<DashboardResponse>;
      })
      .then((payload) => {
        if (active) setDashboard(payload);
      })
      .catch(() => {
        if (active) setDashboard(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const stats = {
    images: dashboard?.stats?.images ?? dashboardStats.images,
    analyses: dashboard?.stats?.analyses ?? dashboardStats.analyses,
    indices: dashboard?.stats?.indices ?? dashboardStats.indices,
    exports: dashboard?.stats?.exports ?? dashboardStats.exports,
  };

  const recentAnalyses = useMemo<DashboardAnalysis[]>(() => {
    if (dashboard?.recent_analyses?.length) {
      return dashboard.recent_analyses.slice(0, 6).map(normalizeBackendAnalysis);
    }
    return mockAnalyses.slice(0, 6).map(mockToDashboardAnalysis);
  }, [dashboard]);

  const availableIndices = (
    dashboard?.indices?.length ? dashboard.indices : indices
  ) as SpectralIndex[];
  const completedCount = recentAnalyses.filter((item) => item.status === "Completed").length;
  const runningCount = recentAnalyses.filter((item) => item.status === "Running").length;
  const failedCount = recentAnalyses.filter((item) => item.status === "Failed").length;
  const completionRate = recentAnalyses.length
    ? Math.round((completedCount / recentAnalyses.length) * 100)
    : 0;
  const sensorSummary = images
    .map((item) => item.sensor)
    .filter((sensor, index, all) => all.indexOf(sensor) === index)
    .join(", ");
  const displaySensorSummary = displaySourceText(sensorSummary, language);
  const indexUsage = availableIndices.map((idx) => ({
    ...idx,
    count: recentAnalyses.filter((analysis) => analysis.index === idx.id).length,
  }));
  const displayStatus = (status: string) => {
    if (status === "Completed") return t("status.completed");
    if (status === "Running") return t("status.running");
    if (status === "Failed") return t("status.failed");
    return status || t("status.unknown");
  };

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 p-6">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label={t("dashboard.availableImages")}
          value={stats.images}
          hint={displaySensorSummary || t("dashboard.catalogSources")}
          icon={Satellite}
          tone="bg-primary/10 text-primary"
        />
        <StatCard
          label={t("dashboard.rasterAnalyses")}
          value={stats.analyses}
          hint={t("dashboard.completedLatest", { rate: completionRate })}
          icon={Activity}
          tone="bg-success/15 text-success"
        />
        <StatCard
          label={t("dashboard.analysisMethods")}
          value={stats.indices}
          hint={t("dashboard.indicesClassifications")}
          icon={LayersIcon}
          tone="bg-accent/40 text-accent-foreground"
        />
        <StatCard
          label={t("dashboard.generatedExports")}
          value={stats.exports}
          hint="GeoTIFF, PNG, PDF, CSV"
          icon={Download}
          tone="bg-warning/20 text-warning-foreground"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="rounded-2xl border bg-card shadow-sm">
          <SectionHeader title={t("dashboard.processingOverview")} />
          <div className="space-y-4 p-4">
            <div>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{t("dashboard.latestCompletionRate")}</span>
                <b>{completionRate}%</b>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-success transition-all"
                  style={{ width: `${completionRate}%` }}
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="rounded-xl border bg-success/10 p-3">
                <CheckCircle2 className="mx-auto mb-1 h-4 w-4 text-success" />
                <b className="block text-base">{completedCount}</b>
                <span className="text-muted-foreground">{t("status.completed")}</span>
              </div>
              <div className="rounded-xl border bg-warning/10 p-3">
                <Activity className="mx-auto mb-1 h-4 w-4 text-warning-foreground" />
                <b className="block text-base">{runningCount}</b>
                <span className="text-muted-foreground">{t("status.running")}</span>
              </div>
              <div className="rounded-xl border bg-destructive/10 p-3">
                <BarChart3 className="mx-auto mb-1 h-4 w-4 text-destructive" />
                <b className="block text-base">{failedCount}</b>
                <span className="text-muted-foreground">{t("status.failed")}</span>
              </div>
            </div>
            <div className="rounded-xl border bg-muted/30 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("dashboard.operationalFocus")}
              </p>
              <p className="mt-2 text-sm">{t("dashboard.operationalFocusText")}</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border bg-card shadow-sm xl:col-span-2">
          <SectionHeader
            title={t("dashboard.recentRasterAnalyses")}
            action={
              <Link
                to="/history"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                {t("dashboard.viewHistory")} <ArrowRight className="h-3 w-3" />
              </Link>
            }
          />
          <div className="divide-y">
            {recentAnalyses.map((analysis) => {
              const Icon = ICONS[analysis.index] ?? BarChart3;
              return (
                <div
                  key={analysis.id}
                  className="flex items-center gap-3 p-3 transition-colors hover:bg-muted/40"
                >
                  <div
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${INDEX_TONES[analysis.index] ?? "bg-primary/10 text-primary"}`}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-semibold">
                        {displayIndexName(analysis.index, analysis.name, language)}
                      </p>
                      <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium">
                        {compactIndexLabel(analysis.index, language)}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {displaySourceText(analysis.image, language)} ·{" "}
                      {displayAreaText(analysis.area, language)}
                    </p>
                  </div>
                  <span className="hidden text-xs text-muted-foreground sm:inline">
                    {analysis.date}
                  </span>
                  <span
                    className={`rounded-md px-2 py-0.5 text-xs ${statusClasses(analysis.status)}`}
                  >
                    {displayStatus(analysis.status)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <div className="rounded-2xl border bg-card shadow-sm">
          <SectionHeader title={t("dashboard.analysisPortfolio")} />
          <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2">
            {indexUsage.map((idx) => {
              const Icon = ICONS[idx.id] ?? BarChart3;
              return (
                <Link
                  key={idx.id}
                  to="/map"
                  className="group rounded-xl border p-3 transition-colors hover:bg-muted/40"
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${INDEX_TONES[idx.id] ?? "bg-success/15 text-success"}`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold">
                          {compactIndexLabel(idx.id, language)}{" "}
                          <span className="font-normal text-muted-foreground">
                            · {displayIndexTopic(idx.id, idx.topic, language)}
                          </span>
                        </p>
                        <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                          {t("dashboard.recentCount", { count: idx.count })}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                        {displayIndexDescription(idx.id, idx.description, language)}
                      </p>
                      {displayIndexBands(idx.id, idx.bands, language).length > 0 && (
                        <p className="mt-2 text-[11px] text-muted-foreground">
                          {t("dashboard.bands")}:{" "}
                          {displayIndexBands(idx.id, idx.bands, language).join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
