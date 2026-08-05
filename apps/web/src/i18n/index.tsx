import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { en } from "./en";
import { zhCN, type TranslationKey } from "./zh-CN";

export type Locale = "zh-CN" | "en";
type I18nValue = { locale: Locale; toggleLocale: () => void; t: (key: TranslationKey) => string };
const I18nContext = createContext<I18nValue | null>(null);

function initialLocale(): Locale {
  const saved = window.localStorage.getItem("agentbridge_locale");
  return saved === "en" ? "en" : "zh-CN";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const value = useMemo<I18nValue>(() => {
    const messages = locale === "en" ? en : zhCN;
    return {
      locale,
      toggleLocale: () => setLocale((current) => {
        const next = current === "en" ? "zh-CN" : "en";
        window.localStorage.setItem("agentbridge_locale", next === "en" ? "en" : "zh-CN");
        return next;
      }),
      t: (key) => messages[key],
    };
  }, [locale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (value) return value;
  return { locale: "zh-CN", toggleLocale: () => undefined, t: (key) => zhCN[key] };
}
