import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  Filter,
  History,
  Loader2,
  Play,
  Search,
  Trash2,
} from "lucide-react";
import {
  deleteAnalysis,
  downloadExport,
  getAnalysisHistory,
  getRunResult,
} from "@/lib/georaster-api";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "History - GeoRaster Analytics" },
      { name: "description", content: "History of completed raster analyses." },
    ],
  }),
  component: HistoryPage,
});

type HistoryStatus = "Completed" | "Running" | "Failed" | "Unknown";

type HistoryItem = {
  id: string;
  run_id: string;
  analysis_id: string;
  name: string;
  study_area_name: string;
  period: string;
  sensor: string;
  status: HistoryStatus;
  executed_at: string;
  date: string;
  surface_ha?: number | string | null;
  area: string;
  index: string;
  export_summary: string;
  exports: Array<{ id?: string; kind?: string; filename?: string }>;
  coverage_percent?: number | null;
};

const HISTORY_RESTORE_STORAGE_KEY = "georaster:history-restore";

function compactIndexLabel(index: string, language: string) {
  if (index === "SUPERVISED_CLASSIFICATION") return language === "ar" ? "موجَّه" : "SUPERVISED";
  if (index === "UNSUPERVISED_CLASSIFICATION")
    return language === "ar" ? "غير موجَّه" : "UNSUPERVISED";
  if (index === "OSI_SAR") return "OSI-SAR";
  return index.replace("CHANGE_", "D ");
}

function normalizeStatus(value: unknown): HistoryStatus {
  const status = String(value || "Unknown").toLowerCase();
  if (["completed", "succeeded", "success", "termine"].some((item) => status.includes(item)))
    return "Completed";
  if (["running", "queued", "en cours"].some((item) => status.includes(item))) return "Running";
  if (["failed", "error", "erreur"].some((item) => status.includes(item))) return "Failed";
  return "Unknown";
}

function statusClasses(status: HistoryStatus) {
  if (status === "Completed") return "bg-success/15 text-success";
  if (status === "Running") return "bg-warning/20 text-warning-foreground";
  if (status === "Failed") return "bg-destructive/15 text-destructive";
  return "bg-muted text-muted-foreground";
}

function statusIcon(status: HistoryStatus) {
  if (status === "Completed") return CheckCircle2;
  if (status === "Running") return Clock3;
  if (status === "Failed") return AlertTriangle;
  return History;
}

function formatDateTime(value: string, language = "en") {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString(language === "ar" ? "ar-SA-u-nu-latn" : "en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSurface(item: any, language = "en") {
  const value = item?.surface_ha ?? item?.stats?.surface_ha;
  const numeric = Number(value);
  if (Number.isFinite(numeric))
    return `${numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${language === "ar" ? "هكتار" : "ha"}`;
  return String(item?.area ?? "-");
}

function displayHistoryText(value: string, t: ReturnType<typeof useI18n>["t"], language: string) {
  if (value === "Selected study area") return t("history.selectedStudyArea");
  if (value === "No export yet") return t("history.noExport");
  if (language === "ar" && value.endsWith(" ha")) return value.replace(" ha", " هكتار");
  return value;
}

function displayAnalysisName(value: string, language: string) {
  if (language !== "ar") return value;
  return value
    .replace(/\bChange Detection\b/g, "كشف التغير")
    .replace(/\bAnalysis\b/g, "تحليل")
    .replace(/^Raster\b/g, "راستر");
}

function fromBackendHistory(item: any, language = "en"): HistoryItem {
  return {
    id: String(item?.id ?? item?.run_id ?? crypto.randomUUID()),
    run_id: String(item?.run_id ?? item?.id ?? ""),
    analysis_id: String(item?.analysis_id ?? ""),
    name: String(item?.name ?? `${item?.index ?? "Raster"} Analysis`),
    study_area_name: String(item?.study_area_name ?? "Selected study area"),
    period: String(item?.period ?? "-"),
    sensor: String(item?.sensor ?? "-"),
    status: normalizeStatus(item?.status),
    executed_at: String(item?.executed_at ?? item?.date ?? ""),
    date: String(item?.date ?? item?.executed_at ?? "-").slice(0, 10),
    surface_ha: item?.surface_ha,
    area: formatSurface(item, language),
    index: String(item?.index ?? "NDVI"),
    export_summary: String(item?.export_summary ?? "No export yet"),
    exports: Array.isArray(item?.exports) ? item.exports : [],
    coverage_percent: item?.coverage_percent,
  };
}

function HistoryPage() {
  const navigate = useNavigate();
  const { t, isRtl, language } = useI18n();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [backendAvailable, setBackendAvailable] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | HistoryStatus>("all");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  const loadHistory = async () => {
    try {
      setIsLoading(true);
      const response = await getAnalysisHistory();
      setItems((response.items ?? []).map((item: any) => fromBackendHistory(item, language)));
      setBackendAvailable(true);
    } catch (error) {
      console.error(error);
      setItems([]);
      setBackendAvailable(false);
      toast.error(t("history.unableLoadBackend"), { description: t("history.backendRealOnly") });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [language]);

  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesSearch =
        !needle ||
        [
          item.name,
          item.study_area_name,
          item.period,
          item.sensor,
          item.index,
          item.status,
          item.export_summary,
        ]
          .join(" ")
          .toLowerCase()
          .includes(needle);
      const matchesStatus = statusFilter === "all" || item.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [items, query, statusFilter]);

  const completedCount = items.filter((item) => item.status === "Completed").length;
  const runningCount = items.filter((item) => item.status === "Running").length;
  const failedCount = items.filter((item) => item.status === "Failed").length;
  const displayStatus = (status: HistoryStatus) => {
    if (status === "Completed") return t("status.completed");
    if (status === "Running") return t("status.running");
    if (status === "Failed") return t("status.failed");
    return t("status.unknown");
  };

  const viewAnalysis = async (item: HistoryItem) => {
    if (!item.run_id) {
      toast.error(t("history.runUnavailable"), { description: t("history.noLinkedRun") });
      return;
    }
    try {
      setRestoringId(item.id);
      const response = await getRunResult(item.run_id);
      sessionStorage.setItem(
        HISTORY_RESTORE_STORAGE_KEY,
        JSON.stringify({
          run_id: item.run_id,
          item: response.item,
          stored_at: Date.now(),
        }),
      );
    } catch (error) {
      console.warn("History preload failed, falling back to map restore.", error);
    } finally {
      setRestoringId(null);
      void navigate({ to: "/map", search: { run_id: item.run_id } });
    }
  };

  const downloadFirstExport = (item: HistoryItem) => {
    const exportId = item.exports?.find((entry) => entry.id)?.id;
    if (!exportId) {
      toast.info(t("history.noExportToast"), {
        description: t("history.openExportFirst"),
      });
      return;
    }
    downloadExport(exportId);
  };

  const removeAnalysis = async (item: HistoryItem) => {
    if (!item.analysis_id) {
      toast.error(t("history.analysisIdUnavailable"), {
        description: t("history.cannotDeleteSafely"),
      });
      return;
    }
    try {
      setDeletingId(item.id);
      await deleteAnalysis(item.analysis_id);
      setItems((current) => current.filter((entry) => entry.analysis_id !== item.analysis_id));
      toast.success(t("history.analysisDeleted"), { description: item.name });
    } catch (error) {
      toast.error(t("history.unableDelete"), {
        description: isRtl
          ? t("history.backendError")
          : error instanceof Error
            ? error.message
            : t("history.backendError"),
      });
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div dir={isRtl ? "rtl" : "ltr"} className="p-6 space-y-5 max-w-[1600px] mx-auto">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">{t("history.title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("history.subtitle")}</p>
        </div>
        <Link
          to="/map"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Play className="h-4 w-4" /> {t("history.runNew")}
        </Link>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCard
          label={t("history.totalRecords")}
          value={items.length}
          icon={History}
          tone="bg-primary/10 text-primary"
        />
        <SummaryCard
          label={t("status.completed")}
          value={completedCount}
          icon={CheckCircle2}
          tone="bg-success/15 text-success"
        />
        <SummaryCard
          label={t("status.running")}
          value={runningCount}
          icon={Clock3}
          tone="bg-warning/20 text-warning-foreground"
        />
        <SummaryCard
          label={t("status.failed")}
          value={failedCount}
          icon={AlertTriangle}
          tone="bg-destructive/15 text-destructive"
        />
      </div>

      <div className="rounded-xl border bg-card overflow-hidden shadow-sm">
        <div className="flex flex-col gap-3 border-b p-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="font-semibold">{t("history.records")}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t("history.visibleItems", { count: filteredItems.length })}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("history.searchPlaceholder")}
                className="w-72 bg-transparent outline-none placeholder:text-muted-foreground"
              />
            </div>
            <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as any)}
                className="bg-transparent outline-none"
              >
                <option value="all">{t("history.allStatus")}</option>
                <option value="Completed">{t("status.completed")}</option>
                <option value="Running">{t("status.running")}</option>
                <option value="Failed">{t("status.failed")}</option>
                <option value="Unknown">{t("status.unknown")}</option>
              </select>
            </label>
          </div>
        </div>

        <div className="overflow-auto">
          <table className="w-full min-w-[1280px] text-sm">
            <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-3">{t("history.analysis")}</th>
                <th className="text-left px-4 py-3">{t("history.studyArea")}</th>
                <th className="text-left px-4 py-3">{t("history.period")}</th>
                <th className="text-left px-4 py-3">{t("history.sensor")}</th>
                <th className="text-left px-4 py-3">{t("history.status")}</th>
                <th className="text-left px-4 py-3">{t("history.executionDate")}</th>
                <th className="text-left px-4 py-3">{t("history.surface")}</th>
                <th className="text-left px-4 py-3">{t("history.exports")}</th>
                <th className="text-right px-4 py-3">{t("history.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">
                    <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />
                    {t("history.loading")}
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">
                    {t("history.empty")}
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => {
                  const StatusIcon = statusIcon(item.status);
                  return (
                    <tr key={item.id} className="border-t hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <p className="font-medium">{displayAnalysisName(item.name, language)}</p>
                        <span className="mt-1 inline-flex text-[11px] px-2 py-0.5 rounded bg-primary/10 text-primary font-semibold">
                          {compactIndexLabel(item.index, language)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-[220px] truncate">
                        {displayHistoryText(item.study_area_name, t, language)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-[240px]">
                        {item.period}
                      </td>
                      <td className="px-4 py-3">{item.sensor}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded ${statusClasses(item.status)}`}
                        >
                          <StatusIcon className="h-3 w-3" /> {displayStatus(item.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDateTime(item.executed_at, language)}
                      </td>
                      <td className="px-4 py-3 tabular-nums">
                        {displayHistoryText(item.area, t, language)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-[220px] truncate">
                        {displayHistoryText(item.export_summary, t, language)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex gap-1">
                          <button
                            onClick={() => void viewAnalysis(item)}
                            disabled={restoringId === item.id}
                            className="p-1.5 rounded hover:bg-muted disabled:opacity-50"
                            title={t("history.viewOnMap")}
                          >
                            {restoringId === item.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            onClick={() => downloadFirstExport(item)}
                            className="p-1.5 rounded hover:bg-muted"
                            title={t("history.downloadExport")}
                          >
                            <Download className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => removeAnalysis(item)}
                            disabled={deletingId === item.id}
                            className="p-1.5 rounded hover:bg-destructive/10 text-destructive disabled:opacity-50"
                            title={t("history.deleteAnalysis")}
                          >
                            {deletingId === item.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  icon: typeof History;
  tone: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
        </div>
        <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${tone}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}
