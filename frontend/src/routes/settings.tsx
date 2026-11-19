import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  getPlatformSettings,
  notifyPlatformSettingsUpdated,
  resetPlatformLogo,
  resolveApiAssetUrl,
  uploadPlatformLogo,
  updatePlatformSettings,
  type PlatformSettings,
} from "@/lib/georaster-api";
import {
  Image as ImageIcon,
  RotateCcw,
  Save,
  Upload,
  User,
  Map as MapIcon,
  Download,
  Ruler,
  Server,
  Globe2,
} from "lucide-react";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings - GeoRaster Analytics" },
      { name: "description", content: "WebGIS platform settings." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const { t, isRtl } = useI18n();
  const [name, setName] = useState("GIS analyst");
  const [email, setEmail] = useState("user@georaster.app");
  const [defaultBasemap, setDefaultBasemap] = useState<PlatformSettings["default_basemap"]>("osm");
  const [exportFmt, setExportFmt] = useState<PlatformSettings["export_format"]>("geotiff");
  const [unit, setUnit] = useState<PlatformSettings["measurement_unit"]>("ha");
  const [backend, setBackend] = useState("fastapi");
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:8010");
  const [apiKey, setApiKey] = useState("");
  const [projectionMode, setProjectionMode] =
    useState<PlatformSettings["projection_mode"]>("automatic");
  const [manualCrs, setManualCrs] = useState<PlatformSettings["manual_crs"]>(null);
  const [simulation3dEnabled, setSimulation3dEnabled] = useState(false);
  const [effectiveCrs, setEffectiveCrs] = useState<any>(null);
  const [analysisChoices, setAnalysisChoices] = useState<
    Array<{ code: string; name: string; unit: string | null; utm_zone: number | null }>
  >([]);
  const [currentLogoUrl, setCurrentLogoUrl] = useState<string | null>(null);
  const [pendingLogoFile, setPendingLogoFile] = useState<File | null>(null);
  const [pendingLogoPreview, setPendingLogoPreview] = useState<string | null>(null);
  const [isLogoSaving, setIsLogoSaving] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  useEffect(() => {
    getPlatformSettings()
      .then((settings) => {
        setCurrentLogoUrl(settings.logo_url);
        setName(settings.user_profile?.name ?? "GIS analyst");
        setEmail(settings.user_profile?.email ?? "user@georaster.app");
        setDefaultBasemap(settings.default_basemap ?? "osm");
        setExportFmt(settings.export_format ?? "geotiff");
        setUnit(settings.measurement_unit ?? "ha");
        setBackend(settings.backend_connection?.raster_server ?? "fastapi");
        setEndpoint(settings.backend_connection?.endpoint ?? "http://127.0.0.1:8010");
        setApiKey(settings.backend_connection?.api_key ?? "");
        setProjectionMode(settings.projection_mode ?? "automatic");
        setManualCrs(settings.manual_crs ?? null);
        setSimulation3dEnabled(settings.simulation_3d_enabled ?? false);
        setEffectiveCrs(settings.coordinate_reference?.effective ?? null);
        setAnalysisChoices(settings.coordinate_reference?.analysis_choices ?? []);
        window.localStorage.setItem(
          "georaster.userName",
          settings.user_profile?.name ?? "GIS analyst",
        );
      })
      .catch(() => setCurrentLogoUrl(null));
  }, []);

  useEffect(() => {
    return () => {
      if (pendingLogoPreview) URL.revokeObjectURL(pendingLogoPreview);
    };
  }, [pendingLogoPreview]);

  const selectLogo = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error(t("settings.unsupportedFormat"), { description: t("settings.logoMustBeImage") });
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      toast.error(t("settings.fileTooLarge"), { description: t("settings.maxLogoSize") });
      return;
    }
    if (pendingLogoPreview) URL.revokeObjectURL(pendingLogoPreview);
    setPendingLogoFile(file);
    setPendingLogoPreview(URL.createObjectURL(file));
    await saveLogo(file);
  };

  const saveLogo = async (logoFile = pendingLogoFile) => {
    if (!logoFile) {
      toast.info(t("settings.importLogoFirst"));
      return;
    }
    try {
      setIsLogoSaving(true);
      const response = await uploadPlatformLogo(logoFile);
      setCurrentLogoUrl(response.logo_url);
      setPendingLogoFile(null);
      if (pendingLogoPreview) URL.revokeObjectURL(pendingLogoPreview);
      setPendingLogoPreview(null);
      notifyPlatformSettingsUpdated();
      toast.success(
        isRtl ? t("settings.logoUpdated") : response.message || t("settings.logoUpdated"),
      );
    } catch (error) {
      toast.error(t("settings.logoSaveError"), {
        description: isRtl
          ? t("settings.backendError")
          : error instanceof Error
            ? error.message
            : t("settings.backendError"),
      });
    } finally {
      setIsLogoSaving(false);
    }
  };

  const resetLogo = async () => {
    try {
      setIsLogoSaving(true);
      const response = await resetPlatformLogo();
      setCurrentLogoUrl(null);
      setPendingLogoFile(null);
      if (pendingLogoPreview) URL.revokeObjectURL(pendingLogoPreview);
      setPendingLogoPreview(null);
      notifyPlatformSettingsUpdated();
      toast.success(isRtl ? t("settings.logoReset") : response.message || t("settings.logoReset"));
    } catch (error) {
      toast.error(t("settings.logoResetError"), {
        description: isRtl
          ? t("settings.backendError")
          : error instanceof Error
            ? error.message
            : t("settings.backendError"),
      });
    } finally {
      setIsLogoSaving(false);
    }
  };

  const logoPreviewUrl = pendingLogoPreview ?? resolveApiAssetUrl(currentLogoUrl);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSavingSettings(true);
      const settings = await updatePlatformSettings({
        platform_name: "GeoRaster",
        logo_url: currentLogoUrl,
        user_profile: {
          name,
          email,
        },
        default_basemap: defaultBasemap,
        export_format: exportFmt,
        measurement_unit: unit,
        backend_connection: {
          raster_server: backend,
          endpoint,
          api_key: apiKey,
        },
        projection_mode: projectionMode,
        web_map_crs: "EPSG:3857",
        analysis_crs: "AUTO_KSA_GRF17",
        manual_crs: projectionMode === "manual" ? manualCrs : null,
        simulation_3d_enabled: simulation3dEnabled,
        simulation_3d_crs: "EPSG:9332",
      });
      setEffectiveCrs(settings.coordinate_reference?.effective ?? null);
      setAnalysisChoices(settings.coordinate_reference?.analysis_choices ?? []);
      window.localStorage.setItem("georaster.userName", settings.user_profile?.name ?? name);
      notifyPlatformSettingsUpdated();
      toast.success(t("settings.saved"));
    } catch (error) {
      toast.error(t("settings.backendError"), {
        description: isRtl
          ? t("settings.backendError")
          : error instanceof Error
            ? error.message
            : t("settings.backendError"),
      });
    } finally {
      setIsSavingSettings(false);
    }
  };

  return (
    <form
      dir={isRtl ? "rtl" : "ltr"}
      onSubmit={save}
      className="p-6 space-y-5 max-w-[1100px] mx-auto"
    >
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("settings.title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("settings.subtitle")}</p>
        </div>
        <button
          type="submit"
          disabled={isSavingSettings}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
        >
          <Save className="h-4 w-4" /> {t("settings.save")}
        </button>
      </div>

      <Section icon={User} title={t("settings.userProfile")}>
        <Field label={t("settings.name")}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full text-sm rounded-md border bg-background px-3 py-2"
          />
        </Field>
        <Field label={t("settings.email")}>
          <input
            value={email}
            type="email"
            onChange={(e) => setEmail(e.target.value)}
            className="w-full text-sm rounded-md border bg-background px-3 py-2"
          />
        </Field>
      </Section>

      <Section icon={ImageIcon} title={t("settings.logo")}>
        <div className="md:col-span-2 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 min-w-16 max-w-40 items-center justify-center overflow-hidden rounded-xl border bg-muted/40 px-2">
              {logoPreviewUrl ? (
                <img
                  src={logoPreviewUrl}
                  alt="Logo GeoRaster"
                  className="max-h-full w-auto max-w-full object-contain"
                />
              ) : (
                <ImageIcon className="h-7 w-7 text-muted-foreground" />
              )}
            </div>
            <div>
              <p className="text-sm font-medium">{t("settings.currentLogoPreview")}</p>
              <p className="text-xs text-muted-foreground">{t("settings.logoHelp")}</p>
              {pendingLogoFile && (
                <p className="mt-1 text-xs text-primary">
                  {t("settings.newLogoSelected", { name: pendingLogoFile.name })}
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted/50">
              <Upload className="h-4 w-4" /> {t("settings.importLogo")}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => selectLogo(e.target.files?.[0])}
              />
            </label>
            <button
              type="button"
              onClick={resetLogo}
              disabled={isLogoSaving}
              className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted/50 disabled:opacity-50"
            >
              <RotateCcw className="h-4 w-4" /> {t("settings.resetLogo")}
            </button>
          </div>
        </div>
      </Section>

      <Section icon={MapIcon} title={t("settings.mapDisplay")}>
        <Field label={t("settings.defaultBasemap")}>
          <select
            value={defaultBasemap}
            onChange={(e) =>
              setDefaultBasemap(e.target.value as PlatformSettings["default_basemap"])
            }
            className="w-full text-sm rounded-md border bg-background px-3 py-2"
          >
            <option value="osm">OpenStreetMap</option>
            <option value="googleSatellite">{t("settings.basemapGoogleSatellite")}</option>
            <option value="satellite">{t("settings.basemapSatellite")}</option>
            <option value="terrain">{t("settings.basemapTerrain")}</option>
            <option value="light">{t("settings.basemapLight")}</option>
          </select>
        </Field>
      </Section>

      <Section icon={Globe2} title={t("settings.coordinateReferenceSystem")}>
        <Field label={t("settings.webMapCrs")}>
          <input
            value="EPSG:3857 - WGS 84 / Web Mercator"
            disabled
            className="w-full text-sm rounded-md border bg-muted/50 px-3 py-2 text-muted-foreground"
          />
        </Field>
        <Field label={t("settings.projectionMode")}>
          <select
            value={projectionMode}
            onChange={(e) =>
              setProjectionMode(e.target.value as PlatformSettings["projection_mode"])
            }
            className="w-full text-sm rounded-md border bg-background px-3 py-2"
          >
            <option value="automatic">{t("settings.automaticRecommended")}</option>
            <option value="manual">{t("settings.manualSelection")}</option>
          </select>
        </Field>
        <Field label={t("settings.analysisExportCrs")}>
          <select
            value={manualCrs ?? "EPSG:9358"}
            onChange={(e) => setManualCrs(e.target.value as PlatformSettings["manual_crs"])}
            disabled={projectionMode !== "manual"}
            className="w-full text-sm rounded-md border bg-background px-3 py-2 disabled:bg-muted/40 disabled:text-muted-foreground"
          >
            {analysisChoices.map((choice) => (
              <option key={choice.code} value={choice.code}>
                {choice.code} - {choice.name}
              </option>
            ))}
          </select>
        </Field>
        <div className="md:col-span-2 rounded-lg border bg-muted/20 p-4 text-sm">
          <div className="font-semibold text-sm">{t("settings.effectiveCrs")}</div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <div>
              <span className="text-muted-foreground">{t("settings.effectiveCode")}: </span>
              {effectiveCrs?.analysis_crs ?? t("settings.waitingForAoi")}
            </div>
            <div>
              <span className="text-muted-foreground">{t("settings.effectiveName")}: </span>
              {effectiveCrs?.analysis_crs_name ?? t("settings.waitingForAoi")}
            </div>
            <div>
              <span className="text-muted-foreground">{t("settings.effectiveZone")}: </span>
              {effectiveCrs?.utm_zone ?? "-"}
            </div>
            <div>
              <span className="text-muted-foreground">{t("settings.effectiveUnit")}: </span>
              {effectiveCrs?.unit ?? "-"}
            </div>
            <div>
              <span className="text-muted-foreground">{t("settings.effectiveSelection")}: </span>
              {effectiveCrs?.selection_method ?? "-"}
            </div>
            <div>
              <span className="text-muted-foreground">{t("settings.effectiveStatus")}: </span>
              {effectiveCrs?.status ?? "-"}
            </div>
          </div>
          {effectiveCrs?.warning ? (
            <p className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {effectiveCrs.warning}
            </p>
          ) : null}
          {projectionMode === "automatic" ? (
            <p className="mt-3 text-xs text-muted-foreground">
              {t("settings.projectionAutomaticNote")}
            </p>
          ) : null}
        </div>
      </Section>

      <Section icon={Globe2} title={t("settings.simulation3dTitle")}>
        <div className="md:col-span-2 rounded-lg border border-amber-300 bg-amber-50/60 p-4 text-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold">{t("settings.simulation3dCrs")}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("settings.simulation3dDescription")}
              </p>
            </div>
            <span className="rounded-full border border-amber-400 px-2 py-1 text-[10px] font-semibold uppercase text-amber-800">
              {t("settings.configOnly")}
            </span>
          </div>
          <label className="mt-4 flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={simulation3dEnabled}
              onChange={(e) => setSimulation3dEnabled(e.target.checked)}
            />
            {t("settings.enable3dSimulation")}
          </label>
          <p className="mt-3 text-[11px] text-amber-900">{t("settings.simulation3dHeightNote")}</p>
        </div>
      </Section>

      <Section icon={Download} title={t("settings.exportDefaults")}>
        <Field label={t("settings.format")}>
          <select
            value={exportFmt}
            onChange={(e) => setExportFmt(e.target.value as PlatformSettings["export_format"])}
            className="w-full text-sm rounded-md border bg-background px-3 py-2"
          >
            <option value="geotiff">GeoTIFF</option>
            <option value="png">PNG</option>
            <option value="pdf">{t("settings.exportMapPdf")}</option>
            <option value="csv">{t("settings.exportStatisticsCsv")}</option>
          </select>
        </Field>
      </Section>

      <Section icon={Ruler} title={t("settings.measurementUnits")}>
        <div className="flex gap-2 md:col-span-2">
          {(["ha", "km2", "m2"] as const).map((u) => (
            <button
              key={u}
              type="button"
              onClick={() => setUnit(u)}
              className={`flex-1 py-2 rounded-md border text-sm ${unit === u ? "border-primary bg-primary/5 text-primary font-medium" : "hover:bg-muted/40"}`}
            >
              {u}
            </button>
          ))}
        </div>
      </Section>

      <Section icon={Server} title={t("settings.backendConnection")}>
        <Field label={t("settings.rasterServer")}>
          <select
            value={backend}
            onChange={(e) => setBackend(e.target.value)}
            className="w-full text-sm rounded-md border bg-background px-3 py-2"
          >
            <option value="fastapi">FastAPI API (custom)</option>
            <option value="titiler">TiTiler</option>
            <option value="geoserver">GeoServer</option>
          </select>
        </Field>
        <Field label={t("settings.endpoint")}>
          <input
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            className="w-full text-sm rounded-md border bg-background px-3 py-2 font-mono"
          />
        </Field>
        <Field label={t("settings.apiKey")}>
          <input
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="............"
            type="password"
            className="w-full text-sm rounded-md border bg-background px-3 py-2 font-mono"
          />
        </Field>
        <p className="text-[11px] text-muted-foreground md:col-span-2">
          {t("settings.backendNote")}
        </p>
      </Section>
    </form>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof User;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border bg-card">
      <div className="flex items-center gap-2 p-4 border-b">
        <Icon className="h-4 w-4 text-primary" />
        <h2 className="font-semibold text-sm">{title}</h2>
      </div>
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
