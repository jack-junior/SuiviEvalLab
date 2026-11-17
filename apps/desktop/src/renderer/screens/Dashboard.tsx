// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Portfolio dashboard (module M14): one card per project with time, physical and
// financial progress and a global status, the overview of the portfolio, common
// indicators, packs received from other offices, and the synthesis note.

import { useEffect, useMemo, useState } from "react";
import {
  call,
  Dashboard as Data,
  pick,
  PortfolioCard,
  PortfolioSettings,
  PortfolioStatus,
  portfolioDashboard,
  portfolioExport,
  openFile,
  recentToken,
} from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Empty, Field, Icon, IconButton, Notice, Panel, Progress, rowOpen } from "../ui";

const STATUSES: PortfolioStatus[] = ["on_track", "watch", "difficulty", "unknown"];
type Filter = { donor: string; country: string; sector: string; manager: string; status: string };

export function Dashboard() {
  const { t, lang, number, day } = useI18n();
  const { run, go, describe } = useProject();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>({ donor: "", country: "", sector: "", manager: "", status: "" });
  const [note, setNote] = useState<{ token: string; name: string } | null>(null);
  const [settings, setSettings] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    portfolioDashboard()
      .then((d) => live && setData(d))
      .catch((e) => live && setError(describe(e)));
    return () => {
      live = false;
    };
  }, [version, describe]);

  const cards = useMemo(() => {
    if (!data) return [];
    return data.cards.filter(
      (c) =>
        (!filter.donor || (c.profile.donors ?? []).some((d) => d.name === filter.donor)) &&
        (!filter.country || (c.profile.countries ?? []).includes(filter.country)) &&
        (!filter.sector || (c.profile.sectors ?? []).includes(filter.sector)) &&
        (!filter.manager || c.profile.manager === filter.manager) &&
        (!filter.status || c.status === filter.status),
    );
  }, [data, filter]);

  const open = async (c: PortfolioCard) => {
    if (c.source !== "file") return;
    const token = await recentToken(c.path);
    if (token && (await run("project.open", { file_token: token }))) go("today");
  };
  const exportAs = async (kind: "note" | "html" | "pdf") => {
    setNote(null);
    const ext = { note: "docx", html: "html", pdf: "pdf" }[kind];
    const file = await pick(
      kind === "note" ? "report-save" : kind === "html" ? "html-save" : "pdf-save",
      `${t("dash.fileName")}.${ext}`,
    );
    if (!file) return;
    try {
      await portfolioExport(kind, file.token, lang);
      setNote(file);
    } catch (e) {
      setError(describe(e));
    }
  };
  const importPack = async () => {
    const file = await pick("pack-open");
    if (!file) return;
    try {
      await call("portfolio.import_pack", { file_token: file.token });
      setVersion(version + 1);
    } catch (e) {
      setError(describe(e));
    }
  };
  const removePack = async (uid: string) => {
    await call("portfolio.remove_pack", { uid });
    setVersion(version + 1);
  };

  const options = (key: "donor" | "country" | "sector") => Object.keys(data?.distribution[key] ?? {});
  const managers = [...new Set((data?.cards ?? []).map((c) => c.profile.manager).filter(Boolean))] as string[];
  const o = data?.overview;
  const pc = (x: number | null) => (x === null ? "-" : `${Math.round(x * 100)} %`);

  return (
    <div className="inner wide stack-lg" data-testid="dashboard">
      <div className="page-head">
        <div>
          <h1>{t("nav.dashboard")}</h1>
          <p className="lead">{t("dash.lead")}</p>
        </div>
        <div className="row-actions">
          <button className="btn" onClick={() => setSettings(true)}>
            {t("dash.settings")}
          </button>
          <button className="btn" onClick={importPack} data-testid="dash-import-pack">
            {t("dash.importPack")}
          </button>
        </div>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!data ? (
        !error && <p className="muted">{t("dash.loading")}</p>
      ) : data.cards.length === 0 ? (
        <Empty icon="chart" title={t("dash.none")} text={t("dash.noneText")} />
      ) : (
        <>
          <div className="kpis">
            <div className="kpi">
              <span className="kpi-label">{t("dash.projects")}</span>
              <span className="kpi-value">{o!.projects}</span>
              <span className="kpi-sub">
                {STATUSES.filter((s) => o!.by_status[s])
                  .map((s) => `${o!.by_status[s]} ${t(`dash.st_${s}`).toLowerCase()}`)
                  .join(", ")}
              </span>
            </div>
            <div className="kpi">
              <span className="kpi-label">{t("dash.late")}</span>
              <span className="kpi-value">{o!.late_indicators + o!.late_activities}</span>
              <span className="kpi-sub">{t("dash.lateSub", { i: o!.late_indicators, a: o!.late_activities })}</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">{t("dash.deadlines")}</span>
              <span className="kpi-value">{o!.deadlines_30}</span>
              <span className="kpi-sub">{t("dash.feedbackOverdue", { n: o!.feedback_overdue })}</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">{t("dash.budget")}</span>
              <span className="kpi-value">{o!.planned ? pc(o!.spent / o!.planned) : "-"}</span>
              <span className="kpi-sub">{t("dash.budgetSub")}</span>
            </div>
          </div>

          <div className="row-actions start wrap" data-testid="dash-filters">
            {(["donor", "country", "sector"] as const).map((k) =>
              options(k).length ? (
                <select
                  key={k}
                  className="input"
                  style={{ maxWidth: 200 }}
                  value={filter[k]}
                  onChange={(e) => setFilter({ ...filter, [k]: e.target.value })}
                  aria-label={t(`dash.f_${k}`)}
                >
                  <option value="">{t(`dash.f_${k}`)}</option>
                  {options(k).map((x) => (
                    <option key={x} value={x}>
                      {x} ({data.distribution[k][x]})
                    </option>
                  ))}
                </select>
              ) : null,
            )}
            {managers.length > 0 && (
              <select
                className="input"
                style={{ maxWidth: 200 }}
                value={filter.manager}
                onChange={(e) => setFilter({ ...filter, manager: e.target.value })}
                aria-label={t("dash.f_manager")}
              >
                <option value="">{t("dash.f_manager")}</option>
                {managers.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            )}
            <select
              className="input"
              style={{ maxWidth: 200 }}
              value={filter.status}
              onChange={(e) => setFilter({ ...filter, status: e.target.value })}
              aria-label={t("dash.f_status")}
            >
              <option value="">{t("dash.f_status")}</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`dash.st_${s}`)}
                </option>
              ))}
            </select>
          </div>

          <div className="table-wrap">
            <table className="table" data-testid="dash-table">
              <thead>
                <tr>
                  <th>{t("dash.project")}</th>
                  <th>{t("dash.time")}</th>
                  <th>{t("dash.indicators")}</th>
                  <th>{t("dash.activities")}</th>
                  <th>{t("dash.financial")}</th>
                  <th>{t("dash.next")}</th>
                  <th>{t("dash.status")}</th>
                </tr>
              </thead>
              <tbody>
                {cards.map((c) => (
                  <tr
                    key={c.path}
                    className={c.source === "file" ? "clickable" : ""}
                    {...(c.source === "file" ? rowOpen(() => void open(c)) : {})}
                    data-testid="dash-row"
                  >
                    <td style={{ borderLeft: `4px solid ${c.profile.color ?? "var(--ligne)"}` }}>
                      <strong>{c.name}</strong>
                      <div className="muted small">
                        {[
                          (c.profile.donors ?? []).map((d) => d.name).join(", "),
                          (c.profile.countries ?? []).join(", "),
                        ]
                          .filter(Boolean)
                          .join(" / ")}
                        {c.source === "pack" && (
                          <>
                            {" "}
                            <span className="tag">{t("dash.packTag", { date: day(c.exported_at) })}</span>
                          </>
                        )}
                      </div>
                    </td>
                    <td>
                      <Progress value={c.time} />
                    </td>
                    <td>
                      <Progress value={c.indicators_on_track} />
                      <div className="muted small">{t("dash.onTrackOf", { n: c.indicators_judged })}</div>
                    </td>
                    <td>
                      <Progress value={c.physical} />
                      {c.late_activities > 0 && (
                        <div className="muted small">{t("dash.lateN", { n: c.late_activities })}</div>
                      )}
                    </td>
                    <td>
                      <Progress value={c.financial} />
                    </td>
                    <td className="small">
                      {c.next_deadline
                        ? t(c.next_deadline.kind === "data" ? "ws.nextData" : "ws.nextReport", {
                            period: lang === "en" ? c.next_deadline.label_en : c.next_deadline.label_fr,
                            when: day(c.next_deadline.date),
                          })
                        : ""}
                    </td>
                    <td>
                      <span
                        className={`status-chip pf-${c.status}`}
                        title={c.reasons.map((r) => t(`dash.reason_${r}`)).join(", ")}
                      >
                        {t(`dash.st_${c.status}`)}
                      </span>
                      {c.reasons.length > 0 && (
                        <div className="muted small">{c.reasons.map((r) => t(`dash.reason_${r}`)).join(", ")}</div>
                      )}
                      {c.source === "pack" && (
                        <IconButton icon="close" label={t("dash.removePack")} onClick={() => void removePack(c.uid)} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            {t("dash.formula", {
              a: pc(data.settings.indicators_on_track),
              b: pc(data.settings.indicators_difficulty),
              m: pc(data.settings.financial_margin),
              l: pc(data.settings.late_activities),
            })}
          </p>

          {data.common.length > 0 && (
            <section className="stack" data-testid="dash-common">
              <h2>{t("dash.common")}</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("dash.indicator")}</th>
                    <th>{t("dash.byProject")}</th>
                    <th className="num">{t("dash.total")}</th>
                    <th className="num">{t("dash.target")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.common.map((x) => (
                    <tr key={x.library_id}>
                      <td>{x.name}</td>
                      <td className="small">
                        {x.projects
                          .map((p) => `${p.name} : ${p.to_date === null ? "-" : number(p.to_date, 0)}`)
                          .join(", ")}
                      </td>
                      <td className="num">
                        {x.total === null ? (
                          <span className="muted small">{t("dash.notAdditive")}</span>
                        ) : (
                          number(x.total, 0)
                        )}
                        {x.double_count_possible && <div className="muted small">{t("dash.maxPeople")}</div>}
                      </td>
                      <td className="num">{x.target ? number(x.target, 0) : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section className="stack">
            <h2>{t("dash.export")}</h2>
            <div className="row-actions start">
              <button className="btn" onClick={() => exportAs("note")} data-testid="dash-note">
                <Icon name="doc" /> {t("dash.note")}
              </button>
              <button className="btn" onClick={() => exportAs("pdf")}>
                <Icon name="download" /> PDF
              </button>
              <button className="btn" onClick={() => exportAs("html")}>
                <Icon name="download" /> {t("dash.html")}
              </button>
            </div>
            {note && (
              <Notice kind="ok">
                <span data-testid="dash-done">{t("exp.done", { name: note.name })}</span>{" "}
                <button className="link" onClick={() => openFile(note.token)}>
                  {t("report.open")}
                </button>
              </Notice>
            )}
          </section>
        </>
      )}
      {settings && data && (
        <SettingsPanel
          current={data.settings}
          onClose={(changed) => {
            setSettings(false);
            if (changed) setVersion(version + 1);
          }}
        />
      )}
    </div>
  );
}

function SettingsPanel({ current, onClose }: { current: PortfolioSettings; onClose: (changed: boolean) => void }) {
  const { t } = useI18n();
  const { describe } = useProject();
  const [v, setV] = useState<Record<keyof PortfolioSettings, string>>(
    Object.fromEntries(Object.entries(current).map(([k, x]) => [k, String(Math.round(x * 100))])) as Record<
      keyof PortfolioSettings,
      string
    >,
  );
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    try {
      await call("portfolio.settings", {
        settings: Object.fromEntries(Object.entries(v).map(([k, x]) => [k, Number(x) / 100])),
      });
      onClose(true);
    } catch (e) {
      setError(describe(e));
    }
  };
  return (
    <Panel
      title={t("dash.settings")}
      onClose={() => onClose(false)}
      footer={
        <>
          <span className="spacer" />
          <button className="btn" onClick={() => onClose(false)}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save}>
            {t("common.save")}
          </button>
        </>
      }
    >
      {error && <Notice kind="error">{error}</Notice>}
      <p className="muted small">{t("dash.settingsLead")}</p>
      {(Object.keys(v) as (keyof PortfolioSettings)[]).map((k) => (
        <Field key={k} label={t(`dash.set_${k}`)}>
          {(id) => (
            <input
              id={id}
              className="input num"
              style={{ maxWidth: 120 }}
              inputMode="numeric"
              value={v[k]}
              onChange={(e) => setV({ ...v, [k]: e.target.value.replace(/[^\d]/g, "") })}
            />
          )}
        </Field>
      ))}
    </Panel>
  );
}
