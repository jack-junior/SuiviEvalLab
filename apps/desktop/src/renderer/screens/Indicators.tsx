// Indicators: definition, calculation rule from a data column, baseline and target.

import { useEffect, useMemo, useState } from "react";
import { call, Indicator } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Confirm, Empty, Field, IconButton, Notice, Panel } from "../ui";

type Draft = Omit<Indicator, "id" | "node_id"> & { id?: string; node_id: string };

const blank = (node_id: string): Draft => ({
  node_id,
  name: "",
  definition: "",
  unit: "percent",
  direction: "increase",
  column: null,
  success_values: [],
  disaggregation: null,
  baseline_manual: null,
  target: null,
  unit_label: "",
  source: "",
});

/** Number typed by the user: percentages in %, stored as shares. */
const toInput = (v: number | null, unit: string) =>
  v === null ? "" : String(+(unit === "percent" ? v * 100 : v).toFixed(4));
const fromInput = (s: string, unit: string): number | null => {
  const v = Number(s.replace(",", ".").replace(/\s/g, ""));
  if (s.trim() === "" || Number.isNaN(v)) return null;
  return unit === "percent" ? v / 100 : v;
};

export function Indicators() {
  const { t, percent, number } = useI18n();
  const { snap, run, error, focus } = useProject();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [targetText, setTargetText] = useState("");
  const [baseText, setBaseText] = useState("");
  const [loaded, setLoaded] = useState<{ col: string; values: { value: string | null; n: number }[] } | null>(null);
  const [deleting, setDeleting] = useState<Indicator | null>(null);

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

  // Values of the chosen column, from the first dataset that has it (cleaned data).
  const col = draft?.column ?? null;
  useEffect(() => {
    if (!col || !columns.has(col)) return;
    const dsId = columns.get(col)!.datasets[0];
    call<{ values: { value: string | null; n: number }[] }>("dataset.column_values", { id: dsId, column: col })
      .then((r) => setLoaded({ col, values: r.values }))
      .catch(() => setLoaded({ col, values: [] }));
  }, [col, columns]);
  const values = loaded && loaded.col === col ? loaded.values : [];

  if (!snap) return null;
  const results = snap.framework.filter((n) => n.level !== "activity");

  const edit = (d: Draft) => {
    setDraft(d);
    setTargetText(toInput(d.target, d.unit));
    setBaseText(toInput(d.baseline_manual, d.unit));
  };

  const save = async () => {
    if (!draft) return;
    const indicator = {
      ...draft,
      target: fromInput(targetText, draft.unit),
      baseline_manual: fromInput(baseText, draft.unit),
    };
    const ok = await run("indicator.save", { id: draft.id, node_id: draft.node_id, indicator });
    if (ok) setDraft(null);
  };

  const fmt = (v: number | null, unit: string) =>
    v === null ? t("common.none") : unit === "percent" ? percent(v) : number(v, 2);

  if (results.length === 0)
    return (
      <div className="inner wide">
        <h1>{t("nav.indicators")}</h1>
        <Empty icon="target" title={t("indicators.needFramework")} text={t("indicators.needFrameworkText")} />
      </div>
    );

  const textColumns = [...columns.entries()].filter(([, c]) => c.type === "text" && c.distinct <= 40);

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
                {t(`levels.${node.level}`)} {node.code}
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
                        {ind.column
                          ? ind.unit === "percent"
                            ? t("indicators.rulePercent", { column: ind.column, values: ind.success_values.join(", ") })
                            : t("indicators.ruleMean", { column: ind.column })
                          : t("indicators.noRule")}
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
                    {t("common.labelled", { a: `${t(`levels.${n.level}`)} ${n.code}`.trim(), b: n.title })}
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
            <span className="label">{t("indicators.unit")}</span>
            <div className="chips">
              {(["percent", "mean"] as const).map((u) => (
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
          {columns.size === 0 ? (
            <p className="muted small">{t("indicators.noDataYet")}</p>
          ) : (
            <>
              <Field label={t("indicators.column")} hint={t("indicators.columnHint")}>
                {(id) => (
                  <select
                    id={id}
                    className="input"
                    value={draft.column ?? ""}
                    onChange={(e) => setDraft({ ...draft, column: e.target.value || null, success_values: [] })}
                    data-testid="indicator-column"
                  >
                    <option value="">{t("common.choose")}</option>
                    {[...columns.entries()].map(([name, c]) => (
                      <option key={name} value={name}>
                        {name} {c.datasets.length < (snap.datasets.length || 1) ? t("indicators.notInAll") : ""}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
              {draft.unit === "percent" && draft.column && (
                <div className="field">
                  <span className="label">{t("indicators.success")}</span>
                  <div className="field-hint">{t("indicators.successHint")}</div>
                  <div className="value-list" data-testid="success-values">
                    {values
                      .filter((v) => v.value !== null)
                      .map((v) => (
                        <label key={v.value} className="check">
                          <input
                            type="checkbox"
                            data-testid={`value-${v.value}`}
                            checked={draft.success_values.includes(v.value!)}
                            onChange={(e) =>
                              setDraft({
                                ...draft,
                                success_values: e.target.checked
                                  ? [...draft.success_values, v.value!]
                                  : draft.success_values.filter((x) => x !== v.value),
                              })
                            }
                          />
                          <span className="check-text">{v.value}</span>
                          <span className="muted small">{number(v.n, 0)}</span>
                        </label>
                      ))}
                  </div>
                  <div className="field-hint">{t("indicators.missingExcluded")}</div>
                </div>
              )}
              <Field label={t("indicators.disaggregation")}>
                {(id) => (
                  <select
                    id={id}
                    className="input"
                    value={draft.disaggregation ?? ""}
                    onChange={(e) => setDraft({ ...draft, disaggregation: e.target.value || null })}
                  >
                    <option value="">{t("indicators.noDisaggregation")}</option>
                    {textColumns.map(([name]) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            </>
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
