import { useEffect, useState } from "react";
import { appInfo, AppInfo, call, isSimulated, Proportion, Versions } from "./api";

type Health = "waiting" | "ready" | "error";

const formatNumber = (x: number, d = 1) =>
  x.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
const formatPercent = (x: number) => `${formatNumber(x * 100)}\u202F%`;

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
    <span className={`status ${className}`}>
      <StatusIcon state={state} />
      {label}
    </span>
  );
}

const STEPS = ["Vue d'ensemble", "Cadre de résultats", "Indicateurs", "Données", "Rapport"];

export function App() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [versions, setVersions] = useState<Versions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Proportion | null>(null);
  const [computing, setComputing] = useState(false);
  const [computeError, setComputeError] = useState<string | null>(null);
  const [design, setDesign] = useState<"survey" | "simple">("survey");
  const [showScript, setShowScript] = useState(false);
  const [folded, setFolded] = useState(false);

  const loadVersions = () =>
    call<Versions>("system.versions")
      .then(setVersions)
      .catch((e: Error) => setError(e.message));

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
    call<Proportion>("demo.proportion", { design: design })
      .then((r) => setResult(r))
      .catch((e: Error) => setComputeError(e.message))
      .finally(() => setComputing(false));
  };

  const pythonState: Health = error ? "error" : versions ? "ready" : "waiting";
  const rState: Health = error || versions?.r_error ? "error" : versions?.r ? "ready" : "waiting";
  const allReady = pythonState === "ready" && rState === "ready";

  const toggleTheme = () => {
    const r = document.documentElement;
    const dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark";
  };

  return (
    <div className={`app${folded ? " folded" : ""}`}>
      <aside className="side" aria-label="Navigation">
        <div className="side-top">
          <span className="mark fold-hide">
            SuiviEval<span>Lab</span>
          </span>
          <button
            className="icon-btn"
            onClick={() => setFolded(!folded)}
            aria-label="Replier la barre latérale"
            aria-expanded={!folded}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <rect x="2.5" y="3" width="13" height="12" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
              <path d="M7 3v12" stroke="currentColor" strokeWidth="1.4" />
            </svg>
          </button>
        </div>
        <div className="fold-hide">
          <div className="group-title">Projet</div>
          <nav aria-label="Étapes du projet">
            <a href="#demarrage" aria-current="page">
              Démarrage
            </a>
            {STEPS.map((step) => (
              <span key={step} className="nav-off" title="Disponible dans une prochaine version">
                {step}
              </span>
            ))}
          </nav>
        </div>
        <div className="side-foot">
          <span className="small muted fold-hide">Version {info?.version ?? "0.1.0"}</span>
          <button className="icon-btn" onClick={toggleTheme} aria-label="Changer de thème">
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
            SuiviEvalLab <span aria-hidden="true">/</span> <b>Démarrage</b>
          </div>
          <span className="saved">{isSimulated ? "Aperçu, moteurs simulés" : "Hors ligne"}</span>
        </div>
        <div className="col">
          <div className="inner">
            <div>
              <h1>Démarrage</h1>
              <p className="lead">
                Cette première version vérifie que l'application et ses deux moteurs de calcul fonctionnent sur votre
                ordinateur, sans connexion internet.
              </p>
            </div>

            <section>
              <div className="section-head">
                <h2>Moteurs de calcul</h2>
                <button className="btn" onClick={checkEngines}>
                  Vérifier à nouveau
                </button>
              </div>
              <div className="list">
                <div className="row">
                  <span className="t">Interface</span>
                  <span className="s">Electron {info?.electron ?? ""}</span>
                  <span className="v">
                    <StatusLabel state="ready" label="Prête" />
                  </span>
                </div>
                <div className="row">
                  <span className="t">Moteur Python</span>
                  <span className="s">
                    {versions
                      ? `Python ${versions.python}, polars ${versions.polars}, moteur ${versions.engine}`
                      : (error ?? "Démarrage en cours")}
                  </span>
                  <span className="v">
                    <StatusLabel
                      state={pythonState}
                      label={pythonState === "ready" ? "Prêt" : pythonState === "error" ? "Erreur" : "En attente"}
                    />
                  </span>
                </div>
                <div className="row">
                  <span className="t">Moteur statistique R</span>
                  <span className="s">
                    {versions?.r
                      ? `R ${versions.r.r}, survey ${versions.r.packages.survey ?? "absent"}, nanoarrow ${versions.r.packages.nanoarrow ?? "absent"}`
                      : (versions?.r_error ?? (error ? "Indisponible" : "Démarrage en cours, quelques secondes"))}
                  </span>
                  <span className="v">
                    <StatusLabel
                      state={rState}
                      label={rState === "ready" ? "Prêt" : rState === "error" ? "Erreur" : "En attente"}
                    />
                  </span>
                </div>
              </div>
              {info?.logs && (pythonState === "error" || rState === "error") && (
                <p className="small muted" style={{ marginTop: 12 }}>
                  Journal du moteur : {info.logs}
                </p>
              )}
            </section>

            <section className="stack">
              <h2>Calcul de démonstration</h2>
              <p className="muted" style={{ margin: 0 }}>
                Proportion de filles de 6 à 11 ans scolarisées, sur 612 ménages fictifs. Le calcul est fait par R, comme
                le seront tous les calculs de l'application.
              </p>
              <div className="chips" role="group" aria-label="Type de calcul">
                <button className="chip" aria-pressed={design === "survey"} onClick={() => setDesign("survey")}>
                  Avec plan d'enquête
                </button>
                <button className="chip" aria-pressed={design === "simple"} onClick={() => setDesign("simple")}>
                  Échantillon simple
                </button>
              </div>
              <div>
                <button className="btn primary" onClick={runDemo} disabled={!allReady || computing}>
                  {computing ? "Calcul en cours" : "Lancer le calcul"}
                </button>
              </div>
              {computeError && (
                <div className="hint hint-err" role="alert">
                  <StatusIcon state="error" />
                  <div>
                    <div className="t">Le calcul n'a pas abouti</div>
                    <div className="small">{computeError}</div>
                  </div>
                </div>
              )}
              {result && (
                <div className="result">
                  <span className="figure">{formatPercent(result.estimate)}</span>
                  <span className="muted">
                    Intervalle de confiance à {formatNumber(result.level * 100, 0)} % : {formatPercent(result.ci_low)} à{" "}
                    {formatPercent(result.ci_high)}
                  </span>
                  <span className="small muted">
                    {result.successes} filles scolarisées sur {result.n}. {result.method}.
                  </span>
                  <div>
                    <button className="btn" onClick={() => setShowScript(!showScript)} aria-expanded={showScript}>
                      {showScript ? "Masquer le script R" : "Voir le script R"}
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
