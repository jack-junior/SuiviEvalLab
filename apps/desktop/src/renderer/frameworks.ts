// The results framework model of the open project: level names in the interface
// language, how deep the chain goes, which levels carry indicators.

import { useCallback, useMemo } from "react";
import { FrameworkModel, Level } from "./api";
import { useI18n } from "./i18n";
import { useProject } from "./state";

export const LEVEL_KEYS: Level[] = ["impact", "outcome", "output", "activity"];

const STANDARD: FrameworkModel = {
  id: "standard",
  levels: [
    { fr: "Impact", en: "Impact", indicators: true },
    { fr: "Effet", en: "Outcome", indicators: true },
    { fr: "Extrant", en: "Output", indicators: true },
    { fr: "Activité", en: "Activity", indicators: false },
  ],
};

export function levelNames(model: FrameworkModel, lang: string): string[] {
  return model.levels.map((l) => (lang === "en" ? l.en || l.fr : l.fr));
}

export function useLevels() {
  const { lang } = useI18n();
  const { snap } = useProject();
  const model = snap?.project.framework_model ?? STANDARD;
  const names = useMemo(() => levelNames(model, lang), [model, lang]);
  const index = (level: Level) => LEVEL_KEYS.indexOf(level);
  const name = useCallback((level: Level) => names[LEVEL_KEYS.indexOf(level)] ?? level, [names]);
  return {
    model,
    names,
    name,
    /** The level below, or null at the bottom of this model. */
    next: (level: Level): Level | null =>
      index(level) + 1 < model.levels.length ? LEVEL_KEYS[index(level) + 1] : null,
    carries: (level: Level) => Boolean(model.levels[index(level)]?.indicators),
  };
}
