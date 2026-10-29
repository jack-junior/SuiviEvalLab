import { useEffect, useState } from "react";
import { appInfo, AppInfo, call, EngineCallError, isSimulated, Proportion, Versions } from "./api";
import { Lang, useI18n } from "./i18n";
import type { MessageKey } from "./i18n/messages";

type Health = "waiting" | "ready" | "error";

function StatusIcon({ state }: { state: Health }) {
  if (state === "ready")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <circle cx="7" cy="7" r="5.6" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M4.6 7.2l1.7 1.7 3.2-3.4" fill="none" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    );
  if (state === "error")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <path d="M7 1.8l5.4 9.6H1.6z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
        <path d="M7 5.6v2.6" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    );
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <circle cx="7" cy="7" r="5.6" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M7 4v3.2l2 1.3" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function StatusLabel({ state, label }: { state: Health; label: string }) {
  const className = state === "ready" ? "st-ok" : state === "error" ? "st-late" : "st-mid";
  return (
    <span className={`status ${className}`} data-testid={`status-${state}`}>
      <StatusIcon state={state} />
      {label}
    </span>
  );
}

const STEPS: MessageKey[] = ["nav.overview", "nav.framework", "nav.indicators", "nav.data", "nav.report"];
const LANGS: { code: Lang; label: string; name: string }[] = [
  { code: "fr", label: "FR", name: "Français" },
  { code: "en", label: "EN", name: "English" },
];

/** Engine errors are stored as keys and translated at render time, so they follow the language. */
interface UiError {
  key: string;
  detail: string;
}

const toUiError = (e: unknown): UiError =>
  e instanceof EngineCallError ? { key: e.key, detail: e.message } : { key: "unknown", detail: String(e) };

export function App() {
  const { t, lang, setLang, hasKey, percent } = useI18n();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [versions, setVersions] = useState<Versions | null>(null);
  const [error, setError] = useState<UiError | null>(null);
  const [result, setResult] = useState<Proportion | null>(null);
  const [computing, setComputing] = useState(false);
  const [computeError, setComputeError] = useState<UiError | null>(null);
  const [design, setDesign] = useState<"survey" | "simple">("survey");
  const [showScript, setShowScript] = useState(false);
  const [folded, setFolded] = useState(false);

  const describe = (err: UiError) => {
    const key = `errors.${err.key}`;
    return hasKey(key) ? t(key, { detail: err.detail }) : t("errors.unknown", { detail: err.detail });
  };

  const loadVersions = () =>
    call<Versions>("system.versions")
      .then(setVersions)
      .catch((e: unknown) => setError(toUiError(e)));

  const checkEngines = () => {
    setError(null);
    setVersions(null);
    void loadVersions();
  };

  useEffect(() => {
    appInfo()
      .then(setInfo)
      .catch(() => undefined);
    void loadVersions();
  }, []);

  const runDemo = () => {
    setComputing(true);
    setComputeError(null);
    call<Proportion>("demo.proportion", { design })
      .then((r) => setResult(r))
      .catch((e: unknown) => setComputeError(toUiError(e)))
      .finally(() => setComputing(false));
  };

  const pythonState: Health = error ? "error" : versions ? "ready" : "waiting";
  const rState: Health = error || versions?.r_error ? "error" : versions?.r ? "ready" : "waiting";
  const allReady = pythonState === "ready" && rState === "ready";
  const statusText = (state: Health) =>
    state === "ready" ? t("status.ready") : state === "error" ? t("status.error") : t("status.waiting");

  const toggleTheme = () => {
    const r = document.documentElement;
    const dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark";
  };

  const methodText = (r: Proportion) => {
    const key = `method.${r.method_key}`;
    return hasKey(key) ? t(key) : r.method;
  };

  return (
    <div className={`app${folded ? " folded" : ""}`}>
      <aside className="side" aria-label={t("nav.label")}>
        <div className="side-top">
          <span className="mark fold-hide">
            SuiviEval<span>Lab</span>
          </span>
          <button
            className="icon-btn"
            onClick={() => setFolded(!folded)}
            aria-label={t("side.fold")}
            aria-expanded={!folded}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <rect x="2.5" y="3" width="13" height="12" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
              <path d="M7 3v12" stroke="currentColor" strokeWidth="1.4" />
            </svg>
          </button>
        </div>
        <div className="fold-hide">
          <div className="group-title">{t("nav.project")}</div>
          <nav aria-label={t("nav.steps")}>
            <a href="#start" aria-current="page">
              {t("nav.start")}
            </a>
            {STEPS.map((step) => (
              <span key={step} className="nav-off" title={t("nav.soon")}>
                {t(step)}
              </span>
            ))}
          </nav>
        </div>
        <div className="side-foot">
          <div className="lang fold-hide" role="group" aria-label={t("side.language")}>
            {LANGS.map((l) => (
              <button
                key={l.code}
                className="lang-btn"
                aria-pressed={lang === l.code}
                onClick={() => setLang(l.code)}
                title={l.name}
                data-testid={`lang-${l.code}`}
                lang={l.code}
              >
                {l.label}
              </button>
            ))}
          </div>
          <button className="icon-btn" onClick={toggleTheme} aria-label={t("side.theme")} data-testid="theme">
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <circle cx="9" cy="9" r="6" fill="none" stroke="currentColor" strokeWidth="1.4" />
              <path d="M9 3a6 6 0 0 1 0 12z" fill="currentColor" />
            </svg>
          </button>
        </div>
      </aside>

      <div className="main">
        <div className="bar">
          <div className="crumb">
            SuiviEvalLab <span aria-hidden="true">/</span> <b>{t("start.title")}</b>
          </div>
          <span className="saved">
            {isSimulated ? t("app.preview") : t("app.offline")}
            <span className="muted" style={{ marginLeft: 12 }}>
              {t("side.version", { version: info?.version ?? "0.1.0" })}
            </span>
          </span>
        </div>
        <div className="col">
          <div className="inner">
            <div>
              <h1>{t("start.title")}</h1>
              <p className="lead">{t("start.lead")}</p>
            </div>

            <section>
              <div className="section-head">
                <h2>{t("engines.title")}</h2>
                <button className="btn" onClick={checkEngines}>
                  {t("engines.recheck")}
                </button>
              </div>
              <div className="list">
                <div className="row">
                  <span className="t">{t("engines.ui")}</span>
                  <span className="s">Electron {info?.electron ?? ""}</span>
                  <span className="v">
                    <StatusLabel state="ready" label={t("status.readyFeminine")} />
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
                        ? describe(error)
                        : t("engines.starting")}
                  </span>
                  <span className="v">
                    <StatusLabel state={pythonState} label={statusText(pythonState)} />
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
                    <StatusLabel state={rState} label={statusText(rState)} />
                  </span>
                </div>
              </div>
              {info?.logs && (pythonState === "error" || rState === "error") && (
                <p className="small muted" style={{ marginTop: 12 }}>
                  {t("engines.logs", { path: info.logs })}
                </p>
              )}
            </section>

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
                  disabled={!allReady || computing}
                  data-testid="run-demo"
                >
                  {computing ? t("demo.running") : t("demo.run")}
                </button>
              </div>
              {computeError && (
                <div className="hint hint-err" role="alert">
                  <StatusIcon state="error" />
                  <div>
                    <div className="t">{t("demo.failed")}</div>
                    <div className="small">{describe(computeError)}</div>
                  </div>
                </div>
              )}
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
                    {t("demo.counts", { x: result.successes, n: result.n })} {methodText(result)}.
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
        </div>
      </div>
    </div>
  );
}
