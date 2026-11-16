// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Indicator tracking table: for the chosen period, what was planned, what was
// achieved in the period and to date, the rate, the status, and the gap explained.

import { Fragment, useEffect, useMemo, useState } from "react";
import { call, Indicator, isEntry, Snapshot, TrackRow } from "../api";
import { useLevels } from "../frameworks";
import { useI18n } from "../i18n";
import { defaultPeriod, periodLabel } from "../monitoring";
import { useProject } from "../state";
import { CrosstabPanel } from "./Crosstab";
import { Empty, Field, Notice, Panel, useValueFormat } from "../ui";

interface Filters {
  period: string | null;
  provisional: boolean;
  place_id: string;
  partner_id: string;
}

export function Tracking() {
  const { t, tn, lang, percent } = useI18n();
  const { snap, setSnap, go, describe } = useProject();
  const levels = useLevels();
  const format = useValueFormat();
  const [chosen, setF] = useState<Filters>({ period: null, provisional: false, place_id: "", partner_id: "" });
  const f = { ...chosen, period: chosen.period ?? (snap ? defaultPeriod(snap.periods) : null) };
  const [rows, setRows] = useState<TrackRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gap, setGap] = useState<Indicator | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [crossing, setCrossing] = useState(false);

  // Recomputed when the filters or the project data change.
  const stamp = snap ? `${snap.submissions.map((s) => s.status).join()}|${snap.indicators.length}` : "";
  useEffect(() => {
    if (!snap || !f.period) return;
    let live = true;
    call<{ rows: TrackRow[] }>("tracking.table", {
      period: f.period,
      provisional: f.provisional,
      place_id: f.place_id || null,
      partner_id: f.partner_id || null,
    })
      .then((r) => live && setRows(r.rows))
      .catch((e) => live && setError(describe(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.period, f.provisional, f.place_id, f.partner_id, stamp]);

  const groups = useMemo(() => {
    if (!snap) return [];
    const entry = snap.indicators.filter(isEntry);
    return snap.framework
      .filter((n) => levels.carries(n.level))
      .map((node) => ({ node, list: entry.filter((i) => i.node_id === node.id) }))
      .filter((g) => g.list.length);
  }, [snap, levels]);

  if (!snap) return null;
  const per = snap.periods.find((p) => p.code === f.period);
  const byId = new Map((rows ?? []).map((r) => [r.indicator_id, r]));
  const gapOf = (indId: string) => snap.gap_comments[indId]?.find((g) => g.period === f.period);
  const rate = (v: number | null) => (v === null ? "" : percent(v, 0));
  const trend = (x: TrackRow["trend"]) => (x === "up" ? "↗" : x === "down" ? "↘" : x === "flat" ? "→" : "");
  const surveys = snap.indicators.filter((i) => !isEntry(i));

  const markReported = async () => {
    if (!per) return;
    try {
      setSnap(await call<Snapshot>("period.mark_reported", { id: per.id, done: !per.reported_at }));
    } catch (e) {
      setError(describe(e));
    }
  };

  if (!snap.periods.length)
    return (
      <div className="inner">
        <h1>{t("nav.tracking")}</h1>
        <Notice>
          {t("rec.noCalendar")}{" "}
          <button className="link" onClick={() => go("setup")}>
            {t("mplan.openSetup")}
          </button>
        </Notice>
      </div>
    );

  return (
    <div className="inner wide">
      <div className="page-head">
        <div>
          <h1>{t("nav.tracking")}</h1>
          <p className="lead">{t("trk.lead")}</p>
        </div>
        <div className="row-actions">
          <button
            className="btn"
            onClick={() => setCrossing(true)}
            disabled={!groups.length}
            data-testid="trk-crosstab"
          >
            {t("xt.open")}
          </button>
          {per && per.end < new Date().toISOString().slice(0, 10) && (
            <button className="btn" onClick={markReported} data-testid="trk-reported">
              {per.reported_at ? t("trk.reportedUndo") : t("trk.reported")}
            </button>
          )}
        </div>
      </div>

      <div className="filters">
        <Field label={t("setup.period")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={f.period ?? ""}
              onChange={(e) => setF({ ...f, period: e.target.value })}
              data-testid="trk-period"
            >
              {snap.periods.map((p) => (
                <option key={p.id} value={p.code}>
                  {periodLabel(p, lang)}
                </option>
              ))}
            </select>
          )}
        </Field>
        {snap.places.length > 0 && (
          <Field label={t("trk.place")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={f.place_id}
                onChange={(e) => setF({ ...f, place_id: e.target.value })}
              >
                <option value="">{t("trk.allPlaces")}</option>
                {snap.places.map((p) => (
                  <option key={p.id} value={p.id}>
                    {" ".repeat(p.level * 3)}
                    {p.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        {snap.partners.length > 0 && (
          <Field label={t("trk.partner")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={f.partner_id}
                onChange={(e) => setF({ ...f, partner_id: e.target.value })}
              >
                <option value="">{t("trk.allPartners")}</option>
                {snap.partners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.acronym || p.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        <label className="check">
          <input
            type="checkbox"
            checked={f.provisional}
            onChange={(e) => setF({ ...f, provisional: e.target.checked })}
            data-testid="trk-provisional"
          />{" "}
          {t("trk.provisional")}
        </label>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {per?.reported_at && <Notice kind="ok">{t("trk.reportedOn", { date: per.reported_at.slice(0, 10) })}</Notice>}

      {groups.length === 0 ? (
        <Empty icon="chart" title={t("trk.empty")} text={t("trk.emptyText")} />
      ) : (
        <div className="grid-scroll">
          <table className="table tracking" data-testid="trk-table">
            <thead>
              <tr>
                <th className="sticky">{t("mplan.indicator")}</th>
                <th>{t("mplan.baseline")}</th>
                <th>{t("trk.targetPeriod")}</th>
                <th>{t("trk.valuePeriod")}</th>
                <th>{t("trk.toDate")}</th>
                <th>{t("trk.targetToDate")}</th>
                <th>{t("trk.rate")}</th>
                <th>{t("mplan.total")}</th>
                <th>{t("trk.status")}</th>
                <th>{t("trk.gap")}</th>
              </tr>
            </thead>
            <tbody>
              {groups.map(({ node, list }) => (
                <Fragment key={node.id}>
                  <tr className="group-row">
                    <td colSpan={10}>
                      {t("common.labelled", {
                        a: [levels.name(node.level), node.code].filter(Boolean).join(" "),
                        b: node.title,
                      })}
                    </td>
                  </tr>
                  {list.map((ind) => {
                    const r = byId.get(ind.id);
                    const g = gapOf(ind.id);
                    const v = (x: number | null | undefined) =>
                      x === null || x === undefined ? "" : format(x, ind.unit);
                    const ms = ind.unit === "milestone";
                    return (
                      <Fragment key={ind.id}>
                        <tr data-testid={`trk-row-${ind.name}`}>
                          <td className="sticky">
                            <button className="link" onClick={() => setOpen(open === ind.id ? null : ind.id)}>
                              {ind.name}
                            </button>
                            <div className="muted small">
                              {t(`indicators.unit_${ind.unit}`)},{" "}
                              {t(`indicators.agg_${r?.mode ?? "sum"}`).toLowerCase()}
                              {r?.provisional && <span className="tag">{t("trk.provisionalTag")}</span>}
                            </div>
                          </td>
                          <td className="num muted">{ms ? "" : v(r?.baseline)}</td>
                          <td className="num">{ms ? "" : v(r?.target_period)}</td>
                          <td className="num" data-testid="trk-value">
                            {ms
                              ? r?.value_period === 1
                                ? t("rec.done")
                                : r?.value_period === 0
                                  ? t("rec.notDone")
                                  : ""
                              : v(r?.value_period)}{" "}
                            <span className="muted">{trend(r?.trend ?? null)}</span>
                            {r?.reason && <div className="muted small">{t(`trk.reason_${r.reason}`)}</div>}
                          </td>
                          <td className="num" data-testid="trk-to-date">
                            <strong>{ms ? "" : v(r?.to_date)}</strong>
                          </td>
                          <td className="num">
                            {ms ? "" : v(r?.target_to_date)}
                            {r?.interpolated && (
                              <span className="muted small" title={t("trk.interpolatedHint")}>
                                {" "}
                                *
                              </span>
                            )}
                          </td>
                          <td className="num">{rate(r?.rate_to_date ?? null)}</td>
                          <td className="num">{ms ? "" : v(r?.target)}</td>
                          <td>
                            <span className={`status-chip status-${r?.status ?? "unknown"}`} data-testid="trk-status">
                              {t(`trk.status_${r?.status ?? "unknown"}`)}
                            </span>
                          </td>
                          <td>
                            <button
                              className={`btn small${r?.status === "late" && !g ? " warn" : ""}`}
                              onClick={() => setGap(ind)}
                              data-testid={`trk-gap-${ind.name}`}
                              title={g?.text}
                            >
                              {g ? t("trk.gapEdit") : t("trk.gapAdd")}
                            </button>
                          </td>
                        </tr>
                        {open === ind.id && r && (
                          <tr className="detail-row">
                            <td colSpan={10}>
                              <Series ind={ind} row={r} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {groups.length > 0 && rows?.some((r) => r.interpolated) && (
        <p className="muted small">* {t("trk.interpolatedHint")}</p>
      )}
      {surveys.length > 0 && (
        <p className="muted small">
          {tn("trk.surveys", surveys.length)}{" "}
          <button className="link" onClick={() => go("overview")}>
            {t("nav.overview")}
          </button>
        </p>
      )}

      {gap && f.period && <GapPanel ind={gap} period={f.period} onClose={() => setGap(null)} />}
      {crossing && (
        <CrosstabPanel
          indicators={groups.flatMap((g) => g.list)}
          period={f.period}
          provisional={f.provisional}
          onClose={() => setCrossing(false)}
        />
      )}
    </div>
  );
}

function Series({ ind, row }: { ind: Indicator; row: TrackRow }) {
  const { t, lang } = useI18n();
  const { snap } = useProject();
  const format = useValueFormat();
  const v = (x: number | null) => (x === null ? "" : format(x, ind.unit));
  const label = (code: string) =>
    periodLabel(
      snap?.periods.find((p) => p.code === code),
      lang,
    );
  const max = Math.max(...row.series.map((s) => Math.max(s.to_date ?? 0, s.target_to_date ?? 0)), 0) || 1;
  return (
    <div className="series">
      <table className="table compact">
        <thead>
          <tr>
            <th>{t("setup.period")}</th>
            <th>{t("trk.targetPeriod")}</th>
            <th>{t("trk.valuePeriod")}</th>
            <th>{t("trk.toDate")}</th>
            <th>{t("trk.targetToDate")}</th>
            <th aria-hidden="true" />
          </tr>
        </thead>
        <tbody>
          {row.series.map((s) => (
            <tr key={s.period} className={s.period === row.period ? "current" : undefined}>
              <td>{label(s.period)}</td>
              <td className="num">{v(s.target)}</td>
              <td className="num">
                {v(s.value)}
                {s.provisional && <span className="muted"> ({t("trk.provisionalTag")})</span>}
              </td>
              <td className="num">{v(s.to_date)}</td>
              <td className="num">{v(s.target_to_date)}</td>
              <td className="bar-cell" aria-hidden="true">
                <span className="bar target" style={{ width: `${((s.target_to_date ?? 0) / max) * 100}%` }} />
                <span className="bar done" style={{ width: `${((s.to_date ?? 0) / max) * 100}%` }} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GapPanel({ ind, period, onClose }: { ind: Indicator; period: string; onClose: () => void }) {
  const { t, lang } = useI18n();
  const { snap, run } = useProject();
  const current = snap?.gap_comments[ind.id]?.find((g) => g.period === period);
  const [text, setText] = useState(current?.text ?? "");
  const save = async () => {
    if (await run("gap.save", { indicator_id: ind.id, period, text })) onClose();
  };
  return (
    <Panel
      title={t("trk.gapTitle", {
        name: ind.name,
        period: periodLabel(
          snap?.periods.find((p) => p.code === period),
          lang,
        ),
      })}
      onClose={onClose}
      testId="gap-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} data-testid="gap-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <p className="muted small">{t("trk.gapHint")}</p>
      <Field label={t("trk.gap")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            data-testid="gap-text"
          />
        )}
      </Field>
    </Panel>
  );
}
