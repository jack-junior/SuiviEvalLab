// Diagnostic of the calculation engines, with the demo calculation of version 0.1.

import { useState } from "react";
import { AppInfo, call, EngineCallError, Proportion, Versions } from "../api";
import { useI18n } from "../i18n";
import { UpdatesSection } from "../updates";

type Health = "waiting" | "ready" | "error";

export function EngineStatus({ state, label }: { state: Health; label: string }) {
  const cls = state === "ready" ? "st-ok" : state === "error" ? "st-late" : "st-mid";
  return (
    <span className={`status ${cls}`} data-testid={`engine-${state}`}>
      <span className="dot-ring" aria-hidden="true" />
      {label}
    </span>
  );
}

export function Engines({
  info,
  versions,
  error,
  onRecheck,
}: {
  info: AppInfo | null;
  versions: Versions | null;
  error: { key: string; detail: string } | null;
  onRecheck: () => void;
}) {
  const { t, hasKey, percent } = useI18n();
  const [result, setResult] = useState<Proportion | null>(null);
  const [computing, setComputing] = useState(false);
  const [computeError, setComputeError] = useState<string | null>(null);
  const [design, setDesign] = useState<"survey" | "simple">("survey");
  const [showScript, setShowScript] = useState(false);

  const describe = (key: string, detail: string) =>
    hasKey(`errors.${key}`) ? t(`errors.${key}`, { detail }) : t("errors.unknown", { detail });

  const pythonState: Health = error ? "error" : versions ? "ready" : "waiting";
  const rState: Health = error || versions?.r_error ? "error" : versions?.r ? "ready" : "waiting";
  const label = (s: Health) =>
    s === "ready" ? t("engines.ready") : s === "error" ? t("engines.error") : t("engines.waiting");

  const runDemo = () => {
    setComputing(true);
    setComputeError(null);
    call<Proportion>("demo.proportion", { design })
      .then(setResult)
      .catch((e: unknown) =>
        setComputeError(e instanceof EngineCallError ? describe(e.key, e.message) : describe("unknown", String(e))),
      )
      .finally(() => setComputing(false));
  };

  return (
    <div className="inner">
      <div>
        <h1>{t("engines.title")}</h1>
        <p className="lead">{t("engines.lead")}</p>
      </div>
      <section>
        <div className="section-head">
          <h2>{t("engines.listTitle")}</h2>
          <button className="btn" onClick={onRecheck}>
            {t("engines.recheck")}
          </button>
        </div>
        <div className="list">
          <div className="row">
            <span className="t">{t("engines.ui")}</span>
            <span className="s">Electron {info?.electron ?? ""}</span>
            <span className="v">
              <EngineStatus state="ready" label={t("engines.ready")} />
            </span>
          </div>
          <div className="row">
            <span className="t">{t("engines.python")}</span>
            <span className="s">
              {versions
                ? t("engines.pythonDetail", {
                    python: versions.python,
                    polars: versions.polars,
                    engine: versions.engine,
                  })
                : error
                  ? describe(error.key, error.detail)
                  : t("engines.starting")}
            </span>
            <span className="v">
              <EngineStatus state={pythonState} label={label(pythonState)} />
            </span>
          </div>
          <div className="row">
            <span className="t">{t("engines.r")}</span>
            <span className="s">
              {versions?.r
                ? t("engines.rDetail", {
                    r: versions.r.r,
                    survey: versions.r.packages.survey ?? t("engines.missing"),
                    nanoarrow: versions.r.packages.nanoarrow ?? t("engines.missing"),
                  })
                : (versions?.r_error ?? (error ? t("engines.unavailable") : t("engines.rStarting")))}
            </span>
            <span className="v">
              <EngineStatus state={rState} label={label(rState)} />
            </span>
          </div>
        </div>
        {info?.logs && (pythonState === "error" || rState === "error") && (
          <p className="small muted">{t("engines.logs", { path: info.logs })}</p>
        )}
      </section>

      <UpdatesSection />

      <section className="stack">
        <h2>{t("demo.title")}</h2>
        <p className="muted" style={{ margin: 0 }}>
          {t("demo.lead")}
        </p>
        <div className="chips" role="group" aria-label={t("demo.designLabel")}>
          <button className="chip" aria-pressed={design === "survey"} onClick={() => setDesign("survey")}>
            {t("demo.survey")}
          </button>
          <button className="chip" aria-pressed={design === "simple"} onClick={() => setDesign("simple")}>
            {t("demo.simple")}
          </button>
        </div>
        <div>
          <button
            className="btn primary"
            onClick={runDemo}
            disabled={rState !== "ready" || computing}
            data-testid="run-demo"
          >
            {computing ? t("demo.running") : t("demo.run")}
          </button>
        </div>
        {computeError && <div className="notice notice-error">{computeError}</div>}
        {result && (
          <div className="result">
            <span className="figure" data-testid="figure">
              {percent(result.estimate)}
            </span>
            <span className="muted" data-testid="ci">
              {t("demo.ci", {
                level: percent(result.level, 0),
                low: percent(result.ci_low),
                high: percent(result.ci_high),
              })}
            </span>
            <span className="small muted">
              {t("demo.counts", { x: result.successes, n: result.n })} {t(`method.${result.method_key}`)}.
            </span>
            <div>
              <button className="btn" onClick={() => setShowScript(!showScript)} aria-expanded={showScript}>
                {showScript ? t("demo.hideScript") : t("demo.showScript")}
              </button>
            </div>
            {showScript && <pre className="code-block">{result.script}</pre>}
          </div>
        )}
      </section>
    </div>
  );
}
