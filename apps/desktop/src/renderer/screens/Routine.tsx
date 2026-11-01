// Routine monitoring indicator: value to date, chart, and the grid of values per
// period (typed, or pasted from Excel). Saved as a whole.

import { useState } from "react";
import { call, Estimate, IndicatorAnalysis, RoutinePeriod } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { IconButton, Notice, ResultChart, StatusTag, useValueFormat } from "../ui";

export interface RoutineAnalysis extends IndicatorAnalysis {
  source: "routine";
  aggregation: "sum" | "last" | "mean";
  periods: RoutinePeriod[];
  current_period: string | null;
  planned_to_date: number | null;
  pace: number | null;
  by_total: Record<string, number>;
}

type Row = { period: string; end: string; achieved: string; planned: string; by: Record<string, string>; note: string };

const toRow = (p: RoutinePeriod, percent: boolean): Row => {
  const v = (x: number | null | undefined) =>
    x === null || x === undefined ? "" : String(+(percent ? x * 100 : x).toFixed(4));
  return {
    period: p.period,
    end: p.end ?? "",
    achieved: v(p.achieved),
    planned: v(p.planned),
    by: Object.fromEntries(Object.entries(p.by ?? {}).map(([k, x]) => [k, v(x)])),
    note: p.note ?? "",
  };
};

export function Routine({ a: initial }: { a: RoutineAnalysis }) {
  const { t, number, percent } = useI18n();
  const { run, describe } = useProject();
  const format = useValueFormat();
  const [a, setA] = useState(initial);
  const ind = a.indicator;
  const pct = ind.unit === "percent";
  const cats = ind.categories ?? [];
  const fmt = (v: number | null | undefined) => (v === null || v === undefined ? "" : format(v, ind.unit));
  const [rows, setRows] = useState<Row[]>(() => a.periods.map((p) => toRow(p, pct)));
  const [dirty, setDirty] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [pasted, setPasted] = useState("");
  const [note, setNote] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const edit = (i: number, patch: Partial<Row>) => {
    setRows(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
    setDirty(true);
  };
  const values = () =>
    rows
      .filter((r) => r.period.trim())
      .map((r) => ({ period: r.period, end: r.end, achieved: r.achieved, planned: r.planned, by: r.by, note: r.note }));

  const save = async () => {
    const res = await run<{ saved: number; analysis: RoutineAnalysis }>("routine.save", {
      indicator_id: ind.id,
      values: values(),
    });
    if (res) {
      setA(res.analysis);
      setRows(res.analysis.periods.map((p) => toRow(p, pct)));
      setDirty(false);
      setNote({ kind: "ok", text: t("routine.saved", { n: res.saved }) });
    }
  };

  const readPaste = async () => {
    try {
      const res = await call<{ values: RoutinePeriod[] }>("routine.parse", { indicator_id: ind.id, text: pasted });
      setRows(res.values.map((p) => toRow(p, pct)));
      setDirty(true);
      setPasting(false);
      setPasted("");
      setNote({ kind: "ok", text: t("routine.pastedRows", { n: res.values.length }) });
    } catch (e) {
      setNote({ kind: "error", text: describe(e) });
    }
  };

  const done = a.periods.filter((p) => p.to_date !== null && p.to_date !== undefined);
  const bars = done.map((p) => ({
    label: p.period,
    value: { estimate: p.to_date ?? null, ci_low: null, ci_high: null, n: 0 } as Estimate,
  }));

  return (
    <div className="stack-lg" data-testid="routine">
      <div className="kpis">
        <div className="kpi">
          <span className="kpi-label">{t("routine.toDate")}</span>
          <span className="kpi-value" data-testid="current-value">
            {a.current === null ? "" : fmt(a.current)}
          </span>
          <span className="kpi-sub">
            {a.current_period ? t("routine.atPeriod", { period: a.current_period }) : t("routine.noValue")}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("overview.colTarget")}</span>
          <span className="kpi-value">{a.target === null ? "" : fmt(a.target)}</span>
          <span className="kpi-sub">
            {a.achievement !== null ? t("analysis.achievement", { rate: percent(a.achievement, 0) }) : ""}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("routine.plannedToDate")}</span>
          <span className="kpi-value">{a.planned_to_date === null ? "" : fmt(a.planned_to_date)}</span>
          <span className="kpi-sub">{a.pace !== null ? t("routine.pace", { rate: percent(a.pace, 0) }) : ""}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("overview.colStatus")}</span>
          <span className="kpi-value small-kpi">
            <StatusTag status={a.status} />
          </span>
          <span className="kpi-sub">{t(`indicators.agg_${a.aggregation}`)}</span>
        </div>
      </div>
      {Object.keys(a.by_total).length > 0 && (
        <p className="muted">
          {t("routine.breakdown", {
            parts: Object.entries(a.by_total)
              .map(([k, v]) => `${k} ${fmt(v)}`)
              .join(", "),
          })}
        </p>
      )}
      {bars.length > 0 && <ResultChart bars={bars} target={a.target} unit={ind.unit} />}

      <div className="section-head">
        <h2>{t("routine.values")}</h2>
        <div className="row-actions">
          <button className="btn" onClick={() => setPasting(!pasting)} data-testid="routine-paste">
            {t("routine.paste")}
          </button>
          <button className="btn primary" onClick={save} disabled={!dirty} data-testid="routine-save">
            {t("common.save")}
          </button>
        </div>
      </div>
      <p className="muted small">{pct ? t("routine.helpPercent") : t("routine.help")}</p>
      {note && <Notice kind={note.kind}>{note.text}</Notice>}
      {pasting && (
        <div className="stack paste-box">
          <p className="muted small">
            {t("routine.pasteHelp", {
              columns: [
                t("routine.colPeriod"),
                t("routine.colEnd"),
                t("routine.colAchieved"),
                t("routine.colPlanned"),
                ...cats,
              ].join(", "),
            })}
          </p>
          <textarea
            className="input mono"
            rows={6}
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            data-testid="routine-paste-text"
          />
          <div className="row-actions start">
            <button className="btn" onClick={readPaste} disabled={!pasted.trim()} data-testid="routine-paste-read">
              {t("routine.pasteRead")}
            </button>
          </div>
        </div>
      )}
      <div className="grid-wrap">
        <table className="table compact routine-grid" data-testid="routine-grid">
          <thead>
            <tr>
              <th>{t("routine.colPeriod")}</th>
              <th>{t("routine.colEnd")}</th>
              <th>{t("routine.colAchieved")}</th>
              {cats.map((c) => (
                <th key={c}>{c}</th>
              ))}
              <th>{t("routine.colPlanned")}</th>
              <th>{t("routine.colToDate")}</th>
              <th>{t("routine.colNote")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const saved = a.periods.find((p) => p.period === r.period);
              return (
                <tr key={i}>
                  <td>
                    <input
                      className="input"
                      value={r.period}
                      placeholder="2026-T1"
                      onChange={(e) => edit(i, { period: e.target.value })}
                      aria-label={t("routine.colPeriod")}
                      data-testid={`routine-period-${i}`}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      type="date"
                      value={r.end}
                      onChange={(e) => edit(i, { end: e.target.value })}
                      aria-label={t("routine.colEnd")}
                    />
                  </td>
                  <td>
                    <input
                      className="input num"
                      inputMode="decimal"
                      value={r.achieved}
                      onChange={(e) => edit(i, { achieved: e.target.value })}
                      aria-label={t("routine.colAchieved")}
                      placeholder={cats.length && !pct ? t("routine.sumOfCategories") : ""}
                      data-testid={`routine-achieved-${i}`}
                    />
                  </td>
                  {cats.map((c) => (
                    <td key={c}>
                      <input
                        className="input num"
                        inputMode="decimal"
                        value={r.by[c] ?? ""}
                        onChange={(e) => edit(i, { by: { ...r.by, [c]: e.target.value } })}
                        aria-label={c}
                      />
                    </td>
                  ))}
                  <td>
                    <input
                      className="input num"
                      inputMode="decimal"
                      value={r.planned}
                      onChange={(e) => edit(i, { planned: e.target.value })}
                      aria-label={t("routine.colPlanned")}
                      data-testid={`routine-planned-${i}`}
                    />
                  </td>
                  <td className="num muted">{dirty ? "" : fmt(saved?.to_date)}</td>
                  <td>
                    <input
                      className="input"
                      value={r.note}
                      onChange={(e) => edit(i, { note: e.target.value })}
                      aria-label={t("routine.colNote")}
                    />
                  </td>
                  <td>
                    <IconButton
                      icon="trash"
                      label={t("common.delete")}
                      onClick={() => {
                        setRows(rows.filter((_, k) => k !== i));
                        setDirty(true);
                      }}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="row-actions start">
        <button
          className="btn"
          onClick={() => {
            setRows([...rows, { period: "", end: "", achieved: "", planned: "", by: {}, note: "" }]);
            setDirty(true);
          }}
          data-testid="routine-add"
        >
          {t("routine.addPeriod")}
        </button>
        {dirty && <span className="muted small">{t("routine.unsaved")}</span>}
      </div>
      <p className="muted small">{t("routine.method", { n: number(a.periods.length, 0) })}</p>
    </div>
  );
}
