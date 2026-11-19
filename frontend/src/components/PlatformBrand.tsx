import { useEffect, useState } from "react";
import { Satellite } from "lucide-react";
import {
  getPlatformSettings,
  readCachedPlatformSettings,
  resolveApiAssetUrl,
  type PlatformSettings,
} from "@/lib/georaster-api";

type Props = {
  compact?: boolean;
  showSubtitle?: boolean;
  className?: string;
  title?: string;
  subtitle?: string;
  isRtl?: boolean;
};

export function PlatformBrand({
  compact = false,
  showSubtitle = true,
  className = "",
  title,
  subtitle,
  isRtl = false,
}: Props) {
  const [settings, setSettings] = useState<PlatformSettings>(
    () => readCachedPlatformSettings() ?? { platform_name: "GeoRaster", logo_url: null },
  );
  const [isLoadingSettings, setIsLoadingSettings] = useState(
    () => readCachedPlatformSettings() == null,
  );

  useEffect(() => {
    let active = true;
    const load = () => {
      getPlatformSettings()
        .then((item) => {
          if (active) {
            setSettings(item);
            setIsLoadingSettings(false);
          }
        })
        .catch(() => {
          if (active) setIsLoadingSettings(false);
        });
    };
    load();
    window.addEventListener("platform-settings-updated", load);
    return () => {
      active = false;
      window.removeEventListener("platform-settings-updated", load);
    };
  }, []);

  const logoUrl = resolveApiAssetUrl(settings.logo_url);
  const displayedTitle = title || settings.platform_name || "GeoRaster";
  const displayedSubtitle = subtitle || "Analytics Platform";

  return (
    <div
      dir={isRtl ? "rtl" : "ltr"}
      className={`flex items-center gap-2 ${isRtl ? "text-right" : "text-left"} ${className}`}
    >
      <div
        className={`platform-logo-frame flex h-9 shrink-0 items-center justify-center overflow-hidden rounded-lg text-sidebar-primary-foreground ${logoUrl ? "min-w-9 max-w-24 bg-transparent px-1 group-data-[collapsible=icon]:w-9 group-data-[collapsible=icon]:px-0" : isLoadingSettings ? "w-9 bg-transparent" : "w-9 bg-sidebar-primary"}`}
      >
        {logoUrl ? (
          <img
            src={logoUrl}
            alt={`${displayedTitle} logo`}
            className="h-[125%] w-auto max-w-24 object-contain"
          />
        ) : isLoadingSettings ? (
          <span className="h-full w-full" />
        ) : (
          <Satellite className="h-5 w-5" />
        )}
      </div>
      {!compact && (
        <div
          className={`flex min-w-0 flex-col group-data-[collapsible=icon]:hidden ${isRtl ? "items-start text-right" : "items-start text-left"}`}
        >
          <span className="w-full truncate text-sm font-semibold leading-tight text-current">
            {displayedTitle}
          </span>
          {showSubtitle && (
            <span className="w-full truncate text-xs leading-tight opacity-70">
              {displayedSubtitle}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
