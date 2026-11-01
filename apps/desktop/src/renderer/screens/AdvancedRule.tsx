// Forms of the advanced cleaning rules: new variables, classes, dates, text,
// consistency checks and conditional replacement. Each form reports the rule it
// describes (without the note), or null while it is incomplete.

import { useEffect, useState } from "react";
import {
  allColumns,
  ComputeOp,
  CondOp,
  Dataset,
  DateMode,
  Rule,
  RuleClass,
  RuleCondition,
  RuleKind,
  TextOp,
} from "../api";
import { useI18n } from "../i18n";
import { Field, IconButton } from "../ui";

export const ADVANCED: RuleKind[] = ["text", "compute", "classes", "date", "check", "conditional"];
export const GROUPS: { key: string; kinds: RuleKind[] }[] = [
  { key: "fix", kinds: ["recode", "exclude", "range", "duplicates", "text"] },
  { key: "create", kinds: ["compute", "classes", "date"] },
  { key: "control", kinds: ["check", "conditional"] },
];

type Draft = Partial<Rule> | null;
const NAME = /^[A-Za-z_][A-Za-z0-9_.]{0,59}$/;
const num = (s: string) => (s.trim() === "" ? null : Number(s.replace(",", ".")));
const list = (s: string) =>
  s
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

function useTarget(ds: Dataset, suggestion: string) {
  const { t } = useI18n();
  const [name, setName] = useState(suggestion);
  const taken = allColumns(ds).some((c) => c.name === name);
  const error = !name ? "" : !NAME.test(name) ? t("advanced.nameInvalid") : taken ? t("advanced.nameTaken") : "";
  const ok = !!name && !error;
  const field = (
    <Field label={t("advanced.target")} hint={error || t("advanced.targetHint")}>
      {(id) => (
        <input
          id={id}
          className="input mono"
          value={name}
          onChange={(e) => setName(e.target.value.trim())}
          aria-invalid={!!error}
          data-testid="rule-target"
        />
      )}
    </Field>
  );
  return { name, ok, field };
}

function ColumnSelect({
  ds,
  value,
  onChange,
  label,
  numeric,
  testId,
}: {
  ds: Dataset;
  value: string;
  onChange: (v: string) => void;
  label: string;
  numeric?: boolean;
  testId?: string;
}) {
  const { t } = useI18n();
  return (
    <Field label={label}>
      {(id) => (
        <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId}>
          <option value="">{t("common.choose")}</option>
          {allColumns(ds)
            .filter((c) => !numeric || c.type === "number")
            .map((c) => (
              <option key={c.name}>{c.name}</option>
            ))}
        </select>
      )}
    </Field>
  );
}

function ColumnChips({
  ds,
  value,
  onChange,
  label,
  numeric,
}: {
  ds: Dataset;
  value: string[];
  onChange: (v: string[]) => void;
  label: string;
  numeric?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="field">
      <span className="label">{label}</span>
      <div className="chips">
        {value.map((c) => (
          <button key={c} className="chip" aria-pressed="true" onClick={() => onChange(value.filter((x) => x !== c))}>
            {c} ×
          </button>
        ))}
        <select
          className="input inline"
          value=""
          onChange={(e) => e.target.value && onChange([...value, e.target.value])}
          aria-label={t("cleaning.addColumn")}
          data-testid="rule-add-column"
        >
          <option value="">{t("cleaning.addColumn")}</option>
          {allColumns(ds)
            .filter((c) => !value.includes(c.name) && (!numeric || c.type === "number"))
            .map((c) => (
              <option key={c.name}>{c.name}</option>
            ))}
        </select>
      </div>
    </div>
  );
}

function Chips<T extends string>({
  options,
  value,
  onChange,
  label,
  prefix,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  prefix: string;
}) {
  const { t } = useI18n();
  return (
    <div className="field">
      <span className="label">{label}</span>
      <div className="chips">
        {options.map((o) => (
          <button
            key={o}
            className="chip"
            aria-pressed={value === o}
            onClick={() => onChange(o)}
            data-testid={`${prefix}-${o}`}
          >
            {t(`advanced.${prefix}_${o}`)}
          </button>
        ))}
      </div>
    </div>
  );
}

// ----- conditions ------------------------------------------------------------------

const COND_OPS: CondOp[] = ["eq", "ne", "in", "not_in", "lt", "le", "gt", "ge", "missing", "present"];
type CondRow = { column: string; op: CondOp; value: string };

const condReady = (c: CondRow) =>
  !!c.column &&
  (c.op === "missing" ||
    c.op === "present" ||
    c.op === "eq" ||
    c.op === "ne" ||
    ((c.op === "in" || c.op === "not_in") && list(c.value).length > 0) ||
    (["lt", "le", "gt", "ge"].includes(c.op) && c.value.trim() !== "" && !Number.isNaN(num(c.value))));

const toCondition = (c: CondRow): RuleCondition => {
  if (c.op === "in" || c.op === "not_in") return { column: c.column, op: c.op, values: list(c.value) };
  if (["lt", "le", "gt", "ge"].includes(c.op)) return { column: c.column, op: c.op, value: num(c.value) };
  if (c.op === "eq" || c.op === "ne") return { column: c.column, op: c.op, value: c.value };
  return { column: c.column, op: c.op };
};

function Conditions({
  ds,
  rows,
  onChange,
  combine,
  onCombine,
}: {
  ds: Dataset;
  rows: CondRow[];
  onChange: (rows: CondRow[]) => void;
  combine: "all" | "any";
  onCombine: (c: "all" | "any") => void;
}) {
  const { t } = useI18n();
  const set = (i: number, patch: Partial<CondRow>) => onChange(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  return (
    <div className="field" data-testid="conditions">
      <span className="label">{t("advanced.conditions")}</span>
      {rows.length > 1 && (
        <div className="chips">
          {(["all", "any"] as const).map((c) => (
            <button key={c} className="chip" aria-pressed={combine === c} onClick={() => onCombine(c)}>
              {t(`advanced.combine_${c}`)}
            </button>
          ))}
        </div>
      )}
      {rows.map((r, i) => (
        <div key={i} className="condition-row">
          <select
            className="input"
            value={r.column}
            onChange={(e) => set(i, { column: e.target.value })}
            aria-label={t("cleaning.column")}
            data-testid={`cond-column-${i}`}
          >
            <option value="">{t("cleaning.column")}</option>
            {allColumns(ds).map((c) => (
              <option key={c.name}>{c.name}</option>
            ))}
          </select>
          <select
            className="input"
            value={r.op}
            onChange={(e) => set(i, { op: e.target.value as CondOp })}
            aria-label={t("advanced.operator")}
            data-testid={`cond-op-${i}`}
          >
            {COND_OPS.map((o) => (
              <option key={o} value={o}>
                {t(`advanced.op_${o}`)}
              </option>
            ))}
          </select>
          {r.op !== "missing" && r.op !== "present" ? (
            <input
              className="input"
              value={r.value}
              onChange={(e) => set(i, { value: e.target.value })}
              placeholder={r.op === "in" || r.op === "not_in" ? t("advanced.valuesHint") : t("advanced.value")}
              aria-label={t("advanced.value")}
              inputMode={["lt", "le", "gt", "ge"].includes(r.op) ? "decimal" : undefined}
              data-testid={`cond-value-${i}`}
            />
          ) : (
            <span />
          )}
          {rows.length > 1 ? (
            <IconButton
              icon="trash"
              label={t("common.remove")}
              onClick={() => onChange(rows.filter((_, k) => k !== i))}
            />
          ) : (
            <span />
          )}
        </div>
      ))}
      {rows.length < 6 && (
        <div className="row-actions start">
          <button
            className="link"
            onClick={() => onChange([...rows, { column: "", op: "eq", value: "" }])}
            data-testid="cond-add"
          >
            {t("advanced.addCondition")}
          </button>
        </div>
      )}
    </div>
  );
}

// ----- the forms -------------------------------------------------------------------

export function AdvancedFields({
  kind,
  ds,
  onChange,
}: {
  kind: RuleKind;
  ds: Dataset;
  onChange: (rule: Draft) => void;
}) {
  switch (kind) {
    case "text":
      return <TextForm ds={ds} onChange={onChange} />;
    case "compute":
      return <ComputeForm ds={ds} onChange={onChange} />;
    case "classes":
      return <ClassesForm ds={ds} onChange={onChange} />;
    case "date":
      return <DateForm ds={ds} onChange={onChange} />;
    case "check":
      return <CheckForm ds={ds} onChange={onChange} />;
    case "conditional":
      return <ConditionalForm ds={ds} onChange={onChange} />;
    default:
      return null;
  }
}

type FormProps = { ds: Dataset; onChange: (rule: Draft) => void };

function TextForm({ ds, onChange }: FormProps) {
  const { t } = useI18n();
  const [column, setColumn] = useState("");
  const [ops, setOps] = useState<TextOp[]>(["trim", "squeeze"]);
  const [kase, setKase] = useState<"keep" | "lower" | "upper" | "title">("keep");
  useEffect(() => {
    const all = [...ops.filter((o) => !["lower", "upper", "title"].includes(o)), ...(kase === "keep" ? [] : [kase])];
    onChange(column && all.length ? { kind: "text", column, ops: all as TextOp[] } : null);
  }, [column, ops, kase, onChange]);
  const toggle = (o: TextOp) => setOps(ops.includes(o) ? ops.filter((x) => x !== o) : [...ops, o]);
  return (
    <>
      <ColumnSelect ds={ds} value={column} onChange={setColumn} label={t("cleaning.column")} testId="rule-column" />
      <div className="field">
        <span className="label">{t("advanced.textOps")}</span>
        {(["trim", "squeeze", "accents"] as TextOp[]).map((o) => (
          <label key={o} className="check">
            <input type="checkbox" checked={ops.includes(o)} onChange={() => toggle(o)} data-testid={`textop-${o}`} />
            <span className="check-text">{t(`advanced.textop_${o}`)}</span>
          </label>
        ))}
      </div>
      <Chips
        options={["keep", "lower", "upper", "title"] as const}
        value={kase}
        onChange={setKase}
        label={t("advanced.case")}
        prefix="case"
      />
      <p className="muted small">{t("advanced.textHelp")}</p>
    </>
  );
}

const OPS: ComputeOp[] = ["sum", "mean", "min", "max", "difference", "ratio", "count_values"];

function ComputeForm({ ds, onChange }: FormProps) {
  const { t } = useI18n();
  const [op, setOp] = useState<ComputeOp>("sum");
  const [columns, setColumns] = useState<string[]>([]);
  const [values, setValues] = useState("");
  const target = useTarget(ds, "");
  const pair = op === "difference" || op === "ratio";
  const counted = op === "count_values";
  useEffect(() => {
    const ok = target.ok && (pair ? columns.length === 2 : columns.length > 0) && (!counted || list(values).length > 0);
    onChange(
      ok ? { kind: "compute", op, columns, target: target.name, ...(counted ? { values: list(values) } : {}) } : null,
    );
  }, [op, columns, values, target.ok, target.name, pair, counted, onChange]);
  return (
    <>
      <Chips options={OPS} value={op} onChange={setOp} label={t("advanced.operation")} prefix="compute" />
      <p className="muted small">{t(`advanced.computeHelp_${op}`)}</p>
      <ColumnChips
        ds={ds}
        value={columns}
        onChange={(v) => setColumns(pair ? v.slice(-2) : v)}
        label={pair ? t("advanced.twoColumns") : t("advanced.columns")}
        numeric={!counted}
      />
      {counted && (
        <Field label={t("advanced.valuesToCount")} hint={t("advanced.valuesHint")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={values}
              onChange={(e) => setValues(e.target.value)}
              data-testid="rule-count-values"
            />
          )}
        </Field>
      )}
      {target.field}
    </>
  );
}

type ClassRow = { from: string; to: string; label: string };

function ClassesForm({ ds, onChange }: FormProps) {
  const { t, number } = useI18n();
  const [column, setColumn] = useState("");
  const [rows, setRows] = useState<ClassRow[]>([
    { from: "", to: "", label: "" },
    { from: "", to: "", label: "" },
  ]);
  const target = useTarget(ds, "");
  const info = allColumns(ds).find((c) => c.name === column);
  useEffect(() => {
    const classes: RuleClass[] = rows
      .filter((r) => r.label.trim())
      .map((r) => ({ from: num(r.from), to: num(r.to), label: r.label.trim() }));
    const ok =
      !!column &&
      target.ok &&
      classes.length > 0 &&
      classes.every((c) => (c.from !== null || c.to !== null) && (c.from === null || c.to === null || c.from < c.to));
    onChange(ok ? { kind: "classes", column, target: target.name, classes } : null);
  }, [column, rows, target.ok, target.name, onChange]);
  const set = (i: number, patch: Partial<ClassRow>) => setRows(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  return (
    <>
      <ColumnSelect
        ds={ds}
        value={column}
        onChange={setColumn}
        label={t("cleaning.column")}
        numeric
        testId="rule-column"
      />
      {info?.min !== undefined && info?.max !== undefined && (
        <p className="muted small">{t("cleaning.observed", { min: number(info.min, 2), max: number(info.max, 2) })}</p>
      )}
      <div className="field">
        <span className="label">{t("advanced.classes")}</span>
        <p className="muted small">{t("advanced.classesHelp")}</p>
        <div className="class-row head muted small">
          <span>{t("advanced.from")}</span>
          <span>{t("advanced.to")}</span>
          <span>{t("advanced.label")}</span>
          <span />
        </div>
        {rows.map((r, i) => (
          <div key={i} className="class-row">
            <input
              className="input num"
              inputMode="decimal"
              value={r.from}
              onChange={(e) => set(i, { from: e.target.value })}
              aria-label={t("advanced.from")}
              data-testid={`class-from-${i}`}
            />
            <input
              className="input num"
              inputMode="decimal"
              value={r.to}
              onChange={(e) => set(i, { to: e.target.value })}
              aria-label={t("advanced.to")}
              data-testid={`class-to-${i}`}
            />
            <input
              className="input"
              value={r.label}
              onChange={(e) => set(i, { label: e.target.value })}
              aria-label={t("advanced.label")}
              data-testid={`class-label-${i}`}
            />
            {rows.length > 1 ? (
              <IconButton
                icon="trash"
                label={t("common.remove")}
                onClick={() => setRows(rows.filter((_, k) => k !== i))}
              />
            ) : (
              <span />
            )}
          </div>
        ))}
        <div className="row-actions start">
          <button
            className="link"
            onClick={() => setRows([...rows, { from: rows[rows.length - 1]?.to ?? "", to: "", label: "" }])}
            data-testid="class-add"
          >
            {t("advanced.addClass")}
          </button>
        </div>
      </div>
      {target.field}
    </>
  );
}

const MODES: DateMode[] = ["duration", "age", "year", "month"];

function DateForm({ ds, onChange }: FormProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<DateMode>("duration");
  const [column, setColumn] = useState(() => (allColumns(ds).some((c) => c.name === "start") ? "start" : ""));
  const [end, setEnd] = useState(() => (allColumns(ds).some((c) => c.name === "end") ? "end" : ""));
  const [refKind, setRefKind] = useState<"date" | "column">("date");
  const [refDate, setRefDate] = useState("");
  const [refColumn, setRefColumn] = useState("");
  const target = useTarget(ds, "");
  useEffect(() => {
    let ok = !!column && target.ok;
    const rule: Partial<Rule> = { kind: "date", mode, column, target: target.name };
    if (mode === "duration") {
      ok = ok && !!end;
      rule.end = end;
    }
    if (mode === "age") {
      if (refKind === "date") {
        ok = ok && /^\d{4}-\d{2}-\d{2}$/.test(refDate);
        rule.ref_date = refDate;
      } else {
        ok = ok && !!refColumn;
        rule.ref_column = refColumn;
      }
    }
    onChange(ok ? rule : null);
  }, [mode, column, end, refKind, refDate, refColumn, target.ok, target.name, onChange]);
  return (
    <>
      <Chips options={MODES} value={mode} onChange={setMode} label={t("advanced.dateMode")} prefix="date" />
      <ColumnSelect
        ds={ds}
        value={column}
        onChange={setColumn}
        label={
          mode === "duration"
            ? t("advanced.startColumn")
            : mode === "age"
              ? t("advanced.birthColumn")
              : t("advanced.dateColumn")
        }
        testId="rule-column"
      />
      {mode === "duration" && (
        <ColumnSelect ds={ds} value={end} onChange={setEnd} label={t("advanced.endColumn")} testId="rule-end" />
      )}
      {mode === "age" && (
        <>
          <div className="chips">
            {(["date", "column"] as const).map((k) => (
              <button key={k} className="chip" aria-pressed={refKind === k} onClick={() => setRefKind(k)}>
                {t(`advanced.ref_${k}`)}
              </button>
            ))}
          </div>
          {refKind === "date" ? (
            <Field label={t("advanced.refDate")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  type="date"
                  value={refDate}
                  onChange={(e) => setRefDate(e.target.value)}
                  data-testid="rule-ref-date"
                />
              )}
            </Field>
          ) : (
            <ColumnSelect ds={ds} value={refColumn} onChange={setRefColumn} label={t("advanced.refColumn")} />
          )}
        </>
      )}
      <p className="muted small">{t(`advanced.dateHelp_${mode}`)}</p>
      {target.field}
    </>
  );
}

function CheckForm({ ds, onChange }: FormProps) {
  const { t } = useI18n();
  const [rows, setRows] = useState<CondRow[]>([{ column: "", op: "gt", value: "" }]);
  const [combine, setCombine] = useState<"all" | "any">("all");
  const [action, setAction] = useState<"flag" | "exclude" | "missing">("flag");
  const [column, setColumn] = useState("");
  const target = useTarget(ds, "");
  useEffect(() => {
    let ok = rows.every(condReady);
    const rule: Partial<Rule> = { kind: "check", conditions: rows.map(toCondition), combine, action };
    if (action === "flag") {
      ok = ok && target.ok;
      rule.target = target.name;
    }
    if (action === "missing") {
      ok = ok && !!column;
      rule.column = column;
    }
    onChange(ok ? rule : null);
  }, [rows, combine, action, column, target.ok, target.name, onChange]);
  return (
    <>
      <p className="muted small">{t("advanced.checkHelp")}</p>
      <Conditions ds={ds} rows={rows} onChange={setRows} combine={combine} onCombine={setCombine} />
      <Chips
        options={["flag", "exclude", "missing"] as const}
        value={action}
        onChange={setAction}
        label={t("advanced.action")}
        prefix="action"
      />
      {action === "flag" && target.field}
      {action === "missing" && (
        <ColumnSelect ds={ds} value={column} onChange={setColumn} label={t("advanced.columnToEmpty")} />
      )}
    </>
  );
}

function ConditionalForm({ ds, onChange }: FormProps) {
  const { t } = useI18n();
  const [rows, setRows] = useState<CondRow[]>([{ column: "", op: "eq", value: "" }]);
  const [combine, setCombine] = useState<"all" | "any">("all");
  const [into, setInto] = useState<"existing" | "new">("existing");
  const [column, setColumn] = useState("");
  const [missing, setMissing] = useState(false);
  const [value, setValue] = useState("");
  const target = useTarget(ds, "");
  useEffect(() => {
    const name = into === "existing" ? column : target.name;
    const ok = rows.every(condReady) && (into === "existing" ? !!column : target.ok) && (missing || value !== "");
    onChange(
      ok
        ? {
            kind: "conditional",
            conditions: rows.map(toCondition),
            combine,
            target: name,
            value: missing ? null : value,
          }
        : null,
    );
  }, [rows, combine, into, column, missing, value, target.ok, target.name, onChange]);
  return (
    <>
      <p className="muted small">{t("advanced.conditionalHelp")}</p>
      <Conditions ds={ds} rows={rows} onChange={setRows} combine={combine} onCombine={setCombine} />
      <Chips
        options={["existing", "new"] as const}
        value={into}
        onChange={setInto}
        label={t("advanced.setColumn")}
        prefix="into"
      />
      {into === "existing" ? (
        <ColumnSelect ds={ds} value={column} onChange={setColumn} label={t("cleaning.column")} testId="rule-column" />
      ) : (
        target.field
      )}
      <div className="field">
        <span className="label">{t("advanced.newValue")}</span>
        <label className="check">
          <input type="checkbox" checked={missing} onChange={(e) => setMissing(e.target.checked)} />
          <span className="check-text">{t("cleaning.missing")}</span>
        </label>
        {!missing && (
          <input
            className="input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-label={t("advanced.newValue")}
            data-testid="rule-value"
          />
        )}
      </div>
    </>
  );
}
