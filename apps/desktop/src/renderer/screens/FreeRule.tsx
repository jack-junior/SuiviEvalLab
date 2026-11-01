// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Free cleaning steps: a column computed by a formula, a filter written as a
// formula, and an R script. The formula editor checks the formula as it is typed
// (the engine reads it with its own parser) and shows what it gives on the data.

import { useEffect, useMemo, useRef, useState } from "react";
import { allColumns, call, Dataset, EngineCallError, FormulaPreview, Rule, RuleKind } from "../api";
import { useI18n } from "../i18n";
import { Field } from "../ui";

export const FREE: RuleKind[] = ["formula", "filter", "r_script"];

const NAME = /^[A-Za-z_][A-Za-z0-9_.]{0,59}$/;
const OPERATORS = ["+", "-", "*", "/", "=", "<>", "<", "<=", ">", ">=", "(", ")", ";", '""'];

interface FunctionInfo {
  name: string;
  fr: string;
  en: string;
  min: number;
  max: number | null;
}

let functionsCache: FunctionInfo[] | null = null;

function useFunctions() {
  const [list, setList] = useState<FunctionInfo[]>(functionsCache ?? []);
  useEffect(() => {
    if (functionsCache) return;
    call<{ functions: FunctionInfo[] }>("formula.functions")
      .then((r) => {
        functionsCache = r.functions;
        setList(r.functions);
      })
      .catch(() => undefined);
  }, []);
  return list;
}

/** A column name as written in a formula: between brackets when it is not a plain word. */
export function columnRef(name: string) {
  return /^[^\W\d][\w.]*$/u.test(name) ? name : `[${name}]`;
}

export interface FormulaError {
  reason: string;
  pos: number;
  info: Record<string, string>;
}

export function useFormulaErrorText() {
  const { t, hasKey } = useI18n();
  return (e: FormulaError) => {
    const key = `formula.err_${e.reason}`;
    const base = hasKey(key)
      ? t(key, { name: e.info.name ?? "", sign: e.info.sign ?? "", min: e.info.min ?? "", max: e.info.max ?? "" })
      : t("formula.err_invalid");
    return e.info.suggestion ? `${base} ${t("formula.didYouMean", { name: e.info.suggestion })}` : base;
  };
}

export function FormulaEditor({
  ds,
  value,
  onChange,
  condition = false,
  onState,
  testId = "formula",
}: {
  ds: Dataset;
  value: string;
  onChange: (v: string) => void;
  condition?: boolean;
  onState?: (ok: boolean) => void;
  testId?: string;
}) {
  const { t, lang, number } = useI18n();
  const functions = useFunctions();
  const area = useRef<HTMLTextAreaElement>(null);
  const [preview, setPreview] = useState<FormulaPreview | null>(null);
  const [error, setError] = useState<FormulaError | null>(null);
  const [search, setSearch] = useState("");
  const [palette, setPalette] = useState<"columns" | "functions">("columns");
  const errorText = useFormulaErrorText();
  const stamp = `${ds.id}-${ds.rules.length}-${ds.clean_rows}`;

  useEffect(() => {
    const empty = !value.trim();
    const timer = setTimeout(
      () => {
        if (empty) {
          setPreview(null);
          setError(null);
          onState?.(false);
          return;
        }
        call<FormulaPreview>("formula.preview", { dataset_id: ds.id, expression: value, condition })
          .then((p) => {
            setPreview(p);
            setError(null);
            onState?.(true);
          })
          .catch((e: unknown) => {
            setPreview(null);
            if (e instanceof EngineCallError && e.key === "formula_invalid") {
              const { reason, pos, ...info } = e.data as { reason: string; pos: number } & Record<string, unknown>;
              setError({ reason, pos, info: Object.fromEntries(Object.entries(info).map(([k, v]) => [k, String(v)])) });
            } else {
              setError({ reason: "invalid", pos: 0, info: {} });
            }
            onState?.(false);
          });
      },
      empty ? 0 : 350,
    );
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, condition, ds.id, stamp]);

  const insert = (text: string, back = 0) => {
    const el = area.current;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? value.length;
    const next = value.slice(0, start) + text + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const at = start + text.length - back;
      el.setSelectionRange(at, at);
    });
  };

  const columns = allColumns(ds).filter((c) => c.name.toLowerCase().includes(search.toLowerCase()));
  const fnName = (f: FunctionInfo) => (lang === "fr" ? f.fr : f.en);
  const fns = functions.filter((f) => fnName(f).includes(search.toLowerCase()));

  return (
    <div className="formula" data-testid={testId}>
      <textarea
        ref={area}
        className="input mono formula-text"
        rows={3}
        value={value}
        spellCheck={false}
        onChange={(e) => onChange(e.target.value)}
        placeholder={condition ? t("formula.placeholderCondition") : t("formula.placeholder")}
        aria-label={t("formula.label")}
        aria-invalid={!!error}
        data-testid={`${testId}-text`}
      />
      <div className="formula-ops" aria-label={t("formula.operators")}>
        {OPERATORS.map((o) => (
          <button
            key={o}
            className="chip mono"
            onClick={() => insert(o === '""' ? '""' : ` ${o} `, o === '""' ? 1 : 0)}
          >
            {o}
          </button>
        ))}
        {(lang === "fr" ? ["et", "ou", "non", "manquant"] : ["and", "or", "not", "missing"]).map((w) => (
          <button key={w} className="chip mono" onClick={() => insert(` ${w} `)}>
            {w}
          </button>
        ))}
      </div>
      <div className="formula-palette">
        <div className="chips">
          <button className="chip" aria-pressed={palette === "columns"} onClick={() => setPalette("columns")}>
            {t("formula.columns")}
          </button>
          <button
            className="chip"
            aria-pressed={palette === "functions"}
            onClick={() => setPalette("functions")}
            data-testid={`${testId}-functions`}
          >
            {t("formula.functions")}
          </button>
          <input
            className="input inline"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("formula.search")}
            aria-label={t("formula.search")}
          />
        </div>
        <div className="palette-list">
          {palette === "columns"
            ? columns.slice(0, 200).map((c) => (
                <button
                  key={c.name}
                  className="palette-item mono"
                  onClick={() => insert(columnRef(c.name))}
                  title={c.name}
                >
                  {c.name}
                  <span className="muted small"> {t(`columns.type_${c.type}`)}</span>
                </button>
              ))
            : fns.map((f) => (
                <button
                  key={f.name}
                  className="palette-item"
                  onClick={() => insert(`${fnName(f)}()`, 1)}
                  title={t(`formula.fn_${f.name}`)}
                  data-testid={`fn-${f.name}`}
                >
                  <span className="mono">{fnName(f)}()</span>
                  <span className="muted small"> {t(`formula.fn_${f.name}`)}</span>
                </button>
              ))}
        </div>
      </div>
      {error && (
        <div className="formula-error" role="alert" data-testid={`${testId}-error`}>
          <div>{errorText(error)}</div>
          {value && (
            <code className="formula-where">
              {value.slice(0, error.pos)}
              <mark>{value.slice(error.pos, error.pos + 1) || " "}</mark>
              {value.slice(error.pos + 1)}
            </code>
          )}
        </div>
      )}
      {preview && (
        <div className="formula-preview" data-testid={`${testId}-preview`}>
          {condition ? (
            <span>
              {t("formula.conditionCount", {
                n: number(preview.true ?? 0, 0),
                total: number(preview.rows, 0),
              })}
            </span>
          ) : (
            <>
              <span className="muted small">
                {t("formula.result", {
                  type: t(`formula.type_${preview.type}`),
                  missing: number(preview.missing ?? 0, 0),
                  distinct: number(preview.distinct ?? 0, 0),
                })}
              </span>
              {preview.sample && preview.sample.length > 0 && (
                <table className="table compact">
                  <thead>
                    <tr>
                      {Object.keys(preview.sample[0].inputs).map((c) => (
                        <th key={c} className="mono">
                          {c}
                        </th>
                      ))}
                      <th>{t("formula.value")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.sample.map((r, i) => (
                      <tr key={i}>
                        {Object.values(r.inputs).map((v, j) => (
                          <td key={j} className={v === null ? "na" : undefined}>
                            {v ?? t("data.na")}
                          </td>
                        ))}
                        <td className={r.value === null ? "na" : "strong"}>{r.value ?? t("data.na")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Form of a free step; reports the rule (without the note), or null while it is incomplete. */
export function FreeFields({
  kind,
  ds,
  initial,
  onChange,
}: {
  kind: RuleKind;
  ds: Dataset;
  initial?: Rule;
  onChange: (r: Partial<Rule> | null) => void;
}) {
  const { t } = useI18n();
  const [expression, setExpression] = useState(initial?.expression ?? "");
  const [target, setTarget] = useState(initial?.target ?? "");
  const [action, setAction] = useState<"keep" | "drop">(initial?.action === "drop" ? "drop" : "keep");
  const [code, setCode] = useState(initial?.code ?? "");
  const [formulaOk, setFormulaOk] = useState(false);
  const existing = allColumns(ds).some((c) => c.name === target) && target !== initial?.target;
  const nameError = target && !NAME.test(target) ? t("advanced.nameInvalid") : "";

  const rule = useMemo<Partial<Rule> | null>(() => {
    if (kind === "formula") return formulaOk && target && !nameError ? { kind, target, expression } : null;
    if (kind === "filter") return formulaOk ? { kind, expression, action } : null;
    return code.trim() ? { kind, code } : null;
  }, [kind, formulaOk, target, nameError, expression, action, code]);

  useEffect(() => onChange(rule), [rule, onChange]);

  if (kind === "r_script")
    return (
      <div className="stack-sm">
        <p className="muted small">{t("rscript.help")}</p>
        <textarea
          className="input mono code-area"
          rows={12}
          value={code}
          spellCheck={false}
          onChange={(e) => setCode(e.target.value)}
          placeholder={t("rscript.placeholderCleaning")}
          aria-label={t("rscript.code")}
          data-testid="rscript-code"
        />
        <p className="muted small">{t("rscript.rows")}</p>
      </div>
    );

  return (
    <div className="stack-sm">
      {kind === "formula" ? (
        <Field
          label={t("formula.target")}
          hint={nameError || (existing ? t("formula.targetReplace") : t("formula.targetHint"))}
        >
          {(id) => (
            <input
              id={id}
              className="input mono"
              value={target}
              list="formula-columns"
              onChange={(e) => setTarget(e.target.value.trim())}
              aria-invalid={!!nameError}
              data-testid="rule-target"
            />
          )}
        </Field>
      ) : (
        <div className="chips">
          <button
            className="chip"
            aria-pressed={action === "keep"}
            onClick={() => setAction("keep")}
            data-testid="filter-keep"
          >
            {t("formula.keep")}
          </button>
          <button
            className="chip"
            aria-pressed={action === "drop"}
            onClick={() => setAction("drop")}
            data-testid="filter-drop"
          >
            {t("formula.drop")}
          </button>
        </div>
      )}
      <datalist id="formula-columns">
        {allColumns(ds).map((c) => (
          <option key={c.name} value={c.name} />
        ))}
      </datalist>
      <FormulaEditor
        ds={ds}
        value={expression}
        onChange={setExpression}
        condition={kind === "filter"}
        onState={setFormulaOk}
      />
      <details className="formula-help">
        <summary>{t("formula.examplesTitle")}</summary>
        <ul className="muted small">
          <li className="mono">{t("formula.example1")}</li>
          <li className="mono">{t("formula.example2")}</li>
          <li className="mono">{t("formula.example3")}</li>
          <li className="mono">{t("formula.example4")}</li>
        </ul>
        <p className="muted small">{t("formula.rules")}</p>
      </details>
    </div>
  );
}
