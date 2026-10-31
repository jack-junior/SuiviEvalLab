// Indicators: definition, calculation rule from a data column, baseline and target.

import { useMemo, useState } from "react";
import { Frequency, Indicator } from "../api";
import { useI18n } from "../i18n";
import { useLabels } from "../labels";
import { useProject } from "../state";
import { Confirm, Empty, Field, IconButton, Notice, Panel, useValueFormat } from "../ui";
import { IndicatorRule } from "./IndicatorRule";
import { useLevels } from "../frameworks";

type Draft = Omit<Indicator, "id" | "node_id"> & { id?: string; node_id: string };

const blank = (node_id: string): Draft => ({
  node_id,
  name: "",
  definition: "",
  unit: "percent",
  direction: "increase",
  column: null,
  success_values: [],
  conditions: [],
  combine: "all",
  count_mode: "rows",
  numerator: null,
  denominator: null,
  multiplier: 1,
  disaggregation: null,
  disaggregation2: null,
  baseline_manual: null,
  target: null,
  unit_label: "",
  source: "",
  method: "",
  frequency: "",
  responsible: "",
  target_date: "",
});

const FREQUENCIES: Frequency[] = ["", "monthly", "quarterly", "semiannual", "annual", "rounds", "other"];

/** Number typed by the user: percentages in %, stored as shares. */
const toInput = (v: number | null, unit: string) =>
  v === null ? "" : String(+(unit === "percent" ? v * 100 : v).toFixed(4));
const fromInput = (s: string, unit: string): number | null => {
  const v = Number(s.replace(",", ".").replace(/\s/g, ""));
  if (s.trim() === "" || Number.isNaN(v)) return null;
  return unit === "percent" ? v / 100 : v;
};

export function Indicators() {
  const { t } = useI18n();
  const levels = useLevels();
  const { snap, run, error, focus } = useProject();
  const { colText, valText } = useLabels();
  const fmt = useValueFormat();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [targetText, setTargetText] = useState("");
  const [baseText, setBaseText] = useState("");
  const [deleting, setDeleting] = useState<Indicator | null>(null);
  const [categoriesText, setCategoriesText] = useState("");

  const columns = useMemo(() => {
    const map = new Map<string, { type: string; distinct: number; datasets: string[] }>();
    for (const ds of snap?.datasets ?? [])
      for (const c of ds.columns) {
        const cur = map.get(c.name);
        if (cur) cur.datasets.push(ds.id);
        else map.set(c.name, { type: c.type, distinct: c.distinct, datasets: [ds.id] });
      }
    return map;
  }, [snap?.datasets]);

  if (!snap) return null;
  const results = snap.framework.filter((n) => levels.carries(n.level));
  const routine = draft?.source_type === "routine";

  const edit = (d: Draft) => {
    // Indicators saved before version 0.3 keep their single condition in column + success_values.
    if (!d.conditions?.length && d.column && d.unit === "percent")
      d = { ...d, conditions: [{ column: d.column, values: d.success_values }] };
    setDraft({
      ...d,
      combine: d.combine ?? "all",
      count_mode: d.count_mode ?? "rows",
      multiplier: d.multiplier ?? 1,
      disaggregation2: d.disaggregation2 ?? null,
      conditions: d.conditions ?? [],
    });
    setTargetText(toInput(d.target, d.unit));
    setBaseText(toInput(d.baseline_manual, d.unit));
    setCategoriesText((d.categories ?? []).join(", "));
  };

  const save = async () => {
    if (!draft) return;
    const indicator = {
      ...draft,
      target: fromInput(targetText, draft.unit),
      baseline_manual: fromInput(baseText, draft.unit),
      categories: categoriesText
        .split(/[,;]/)
        .map((c) => c.trim())
        .filter(Boolean),
    };
    const ok = await run("indicator.save", { id: draft.id, node_id: draft.node_id, indicator });
    if (ok) setDraft(null);
  };

  const ruleText = (ind: Indicator) => {
    if (ind.source_type === "routine")
      return t("indicators.ruleRoutine", { how: t(`indicators.agg_${ind.aggregation ?? "sum"}`).toLowerCase() });
    const conds = ind.conditions?.length
      ? ind.conditions
      : ind.column && ind.unit === "percent"
        ? [{ column: ind.column, values: ind.success_values }]
        : [];
    const condText = conds
      .map((c) =>
        t("indicators.condText", {
          column: colText(c.column),
          values: c.values.map((v) => valText(c.column, v)).join(", "),
        }),
      )
      .join(ind.combine === "any" ? t("indicators.or") : t("indicators.and"));
    if (ind.unit === "percent")
      return conds.length ? t("indicators.rulePercent2", { conditions: condText }) : t("indicators.noRule");
    if (ind.unit === "count")
      return ind.count_mode === "sum"
        ? ind.column
          ? t("indicators.ruleSum", { column: colText(ind.column) })
          : t("indicators.noRule")
        : conds.length
          ? t("indicators.ruleCount", { conditions: condText })
          : t("indicators.noRule");
    if (ind.unit === "ratio")
      return ind.numerator && ind.denominator
        ? t("indicators.ruleRatio", { num: colText(ind.numerator), den: colText(ind.denominator) })
        : t("indicators.noRule");
    return ind.column ? t("indicators.ruleMean", { column: colText(ind.column) }) : t("indicators.noRule");
  };

  if (results.length === 0)
    return (
      <div className="inner wide">
        <h1>{t("nav.indicators")}</h1>
        <Empty icon="target" title={t("indicators.needFramework")} text={t("indicators.needFrameworkText")} />
      </div>
    );

  return (
    <div className="inner wide">
      <div className="page-head">
        <div>
          <h1>{t("nav.indicators")}</h1>
          <p className="lead">{t("indicators.lead")}</p>
        </div>
        <button
          className="btn primary"
          onClick={() => edit(blank(focus && results.some((n) => n.id === focus) ? focus : results[0].id))}
          data-testid="add-indicator"
        >
          {t("indicators.add")}
        </button>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      {results.map((node) => {
        const list = snap.indicators.filter((i) => i.node_id === node.id);
        if (!list.length && node.level === "impact") return null;
        return (
          <section key={node.id} className={`ind-group${focus === node.id ? " focused" : ""}`}>
            <div className="ind-group-head">
              <span className="tree-level">
                {levels.name(node.level)} {node.code}
              </span>
              <span className="ind-group-title">{node.title}</span>
              <IconButton icon="plus" label={t("indicators.addHere")} onClick={() => edit(blank(node.id))} />
            </div>
            {list.length === 0 ? (
              <p className="muted small indent">{t("indicators.noneHere")}</p>
            ) : (
              <div className="list">
                {list.map((ind) => (
                  <div key={ind.id} className="row ind-row">
                    <div>
                      <div className="t">{ind.name}</div>
                      <div className="s">
                        {ruleText(ind)}
                        {"  "}
                        {t("indicators.targetShort", { value: fmt(ind.target, ind.unit) })}
                      </div>
                    </div>
                    <div className="v row-tools">
                      <IconButton icon="edit" label={t("common.edit")} onClick={() => edit({ ...ind })} />
                      <IconButton
                        icon="up"
                        label={t("common.moveUp")}
                        onClick={() => run("indicator.move", { id: ind.id, direction: -1 })}
                      />
                      <IconButton
                        icon="down"
                        label={t("common.moveDown")}
                        onClick={() => run("indicator.move", { id: ind.id, direction: 1 })}
                      />
                      <IconButton icon="trash" label={t("common.delete")} onClick={() => setDeleting(ind)} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        );
      })}

      {draft && (
        <Panel
          title={draft.id ? t("indicators.editTitle") : t("indicators.newTitle")}
          onClose={() => setDraft(null)}
          testId="indicator-panel"
          footer={
            <>
              <button className="btn" onClick={() => setDraft(null)}>
                {t("common.cancel")}
              </button>
              <button className="btn primary" onClick={save} disabled={!draft.name.trim()} data-testid="indicator-save">
                {t("common.save")}
              </button>
            </>
          }
        >
          <Field label={t("indicators.result")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={draft.node_id}
                onChange={(e) => setDraft({ ...draft, node_id: e.target.value })}
              >
                {results.map((n) => (
                  <option key={n.id} value={n.id}>
                    {t("common.labelled", { a: `${levels.name(n.level)} ${n.code}`.trim(), b: n.title })}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t("indicators.name")} hint={t("indicators.nameHint")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                data-testid="indicator-name"
              />
            )}
          </Field>
          <Field label={t("indicators.definition")}>
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={3}
                value={draft.definition}
                onChange={(e) => setDraft({ ...draft, definition: e.target.value })}
              />
            )}
          </Field>

          <div className="field">
            <span className="label">{t("indicators.sourceType")}</span>
            <div className="kind-grid">
              {(["survey", "routine"] as const).map((k) => (
                <button
                  key={k}
                  className="kind"
                  aria-pressed={(draft.source_type ?? "survey") === k}
                  onClick={() =>
                    setDraft({
                      ...draft,
                      source_type: k,
                      unit: k === "routine" && draft.unit === "ratio" ? "count" : draft.unit,
                    })
                  }
                  data-testid={`source-${k}`}
                >
                  <span className="kind-title">{t(`indicators.source_${k}`)}</span>
                  <span className="kind-text">{t(`indicators.sourceText_${k}`)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span className="label">{t("indicators.unit")}</span>
            <div className="chips">
              {(routine
                ? (["count", "percent", "mean"] as const)
                : (["percent", "mean", "count", "ratio"] as const)
              ).map((u) => (
                <button
                  key={u}
                  className="chip"
                  aria-pressed={draft.unit === u}
                  onClick={() => setDraft({ ...draft, unit: u })}
                >
                  {t(`indicators.unit_${u}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <span className="label">{t("indicators.direction")}</span>
            <div className="chips">
              {(["increase", "decrease"] as const).map((d) => (
                <button
                  key={d}
                  className="chip"
                  aria-pressed={draft.direction === d}
                  onClick={() => setDraft({ ...draft, direction: d })}
                >
                  {t(`indicators.dir_${d}`)}
                </button>
              ))}
            </div>
          </div>

          <h3 className="panel-section">{t("indicators.calculation")}</h3>
          {routine ? (
            <>
              <div className="field">
                <span className="label">{t("indicators.aggregation")}</span>
                <div className="chips">
                  {(["sum", "last", "mean"] as const).map((a) => (
                    <button
                      key={a}
                      className="chip"
                      aria-pressed={(draft.aggregation ?? (draft.unit === "percent" ? "last" : "sum")) === a}
                      onClick={() => setDraft({ ...draft, aggregation: a })}
                      data-testid={`aggregation-${a}`}
                    >
                      {t(`indicators.agg_${a}`)}
                    </button>
                  ))}
                </div>
                <div className="field-hint">{t("indicators.aggregationHint")}</div>
              </div>
              <Field label={t("indicators.categories")} hint={t("indicators.categoriesHint")}>
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={categoriesText}
                    onChange={(e) => setCategoriesText(e.target.value)}
                    placeholder={t("indicators.categoriesPlaceholder")}
                    data-testid="indicator-categories"
                  />
                )}
              </Field>
              <p className="muted small">{t("indicators.routineValuesWhere")}</p>
            </>
          ) : columns.size === 0 ? (
            <p className="muted small">{t("indicators.noDataYet")}</p>
          ) : (
            <IndicatorRule draft={draft} onChange={(d) => setDraft({ ...draft, ...d })} columns={columns} />
          )}

          <h3 className="panel-section">{t("indicators.values")}</h3>
          <div className="field-row">
            <Field label={draft.unit === "percent" ? t("indicators.targetPercent") : t("indicators.target")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  inputMode="decimal"
                  value={targetText}
                  onChange={(e) => setTargetText(e.target.value)}
                  data-testid="indicator-target"
                />
              )}
            </Field>
            <Field
              label={draft.unit === "percent" ? t("indicators.baselinePercent") : t("indicators.baseline")}
              hint={t("indicators.baselineHint")}
            >
              {(id) => (
                <input
                  id={id}
                  className="input"
                  inputMode="decimal"
                  value={baseText}
                  onChange={(e) => setBaseText(e.target.value)}
                />
              )}
            </Field>
          </div>
          <h3 className="panel-section">{t("indicators.plan")}</h3>
          <p className="muted small">{t("indicators.planHint")}</p>
          <div className="field-row">
            <Field label={t("indicators.source")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={draft.source}
                  onChange={(e) => setDraft({ ...draft, source: e.target.value })}
                />
              )}
            </Field>
            <Field label={t("indicators.method")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={draft.method ?? ""}
                  onChange={(e) => setDraft({ ...draft, method: e.target.value })}
                  data-testid="indicator-method"
                />
              )}
            </Field>
          </div>
          <div className="field-row">
            <Field label={t("indicators.frequency")}>
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={draft.frequency ?? ""}
                  onChange={(e) => setDraft({ ...draft, frequency: e.target.value as Frequency })}
                  data-testid="indicator-frequency"
                >
                  {FREQUENCIES.map((f) => (
                    <option key={f} value={f}>
                      {f ? t(`indicators.freq_${f}`) : t("indicators.freq_none")}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label={t("indicators.responsible")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={draft.responsible ?? ""}
                  onChange={(e) => setDraft({ ...draft, responsible: e.target.value })}
                  data-testid="indicator-responsible"
                />
              )}
            </Field>
          </div>
          <Field label={t("indicators.targetDate")} hint={t("indicators.targetDateHint")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={draft.target_date ?? ""}
                onChange={(e) => setDraft({ ...draft, target_date: e.target.value })}
              />
            )}
          </Field>
        </Panel>
      )}

      {deleting && (
        <Confirm
          text={t("indicators.deleteConfirm", { name: deleting.name })}
          confirmLabel={t("common.delete")}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            await run("indicator.delete", { id: deleting.id });
            setDeleting(null);
          }}
        />
      )}
    </div>
  );
}
