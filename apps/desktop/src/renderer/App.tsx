import { useEffect, useState } from "react";
import { appInfo, AppInfo, call, isSimulated, Proportion, Versions } from "./api";

type Etat = "attente" | "pret" | "erreur";

const fr = (x: number, d = 1) => x.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x: number) => `${fr(x * 100)} %`;

function Icone({ etat }: { etat: Etat }) {
  if (etat === "pret")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <circle cx="7" cy="7" r="5.6" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M4.6 7.2l1.7 1.7 3.2-3.4" fill="none" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    );
  if (etat === "erreur")
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

function Statut({ etat, texte }: { etat: Etat; texte: string }) {
  const cls = etat === "pret" ? "st-ok" : etat === "erreur" ? "st-late" : "st-mid";
  return (
    <span className={`status ${cls}`}>
      <Icone etat={etat} />
      {texte}
    </span>
  );
}

const ETAPES = ["Vue d'ensemble", "Cadre de résultats", "Indicateurs", "Données", "Rapport"];

export function App() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [versions, setVersions] = useState<Versions | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [calcul, setCalcul] = useState<Proportion | null>(null);
  const [calculEnCours, setCalculEnCours] = useState(false);
  const [erreurCalcul, setErreurCalcul] = useState<string | null>(null);
  const [plan, setPlan] = useState<"survey" | "simple">("survey");
  const [script, setScript] = useState(false);
  const [plie, setPlie] = useState(false);

  const verifier = () => {
    setErreur(null);
    setVersions(null);
    call<Versions>("system.versions").then(setVersions).catch((e: Error) => setErreur(e.message));
  };

  useEffect(() => {
    appInfo().then(setInfo).catch(() => undefined);
    verifier();
  }, []);

  const lancer = () => {
    setCalculEnCours(true);
    setErreurCalcul(null);
    call<Proportion>("demo.proportion", { design: plan })
      .then((r) => setCalcul(r))
      .catch((e: Error) => setErreurCalcul(e.message))
      .finally(() => setCalculEnCours(false));
  };

  const etatPython: Etat = erreur ? "erreur" : versions ? "pret" : "attente";
  const etatR: Etat = erreur || versions?.r_error ? "erreur" : versions?.r ? "pret" : "attente";
  const toutPret = etatPython === "pret" && etatR === "pret";

  const basculerTheme = () => {
    const r = document.documentElement;
    const sombre = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = sombre ? "light" : "dark";
  };

  return (
    <div className={`app${plie ? " folded" : ""}`}>
      <aside className="side" aria-label="Navigation">
        <div className="side-top">
          <span className="mark fold-hide">
            SuiviEval<span>Lab</span>
          </span>
          <button className="icon-btn" onClick={() => setPlie(!plie)} aria-label="Replier la barre latérale" aria-expanded={!plie}>
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
            {ETAPES.map((e) => (
              <span key={e} className="nav-off" title="Disponible dans une prochaine version">
                {e}
              </span>
            ))}
          </nav>
        </div>
        <div className="side-foot">
          <span className="small muted fold-hide">Version {info?.version ?? "0.1.0"}</span>
          <button className="icon-btn" onClick={basculerTheme} aria-label="Changer de thème">
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
                Cette première version vérifie que l'application et ses deux moteurs de calcul fonctionnent sur votre ordinateur, sans connexion internet.
              </p>
            </div>

            <section>
              <div className="section-head">
                <h2>Moteurs de calcul</h2>
                <button className="btn" onClick={verifier}>
                  Vérifier à nouveau
                </button>
              </div>
              <div className="list">
                <div className="row">
                  <span className="t">Interface</span>
                  <span className="s">Electron {info?.electron ?? ""}</span>
                  <span className="v">
                    <Statut etat="pret" texte="Prête" />
                  </span>
                </div>
                <div className="row">
                  <span className="t">Moteur Python</span>
                  <span className="s">
                    {versions ? `Python ${versions.python}, polars ${versions.polars}, moteur ${versions.engine}` : erreur ?? "Démarrage en cours"}
                  </span>
                  <span className="v">
                    <Statut etat={etatPython} texte={etatPython === "pret" ? "Prêt" : etatPython === "erreur" ? "Erreur" : "En attente"} />
                  </span>
                </div>
                <div className="row">
                  <span className="t">Moteur statistique R</span>
                  <span className="s">
                    {versions?.r
                      ? `R ${versions.r.r}, survey ${versions.r.packages.survey ?? "absent"}, nanoarrow ${versions.r.packages.nanoarrow ?? "absent"}`
                      : versions?.r_error ?? (erreur ? "Indisponible" : "Démarrage en cours, quelques secondes")}
                  </span>
                  <span className="v">
                    <Statut etat={etatR} texte={etatR === "pret" ? "Prêt" : etatR === "erreur" ? "Erreur" : "En attente"} />
                  </span>
                </div>
              </div>
              {info?.logs && (etatPython === "erreur" || etatR === "erreur") && (
                <p className="small muted" style={{ marginTop: 12 }}>
                  Journal du moteur : {info.logs}
                </p>
              )}
            </section>

            <section className="stack">
              <h2>Calcul de démonstration</h2>
              <p className="muted" style={{ margin: 0 }}>
                Proportion de filles de 6 à 11 ans scolarisées, sur 612 ménages fictifs. Le calcul est fait par R, comme le seront tous les calculs de
                l'application.
              </p>
              <div className="chips" role="group" aria-label="Type de calcul">
                <button className="chip" aria-pressed={plan === "survey"} onClick={() => setPlan("survey")}>
                  Avec plan d'enquête
                </button>
                <button className="chip" aria-pressed={plan === "simple"} onClick={() => setPlan("simple")}>
                  Échantillon simple
                </button>
              </div>
              <div>
                <button className="btn primary" onClick={lancer} disabled={!toutPret || calculEnCours}>
                  {calculEnCours ? "Calcul en cours" : "Lancer le calcul"}
                </button>
              </div>
              {erreurCalcul && (
                <div className="hint hint-err" role="alert">
                  <Icone etat="erreur" />
                  <div>
                    <div className="t">Le calcul n'a pas abouti</div>
                    <div className="small">{erreurCalcul}</div>
                  </div>
                </div>
              )}
              {calcul && (
                <div className="result">
                  <span className="figure">{pct(calcul.estimate)}</span>
                  <span className="muted">
                    Intervalle de confiance à {fr(calcul.level * 100, 0)} % : {pct(calcul.ci_low)} à {pct(calcul.ci_high)}
                  </span>
                  <span className="small muted">
                    {calcul.successes} filles scolarisées sur {calcul.n}. {calcul.method}.
                  </span>
                  <div>
                    <button className="btn" onClick={() => setScript(!script)} aria-expanded={script}>
                      {script ? "Masquer le script R" : "Voir le script R"}
                    </button>
                  </div>
                  {script && <pre className="code-block">{calcul.script}</pre>}
                </div>
              )}
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
