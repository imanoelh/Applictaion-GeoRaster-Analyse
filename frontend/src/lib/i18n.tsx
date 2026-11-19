import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "@/i18n/en.json";
import ar from "@/i18n/ar.json";

export type Language = "en" | "ar";

type TranslationKey = keyof typeof en;

type I18nContextValue = {
  language: Language;
  isRtl: boolean;
  setLanguage: (language: Language) => void;
  t: (key: TranslationKey, values?: Record<string, string | number>) => string;
};

const STORAGE_KEY = "georaster.language";
const dictionaries: Record<Language, Record<string, string>> = { en, ar };
const I18nContext = createContext<I18nContextValue | null>(null);

function getInitialLanguage(): Language {
  if (typeof window === "undefined") return "en";
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved === "ar" || saved === "en" ? saved : "en";
}

function formatTemplate(value: string, values?: Record<string, string | number>) {
  if (!values) return value;
  return Object.entries(values).reduce(
    (text, [key, replacement]) => text.replaceAll(`{${key}}`, String(replacement)),
    value,
  );
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);
  const isRtl = language === "ar";

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
    document.documentElement.dir = isRtl ? "rtl" : "ltr";
    document.body.dir = isRtl ? "rtl" : "ltr";
  }, [isRtl, language]);

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      isRtl,
      setLanguage: setLanguageState,
      t: (key, values) =>
        formatTemplate(dictionaries[language][key] ?? dictionaries.en[key] ?? key, values),
    }),
    [isRtl, language],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used inside I18nProvider");
  return context;
}
