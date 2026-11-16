// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Indicator with values received period by period: value to date, chart and the
// values by period. The values themselves are entered in the Reception screen.

import { Estimate, IndicatorAnalysis } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { ResultChart, StatusTag, useValueFormat } from "../ui";

export interface RoutinePeriodRow {
  period: string;
  code: string;
  achieved: number | null;
  planned: number | null;
  to_date: number | null;
  planned_to_date: number | null;
  provisional: boolean;
}

export interface RoutineAnalysis extends IndicatorAnalysis {
  source: "routine";
  aggregation: "sum" | "last" | "mean" | "max";
  periods: RoutinePeriodRow[];
  current_period: string | null;
  planned_to_date: number | null;
  pace: number | null;
  by_total: Record<string, number>;
}

export function Routine({ a }: { a: RoutineAnalysis }) {
  const { t, percent } = useI18n();
  const { go } = useProject();
  const format = useValueFormat();
  const ind = a.indicator;
  const fmt = (v: number | null | undefined) => (v === null || v === undefined ? "" : format(v, ind.unit));

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
        <button className="btn" onClick={() => go("reception")} data-testid="routine-reception">
          {t("routine.toReception")}
        </button>
      </div>
      <table className="table compact" data-testid="routine-table">
        <thead>
          <tr>
            <th>{t("routine.colPeriod")}</th>
            <th>{t("routine.colPlanned")}</th>
            <th>{t("routine.colAchieved")}</th>
            <th>{t("routine.toDate")}</th>
            <th>{t("routine.plannedToDate")}</th>
          </tr>
        </thead>
        <tbody>
          {a.periods.map((p) => (
            <tr key={p.code}>
              <td>{p.period}</td>
              <td className="num">{fmt(p.planned)}</td>
              <td className="num">
                {fmt(p.achieved)}
                {p.provisional && <span className="muted"> ({t("trk.provisionalTag")})</span>}
              </td>
              <td className="num">{fmt(p.to_date)}</td>
              <td className="num">{fmt(p.planned_to_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
