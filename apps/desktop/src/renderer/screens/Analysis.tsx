// Analysis by indicator: results per round with intervals, comparison test,
// breakdown, and the method with its R script. Every figure shows its source.

import { useEffect, useState } from "react";
import { IndicatorAnalysis } from "../api";
import { useI18n } from "../i18n";
import { useLabels } from "../labels";
import { useProject } from "../state";
import { Empty, Notice, ResultChart, StatusTag, useValueFormat } from "../ui";
import { useLevels } from "../frameworks";
import { Routine, RoutineAnalysis } from "./Routine";

type Tab = "results" | "breakdown" | "method";

export function Analysis() {
  const { t } = useI18n();
  const levels = useLevels();
  const { snap, focus, go, run, error } = useProject();
  const [answer, setAnswer] = useState<{ key: string; data: IndicatorAnalysis | null } | null>(null);
  const [tab, setTab] = useState<Tab>("results");
  const indicators = snap?.indicators ?? [];
  const selected = indicators.find((i) => i.id === focus) ?? indicators[0];
  const key = `${selected?.id}|${snap?.project.updated_at}`;
  const selectedId = selected?.id;

  useEffect(() => {
    if (!selectedId) return;
    let alive = true;
    run<IndicatorAnalysis>("analysis.indicator", { id: selectedId }, "analysis").then((r) => {
      if (alive) setAnswer({ key, data: r });
    });
    return () => {
      alive = false;
    };
  }, [selectedId, key, run]);
  const loading = answer?.key !== key;
  const data = answer?.data ?? null;

  if (!snap) return null;
  if (!indicators.length)
    return (
      <div className="inner wide">
        <h1>{t("nav.analysis")}</h1>
        <Empty
          icon="chart"
          title={t("analysis.emptyTitle")}
          text={t("analysis.emptyText")}
          action={
            <button className="btn primary" onClick={() => go("indicators")}>
              {t("indicators.add")}
            </button>
          }
        />
      </div>
    );

  return (
    <div className="split">
      <aside className="split-list" aria-label={t("nav.indicators")}>
        {snap.framework
          .filter((n) => indicators.some((i) => i.node_id === n.id))
          .map((n) => (
            <div key={n.id} className="split-group">
              <div className="split-group-title">
                {levels.name(n.level)} {n.code}
              </div>
              {indicators
                .filter((i) => i.node_id === n.id)
                .map((i) => (
                  <button
                    key={i.id}
                    className="split-item"
                    aria-current={i.id === selected?.id ? "true" : undefined}
                    onClick={() => go("analysis", i.id)}
                    data-testid="analysis-item"
                  >
                    {i.name}
                  </button>
                ))}
            </div>
          ))}
      </aside>
      <div className="split-main">
        <div className="inner wide">
          {selected && (
            <div>
              <span className="card-kicker">{t(`indicators.unit_${selected.unit}`)}</span>
              <h1 className="h1-small">{selected.name}</h1>
              {selected.definition && <p className="lead small-lead">{selected.definition}</p>}
            </div>
          )}
          {error && <Notice kind="error">{error}</Notice>}
          <div
            className="tabs"
            role="tablist"
            style={selected?.source_type === "routine" ? { display: "none" } : undefined}
          >
            {(["results", "breakdown", "method"] as Tab[]).map((k) => (
              <button
                key={k}
                role="tab"
                className="tab"
                aria-selected={tab === k}
                onClick={() => setTab(k)}
                data-testid={`atab-${k}`}
              >
                {t(`analysis.tab_${k}`)}
              </button>
            ))}
          </div>
          {loading && !data && <p className="muted">{t("common.computing")}</p>}
          {data && data.indicator.id === selected?.id && "source" in data && (
            <div className={loading ? "dim" : undefined}>
              <Routine key={answer?.key} a={data as RoutineAnalysis} />
            </div>
          )}
          {data && data.indicator.id === selected?.id && !("source" in data) && (
            <div className={loading ? "dim" : undefined}>
              {tab === "results" && <Results a={data} />}
              {tab === "breakdown" && <Breakdown a={data} />}
              {tab === "method" && <Method a={data} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function useFmt(unit: string) {
  const format = useValueFormat();
  return (v: number | null | undefined, digits?: number) =>
    v === null || v === undefined ? "" : format(v, unit, unit === "percent" ? (digits ?? 1) : undefined);
}

function Results({ a }: { a: IndicatorAnalysis }) {
  const { t, number, percent } = useI18n();
  const { go } = useProject();
  const ind = a.indicator;
  const fmt = useFmt(ind.unit);
  const usable = a.rounds.filter((r) => !r.result.error_key);
  const missing = a.rounds.filter((r) => r.result.error_key);
  const c = a.comparison && !a.comparison.error_key ? a.comparison : null;
  const pts = (v: number) =>
    ind.unit === "percent" ? `${number(v * 100, 1)} ${t("analysis.points")}` : number(v, ind.unit === "count" ? 0 : 2);
  const diffNum = (v: number | null) =>
    v === null ? "" : ind.unit === "percent" ? number(v * 100, 1) : number(v, ind.unit === "count" ? 0 : 2);

  if (!ind.column)
    return (
      <Empty
        icon="target"
        title={t("analysis.noRule")}
        text={t("analysis.noRuleText")}
        action={
          <button className="btn primary" onClick={() => go("indicators", ind.node_id)}>
            {t("analysis.defineRule")}
          </button>
        }
      />
    );
  if (!usable.length)
    return <Empty icon="table" title={t("analysis.noData")} text={t("analysis.noDataText", { column: ind.column })} />;

  return (
    <div className="stack-lg">
      <div className="kpis">
        <div className="kpi">
          <span className="kpi-label">{t("overview.colBaseline")}</span>
          <span className="kpi-value">{fmt(a.baseline) || t("common.none")}</span>
          <span className="kpi-sub">
            {a.baseline_source === "manual" ? t("analysis.manual") : a.baseline_source ? t("analysis.fromData") : ""}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("overview.colCurrent")}</span>
          <span className="kpi-value" data-testid="current-value">
            {fmt(a.current) || t("common.none")}
          </span>
          <span className="kpi-sub">{a.current_round ? t(`rounds.${a.current_round}`) : ""}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("overview.colTarget")}</span>
          <span className="kpi-value">{fmt(a.target) || t("common.none")}</span>
          <span className="kpi-sub">
            {a.achievement !== null ? t("analysis.achievement", { rate: percent(a.achievement, 0) }) : ""}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("overview.colStatus")}</span>
          <span className="kpi-value small-kpi">
            <StatusTag status={a.status} />
          </span>
        </div>
      </div>

      <ResultChart
        bars={usable.map((r) => ({ label: t(`rounds.${r.round}`), value: r.result }))}
        target={a.target}
        unit={ind.unit}
      />

      <div className="table-wrap">
        <table className="table" data-testid="rounds-table">
          <thead>
            <tr>
              <th>{t("analysis.colRound")}</th>
              <th className="num">{t("analysis.colValue")}</th>
              <th className="num">{t("analysis.colCI")}</th>
              <th className="num">{t("analysis.colN")}</th>
            </tr>
          </thead>
          <tbody>
            {usable.map((r) => (
              <tr key={r.dataset_id}>
                <td>
                  <div className="cell-title">{t(`rounds.${r.round}`)}</div>
                  <button className="cell-sub link" onClick={() => go("data", r.dataset_id)}>
                    {r.name}
                  </button>
                </td>
                <td className="num strong">{fmt(r.result.estimate)}</td>
                <td className="num">
                  {t("analysis.ciRange", { low: fmt(r.result.ci_low), high: fmt(r.result.ci_high) })}
                </td>
                <td className="num">{number(r.result.n, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {missing.length > 0 && (
        <Notice>{t("analysis.missingIn", { names: missing.map((m) => m.name).join(", "), column: ind.column })}</Notice>
      )}

      {c ? (
        <section className="compare" data-testid="comparison">
          <h2>{t("analysis.compareTitle")}</h2>
          {c.warning === "weights_scale" && c.mean_weights && (
            <div className="notice notice-error" role="alert" data-testid="weights-scale">
              {t("analysis.weightsScale", { a: number(c.mean_weights[0], 2), b: number(c.mean_weights[1], 2) })}
            </div>
          )}
          {c.p_value === null ? (
            <p>
              {t("analysis.compareDescriptive", {
                a: fmt(c.a.estimate),
                b: fmt(c.b.estimate),
                direction: c.difference >= 0 ? t("analysis.up") : t("analysis.down"),
                diff: pts(Math.abs(c.difference)),
              })}
            </p>
          ) : (
            <p>
              {t("analysis.compareSentence", {
                a: fmt(c.a.estimate),
                b: fmt(c.b.estimate),
                direction: c.difference >= 0 ? t("analysis.up") : t("analysis.down"),
                diff: pts(Math.abs(c.difference)),
                low: diffNum(c.ci_low),
                high: diffNum(c.ci_high),
              })}{" "}
              {c.p_value < 0.05
                ? t("analysis.significant", { p: pText(c.p_value, number, t) })
                : t("analysis.notSignificant", { p: pText(c.p_value, number, t) })}
            </p>
          )}
          <dl className="facts">
            <div>
              <dt>{t("analysis.test")}</dt>
              <dd>{t(`tests.${c.test_key}`)}</dd>
            </div>
            <div>
              <dt>{t("analysis.effect")}</dt>
              <dd>
                {c.effect_size === null
                  ? t("common.none")
                  : `${t(`effects.${c.effect_key}`)} = ${number(c.effect_size, 2)} (${t(`effects.size_${effectSize(c.effect_size)}`)})`}
              </dd>
            </div>
          </dl>
        </section>
      ) : (
        usable.length === 1 && <Notice>{t("analysis.oneRound")}</Notice>
      )}
    </div>
  );
}

const pText = (
  p: number,
  number: (x: number, d?: number) => string,
  t: (k: string, v?: Record<string, string | number>) => string,
) => (p < 0.001 ? t("analysis.pSmall") : t("analysis.pEq", { p: number(p, 3) }));

const effectSize = (v: number) => {
  const a = Math.abs(v);
  return a < 0.2 ? "negligible" : a < 0.5 ? "small" : a < 0.8 ? "medium" : "large";
};

function Breakdown({ a }: { a: IndicatorAnalysis }) {
  const { t, number } = useI18n();
  const { colText, valText } = useLabels();
  const fmt = useFmt(a.indicator.unit);
  const usable = a.rounds.filter((r) => !r.result.error_key);
  if (!a.indicator.disaggregation)
    return <Empty icon="table" title={t("analysis.noBreakdown")} text={t("analysis.noBreakdownText")} />;
  const groups = [...new Set(usable.flatMap((r) => (r.result.by ?? []).map((g) => g.group)))].sort();
  const cols = [a.indicator.disaggregation, a.indicator.disaggregation2].filter((x): x is string => !!x);
  // Crossed groups arrive as "code1 / code2": each part takes the label of its column.
  const groupText = (g: string) =>
    cols.length === 2
      ? g
          .split(" / ")
          .map((part, i) => valText(cols[i] ?? cols[0], part))
          .join(" / ")
      : valText(cols[0], g);
  return (
    <div className="stack">
      <p className="muted">
        {t("analysis.breakdownBy", {
          column: [a.indicator.disaggregation, a.indicator.disaggregation2]
            .filter((x): x is string => !!x)
            .map((x) => colText(x))
            .join(" × "),
        })}
      </p>
      <div className="table-wrap">
        <table className="table" data-testid="breakdown-table">
          <thead>
            <tr>
              <th>{t("analysis.colGroup")}</th>
              {usable.map((r) => (
                <th key={r.dataset_id} className="num">
                  {t(`rounds.${r.round}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g}>
                <td>
                  {groupText(g)}
                  {groupText(g) !== g && <span className="cell-sub mono">{g}</span>}
                </td>
                {usable.map((r) => {
                  const hit = r.result.by?.find((x) => x.group === g);
                  return (
                    <td key={r.dataset_id} className="num">
                      {hit && hit.estimate !== null ? (
                        <>
                          <span className="strong">{fmt(hit.estimate)}</span>
                          <span className="cell-sub">
                            {t("analysis.ciRange", { low: fmt(hit.ci_low), high: fmt(hit.ci_high) })}, n ={" "}
                            {number(hit.n, 0)}
                          </span>
                        </>
                      ) : (
                        t("common.none")
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Method({ a }: { a: IndicatorAnalysis }) {
  const { t } = useI18n();
  const usable = a.rounds.filter((r) => !r.result.error_key);
  const [which, setWhich] = useState(0);
  const r = usable[Math.min(which, usable.length - 1)];
  return (
    <div className="stack">
      {r && r.result.method_key && <p>{t(`methods.${r.result.method_key}`)}</p>}
      {a.comparison && !a.comparison.error_key && <p>{t(`tests.${a.comparison.test_key}`)}</p>}
      <p className="muted small">{t("analysis.scriptHelp")}</p>
      {usable.length > 1 && (
        <div className="chips">
          {usable.map((x, i) => (
            <button key={x.dataset_id} className="chip" aria-pressed={i === which} onClick={() => setWhich(i)}>
              {t(`rounds.${x.round}`)}
            </button>
          ))}
        </div>
      )}
      {r?.result.script && (
        <pre className="code-block" data-testid="r-script">
          {r.result.script}
        </pre>
      )}
    </div>
  );
}
