// Sample size for a survey, computed by R: estimate a share or a mean, or detect a
// change between two rounds. Every step of the calculation is shown.

import { ChangeEvent, useEffect, useState } from "react";
import { call } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Field, Notice, Panel } from "../ui";

type Goal = "estimate_prop" | "estimate_mean" | "compare_prop" | "compare_mean";
const GOALS: Goal[] = ["estimate_prop", "compare_prop", "estimate_mean", "compare_mean"];

interface Result {
  method_key: string;
  per_round: boolean;
  n0: number;
  n_deff: number;
  n_fpc: number;
  n_domains: number;
  n: number;
  script: string;
}

type Form = Record<string, string>;
const DEFAULTS: Form = {
  p: "50",
  p2: "60",
  margin: "5",
  sd: "10",
  delta: "2",
  deff: "1.5",
  population: "",
  domains: "1",
  response: "90",
  conf: "0.95",
  power: "0.8",
};

/** "12,5" or "12.5" -> 12.5; empty -> null. */
function parse(v: string): number | null {
  const x = Number(v.replace(",", ".").replace(/\s/g, ""));
  return v.trim() === "" || !Number.isFinite(x) ? null : x;
}

export function SampleSizePanel({ onClose }: { onClose: () => void }) {
  const { t, number, percent } = useI18n();
  const { describe } = useProject();
  const [goal, setGoal] = useState<Goal>("estimate_prop");
  const [form, setForm] = useState<Form>(DEFAULTS);
  const [out, setOut] = useState<{ for: string; r?: Result; err?: string } | null>(null);
  const set = (k: string) => (e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const pct = (k: string) => {
    const x = parse(form[k]);
    return x === null ? null : x / 100;
  };
  const params: Record<string, unknown> = {
    goal,
    conf: Number(form.conf),
    power: Number(form.power),
    deff: parse(form.deff),
    domains: parse(form.domains),
    response: pct("response"),
    population: parse(form.population),
    ...(goal.endsWith("prop") ? { p: pct("p") } : { sd: parse(form.sd) }),
    ...(goal === "compare_prop" ? { p2: pct("p2") } : {}),
    ...(goal === "estimate_prop" ? { margin: pct("margin") } : {}),
    ...(goal === "estimate_mean" ? { margin: parse(form.margin) } : {}),
    ...(goal === "compare_mean" ? { delta: parse(form.delta) } : {}),
  };
  const key = JSON.stringify(params);

  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      call<Result>("tool.sample_size", JSON.parse(key))
        .then((r) => live && setOut({ for: key, r }))
        .catch((e) => live && setOut({ for: key, err: describe(e) }));
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [key, describe]);

  const current = out?.for === key ? out : null;
  const r = current?.r;
  const field = (k: string, label: string, hint?: string) => (
    <Field label={label} hint={hint}>
      {(id) => (
        <input
          id={id}
          className="input"
          inputMode="decimal"
          value={form[k]}
          onChange={set(k)}
          data-testid={`ss-${k}`}
        />
      )}
    </Field>
  );

  return (
    <Panel title={t("sample.title")} onClose={onClose} testId="sample-panel">
      <p className="muted">{t("sample.lead")}</p>
      <div className="field">
        <span className="label">{t("sample.goal")}</span>
        <div className="kind-grid">
          {GOALS.map((g) => (
            <button
              key={g}
              className="chip"
              aria-pressed={goal === g}
              onClick={() => setGoal(g)}
              data-testid={`ss-goal-${g}`}
            >
              {t(`sample.goal_${g}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="field-row">
        {goal.endsWith("prop")
          ? field("p", goal === "compare_prop" ? t("sample.p1") : t("sample.p"), t("sample.pHint"))
          : field("sd", t("sample.sd"), t("sample.sdHint"))}
        {goal === "compare_prop" && field("p2", t("sample.p2"))}
        {goal === "estimate_prop" && field("margin", t("sample.marginPct"))}
        {goal === "estimate_mean" && field("margin", t("sample.margin"))}
        {goal === "compare_mean" && field("delta", t("sample.delta"))}
      </div>
      <div className="field-row">
        {field("deff", t("sample.deff"), t("sample.deffHint"))}
        {field("response", t("sample.response"))}
      </div>
      <div className="field-row">
        {field("domains", t("sample.domains"), t("sample.domainsHint"))}
        {goal.startsWith("estimate") && field("population", t("sample.population"), t("sample.populationHint"))}
      </div>
      <div className="field-row">
        <div className="field">
          <span className="label">{t("sample.conf")}</span>
          <div className="chips">
            {["0.9", "0.95", "0.99"].map((c) => (
              <button
                key={c}
                className="chip"
                aria-pressed={form.conf === c}
                onClick={() => setForm({ ...form, conf: c })}
              >
                {percent(Number(c), 0)}
              </button>
            ))}
          </div>
        </div>
        {goal.startsWith("compare") && (
          <div className="field">
            <span className="label">{t("sample.power")}</span>
            <div className="chips">
              {["0.8", "0.9"].map((c) => (
                <button
                  key={c}
                  className="chip"
                  aria-pressed={form.power === c}
                  onClick={() => setForm({ ...form, power: c })}
                >
                  {percent(Number(c), 0)}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
      {current?.err && <Notice kind="error">{current.err}</Notice>}
      {r && (
        <div className="merge-check" data-testid="sample-result">
          <p className="sample-n">{t(r.per_round ? "sample.resultRound" : "sample.result", { n: number(r.n, 0) })}</p>
          <ol className="small muted sample-steps">
            <li>{t(`sample.step_${r.method_key}`, { n: number(r.n0, 1) })}</li>
            {r.n_deff !== r.n0 && <li>{t("sample.step_deff", { n: number(r.n_deff, 1), deff: form.deff })}</li>}
            {r.n_fpc !== r.n_deff && <li>{t("sample.step_fpc", { n: number(r.n_fpc, 1) })}</li>}
            {r.n_domains !== r.n_fpc && (
              <li>{t("sample.step_domains", { n: number(r.n_domains, 1), k: form.domains })}</li>
            )}
            <li>{t("sample.step_response", { n: number(r.n, 0), rate: form.response })}</li>
          </ol>
          <details>
            <summary className="small">{t("sample.script")}</summary>
            <pre className="code small">{r.script}</pre>
          </details>
        </div>
      )}
    </Panel>
  );
}
