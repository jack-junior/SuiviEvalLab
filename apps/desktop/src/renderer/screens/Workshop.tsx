// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Analyses: a results document, as in JASP. The user picks an analysis, fills its
// options, and the results (tables, charts, a reading in words, the R code)
// update as the options change. Everything follows the survey design of the
// dataset. Advanced users can write an R script instead. Each analysis can go
// into the Word report.

import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { allColumns, AnalysisResult, AnalysisSpec, AnalysisType, call, CellFormat, Dataset, ResultTable } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Confirm, Empty, Field, Icon, IconButton, Notice } from "../ui";

const TYPES: { type: AnalysisType; icon: string }[] = [
  { type: "descriptives", icon: "table" },
  { type: "crosstab", icon: "calc" },
  { type: "means", icon: "chart" },
  { type: "correlation", icon: "history" },
  { type: "regression", icon: "target" },
  { type: "did", icon: "scale" },
  { type: "r_script", icon: "doc" },
];

const blank = (type: AnalysisType, ds: string): Partial<AnalysisSpec> => {
  const base = { type, dataset_id: ds, title: "", note: "", level: 0.95, in_report: true };
  switch (type) {
    case "descriptives":
      return { ...base, variables: [], by: null, types: {} };
    case "crosstab":
      return { ...base, row: "", column: "", percent: "row" };
    case "means":
      return { ...base, outcome: "", group: "" };
    case "correlation":
      return { ...base, variables: [] };
    case "regression":
      return { ...base, outcome: "", predictors: [], family: "linear", success: [], factors: [] };
    case "did":
      return { ...base, outcome: "", success: null, group: "", treated: [], period: "", after: [] };
    default:
      return { ...base, code: "" };
  }
};

/** Whether the options are complete enough to save and compute. */
function complete(a: Partial<AnalysisSpec>): boolean {
  switch (a.type) {
    case "descriptives":
      return (a.variables?.length ?? 0) > 0;
    case "crosstab":
      return !!a.row && !!a.column && a.row !== a.column;
    case "means":
      return !!a.outcome && !!a.group;
    case "correlation":
      return (a.variables?.length ?? 0) >= 2;
    case "regression":
      return (
        !!a.outcome && (a.predictors?.length ?? 0) > 0 && (a.family !== "logistic" || (a.success?.length ?? 0) > 0)
      );
    case "did":
      return (
        !!a.outcome &&
        !!a.group &&
        !!a.period &&
        (a.treated?.length ?? 0) > 0 &&
        (a.after?.length ?? 0) > 0 &&
        (a.success === null || a.success === undefined || a.success.length > 0)
      );
    case "r_script":
      return !!a.code?.trim();
    default:
      return false;
  }
}

export function useCell() {
  const { number, percent, lang } = useI18n();
  return (v: string | number | null, fmt: CellFormat) => {
    if (v === null || v === undefined) return "";
    if (typeof v === "string" || fmt === "text") return String(v);
    if (fmt === "int") return number(v, 0);
    if (fmt === "pct") return percent(v, 1);
    if (fmt === "p") return v < 0.001 ? (lang === "fr" ? "< 0,001" : "< 0.001") : number(v, 3);
    const a = Math.abs(v);
    return number(v, a >= 10000 ? 0 : a >= 100 ? 1 : a >= 1 || a === 0 ? 2 : 3);
  };
}

export function Workshop() {
  const { t } = useI18n();
  const { snap, run, error } = useProject();
  const [selected, setSelected] = useState<string | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [deleting, setDeleting] = useState<AnalysisSpec | null>(null);
  const [draftNew, setDraftNew] = useState<Partial<AnalysisSpec> | null>(null);
  // The editor keeps its state while a new analysis is saved for the first time.
  const [editorKey, setEditorKey] = useState(0);
  if (!snap) return null;
  const current = snap.analyses.find((a) => a.id === selected) ?? null;

  if (snap.datasets.length === 0)
    return (
      <div className="inner">
        <Empty icon="table" title={t("analyses.noDataTitle")} text={t("analyses.noDataText")} />
      </div>
    );

  const create = (type: AnalysisType) => {
    // An analysis is saved once its options are complete; until then it is a draft on screen.
    setChoosing(false);
    setSelected(null);
    setDraftNew(blank(type, snap.datasets[0].id));
    setEditorKey((k) => k + 1);
  };

  return (
    <div className="split">
      <aside className="split-list" aria-label={t("analyses.document")}>
        <button
          className="btn primary"
          onClick={() => {
            setChoosing(true);
            setSelected(null);
            setDraftNew(null);
          }}
          data-testid="new-analysis"
        >
          {t("analyses.new")}
        </button>
        <div className="split-group">
          <div className="split-group-title">{t("analyses.document")}</div>
          {snap.analyses.length === 0 && <p className="muted small indent">{t("analyses.none")}</p>}
          {snap.analyses.map((a) => (
            <div key={a.id} className="saved-test">
              <button
                className="split-item"
                aria-current={selected === a.id ? "true" : undefined}
                onClick={() => {
                  setSelected(a.id);
                  setChoosing(false);
                  setDraftNew(null);
                  setEditorKey((k) => k + 1);
                }}
                data-testid={`analysis-item-${a.type}`}
              >
                <span className="split-item-kicker">{t(`analyses.type_${a.type}`)}</span>
                {a.title || defaultTitle(a, t)}
                {!a.in_report && <span className="muted small"> {t("analyses.notInReport")}</span>}
              </button>
              <div className="row-tools">
                <IconButton
                  icon="up"
                  label={t("common.moveUp")}
                  onClick={() => run("analysis.move", { id: a.id, direction: -1 })}
                />
                <IconButton icon="trash" label={t("common.delete")} onClick={() => setDeleting(a)} />
              </div>
            </div>
          ))}
        </div>
      </aside>
      <div className="split-main">
        <div className="inner wide">
          <div>
            <h1 className="h1-small">{t("nav.workshop")}</h1>
            <p className="lead small-lead">{t("analyses.lead")}</p>
          </div>
          {error && <Notice kind="error">{error}</Notice>}
          {choosing || (!current && !draftNew) ? (
            <div className="question-grid">
              {TYPES.map(({ type, icon }) => (
                <button key={type} className="question" onClick={() => create(type)} data-testid={`atype-${type}`}>
                  <Icon name={icon} size={22} />
                  <span className="question-title">{t(`analyses.type_${type}`)}</span>
                  <span className="question-text">{t(`analyses.typeText_${type}`)}</span>
                </button>
              ))}
            </div>
          ) : (
            <AnalysisEditor
              key={editorKey}
              initial={current ?? draftNew!}
              onCreated={(id) => {
                setDraftNew(null);
                setSelected(id);
              }}
            />
          )}
        </div>
      </div>
      {deleting && (
        <Confirm
          text={t("analyses.deleteConfirm", { name: deleting.title || defaultTitle(deleting, t) })}
          confirmLabel={t("common.delete")}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            await run("analysis.delete", { id: deleting.id });
            if (selected === deleting.id) setSelected(null);
            setDeleting(null);
          }}
        />
      )}
    </div>
  );
}

export function defaultTitle(a: Partial<AnalysisSpec>, t: (k: string, v?: Record<string, string | number>) => string) {
  const names = (a.variables ?? []).slice(0, 3).join(", ");
  switch (a.type) {
    case "descriptives":
      return t("analyses.title_descriptives", { variables: names || "..." });
    case "crosstab":
      return t("analyses.title_crosstab", { row: a.row || "...", column: a.column || "..." });
    case "means":
      return t("analyses.title_means", { outcome: a.outcome || "...", group: a.group || "..." });
    case "correlation":
      return t("analyses.title_correlation", { variables: names || "..." });
    case "regression":
      return t(`analyses.title_regression_${a.family ?? "linear"}`, { outcome: a.outcome || "..." });
    case "did":
      return t("analyses.title_did", { outcome: a.outcome || "..." });
    default:
      return t("analyses.type_r_script");
  }
}

function AnalysisEditor({ initial, onCreated }: { initial: Partial<AnalysisSpec>; onCreated: (id: string) => void }) {
  const { t, lang } = useI18n();
  const { snap, run, describe } = useProject();
  const [draft, setDraft] = useState<Partial<AnalysisSpec>>(initial);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [computing, setComputing] = useState(false);
  const [runErr, setRunErr] = useState<string | null>(null);
  const id = useRef<string | undefined>(initial.id);
  const ds = snap!.datasets.find((d) => d.id === draft.dataset_id) ?? snap!.datasets[0];
  const isScript = draft.type === "r_script";
  const stamp = `${ds.id}-${ds.clean_rows}-${ds.rules.length}-${JSON.stringify(ds.design)}`;

  const compute = useCallback(
    async (spec: Partial<AnalysisSpec>) => {
      if (!complete(spec)) return;
      setComputing(true);
      setRunErr(null);
      const { id: _drop, trusted: _t, ...body } = spec;
      void _drop;
      void _t;
      const saved = await run<{ created: string }>(
        "analysis.save",
        id.current ? { id: id.current, analysis: body } : { analysis: body },
        "analysis",
      );
      if (!saved) {
        setComputing(false);
        return;
      }
      if (!id.current) {
        id.current = saved.created;
        onCreated(saved.created);
      }
      try {
        setResult(await call<AnalysisResult>("analysis.run", { id: id.current, lang }));
      } catch (e) {
        setRunErr(describe(e));
      } finally {
        setComputing(false);
      }
    },
    [run, lang, describe, onCreated],
  );

  // Recompute when the options change (after a short pause), except R scripts which run on demand.
  const options = JSON.stringify({
    ...draft,
    title: undefined,
    note: undefined,
    in_report: undefined,
    code: undefined,
  });
  useEffect(() => {
    if (isScript && !id.current) return;
    const timer = setTimeout(() => compute(draft), isScript ? 0 : 450);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options, stamp, lang]);

  const update = (p: Partial<AnalysisSpec>) => setDraft((d) => ({ ...d, ...p }));
  const saveMeta = (p: Partial<AnalysisSpec>) => {
    update(p);
    if (id.current) run("analysis.save", { id: id.current, analysis: p }, "analysis");
  };

  return (
    <>
      <section className="test-form" data-testid="analysis-form">
        <div className="field-row">
          <Field label={t("tests.dataset")}>
            {(fid) => (
              <select
                id={fid}
                className="input"
                value={draft.dataset_id}
                onChange={(e) =>
                  setDraft({ ...blank(draft.type!, e.target.value), title: draft.title, note: draft.note })
                }
                data-testid="analysis-dataset"
              >
                {snap!.datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {!isScript && (
            <Field label={t("analyses.level")}>
              {(fid) => (
                <select
                  id={fid}
                  className="input"
                  value={draft.level}
                  onChange={(e) => update({ level: Number(e.target.value) })}
                >
                  {[0.9, 0.95, 0.99].map((l) => (
                    <option key={l} value={l}>
                      {Math.round(l * 100)} %
                    </option>
                  ))}
                </select>
              )}
            </Field>
          )}
        </div>
        <TypeOptions ds={ds} draft={draft} update={update} />
        {isScript && (
          <div className="row-actions">
            <button
              className="btn primary"
              onClick={() => compute(draft)}
              disabled={!complete(draft) || computing}
              data-testid="run-script"
            >
              {t("rscript.run")}
            </button>
          </div>
        )}
        <details className="analysis-meta">
          <summary>{t("analyses.titleAndNote")}</summary>
          <div className="stack-sm">
            <Field label={t("analyses.title")} hint={t("analyses.titleHint")}>
              {(fid) => (
                <input
                  id={fid}
                  className="input"
                  value={draft.title ?? ""}
                  placeholder={defaultTitle(draft, t)}
                  onChange={(e) => update({ title: e.target.value })}
                  onBlur={(e) => saveMeta({ title: e.target.value })}
                  data-testid="analysis-title"
                />
              )}
            </Field>
            <Field label={t("analyses.note")} hint={t("analyses.noteHint")}>
              {(fid) => (
                <textarea
                  id={fid}
                  className="input"
                  rows={2}
                  value={draft.note ?? ""}
                  onChange={(e) => update({ note: e.target.value })}
                  onBlur={(e) => saveMeta({ note: e.target.value })}
                />
              )}
            </Field>
          </div>
        </details>
        <label className="check">
          <input
            type="checkbox"
            checked={draft.in_report !== false}
            onChange={(e) => saveMeta({ in_report: e.target.checked })}
            data-testid="analysis-in-report"
          />
          <span className="check-text">{t("analyses.inReport")}</span>
        </label>
      </section>

      <section className="analysis-result" aria-live="polite" data-testid="analysis-result">
        {!complete(draft) ? (
          <p className="muted">{t(isScript ? "rscript.writeFirst" : "analyses.fillOptions")}</p>
        ) : computing && !result ? (
          <p className="muted">{t("analyses.computing")}</p>
        ) : runErr ? (
          <Notice kind="error">{runErr}</Notice>
        ) : result ? (
          <ResultView res={result} computing={computing} />
        ) : null}
      </section>
    </>
  );
}

function ResultView({ res, computing }: { res: AnalysisResult; computing: boolean }) {
  const { t } = useI18n();
  const cell = useCell();
  const [copied, setCopied] = useState(false);
  if (res.paused) return <Notice kind="info">{t("analyses.paused")}</Notice>;
  if (res.error)
    return (
      <Notice kind="error">
        <span data-testid="analysis-error">
          {t(`analyses.err_${res.error}`, { columns: (res.columns ?? []).join(", "), detail: res.message ?? "" })}
        </span>
      </Notice>
    );
  if (res.script_result) {
    const out = res.script_result;
    return (
      <div className={`stack${computing ? " dim" : ""}`}>
        {out.output && (
          <pre className="mono code-view" data-testid="script-output">
            {out.output}
          </pre>
        )}
        {out.table && <DataTableView columns={out.table.columns} rows={out.table.rows} />}
        {out.plots.map((p, i) => (
          <img key={i} className="result-chart" src={`data:image/png;base64,${p}`} alt={t("analyses.chartAlt")} />
        ))}
      </div>
    );
  }
  return (
    <div className={`stack${computing ? " dim" : ""}`}>
      {res.reading && res.reading.length > 0 && (
        <div className="reading" data-testid="analysis-reading">
          {res.reading.map((r, i) => (
            <p key={i}>{r}</p>
          ))}
        </div>
      )}
      {(res.tables ?? []).map((tab, i) => (
        <ResultTableView key={i} tab={tab} cell={cell} />
      ))}
      {(res.tests ?? []).map((ts, i) => (
        <p key={i} className="muted small">
          {t("analyses.testLine", {
            test: ts.label,
            stat: ts.statistic !== undefined && ts.statistic !== null ? cell(ts.statistic, "num") : "",
            p: ts.p_value !== undefined && ts.p_value !== null ? cell(ts.p_value, "p") : "",
          })}
        </p>
      ))}
      {(res.notes ?? []).map((n, i) => (
        <p key={i} className="muted small">
          {n}
        </p>
      ))}
      {(res.charts ?? []).map((c, i) => (
        <img
          key={i}
          className="result-chart"
          src={`data:image/png;base64,${c}`}
          alt={t("analyses.chartAlt")}
          data-testid="analysis-chart"
        />
      ))}
      {res.script && (
        <details className="analysis-script">
          <summary>{t("analyses.rCode")}</summary>
          <p className="muted small">{t("analyses.rCodeHelp")}</p>
          <pre className="mono code-view">{res.script}</pre>
          <button
            className="btn"
            onClick={() => {
              navigator.clipboard?.writeText(res.script ?? "").then(() => setCopied(true));
            }}
          >
            {copied ? t("analyses.copied") : t("analyses.copy")}
          </button>
        </details>
      )}
    </div>
  );
}

function ResultTableView({ tab, cell }: { tab: ResultTable; cell: ReturnType<typeof useCell> }) {
  return (
    <div className="result-table" data-testid={`rtable-${tab.key}`}>
      {tab.title && <div className="strong small">{tab.title}</div>}
      <div className="table-wrap">
        <table className="table compact">
          <thead>
            <tr>
              {tab.columns.map((c, i) => (
                <th key={i} className={c.fmt !== "text" ? "num" : undefined}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tab.rows.map((r, i) => (
              <tr key={i}>
                {r.map((v, j) => (
                  <td key={j} className={tab.columns[j]?.fmt !== "text" ? "num" : undefined}>
                    {cell(v, tab.columns[j]?.fmt ?? "text")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const NUMBER = /^-?\d+(\.\d+)?(e[+-]?\d+)?$/i;

function DataTableView({ columns, rows }: { columns: string[]; rows: (string | null)[][] }) {
  const cell = useCell();
  const show = (v: string | null) =>
    v === null ? "" : NUMBER.test(v) ? cell(Number(v), Number.isInteger(Number(v)) ? "int" : "num") : v;
  return (
    <div className="table-wrap">
      <table className="table compact">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (
                <td key={j} className={v !== null && NUMBER.test(v) ? "num" : undefined}>
                  {show(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ----- options per analysis --------------------------------------------------------------

function ColumnSelect({
  ds,
  value,
  onChange,
  label,
  numeric,
  optional,
  testId,
}: {
  ds: Dataset;
  value: string | null | undefined;
  onChange: (v: string) => void;
  label: string;
  numeric?: boolean;
  optional?: boolean;
  testId?: string;
}) {
  const { t } = useI18n();
  return (
    <Field label={label}>
      {(id) => (
        <select
          id={id}
          className="input"
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          data-testid={testId}
        >
          <option value="">{optional ? t("analyses.none_option") : t("common.choose")}</option>
          {allColumns(ds)
            .filter((c) => !numeric || c.type === "number")
            .map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
        </select>
      )}
    </Field>
  );
}

function ColumnsPicker({
  ds,
  values,
  onChange,
  label,
  numeric,
  testId,
  extra,
}: {
  ds: Dataset;
  values: string[];
  onChange: (v: string[]) => void;
  label: string;
  numeric?: boolean;
  testId?: string;
  extra?: (c: string) => ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="field">
      <span className="label">{label}</span>
      <div className="picked-columns">
        {values.map((c) => (
          <div key={c} className="picked-column">
            <span className="mono">{c}</span>
            {extra?.(c)}
            <IconButton
              icon="close"
              label={t("common.remove")}
              onClick={() => onChange(values.filter((x) => x !== c))}
            />
          </div>
        ))}
      </div>
      <select
        className="input"
        value=""
        onChange={(e) => e.target.value && onChange([...values, e.target.value])}
        aria-label={label}
        data-testid={testId}
      >
        <option value="">{t("analyses.addVariable")}</option>
        {allColumns(ds)
          .filter((c) => !values.includes(c.name) && (!numeric || c.type === "number"))
          .map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
      </select>
    </div>
  );
}

function ValuesPicker({
  ds,
  column,
  values,
  onChange,
  label,
  testId,
}: {
  ds: Dataset;
  column: string;
  values: string[];
  onChange: (v: string[]) => void;
  label: string;
  testId?: string;
}) {
  const { number } = useI18n();
  const [list, setList] = useState<{ value: string | null; n: number }[]>([]);
  useEffect(() => {
    if (!column) return;
    call<{ values: { value: string | null; n: number }[] }>("dataset.column_values", { id: ds.id, column, limit: 40 })
      .then((r) => setList(r.values.filter((v) => v.value !== null)))
      .catch(() => setList([]));
  }, [ds.id, column]);
  if (!column) return null;
  return (
    <div className="field">
      <span className="label">{label}</span>
      <div className="chips" data-testid={testId}>
        {list.map((v) => (
          <button
            key={v.value}
            className="chip"
            aria-pressed={values.includes(v.value!)}
            onClick={() =>
              onChange(values.includes(v.value!) ? values.filter((x) => x !== v.value) : [...values, v.value!])
            }
            data-testid={`${testId}-${v.value}`}
          >
            {v.value} <span className="muted small">{number(v.n, 0)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function TypeOptions({
  ds,
  draft,
  update,
}: {
  ds: Dataset;
  draft: Partial<AnalysisSpec>;
  update: (p: Partial<AnalysisSpec>) => void;
}) {
  const { t } = useI18n();
  const types = useMemo(() => draft.types ?? {}, [draft.types]);
  switch (draft.type) {
    case "descriptives":
      return (
        <>
          <ColumnsPicker
            ds={ds}
            label={t("analyses.variables")}
            values={draft.variables ?? []}
            onChange={(v) => update({ variables: v })}
            testId="a-variables"
            extra={(c) => (
              <select
                className="input inline small"
                value={types[c] ?? ""}
                onChange={(e) => {
                  const next = { ...types };
                  if (e.target.value) next[c] = e.target.value as "numeric" | "categorical";
                  else delete next[c];
                  update({ types: next });
                }}
                aria-label={t("analyses.treatAs")}
              >
                <option value="">{t("analyses.auto")}</option>
                <option value="numeric">{t("analyses.asNumeric")}</option>
                <option value="categorical">{t("analyses.asCategorical")}</option>
              </select>
            )}
          />
          <ColumnSelect
            ds={ds}
            label={t("analyses.by")}
            value={draft.by}
            optional
            onChange={(v) => update({ by: v || null })}
            testId="a-by"
          />
        </>
      );
    case "crosstab":
      return (
        <>
          <div className="field-row">
            <ColumnSelect
              ds={ds}
              label={t("analyses.row")}
              value={draft.row}
              onChange={(v) => update({ row: v })}
              testId="a-row"
            />
            <ColumnSelect
              ds={ds}
              label={t("analyses.column")}
              value={draft.column}
              onChange={(v) => update({ column: v })}
              testId="a-column"
            />
          </div>
          <div className="field">
            <span className="label">{t("analyses.percent")}</span>
            <div className="chips">
              {(["row", "column", "total"] as const).map((p) => (
                <button
                  key={p}
                  className="chip"
                  aria-pressed={draft.percent === p}
                  onClick={() => update({ percent: p })}
                >
                  {t(`analyses.percent_${p}`)}
                </button>
              ))}
            </div>
          </div>
        </>
      );
    case "means":
      return (
        <div className="field-row">
          <ColumnSelect
            ds={ds}
            label={t("analyses.outcomeNumeric")}
            value={draft.outcome}
            numeric
            onChange={(v) => update({ outcome: v })}
            testId="a-outcome"
          />
          <ColumnSelect
            ds={ds}
            label={t("analyses.group")}
            value={draft.group}
            onChange={(v) => update({ group: v })}
            testId="a-group"
          />
        </div>
      );
    case "correlation":
      return (
        <ColumnsPicker
          ds={ds}
          label={t("analyses.numericVariables")}
          values={draft.variables ?? []}
          numeric
          onChange={(v) => update({ variables: v })}
          testId="a-variables"
        />
      );
    case "regression":
      return (
        <>
          <div className="field">
            <span className="label">{t("analyses.family")}</span>
            <div className="chips">
              {(["linear", "logistic"] as const).map((f) => (
                <button
                  key={f}
                  className="chip"
                  aria-pressed={draft.family === f}
                  onClick={() => update({ family: f, success: [] })}
                  data-testid={`a-family-${f}`}
                >
                  {t(`analyses.family_${f}`)}
                </button>
              ))}
            </div>
            <span className="hint">{t(`analyses.familyHint_${draft.family ?? "linear"}`)}</span>
          </div>
          <ColumnSelect
            ds={ds}
            label={t("analyses.outcome")}
            value={draft.outcome}
            numeric={draft.family !== "logistic"}
            onChange={(v) => update({ outcome: v, success: [] })}
            testId="a-outcome"
          />
          {draft.family === "logistic" && draft.outcome && (
            <ValuesPicker
              ds={ds}
              column={draft.outcome}
              values={draft.success ?? []}
              onChange={(v) => update({ success: v })}
              label={t("analyses.success")}
              testId="a-success"
            />
          )}
          <ColumnsPicker
            ds={ds}
            label={t("analyses.predictors")}
            values={draft.predictors ?? []}
            onChange={(v) => update({ predictors: v, factors: (draft.factors ?? []).filter((f) => v.includes(f)) })}
            testId="a-predictors"
            extra={(c) => (
              <label className="check inline-check small">
                <input
                  type="checkbox"
                  checked={(draft.factors ?? []).includes(c)}
                  onChange={(e) =>
                    update({
                      factors: e.target.checked
                        ? [...(draft.factors ?? []), c]
                        : (draft.factors ?? []).filter((f) => f !== c),
                    })
                  }
                />
                <span className="check-text">{t("analyses.categorical")}</span>
              </label>
            )}
          />
        </>
      );
    case "did":
      return (
        <>
          <p className="muted small">{t("analyses.didHelp")}</p>
          <ColumnSelect
            ds={ds}
            label={t("analyses.outcome")}
            value={draft.outcome}
            onChange={(v) => update({ outcome: v, success: null })}
            testId="a-outcome"
          />
          {draft.outcome && (
            <div className="chips">
              <button className="chip" aria-pressed={draft.success === null} onClick={() => update({ success: null })}>
                {t("analyses.didMean")}
              </button>
              <button
                className="chip"
                aria-pressed={draft.success !== null && draft.success !== undefined}
                onClick={() => update({ success: [] })}
                data-testid="a-did-share"
              >
                {t("analyses.didShare")}
              </button>
            </div>
          )}
          {draft.outcome && draft.success !== null && draft.success !== undefined && (
            <ValuesPicker
              ds={ds}
              column={draft.outcome}
              values={draft.success}
              onChange={(v) => update({ success: v })}
              label={t("analyses.success")}
              testId="a-success"
            />
          )}
          <div className="field-row">
            <ColumnSelect
              ds={ds}
              label={t("analyses.didGroup")}
              value={draft.group}
              onChange={(v) => update({ group: v, treated: [] })}
              testId="a-group"
            />
            <ColumnSelect
              ds={ds}
              label={t("analyses.didPeriod")}
              value={draft.period}
              onChange={(v) => update({ period: v, after: [] })}
              testId="a-period"
            />
          </div>
          {draft.group && (
            <ValuesPicker
              ds={ds}
              column={draft.group}
              values={draft.treated ?? []}
              onChange={(v) => update({ treated: v })}
              label={t("analyses.didTreated")}
              testId="a-treated"
            />
          )}
          {draft.period && (
            <ValuesPicker
              ds={ds}
              column={draft.period}
              values={draft.after ?? []}
              onChange={(v) => update({ after: v })}
              label={t("analyses.didAfter")}
              testId="a-after"
            />
          )}
        </>
      );
    default:
      return (
        <div className="stack-sm">
          <p className="muted small">{t("rscript.helpAnalysis")}</p>
          <textarea
            className="input mono code-area"
            rows={12}
            spellCheck={false}
            value={draft.code ?? ""}
            onChange={(e) => update({ code: e.target.value })}
            placeholder={t("rscript.placeholderAnalysis")}
            aria-label={t("rscript.code")}
            data-testid="rscript-analysis-code"
          />
        </div>
      );
  }
}
