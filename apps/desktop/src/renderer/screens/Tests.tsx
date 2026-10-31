// Test assistant: pick a question, the data, run the test in R, read the
// conclusion in words, and keep it for the report.

import { useEffect, useMemo, useState } from "react";
import { call, Dataset, TestQuestion, TestResult, TestSpec } from "../api";
import { useI18n } from "../i18n";
import { useLabels } from "../labels";
import { useProject } from "../state";
import { Confirm, Empty, Field, Icon, IconButton, Notice } from "../ui";
import { SampleSizePanel } from "./SampleSize";

const QUESTIONS: { q: TestQuestion; icon: string }[] = [
  { q: "groups", icon: "table" },
  { q: "target", icon: "target" },
  { q: "paired", icon: "chart" },
];

const blank = (q: TestQuestion, ds: string): TestSpec => ({
  question: q,
  kind: "proportion",
  dataset_id: ds,
  outcome: { column: "", values: [] },
  title: "",
  mode: "columns",
});

function ValuePicker({
  ds,
  column,
  values,
  onChange,
}: {
  ds: Dataset;
  column: string;
  values: string[];
  onChange: (v: string[]) => void;
}) {
  const { t, number } = useI18n();
  const { valText, val } = useLabels();
  const [loaded, setLoaded] = useState<{ key: string; values: { value: string | null; n: number }[] } | null>(null);
  const key = `${ds.id}|${column}`;
  useEffect(() => {
    if (!column) return;
    call<{ values: { value: string | null; n: number }[] }>("dataset.column_values", { id: ds.id, column })
      .then((r) => setLoaded({ key, values: r.values }))
      .catch(() => setLoaded({ key, values: [] }));
  }, [ds.id, column, key]);
  const list = loaded?.key === key ? loaded.values : [];
  return (
    <div className="field">
      <span className="label">{t("indicators.success")}</span>
      <div className="value-list" data-testid="test-values">
        {list
          .filter((v) => v.value !== null)
          .map((v) => (
            <label key={v.value} className="check">
              <input
                type="checkbox"
                data-testid={`tvalue-${v.value}`}
                checked={values.includes(v.value!)}
                onChange={(e) =>
                  onChange(e.target.checked ? [...values, v.value!] : values.filter((x) => x !== v.value))
                }
              />
              <span className="check-text">
                {valText(column, v.value!, ds)}
                {val(column, v.value, ds) && <span className="code"> {v.value}</span>}
              </span>
              <span className="muted small">{number(v.n, 0)}</span>
            </label>
          ))}
      </div>
    </div>
  );
}

export function Tests() {
  const { t, lang, number, percent } = useI18n();
  const { snap, run, error } = useProject();
  const { colText, valText, col } = useLabels();
  const [spec, setSpec] = useState<TestSpec | null>(null);
  const [targetText, setTargetText] = useState("");
  const [answer, setAnswer] = useState<{ result: TestResult; conclusion: Record<string, string[]> } | null>(null);
  const [running, setRunning] = useState(false);
  const [sampling, setSampling] = useState(false);
  const [showScript, setShowScript] = useState(false);
  const [deleting, setDeleting] = useState<TestSpec | null>(null);
  const [saved, setSaved] = useState(false);

  const ds = useMemo(
    () => snap?.datasets.find((d) => d.id === spec?.dataset_id) ?? null,
    [snap?.datasets, spec?.dataset_id],
  );
  if (!snap) return null;
  if (!snap.datasets.length)
    return (
      <div className="inner wide">
        <h1>{t("nav.tests")}</h1>
        <Empty icon="table" title={t("tests.noData")} text={t("tests.noDataText")} />
      </div>
    );

  const columns = ds?.columns ?? [];
  const groupColumns = columns.filter((c) => c.type === "text" && c.distinct <= 40 && c.distinct >= 2);
  const numericColumns = columns.filter((c) => c.type === "number");

  const update = (p: Partial<TestSpec>) => {
    setSpec((s) => (s ? { ...s, ...p } : s));
    setAnswer(null);
    setSaved(false);
  };

  const parsedTarget = () => {
    const v = Number(targetText.replace(",", ".").replace(/\s/g, ""));
    if (targetText.trim() === "" || Number.isNaN(v)) return undefined;
    return spec?.kind === "proportion" ? v / 100 : v;
  };

  const complete =
    !!spec &&
    !!spec.outcome.column &&
    (spec.kind === "mean" || spec.outcome.values.length > 0) &&
    (spec.question !== "groups" || !!spec.group) &&
    (spec.question !== "target" || parsedTarget() !== undefined) &&
    (spec.question !== "paired" || (spec.mode === "columns" ? !!spec.column_b : !!spec.dataset_b_id));

  const body = () => ({ ...spec!, target: spec!.question === "target" ? parsedTarget() : undefined });

  const runTest = async () => {
    if (!spec) return;
    setRunning(true);
    const r = await run<{ result: TestResult; conclusion: Record<string, string[]> }>(
      "test.run",
      { test: body() },
      "test",
    );
    setRunning(false);
    if (r) setAnswer(r);
  };

  const saveTest = async () => {
    if (!spec) return;
    const r = await run<{ saved: string }>("test.save", { id: spec.id, test: body() });
    if (r) {
      setSpec({ ...spec, id: r.saved });
      setSaved(true);
    }
  };

  const open = (s: TestSpec) => {
    setSpec(s);
    setTargetText(
      s.target === undefined ? "" : String(s.kind === "proportion" ? +(s.target * 100).toFixed(4) : s.target),
    );
    setAnswer(null);
    setSaved(false);
  };

  const pFmt = (p: number) => (p < 0.001 ? t("analysis.pSmall") : t("analysis.pEq", { p: number(p, 3) }));
  const valueFmt = (v: number | null | undefined) =>
    v === null || v === undefined ? t("common.none") : spec?.kind === "proportion" ? percent(v) : number(v, 2);
  const autoTitle = (s: TestSpec) =>
    s.title ||
    t("common.labelled", {
      a: t(`tests.q_${s.question}`),
      b: `${col(s.outcome.column) ?? s.outcome.column}${s.group ? ` × ${col(s.group) ?? s.group}` : ""}`,
    });

  return (
    <div className="split">
      <aside className="split-list" aria-label={t("tests.saved")}>
        <button
          className="btn primary"
          onClick={() => open(blank("groups", snap.datasets[0].id))}
          data-testid="new-test"
        >
          {t("tests.new")}
        </button>
        <button className="btn" onClick={() => setSampling(true)} data-testid="open-sample">
          <Icon name="calc" /> {t("sample.title")}
        </button>
        {sampling && <SampleSizePanel onClose={() => setSampling(false)} />}
        <div className="split-group">
          <div className="split-group-title">{t("tests.saved")}</div>
          {snap.tests.length === 0 && <p className="muted small indent">{t("tests.noneSaved")}</p>}
          {snap.tests.map((s) => (
            <div key={s.id} className="saved-test">
              <button
                className="split-item"
                aria-current={spec?.id === s.id ? "true" : undefined}
                onClick={() => open(s)}
              >
                {autoTitle(s)}
              </button>
              <IconButton icon="trash" label={t("common.delete")} onClick={() => setDeleting(s)} />
            </div>
          ))}
        </div>
      </aside>

      <div className="split-main">
        <div className="inner wide">
          <div>
            <h1 className="h1-small">{t("nav.tests")}</h1>
            <p className="lead small-lead">{t("tests.lead")}</p>
          </div>
          {error && <Notice kind="error">{error}</Notice>}

          {!spec ? (
            <div className="question-grid">
              {QUESTIONS.map(({ q, icon }) => (
                <button
                  key={q}
                  className="question"
                  onClick={() => open(blank(q, snap.datasets[0].id))}
                  data-testid={`question-${q}`}
                >
                  <Icon name={icon} size={22} />
                  <span className="question-title">{t(`tests.q_${q}`)}</span>
                  <span className="question-text">{t(`tests.qtext_${q}`)}</span>
                </button>
              ))}
            </div>
          ) : (
            <>
              <div className="chips">
                {QUESTIONS.map(({ q }) => (
                  <button
                    key={q}
                    className="chip"
                    aria-pressed={spec.question === q}
                    onClick={() => update({ question: q })}
                  >
                    {t(`tests.q_${q}`)}
                  </button>
                ))}
              </div>

              <section className="test-form">
                <div className="field-row">
                  <Field label={t("tests.dataset")}>
                    {(id) => (
                      <select
                        id={id}
                        className="input"
                        value={spec.dataset_id}
                        onChange={(e) =>
                          update({ dataset_id: e.target.value, outcome: { column: "", values: [] }, group: undefined })
                        }
                      >
                        {snap.datasets.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </Field>
                  <div className="field">
                    <span className="label">{t("tests.kind")}</span>
                    <div className="chips">
                      {(["proportion", "mean"] as const).map((k) => (
                        <button
                          key={k}
                          className="chip"
                          aria-pressed={spec.kind === k}
                          onClick={() => update({ kind: k, outcome: { column: "", values: [] } })}
                          data-testid={`kind-${k}`}
                        >
                          {t(`tests.kind_${k}`)}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <Field label={t("tests.variable")}>
                  {(id) => (
                    <select
                      id={id}
                      className="input"
                      value={spec.outcome.column}
                      onChange={(e) => update({ outcome: { column: e.target.value, values: [] } })}
                      data-testid="test-variable"
                    >
                      <option value="">{t("common.choose")}</option>
                      {(spec.kind === "mean" ? numericColumns : columns).map((c) => (
                        <option key={c.name} value={c.name}>
                          {colText(c.name, ds ?? undefined)}
                        </option>
                      ))}
                    </select>
                  )}
                </Field>
                {spec.kind === "proportion" && spec.outcome.column && ds && (
                  <ValuePicker
                    ds={ds}
                    column={spec.outcome.column}
                    values={spec.outcome.values}
                    onChange={(v) => update({ outcome: { ...spec.outcome, values: v } })}
                  />
                )}

                {spec.question === "groups" && (
                  <Field label={t("tests.group")} hint={t("tests.groupHint")}>
                    {(id) => (
                      <select
                        id={id}
                        className="input"
                        value={spec.group ?? ""}
                        onChange={(e) => update({ group: e.target.value || undefined })}
                        data-testid="test-group"
                      >
                        <option value="">{t("common.choose")}</option>
                        {groupColumns.map((c) => (
                          <option key={c.name} value={c.name}>
                            {colText(c.name, ds ?? undefined)}
                          </option>
                        ))}
                      </select>
                    )}
                  </Field>
                )}

                {spec.question === "target" && (
                  <Field label={spec.kind === "proportion" ? t("indicators.targetPercent") : t("indicators.target")}>
                    {(id) => (
                      <input
                        id={id}
                        className="input"
                        inputMode="decimal"
                        value={targetText}
                        onChange={(e) => {
                          setTargetText(e.target.value);
                          setAnswer(null);
                        }}
                        data-testid="test-target"
                      />
                    )}
                  </Field>
                )}

                {spec.question === "paired" && (
                  <>
                    <div className="field">
                      <span className="label">{t("tests.pairedMode")}</span>
                      <div className="chips">
                        {(["columns", "datasets"] as const).map((m) => (
                          <button
                            key={m}
                            className="chip"
                            aria-pressed={spec.mode === m}
                            onClick={() => update({ mode: m })}
                          >
                            {t(`tests.mode_${m}`)}
                          </button>
                        ))}
                      </div>
                      <div className="field-hint">{t(`tests.modeHint_${spec.mode ?? "columns"}`)}</div>
                    </div>
                    {spec.mode === "datasets" ? (
                      <Field label={t("tests.secondDataset")}>
                        {(id) => (
                          <select
                            id={id}
                            className="input"
                            value={spec.dataset_b_id ?? ""}
                            onChange={(e) => update({ dataset_b_id: e.target.value || undefined })}
                          >
                            <option value="">{t("common.choose")}</option>
                            {snap.datasets
                              .filter((d) => d.id !== spec.dataset_id)
                              .map((d) => (
                                <option key={d.id} value={d.id}>
                                  {d.name}
                                </option>
                              ))}
                          </select>
                        )}
                      </Field>
                    ) : (
                      <Field label={t("tests.secondColumn")}>
                        {(id) => (
                          <select
                            id={id}
                            className="input"
                            value={spec.column_b ?? ""}
                            onChange={(e) => update({ column_b: e.target.value || undefined })}
                            data-testid="test-column-b"
                          >
                            <option value="">{t("common.choose")}</option>
                            {(spec.kind === "mean" ? numericColumns : columns)
                              .filter((c) => c.name !== spec.outcome.column)
                              .map((c) => (
                                <option key={c.name} value={c.name}>
                                  {colText(c.name, ds ?? undefined)}
                                </option>
                              ))}
                          </select>
                        )}
                      </Field>
                    )}
                  </>
                )}

                <div className="row-actions start">
                  <button
                    className="btn primary"
                    onClick={runTest}
                    disabled={!complete || running}
                    data-testid="run-test"
                  >
                    {running ? t("common.computing") : t("tests.run")}
                  </button>
                </div>
              </section>

              {answer && (
                <section className="test-result" data-testid="test-result">
                  <div className="test-conclusion">
                    {(answer.conclusion[lang] ?? answer.conclusion.fr).map((s, i) => (
                      <p key={i}>{s}</p>
                    ))}
                  </div>

                  {answer.result.groups && answer.result.groups.length > 0 && (
                    <div className="table-wrap">
                      <table className="table compact">
                        <thead>
                          <tr>
                            <th>{spec.group ? colText(spec.group, ds ?? undefined) : ""}</th>
                            <th className="num">{t("analysis.colValue")}</th>
                            <th className="num">{t("analysis.colCI")}</th>
                            <th className="num">{t("analysis.colN")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {answer.result.groups.map((g) => (
                            <tr key={g.group}>
                              <td>{spec.group ? valText(spec.group, g.group, ds ?? undefined) : g.group}</td>
                              <td className="num strong">{valueFmt(g.estimate)}</td>
                              <td className="num">
                                {t("analysis.ciRange", { low: valueFmt(g.ci_low), high: valueFmt(g.ci_high) })}
                              </td>
                              <td className="num">{number(g.n, 0)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <dl className="facts">
                    <div>
                      <dt>{t("analysis.test")}</dt>
                      <dd>{t(`stests.${answer.result.test_key}`)}</dd>
                    </div>
                    <div>
                      <dt>{t("tests.pvalue")}</dt>
                      <dd>{answer.result.p_value === null ? t("common.none") : pFmt(answer.result.p_value)}</dd>
                    </div>
                    <div>
                      <dt>{t("tests.statistic")}</dt>
                      <dd>
                        {answer.result.statistic === null
                          ? t("common.none")
                          : `${number(answer.result.statistic, 2)}${
                              answer.result.df !== null
                                ? t("tests.df", {
                                    df: [answer.result.df, answer.result.df2]
                                      .filter((x): x is number => typeof x === "number")
                                      .map((x) => number(x, Number.isInteger(x) ? 0 : 1))
                                      .join(" ; "),
                                  })
                                : ""
                            }`}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("tests.observations")}</dt>
                      <dd>{number(answer.result.n, 0)}</dd>
                    </div>
                  </dl>
                  <p className="muted small">
                    {answer.result.design ? t("tests.withDesign") : t("tests.withoutDesign")}
                  </p>

                  <div className="row-actions start">
                    <Field label={t("tests.title")}>
                      {(id) => (
                        <input
                          id={id}
                          className="input"
                          value={spec.title}
                          placeholder={autoTitle({ ...spec, title: "" })}
                          onChange={(e) => {
                            setSpec({ ...spec, title: e.target.value });
                            setSaved(false);
                          }}
                        />
                      )}
                    </Field>
                    <button className="btn" onClick={saveTest} data-testid="save-test">
                      <Icon name="doc" /> {spec.id ? t("tests.update") : t("tests.save")}
                    </button>
                    <button className="btn" onClick={() => setShowScript(!showScript)}>
                      {showScript ? t("demo.hideScript") : t("demo.showScript")}
                    </button>
                  </div>
                  {saved && <Notice kind="ok">{t("tests.savedNotice")}</Notice>}
                  {showScript && <pre className="code-block">{answer.result.script}</pre>}
                </section>
              )}
            </>
          )}
        </div>
      </div>

      {deleting && (
        <Confirm
          text={t("tests.deleteConfirm", { name: autoTitle(deleting) })}
          confirmLabel={t("common.delete")}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            await run("test.delete", { id: deleting.id });
            if (spec?.id === deleting.id) setSpec(null);
            setDeleting(null);
          }}
        />
      )}
    </div>
  );
}
