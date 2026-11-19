import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Map as MapIcon, Satellite, Search } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/catalog")({
  head: () => ({
    meta: [
      { title: "Image Catalog - GeoRaster Analytics" },
      {
        name: "description",
        content: "Live satellite catalog search is available from Map & Analysis.",
      },
    ],
  }),
  component: CatalogPage,
});

function CatalogPage() {
  const { t, isRtl } = useI18n();

  return (
    <div dir={isRtl ? "rtl" : "ltr"} className="mx-auto max-w-3xl space-y-5 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("catalog.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("catalog.subtitle")}</p>
      </div>

      <div className="rounded-lg border bg-card p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-primary/10 p-2 text-primary">
            <Satellite className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-sm font-semibold">{t("catalog.liveSearchTitle")}</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {t("catalog.liveSearchBody")}
            </p>
            <ul className="space-y-1 text-xs text-muted-foreground">
              <li className="flex items-start gap-2">
                <MapIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{t("catalog.liveSearchStepAoi")}</span>
              </li>
              <li className="flex items-start gap-2">
                <Search className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{t("catalog.liveSearchStepSearch")}</span>
              </li>
            </ul>
            <Link
              to="/map"
              search={{}}
              className="mt-3 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              {t("catalog.openMapSearch")}
              <ArrowRight className={`h-4 w-4 ${isRtl ? "rotate-180" : ""}`} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
