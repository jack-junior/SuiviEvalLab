// Calculation rule of an indicator: conditions on one or more columns
// (percentage, count), a numeric column (mean, sum), or two columns (ratio),
// and up to two breakdown columns.

import { useEffect, useState } from "react";
import { call, Condition, Indicator } from "../api";
import { useI18n } from "../i18n";
import { useLabels } from "../labels";
import { Field, IconButton } from "../ui";

export type RuleDraft = Pick<
  Indicator,
  | "unit"
  | "column"
  | "conditions"
  | "combine"
  | "count_mode"
  | "numerator"
  | "denominator"
  | "multiplier"
  | "disaggregation"
  | "disaggregation2"
>;

export interface ColumnMeta {
  type: string;
  distinct: number;
  datasets: string[];
}

function ColumnSelect({
  value,
  onChange,
  columns,
  numericOnly,
  testId,
  label,
  allowNone,
  noneLabel,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  columns: Map<string, ColumnMeta>;
  numericOnly?: boolean;
  testId?: string;
  label: string;
  allowNone?: boolean;
  noneLabel?: string;
}) {
  const { t } = useI18n();
  const { colText } = useLabels();
  const total = Math.max(1, ...[...columns.values()].map((c) => c.datasets.length));
  return (
    <Field label={label}>
      {(id) => (
        <select
          id={id}
          className="input"
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value || null)}
          data-testid={testId}
        >
          <option value="">{allowNone ? (noneLabel ?? t("indicators.noDisaggregation")) : t("common.choose")}</option>
          {[...columns.entries()]
            .filter(([, c]) => !numericOnly || c.type === "number")
            .map(([name, c]) => (
              <option key={name} value={name}>
                {colText(name)} {c.datasets.length < total ? t("indicators.notInAll") : ""}
              </option>
            ))}
        </select>
      )}
    </Field>
  );
}

function ConditionEditor({
  index,
  cond,
  columns,
  onChange,
  onRemove,
}: {
  index: number;
  cond: Condition;
  columns: Map<string, ColumnMeta>;
  onChange: (c: Condition) => void;
  onRemove?: () => void;
}) {
  const { t, number } = useI18n();
  const { valText, val } = useLabels();
  const [loaded, setLoaded] = useState<{ col: string; values: { value: string | null; n: number }[] } | null>(null);
  const col = cond.column || null;
  useEffect(() => {
    if (!col || !columns.has(col)) return;
    call<{ values: { value: string | null; n: number }[] }>("dataset.column_values", {
      id: columns.get(col)!.datasets[0],
      column: col,
    })
      .then((r) => setLoaded({ col, values: r.values }))
      .catch(() => setLoaded({ col, values: [] }));
  }, [col, columns]);
  const values = loaded && loaded.col === col ? loaded.values : [];
  const suffix = index === 0 ? "" : `-${index}`;
  return (
    <div className="condition">
      <div className="condition-head">
        <span className="condition-n">{t("indicators.conditionN", { n: index + 1 })}</span>
        {onRemove && <IconButton icon="close" label={t("indicators.removeCondition")} onClick={onRemove} />}
      </div>
      <ColumnSelect
        label={t("indicators.column")}
        value={cond.column || null}
        onChange={(v) => onChange({ column: v ?? "", values: [] })}
        columns={columns}
        testId={`indicator-column${suffix}`}
      />
      {cond.column && (
        <div className="field">
          <span className="label">{t("indicators.success")}</span>
          <div className="value-list" data-testid={`success-values${suffix}`}>
            {values
              .filter((v) => v.value !== null)
              .map((v) => (
                <label key={v.value} className="check">
                  <input
                    type="checkbox"
                    data-testid={`value${suffix}-${v.value}`}
                    checked={cond.values.includes(v.value!)}
                    onChange={(e) =>
                      onChange({
                        ...cond,
                        values: e.target.checked
                          ? [...cond.values, v.value!]
                          : cond.values.filter((x) => x !== v.value),
                      })
                    }
                  />
                  <span className="check-text">
                    {valText(cond.column, v.value!)}
                    {val(cond.column, v.value) && <span className="code"> {v.value}</span>}
                  </span>
                  <span className="muted small">{number(v.n, 0)}</span>
                </label>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function IndicatorRule({
  draft,
  onChange,
  columns,
}: {
  draft: RuleDraft;
  onChange: (d: Partial<RuleDraft>) => void;
  columns: Map<string, ColumnMeta>;
}) {
  const { t } = useI18n();
  const textColumns = new Map([...columns].filter(([, c]) => c.type === "text" && c.distinct <= 40));
  const usesConditions = draft.unit === "percent" || (draft.unit === "count" && draft.count_mode === "rows");
  const conds = draft.conditions.length ? draft.conditions : [{ column: "", values: [] }];
  const setConds = (list: Condition[]) => onChange({ conditions: list });

  return (
    <>
      {draft.unit === "count" && (
        <div className="field">
          <span className="label">{t("indicators.countMode")}</span>
          <div className="chips">
            {(["rows", "sum"] as const).map((m) => (
              <button
                key={m}
                className="chip"
                aria-pressed={draft.count_mode === m}
                onClick={() => onChange({ count_mode: m })}
              >
                {t(`indicators.count_${m}`)}
              </button>
            ))}
          </div>
          <div className="field-hint">{t("indicators.countHint")}</div>
        </div>
      )}

      {usesConditions && (
        <>
          {conds.map((c, i) => (
            <ConditionEditor
              key={i}
              index={i}
              cond={c}
              columns={columns}
              onChange={(nc) => setConds(conds.map((x, j) => (j === i ? nc : x)))}
              onRemove={conds.length > 1 ? () => setConds(conds.filter((_, j) => j !== i)) : undefined}
            />
          ))}
          <div className="condition-tools">
            {conds.length < 6 && (
              <button
                className="btn"
                onClick={() => setConds([...conds, { column: "", values: [] }])}
                data-testid="add-condition"
              >
                {t("indicators.addCondition")}
              </button>
            )}
            {conds.length > 1 && (
              <div className="chips">
                {(["all", "any"] as const).map((m) => (
                  <button
                    key={m}
                    className="chip"
                    aria-pressed={draft.combine === m}
                    onClick={() => onChange({ combine: m })}
                  >
                    {t(`indicators.combine_${m}`)}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="field-hint">{t("indicators.missingExcluded")}</div>
        </>
      )}

      {(draft.unit === "mean" || (draft.unit === "count" && draft.count_mode === "sum")) && (
        <ColumnSelect
          label={t("indicators.numericColumn")}
          value={draft.column}
          onChange={(v) => onChange({ column: v })}
          columns={columns}
          numericOnly
          testId="indicator-numeric"
        />
      )}

      {draft.unit === "ratio" && (
        <>
          <ColumnSelect
            label={t("indicators.numerator")}
            value={draft.numerator}
            onChange={(v) => onChange({ numerator: v })}
            columns={columns}
            numericOnly
            testId="indicator-numerator"
          />
          <ColumnSelect
            label={t("indicators.denominator")}
            value={draft.denominator}
            onChange={(v) => onChange({ denominator: v })}
            columns={columns}
            numericOnly
            testId="indicator-denominator"
          />
          <div className="field">
            <span className="label">{t("indicators.multiplier")}</span>
            <div className="chips">
              {[1, 100, 1000].map((m) => (
                <button
                  key={m}
                  className="chip"
                  aria-pressed={draft.multiplier === m}
                  onClick={() => onChange({ multiplier: m })}
                >
                  {t(`indicators.per_${m}`)}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="field-row">
        <ColumnSelect
          label={t("indicators.disaggregation")}
          value={draft.disaggregation}
          onChange={(v) => onChange({ disaggregation: v, disaggregation2: v ? draft.disaggregation2 : null })}
          columns={textColumns}
          allowNone
        />
        {draft.disaggregation && (
          <ColumnSelect
            label={t("indicators.disaggregation2")}
            value={draft.disaggregation2}
            onChange={(v) => onChange({ disaggregation2: v })}
            columns={new Map([...textColumns].filter(([n]) => n !== draft.disaggregation))}
            allowNone
          />
        )}
      </div>
    </>
  );
}
