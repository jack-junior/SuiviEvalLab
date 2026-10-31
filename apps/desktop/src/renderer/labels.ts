// Readable labels of columns and codes, from the questionnaire (XLSForm) or typed
// by the user. Codes stay the reference everywhere; labels are only displayed.

import { useCallback } from "react";
import type { Dataset, LangLabels } from "./api";
import { useI18n } from "./i18n";
import { useProject } from "./state";

export function pickLabel(m: LangLabels | undefined, lang: string): string | undefined {
  if (!m) return undefined;
  return m[lang] || m.default || m.en || Object.values(m).find(Boolean);
}

export function useLabels() {
  const { lang } = useI18n();
  const { snap } = useProject();
  const sets = useCallback((ds?: Dataset) => (ds ? [ds] : (snap?.datasets ?? [])), [snap?.datasets]);

  /** Label of a column, or undefined. */
  const col = useCallback(
    (column: string, ds?: Dataset) => {
      for (const d of sets(ds)) {
        const l = pickLabel(d.labels?.columns?.[column], lang);
        if (l) return l;
      }
      return undefined;
    },
    [sets, lang],
  );

  /** Label of a code of a column, or undefined. */
  const val = useCallback(
    (column: string, code: string | null, ds?: Dataset) => {
      if (code === null) return undefined;
      for (const d of sets(ds)) {
        const l = pickLabel(d.labels?.values?.[column]?.[code], lang);
        if (l) return l;
      }
      return undefined;
    },
    [sets, lang],
  );

  /** "Label (code)" for a column, or the column name. */
  const colText = useCallback(
    (column: string, ds?: Dataset) => {
      const l = col(column, ds);
      return l ? `${l} (${column})` : column;
    },
    [col],
  );

  /** The label of a code, or the code itself. */
  const valText = useCallback((column: string, code: string, ds?: Dataset) => val(column, code, ds) ?? code, [val]);

  return { col, val, colText, valText };
}
