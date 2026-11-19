import { useState } from "react";
import { Globe2 } from "lucide-react";
import { useI18n, type Language } from "@/lib/i18n";

const OPTIONS: Array<{ value: Language; key: "language.english" | "language.arabic" }> = [
  { value: "en", key: "language.english" },
  { value: "ar", key: "language.arabic" },
];

export function LanguageSwitcher() {
  const { language, setLanguage, t, isRtl } = useI18n();
  const [open, setOpen] = useState(false);

  const selectLanguage = (nextLanguage: Language) => {
    setLanguage(nextLanguage);
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-9 items-center gap-2 rounded-md border bg-background px-2.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
        aria-label={t("language.label")}
        aria-expanded={open}
      >
        <Globe2 className="h-4 w-4" />
        <span className="hidden sm:inline">{language.toUpperCase()}</span>
      </button>
      {open && (
        <div
          className={`absolute top-11 z-50 w-36 rounded-xl border bg-popover p-1 text-sm shadow-lg ${isRtl ? "left-0 text-right" : "right-0 text-left"}`}
          role="menu"
        >
          {OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => selectLanguage(option.value)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 transition-colors hover:bg-muted ${language === option.value ? "bg-primary/10 text-primary" : "text-foreground"}`}
              role="menuitem"
            >
              <span>{t(option.key)}</span>
              {language === option.value && <span className="h-2 w-2 rounded-full bg-primary" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
