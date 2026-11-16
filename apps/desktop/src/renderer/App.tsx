// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Application shell: sidebar navigation, top bar, and the screen for the current view.

import { useCallback, useEffect, useState } from "react";
import { appInfo, AppInfo, call, EngineCallError, recents, Versions } from "./api";
import { Lang, useI18n } from "./i18n";
import logo from "./logo.svg";
import { Accountability } from "./screens/Accountability";
import { Agenda } from "./screens/Agenda";
import { Analysis } from "./screens/Analysis";
import { Dashboard } from "./screens/Dashboard";
import { Data } from "./screens/Data";
import { Engines, EngineStatus } from "./screens/Engines";
import { Evaluations } from "./screens/Evaluations";
import { Framework } from "./screens/Framework";
import { Home } from "./screens/Home";
import { Indicators } from "./screens/Indicators";
import { Overview } from "./screens/Overview";
import { Plan } from "./screens/Plan";
import { Reception } from "./screens/Reception";
import { Report } from "./screens/Report";
import { Setup } from "./screens/Setup";
import { Tests } from "./screens/Tests";
import { ProjectTodayScreen, WorkspaceToday } from "./screens/Today";
import { Tracking } from "./screens/Tracking";
import { Workplan } from "./screens/Workplan";
import { Workshop } from "./screens/Workshop";
import { TrustDialog } from "./TrustDialog";
import { useProject, View } from "./state";
import { Icon } from "./ui";
import { UpdateBanner } from "./updates";

const LANGS: { code: Lang; label: string; name: string }[] = [
  { code: "fr", label: "FR", name: "Français" },
  { code: "en", label: "EN", name: "English" },
];

// Project menu, in the order of use (specification 3.3).
const NAV: { group?: string; items: { view: View; icon: string }[] }[] = [
  {
    items: [
      { view: "today", icon: "home" },
      { view: "tracking", icon: "gauge" },
      { view: "reception", icon: "open" },
      { view: "agenda", icon: "calendar" },
      { view: "workplan", icon: "list" },
      { view: "accountability", icon: "chat" },
    ],
  },
  {
    group: "nav.group_design",
    items: [
      { view: "framework", icon: "tree" },
      { view: "indicators", icon: "target" },
      { view: "plan", icon: "plan" },
    ],
  },
  {
    group: "nav.group_surveys",
    items: [
      { view: "overview", icon: "chart" },
      { view: "data", icon: "table" },
      { view: "analysis", icon: "chart" },
      { view: "tests", icon: "scale" },
      { view: "workshop", icon: "calc" },
      { view: "evaluations", icon: "clipboard" },
    ],
  },
  {
    items: [
      { view: "report", icon: "doc" },
      { view: "setup", icon: "people" },
    ],
  },
];

const WS_NAV: { view: View; icon: string; label: string }[] = [
  { view: "ws_today", icon: "home", label: "nav.today" },
  { view: "ws_dashboard", icon: "gauge", label: "nav.dashboard" },
  { view: "overview", icon: "folder", label: "nav.projects" },
  { view: "ws_agenda", icon: "calendar", label: "nav.agenda" },
];

export function App() {
  const { t, lang, setLang } = useI18n();
  const { snap, setSnap, view, go, busy, run } = useProject();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [versions, setVersions] = useState<Versions | null>(null);
  const [engineError, setEngineError] = useState<{ key: string; detail: string } | null>(null);
  const [folded, setFolded] = useState(false);

  const fetchVersions = useCallback(() => {
    call<Versions>("system.versions")
      .then(setVersions)
      .catch((e: unknown) =>
        setEngineError(
          e instanceof EngineCallError ? { key: e.key, detail: e.message } : { key: "unknown", detail: String(e) },
        ),
      );
  }, []);

  // The workspace opens on today's work when there are projects to work on.
  useEffect(() => {
    recents()
      .then((list) => {
        if (list.some((r) => r.exists)) go("ws_today");
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    appInfo()
      .then(setInfo)
      .catch(() => undefined);
    fetchVersions();
  }, [fetchVersions]);

  const loadVersions = () => {
    setEngineError(null);
    setVersions(null);
    fetchVersions();
  };

  const ready = !!versions?.r && !engineError && !versions?.r_error;
  const engineState = engineError || versions?.r_error ? "error" : ready ? "ready" : "waiting";

  const toggleTheme = () => {
    const r = document.documentElement;
    const dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark";
  };

  const closeProject = async () => {
    await run("project.close");
    setSnap(null);
    go("overview");
  };

  const counts: Partial<Record<View, number>> = snap
    ? {
        framework: snap.framework.length,
        indicators: snap.indicators.length,
        data: snap.datasets.length,
        workshop: snap.analyses.length,
        reception:
          snap.submissions.filter((s) => s.status === "submitted" || s.status === "review").length || undefined,
      }
    : {};
  const showEngines = view === "engines";
  const wsView = (WS_NAV.find((n) => n.view === view) ?? WS_NAV[1]).label;
  const title = showEngines ? t("engines.title") : snap ? t(`nav.${view}`) : t(wsView);

  return (
    <div className={`app${folded ? " folded" : ""}`}>
      <aside className="side" aria-label={t("nav.label")}>
        <div className="side-top">
          <span className="brand">
            <img src={logo} alt="" width="26" height="26" />
            <span className="mark fold-hide">
              SuiviEval<span>Lab</span>
            </span>
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

        {snap ? (
          <div className="fold-hide side-project">
            <div className="group-title">{t("nav.project")}</div>
            <div className="project-name" title={snap.project.path} data-testid="project-name">
              {snap.project.name}
            </div>
            <nav aria-label={t("nav.steps")}>
              {NAV.map((g, gi) => (
                <div key={gi} className="nav-group">
                  {g.group && <div className="group-title nav-sub">{t(g.group)}</div>}
                  {g.items.map((n) => (
                    <a
                      key={n.view}
                      href={`#${n.view}`}
                      aria-current={view === n.view ? "page" : undefined}
                      onClick={(e) => {
                        e.preventDefault();
                        go(n.view);
                      }}
                      data-testid={`nav-${n.view}`}
                    >
                      <Icon name={n.icon} />
                      <span className="nav-label">{t(`nav.${n.view}`)}</span>
                      {counts[n.view] !== undefined && <span className="nav-count">{counts[n.view]}</span>}
                    </a>
                  ))}
                </div>
              ))}
            </nav>
            <button className="link side-close" onClick={closeProject} data-testid="close-project">
              {t("nav.close")}
            </button>
          </div>
        ) : (
          <nav className="fold-hide" aria-label={t("nav.steps")}>
            {WS_NAV.map((n) => (
              <a
                key={n.view}
                href={`#${n.view}`}
                aria-current={!showEngines && view === n.view ? "page" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  go(n.view);
                }}
                data-testid={`nav-${n.view}`}
              >
                <Icon name={n.icon} />
                <span className="nav-label">{t(n.label)}</span>
              </a>
            ))}
          </nav>
        )}

        <div className="side-foot">
          <button
            className="engine-pill fold-hide"
            onClick={() => go("engines")}
            data-testid="engines-link"
            title={t("engines.title")}
          >
            <EngineStatus
              state={engineState}
              label={
                engineState === "ready"
                  ? t("engines.allReady")
                  : engineState === "error"
                    ? t("engines.problem")
                    : t("engines.starting")
              }
            />
          </button>
          <div className="side-foot-row">
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
        </div>
      </aside>

      <div className="main">
        <div className="bar">
          <div className="crumb">
            SuiviEvalLab <span aria-hidden="true">/</span>{" "}
            {snap && !showEngines && (
              <>
                {snap.project.name} <span aria-hidden="true">/</span>{" "}
              </>
            )}
            <b>{title}</b>
          </div>
          <span className="saved" data-testid="save-state">
            {busy && busy !== "overview" && busy !== "analysis"
              ? t("app.working")
              : snap
                ? t("app.saved")
                : t("app.offline")}
            <span className="muted version">{t("side.version", { version: info?.version ?? "" })}</span>
          </span>
        </div>
        <UpdateBanner />
        <TrustDialog />
        <div
          className={(view === "analysis" || view === "tests" || view === "workshop") && snap ? "col col-split" : "col"}
        >
          {showEngines ? (
            <Engines info={info} versions={versions} error={engineError} onRecheck={loadVersions} />
          ) : !snap ? (
            view === "ws_today" ? (
              <WorkspaceToday />
            ) : view === "ws_agenda" ? (
              <Agenda scope="workspace" />
            ) : view === "ws_dashboard" ? (
              <Dashboard />
            ) : (
              <Home enginesReady={ready} />
            )
          ) : view === "today" ? (
            <ProjectTodayScreen />
          ) : view === "reception" ? (
            <Reception />
          ) : view === "tracking" ? (
            <Tracking />
          ) : view === "agenda" ? (
            <Agenda scope="project" />
          ) : view === "workplan" ? (
            <Workplan />
          ) : view === "accountability" ? (
            <Accountability />
          ) : view === "evaluations" ? (
            <Evaluations />
          ) : view === "setup" ? (
            <Setup />
          ) : view === "framework" ? (
            <Framework />
          ) : view === "indicators" ? (
            <Indicators />
          ) : view === "plan" ? (
            <Plan />
          ) : view === "data" ? (
            <Data />
          ) : view === "analysis" ? (
            <Analysis />
          ) : view === "tests" ? (
            <Tests />
          ) : view === "workshop" ? (
            <Workshop />
          ) : view === "report" ? (
            <Report />
          ) : (
            <Overview />
          )}
        </div>
      </div>
    </div>
  );
}
