import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";

import appCss from "../styles.css?url";
import { API_BASE_URL } from "@/lib/georaster-api";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { PlatformBrand } from "@/components/PlatformBrand";
import { Bell, Search } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { I18nProvider, useI18n } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

function NotFoundContent() {
  const { t, isRtl } = useI18n();
  return (
    <div
      dir={isRtl ? "rtl" : "ltr"}
      className="flex min-h-screen items-center justify-center bg-background px-4"
    >
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">{t("error.notFoundTitle")}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{t("error.notFoundDescription")}</p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            {t("error.goHome")}
          </Link>
        </div>
      </div>
    </div>
  );
}

function NotFoundComponent() {
  return (
    <I18nProvider>
      <NotFoundContent />
    </I18nProvider>
  );
}

function ErrorContent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  const { t, isRtl } = useI18n();

  return (
    <div
      dir={isRtl ? "rtl" : "ltr"}
      className="flex min-h-screen items-center justify-center bg-background px-4"
    >
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          {t("error.pageLoadTitle")}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("error.pageLoadDescription")}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            {t("error.tryAgain")}
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            {t("error.goHome")}
          </a>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent(props: { error: Error; reset: () => void }) {
  return (
    <I18nProvider>
      <ErrorContent {...props} />
    </I18nProvider>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "GeoRaster Analytics - WebGIS multispectral" },
      {
        name: "description",
        content:
          "WebGIS platform for multispectral raster analysis: NDVI, NDBI, NDWI, BSI, SAVI, and land-cover classification.",
      },
      { name: "author", content: "Lovable" },
      { property: "og:title", content: "GeoRaster Analytics" },
      { property: "og:description", content: "Online multispectral raster analysis." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "twitter:site", content: "@Lovable" },
      { name: "twitter:title", content: "GeoRaster Analytics" },
      { name: "twitter:description", content: "Online multispectral raster analysis." },
      {
        property: "og:image",
        content:
          "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/19300a30-ae67-4979-a5f7-d6441bbbf589/id-preview-31107bcf--c04bc589-31c3-419f-96e8-d500d2875a9b.lovable.app-1779194009315.png",
      },
      {
        name: "twitter:image",
        content:
          "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/19300a30-ae67-4979-a5f7-d6441bbbf589/id-preview-31107bcf--c04bc589-31c3-419f-96e8-d500d2875a9b.lovable.app-1779194009315.png",
      },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: React.ReactNode }) {
  const platformLogoPreloadScript = `
    (function () {
      try {
        var cached = window.localStorage.getItem("georaster.platformSettings");
        if (!cached) return;
        var settings = JSON.parse(cached);
        if (!settings || !settings.logo_url) return;
        var logoUrl = String(settings.logo_url);
        if (!/^https?:\\/\\//i.test(logoUrl)) logoUrl = ${JSON.stringify(API_BASE_URL)} + logoUrl;
        document.documentElement.dataset.platformLogoCache = "true";
        document.documentElement.style.setProperty("--georaster-platform-logo-url", "url(" + JSON.stringify(logoUrl) + ")");
      } catch (error) {}
    })();
  `;

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <HeadContent />
        <script dangerouslySetInnerHTML={{ __html: platformLogoPreloadScript }} />
      </head>
      <body suppressHydrationWarning>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <RootLayout />
      </I18nProvider>
    </QueryClientProvider>
  );
}

function RootLayout() {
  const { t, isRtl } = useI18n();
  const accountControls = (
    <div className="flex items-center gap-2 shrink-0">
      <button className="relative p-2 rounded-md hover:bg-muted">
        <Bell className="h-4 w-4" />
        <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-destructive" />
      </button>
      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary to-accent text-primary-foreground flex items-center justify-center text-xs font-semibold">
        GR
      </div>
    </div>
  );

  return (
    <SidebarProvider>
      <div
        dir="ltr"
        className={`flex min-h-screen w-full bg-background ${isRtl ? "flex-row-reverse" : ""}`}
      >
        <AppSidebar side={isRtl ? "right" : "left"} />
        <div dir={isRtl ? "rtl" : "ltr"} className="flex-1 flex flex-col min-w-0">
          <header className="relative sticky top-0 z-[1000] flex h-14 items-center gap-3 border-b bg-card px-4">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <SidebarTrigger />
              <PlatformBrand
                showSubtitle={false}
                isRtl={isRtl}
                title={isRtl ? t("brand.name") : undefined}
                className="text-sm"
              />
              <span className="hidden min-w-0 truncate text-sm text-muted-foreground sm:inline">
                {t("app.subtitle")}
              </span>
            </div>
            <div className={`flex shrink-0 items-center gap-2 ${isRtl ? "flex-row-reverse" : ""}`}>
              <div className="hidden w-72 shrink-0 items-center gap-2 rounded-md border bg-background px-3 py-1.5 text-sm text-muted-foreground md:flex">
                <Search className="h-4 w-4" />
                <input
                  placeholder={t("app.searchPlaceholder")}
                  className="bg-transparent outline-none flex-1 text-foreground placeholder:text-muted-foreground"
                />
              </div>
              <LanguageSwitcher />
              {accountControls}
            </div>
          </header>
          <main className="flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>
      <Toaster position={isRtl ? "top-left" : "top-right"} richColors />
    </SidebarProvider>
  );
}
