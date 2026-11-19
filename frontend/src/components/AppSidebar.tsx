import { Link, useRouterState } from "@tanstack/react-router";
import { LayoutDashboard, Map, Library, History, Settings } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { PlatformBrand } from "@/components/PlatformBrand";
import { useI18n } from "@/lib/i18n";

const items = [
  { titleKey: "nav.dashboard", url: "/", icon: LayoutDashboard },
  { titleKey: "nav.map", url: "/map", icon: Map },
  { titleKey: "nav.catalog", url: "/catalog", icon: Library },
  { titleKey: "nav.history", url: "/history", icon: History },
  { titleKey: "nav.settings", url: "/settings", icon: Settings },
] as const;

export function AppSidebar({ side = "left" }: { side?: "left" | "right" }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { t, isRtl } = useI18n();
  const isActive = (url: string) => (url === "/" ? pathname === "/" : pathname.startsWith(url));

  return (
    <Sidebar collapsible="icon" side={side}>
      <SidebarHeader className="border-b border-sidebar-border">
        <PlatformBrand
          isRtl={isRtl}
          title={isRtl ? t("brand.name") : undefined}
          subtitle={isRtl ? t("brand.subtitle") : undefined}
          className="px-2 py-3 group-data-[collapsible=icon]:justify-center"
        />
      </SidebarHeader>
      <SidebarContent dir={isRtl ? "rtl" : "ltr"}>
        <SidebarGroup>
          <SidebarGroupLabel className={isRtl ? "justify-start text-right" : "text-left"}>
            {t("nav.modules")}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => {
                const title = t(item.titleKey);
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton asChild isActive={isActive(item.url)} tooltip={title}>
                      <Link
                        to={item.url}
                        dir={isRtl ? "rtl" : "ltr"}
                        className={`flex w-full items-center gap-2 ${isRtl ? "text-right" : "text-left"}`}
                      >
                        <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                        <span className="min-w-0 flex-1">{title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
