import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { en, fr, MessageKey } from "./messages";

export type Lang = "fr" | "en";

const CATALOGUES: Record<Lang, Record<MessageKey, string>> = { fr, en };
const LOCALES: Record<Lang, string> = { fr: "fr-FR", en: "en-GB" };
const STORAGE_KEY = "sme.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "fr" || saved === "en") return saved;
  } catch {
    /* storage unavailable: fall back to the system language */
  }
  return navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en";
}

type Vars = Record<string, string | number>;

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  // Keys built at run time (levels.${level}) are accepted; tools/check-i18n.mjs checks them.
  t: (key: MessageKey | (string & {}), vars?: Vars) => string;
  hasKey: (key: string) => key is MessageKey;
  /** Count text: uses `${key}_one` or `${key}_other` (French: 0 and 1 take the singular). */
  tn: (key: string, n: number, vars?: Vars) => string;
  date: (iso: string | null | undefined) => string;
  number: (x: number, digits?: number) => string;
  percent: (share: number, digits?: number) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* preference not saved: still applied for this session */
    }
  }, []);

  const value = useMemo<I18n>(() => {
    const catalogue = CATALOGUES[lang];
    const locale = LOCALES[lang];
    return {
      lang,
      setLang,
      t: (key, vars) => {
        const text = catalogue[key as MessageKey] ?? key;
        return vars ? text.replace(/\{(\w+)\}/g, (m, name: string) => (name in vars ? String(vars[name]) : m)) : text;
      },
      hasKey: (key): key is MessageKey => key in catalogue,
      date: (iso) =>
        iso ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso)) : "",
      tn: (key, n, vars) => {
        const one = lang === "fr" ? Math.abs(n) < 2 : n === 1;
        const text = catalogue[`${key}_${one ? "one" : "other"}` as MessageKey] ?? key;
        const all: Vars = { n: n.toLocaleString(locale), ...vars };
        return text.replace(/\{(\w+)\}/g, (m, name: string) => (name in all ? String(all[name]) : m));
      },
      number: (x, digits = 1) =>
        x.toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }),
      percent: (share, digits = 1) =>
        new Intl.NumberFormat(locale, {
          style: "percent",
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        }).format(share),
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
