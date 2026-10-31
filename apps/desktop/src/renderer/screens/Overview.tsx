// Overview: where the project stands, and the indicator table with progress.

import { useEffect, useState } from "react";
import { OverviewRow, saveSummary } from "../api";
import { useI18n } from "../i18n";
import { useProject, View } from "../state";
import { Empty, Icon, Notice, Progress, StatusTag } from "../ui";

export function Overview() {
  const { t, tn, percent, number } = useI18n();
  const { snap, run, go, error } = useProject();
  const [answer, setAnswer] = useState<{ stamp?: string; rows: OverviewRow[] } | null>(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const stamp = snap?.project.updated_at;
  const path = snap?.project.path;
  const datasetCount = snap?.datasets.length ?? 0;

  useEffect(() => {
    let alive = true;
    run<{ rows: OverviewRow[] }>("analysis.overview", {}, "overview").then((r) => {
      if (!alive) return;
      const list = r?.rows ?? [];
      setAnswer({ stamp, rows: list });
      if (r && path) {
        const count = (s: string) => list.filter((x) => x.status === s).length;
        void saveSummary(path, {
          indicators: list.length,
          achieved: count("achieved"),
          on_track: count("on_track"),
          late: count("late"),
          unknown: count("unknown"),
          datasets: datasetCount,
        });
      }
    });
    return () => {
      alive = false;
    };
  }, [stamp, run, path, datasetCount]);

  const rows = answer && answer.stamp === stamp ? answer.rows : null;
  if (!snap) return null;
  const { project, framework, indicators, datasets } = snap;
  const fmt = (v: number | null, unit: string) =>
    v === null ? t("common.none") : unit === "percent" ? percent(v) : number(v, 2);

  const steps: { view: View; icon: string; label: string; detail: string; done: boolean }[] = [
    {
      view: "framework",
      icon: "tree",
      label: t("nav.framework"),
      detail: tn("overview.frameworkCount", framework.length),
      done: framework.length > 0,
    },
    {
      view: "indicators",
      icon: "target",
      label: t("nav.indicators"),
      detail: tn("overview.indicatorCount", indicators.length),
      done: indicators.length > 0,
    },
    {
      view: "data",
      icon: "table",
      label: t("nav.data"),
      detail: tn("overview.datasetCount", datasets.length),
      done: datasets.length > 0,
    },
    {
      view: "report",
      icon: "doc",
      label: t("nav.report"),
      detail: t("overview.reportHint"),
      done: false,
    },
  ];

  const saveName = async () => {
    if (name.trim() && name.trim() !== project.name) await run("project.rename", { name: name.trim() });
    setEditing(false);
  };

  return (
    <div className="inner wide">
      <div>
        {editing ? (
          <input
            className="input title-input"
            value={name}
            autoFocus
            onChange={(e) => setName(e.target.value)}
            onBlur={saveName}
            onKeyDown={(e) => {
              if (e.key === "Enter") void saveName();
              if (e.key === "Escape") setEditing(false);
            }}
            aria-label={t("home.projectName")}
          />
        ) : (
          <h1
            className="editable"
            onClick={() => {
              setName(project.name);
              setEditing(true);
            }}
            title={t("overview.rename")}
          >
            {project.name}
          </h1>
        )}
        <p className="lead small-lead">{project.path}</p>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      <section className="steps">
        {steps.map((s) => (
          <button key={s.view} className={`step${s.done ? " done" : ""}`} onClick={() => go(s.view)}>
            <Icon name={s.icon} />
            <span className="step-label">{s.label}</span>
            <span className="step-detail">{s.detail}</span>
          </button>
        ))}
      </section>

      <section>
        <div className="section-head">
          <h2>{t("overview.indicatorsTitle")}</h2>
          {indicators.length > 0 && (
            <button className="btn" onClick={() => go("analysis")}>
              {t("overview.toAnalysis")}
            </button>
          )}
        </div>
        {indicators.length === 0 ? (
          <Empty
            icon="target"
            title={t("overview.noIndicators")}
            text={t("overview.noIndicatorsText")}
            action={
              <button className="btn primary" onClick={() => go(framework.length ? "indicators" : "framework")}>
                {framework.length ? t("indicators.add") : t("framework.start")}
              </button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table" data-testid="overview-table">
              <thead>
                <tr>
                  <th>{t("overview.colIndicator")}</th>
                  <th className="num">{t("overview.colBaseline")}</th>
                  <th className="num">{t("overview.colCurrent")}</th>
                  <th className="num">{t("overview.colTarget")}</th>
                  <th>{t("overview.colProgress")}</th>
                  <th>{t("overview.colStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {indicators.map((ind) => {
                  const r = rows?.find((x) => x.indicator_id === ind.id);
                  const node = framework.find((n) => n.id === ind.node_id);
                  return (
                    <tr key={ind.id} className="clickable" onClick={() => go("analysis", ind.id)}>
                      <td>
                        <div className="cell-title">{ind.name}</div>
                        <div className="cell-sub">{node ? `${t(`levels.${node.level}`)} ${node.code}`.trim() : ""}</div>
                      </td>
                      <td className="num">{r ? fmt(r.baseline, ind.unit) : "…"}</td>
                      <td className="num">{r ? fmt(r.current, ind.unit) : "…"}</td>
                      <td className="num">{fmt(ind.target, ind.unit)}</td>
                      <td>{r ? <Progress value={r.achievement} /> : null}</td>
                      <td>
                        {r ? (
                          <StatusTag status={r.status} />
                        ) : (
                          <span className="muted small">{t("common.computing")}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {indicators.length > 0 && datasets.length === 0 && (
          <Notice>
            {t("overview.noData")}{" "}
            <button className="link" onClick={() => go("data")}>
              {t("data.import")}
            </button>
          </Notice>
        )}
      </section>
    </div>
  );
}
