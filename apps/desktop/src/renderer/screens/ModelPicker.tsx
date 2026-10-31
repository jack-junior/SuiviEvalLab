// Choice of the results framework model: the donor's chain of levels, or a custom one.

import { useEffect, useState } from "react";
import { call, FrameworkLevel, FrameworkModel } from "../api";
import { levelNames } from "../frameworks";
import { useI18n } from "../i18n";

let cache: FrameworkModel[] | null = null;

export function useModels(): FrameworkModel[] | null {
  const [models, setModels] = useState<FrameworkModel[] | null>(cache);
  useEffect(() => {
    if (cache) return;
    let live = true;
    call<{ models: FrameworkModel[] }>("framework.models")
      .then((r) => {
        cache = r.models;
        if (live) setModels(r.models);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return models;
}

const EMPTY_CUSTOM: FrameworkLevel[] = [
  { fr: "", en: "", indicators: true },
  { fr: "", en: "", indicators: true },
  { fr: "", en: "", indicators: true },
];

export function customValid(m: FrameworkModel): boolean {
  return (
    m.id !== "custom" ||
    (m.levels.length >= 2 && m.levels.every((l) => l.fr.trim()) && m.levels.some((l) => l.indicators))
  );
}

export function ModelPicker({ value, onChange }: { value: FrameworkModel; onChange: (m: FrameworkModel) => void }) {
  const { t, lang } = useI18n();
  const models = useModels();
  const [custom, setCustom] = useState<FrameworkLevel[]>(value.id === "custom" ? value.levels : EMPTY_CUSTOM);
  if (!models) return <p className="muted small">{t("models.loading")}</p>;

  const setLevels = (levels: FrameworkLevel[]) => {
    setCustom(levels);
    onChange({ id: "custom", levels });
  };

  return (
    <div className="stack" data-testid="model-picker">
      <div className="model-list" role="radiogroup" aria-label={t("models.title")}>
        {[...models, { id: "custom", levels: custom } as FrameworkModel].map((m) => (
          <button
            key={m.id}
            role="radio"
            aria-checked={value.id === m.id}
            className="model-option"
            onClick={() => onChange(m.id === "custom" ? { id: "custom", levels: custom } : m)}
            data-testid={`model-${m.id}`}
          >
            <span className="model-name">{t(`models.${m.id}`)}</span>
            <span className="model-chain">
              {m.id === "custom" ? t("models.customHint") : levelNames(m, lang).join("  >  ")}
            </span>
          </button>
        ))}
      </div>
      {value.id === "custom" && (
        <div className="custom-levels">
          {custom.map((l, i) => (
            <div key={i} className="custom-level">
              <span className="muted small">{t("models.level", { n: i + 1 })}</span>
              <input
                className="input"
                placeholder={t("models.nameFr")}
                aria-label={t("models.nameFr")}
                value={l.fr}
                onChange={(e) => setLevels(custom.map((x, k) => (k === i ? { ...x, fr: e.target.value } : x)))}
                data-testid={`custom-fr-${i}`}
              />
              <input
                className="input"
                placeholder={t("models.nameEn")}
                aria-label={t("models.nameEn")}
                value={l.en}
                onChange={(e) => setLevels(custom.map((x, k) => (k === i ? { ...x, en: e.target.value } : x)))}
              />
              <label className="check">
                <input
                  type="checkbox"
                  checked={l.indicators}
                  onChange={(e) =>
                    setLevels(custom.map((x, k) => (k === i ? { ...x, indicators: e.target.checked } : x)))
                  }
                />
                <span className="check-text">{t("models.indicators")}</span>
              </label>
            </div>
          ))}
          <div className="row-actions start">
            {custom.length < 4 && (
              <button className="link" onClick={() => setLevels([...custom, { fr: "", en: "", indicators: true }])}>
                {t("models.addLevel")}
              </button>
            )}
            {custom.length > 2 && (
              <button className="link" onClick={() => setLevels(custom.slice(0, -1))}>
                {t("models.removeLevel")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
