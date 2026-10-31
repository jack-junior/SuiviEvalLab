// Data: import Excel, Kobo or CSV files, survey design, cleaning journal, preview.

import { useEffect, useMemo, useState } from "react";
import { call, Dataset, Design, Inspection, Picked, pick, Round, Rule, RuleKind } from "../api";
import { useI18n } from "../i18n";
import { pickLabel, useLabels } from "../labels";
import { useProject } from "../state";
import { Confirm, Empty, Field, Icon, IconButton, Notice, Panel } from "../ui";

const ROUNDS: Round[] = ["baseline", "midline", "endline", "monitoring"];

export function Data() {
  const { t, number } = useI18n();
  const { snap, error, focus, go } = useProject();
  const [importing, setImporting] = useState(false);
  if (!snap) return null;
  const current = snap.datasets.find((d) => d.id === focus) ?? null;

  if (current) return <DatasetDetail ds={current} onBack={() => go("data")} />;

  return (
    <div className="inner wide">
      <div className="page-head">
        <div>
          <h1>{t("nav.data")}</h1>
          <p className="lead">{t("data.lead")}</p>
        </div>
        {snap.datasets.length > 0 && (
          <button className="btn primary" onClick={() => setImporting(true)} data-testid="import-data">
            {t("data.import")}
          </button>
        )}
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {snap.datasets.length === 0 ? (
        <Empty
          icon="table"
          title={t("data.emptyTitle")}
          text={t("data.emptyText")}
          action={
            <button className="btn primary" onClick={() => setImporting(true)} data-testid="import-data">
              {t("data.import")}
            </button>
          }
        />
      ) : (
        <div className="cards">
          {snap.datasets.map((d) => (
            <button key={d.id} className="card" onClick={() => go("data", d.id)} data-testid="dataset-card">
              <span className="card-kicker">{t(`rounds.${d.round}`)}</span>
              <span className="card-title">{d.name}</span>
              <span className="card-meta">
                {t("data.rowsAfter", { rows: number(d.rows, 0), clean: number(d.clean_rows, 0) })}
              </span>
              <span className="card-meta">
                {t("data.columnsAndRules", { columns: number(d.columns.length, 0), rules: number(d.rules.length, 0) })}
              </span>
              <span className="card-meta">{designText(d.design, t)}</span>
            </button>
          ))}
        </div>
      )}
      {importing && <ImportPanel onClose={() => setImporting(false)} />}
    </div>
  );
}

function designText(d: Design, t: (k: string, v?: Record<string, string | number>) => string) {
  const parts = [];
  if (d.weights) parts.push(t("data.designWeights", { col: d.weights }));
  if (d.strata.length) parts.push(t("data.designStrata", { col: d.strata.join(" × ") }));
  if (d.cluster) parts.push(t("data.designCluster", { col: d.cluster }));
  return parts.length ? parts.join(", ") : t("data.designNone");
}

function ImportPanel({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const { run, describe, go, snap } = useProject();
  const [file, setFile] = useState<Picked | null>(null);
  const [info, setInfo] = useState<Inspection | null>(null);
  const [name, setName] = useState("");
  const [round, setRound] = useState<Round>(snap?.datasets.length ? "endline" : "baseline");
  const [design, setDesign] = useState<Design>({ weights: null, strata: [], cluster: null });
  const [idCol, setIdCol] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [useForm, setUseForm] = useState(true);

  const inspect = async (f: Picked, sheet?: string) => {
    setLoading(true);
    setErr(null);
    try {
      const res = await call<Inspection>("dataset.inspect", { file_token: f.token, sheet });
      setInfo(res);
      setDesign(res.design);
      setIdCol(res.id_column);
      if (!name) setName(f.name.replace(/\.[^.]+$/, ""));
    } catch (e) {
      setErr(describe(e));
    } finally {
      setLoading(false);
    }
  };

  const choose = async () => {
    const f = await pick("data-open");
    if (!f) return;
    setFile(f);
    setInfo(null);
    await inspect(f);
  };

  const doImport = async () => {
    if (!file || !info) return;
    setLoading(true);
    const res = await run<{ created: string }>(
      "dataset.import",
      {
        file_token: file.token,
        sheet: info.sheet,
        name: name.trim() || info.file_name,
        round,
        design,
        id_column: idCol,
        form: useForm && info.form ? info.form : null,
      },
      "import",
    );
    setLoading(false);
    if (res) {
      onClose();
      go("data", res.created);
    }
  };

  const cols = info?.columns ?? [];
  return (
    <Panel
      title={t("data.importTitle")}
      onClose={onClose}
      testId="import-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={doImport} disabled={!info || loading} data-testid="import-confirm">
            {loading && info ? t("data.importing") : t("data.importAction")}
          </button>
        </>
      }
    >
      <div className="file-pick">
        <button className="btn" onClick={choose} disabled={loading} data-testid="choose-file">
          <Icon name="file" /> {file ? t("data.otherFile") : t("data.chooseFile")}
        </button>
        <span className="muted small">{file ? file.name : t("data.fileTypes")}</span>
      </div>
      {err && <Notice kind="error">{err}</Notice>}
      {loading && !info && <p className="muted">{t("data.reading")}</p>}
      {info && (
        <>
          {info.sheets.length > 1 && (
            <Field label={t("data.sheet")} hint={t("data.sheetHint")}>
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={info.sheet}
                  onChange={(e) => file && inspect(file, e.target.value)}
                >
                  {info.sheets.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              )}
            </Field>
          )}
          <p className="muted small">{t("data.columnsFound", { n: cols.length })}</p>
          <div className="sample-wrap">
            <table className="table compact">
              <thead>
                <tr>
                  {cols.slice(0, 12).map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {info.sample.slice(0, 5).map((r, i) => (
                  <tr key={i}>
                    {r.slice(0, 12).map((v, j) => (
                      <td key={j}>{v ?? ""}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Field label={t("data.name")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="dataset-name"
              />
            )}
          </Field>
          <div className="field">
            <span className="label">{t("data.round")}</span>
            <div className="chips">
              {ROUNDS.map((r) => (
                <button
                  key={r}
                  className="chip"
                  aria-pressed={round === r}
                  onClick={() => setRound(r)}
                  data-testid={`round-${r}`}
                >
                  {t(`rounds.${r}`)}
                </button>
              ))}
            </div>
          </div>
          {info.form && (
            <label className="check form-check">
              <input
                type="checkbox"
                checked={useForm}
                onChange={(e) => setUseForm(e.target.checked)}
                data-testid="use-form"
              />
              <span className="check-text">
                {t("data.useForm", { survey: info.form.survey, choices: info.form.choices ?? "" })}
              </span>
            </label>
          )}
          <DesignFields columns={cols} design={design} onChange={setDesign} idCol={idCol} onIdCol={setIdCol} />
        </>
      )}
    </Panel>
  );
}

function DesignFields({
  columns,
  design,
  onChange,
  idCol,
  onIdCol,
}: {
  columns: string[];
  design: Design;
  onChange: (d: Design) => void;
  idCol: string | null;
  onIdCol: (c: string | null) => void;
}) {
  const { t } = useI18n();
  const select = (value: string | null, set: (v: string | null) => void, testId?: string) => (id: string) => (
    <select
      id={id}
      className="input"
      value={value ?? ""}
      onChange={(e) => set(e.target.value || null)}
      data-testid={testId}
    >
      <option value="">{t("data.noneColumn")}</option>
      {columns.map((c) => (
        <option key={c}>{c}</option>
      ))}
    </select>
  );
  return (
    <>
      <h3 className="panel-section">{t("data.designTitle")}</h3>
      <p className="muted small">{t("data.designHelp")}</p>
      <Field label={t("data.weights")}>
        {select(design.weights, (v) => onChange({ ...design, weights: v }), "design-weights")}
      </Field>
      <div className="field">
        <span className="label">{t("data.strata")}</span>
        <div className="chips">
          {design.strata.map((s) => (
            <button
              key={s}
              className="chip"
              aria-pressed="true"
              onClick={() => onChange({ ...design, strata: design.strata.filter((x) => x !== s) })}
              title={t("common.remove")}
            >
              {s} ×
            </button>
          ))}
          <select
            className="input inline"
            value=""
            onChange={(e) => e.target.value && onChange({ ...design, strata: [...design.strata, e.target.value] })}
            aria-label={t("data.addStratum")}
          >
            <option value="">{t("data.addStratum")}</option>
            {columns
              .filter((c) => !design.strata.includes(c))
              .map((c) => (
                <option key={c}>{c}</option>
              ))}
          </select>
        </div>
        <div className="field-hint">{t("data.strataHint")}</div>
      </div>
      <Field label={t("data.cluster")} hint={t("data.clusterHint")}>
        {select(design.cluster, (v) => onChange({ ...design, cluster: v }))}
      </Field>
      <Field label={t("data.idColumn")} hint={t("data.idHint")}>
        {select(idCol, onIdCol)}
      </Field>
    </>
  );
}

// ----- one dataset ------------------------------------------------------------------

type Tab = "cleaning" | "preview" | "columns";

function DatasetDetail({ ds, onBack }: { ds: Dataset; onBack: () => void }) {
  const { t, number } = useI18n();
  const { run, error } = useProject();
  const [tab, setTab] = useState<Tab>("cleaning");
  const [settings, setSettings] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exported, setExported] = useState<string | null>(null);

  const attachForm = async () => {
    const f = await pick("data-open");
    if (!f) return;
    const r = await run<{ matched_columns: number }>("dataset.attach_form", { id: ds.id, file_token: f.token });
    if (r) setExported(t("data.formAttached", { n: number(r.matched_columns, 0), name: f.name }));
  };

  const exportCsv = async () => {
    const f = await pick("csv-save", `${ds.name}.csv`);
    if (!f) return;
    const r = await run<{ rows: number }>("dataset.export", { id: ds.id, file_token: f.token });
    if (r) setExported(t("data.exported", { name: f.name, rows: number(r.rows, 0) }));
  };

  return (
    <div className="inner wide">
      <div>
        <button className="link back" onClick={onBack} data-testid="data-back">
          {t("data.back")}
        </button>
        <div className="page-head">
          <div>
            <span className="card-kicker">{t(`rounds.${ds.round}`)}</span>
            <h1>{ds.name}</h1>
            <p className="lead small-lead">
              {t("data.detailLine", {
                file: ds.source_name,
                rows: number(ds.rows, 0),
                clean: number(ds.clean_rows, 0),
                columns: number(ds.columns.length, 0),
              })}
            </p>
            <p className="muted small">{designText(ds.design, t)}</p>
            <p className="muted small">
              {ds.form_source
                ? t("data.labelsFrom", { file: ds.form_source.file })
                : Object.keys(ds.labels?.columns ?? {}).length > 0
                  ? t("data.labelsTyped")
                  : t("data.noLabels")}{" "}
              <button className="link" onClick={attachForm} data-testid="attach-form">
                {t("data.attachForm")}
              </button>
            </p>
          </div>
          <div className="row-actions">
            <button className="btn" onClick={() => setSettings(true)}>
              {t("data.settings")}
            </button>
            <button className="btn" onClick={exportCsv}>
              <Icon name="download" /> {t("data.export")}
            </button>
            <IconButton icon="trash" label={t("common.delete")} onClick={() => setDeleting(true)} />
          </div>
        </div>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {exported && <Notice kind="ok">{exported}</Notice>}

      <div className="tabs" role="tablist">
        {(["cleaning", "preview", "columns"] as Tab[]).map((k) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            className="tab"
            onClick={() => setTab(k)}
            data-testid={`tab-${k}`}
          >
            {t(`data.tab_${k}`)}
            {k === "cleaning" && ds.rules.length > 0 && <span className="tab-count">{ds.rules.length}</span>}
          </button>
        ))}
      </div>
      {tab === "cleaning" && <Journal ds={ds} />}
      {tab === "preview" && <Preview ds={ds} />}
      {tab === "columns" && <Columns ds={ds} />}

      {settings && <SettingsPanel ds={ds} onClose={() => setSettings(false)} />}
      {deleting && (
        <Confirm
          text={t("data.deleteConfirm", { name: ds.name })}
          confirmLabel={t("common.delete")}
          onCancel={() => setDeleting(false)}
          onConfirm={async () => {
            await run("dataset.delete", { id: ds.id });
            setDeleting(false);
            onBack();
          }}
        />
      )}
    </div>
  );
}

function SettingsPanel({ ds, onClose }: { ds: Dataset; onClose: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [name, setName] = useState(ds.name);
  const [round, setRound] = useState<Round>(ds.round);
  const [design, setDesign] = useState<Design>(ds.design);
  const [idCol, setIdCol] = useState<string | null>(ds.id_column);
  const save = async () => {
    if (await run("dataset.update", { id: ds.id, name, round, design, id_column: idCol })) onClose();
  };
  return (
    <Panel
      title={t("data.settings")}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save}>
            {t("common.save")}
          </button>
        </>
      }
    >
      <Field label={t("data.name")}>
        {(id) => <input id={id} className="input" value={name} onChange={(e) => setName(e.target.value)} />}
      </Field>
      <div className="field">
        <span className="label">{t("data.round")}</span>
        <div className="chips">
          {ROUNDS.map((r) => (
            <button key={r} className="chip" aria-pressed={round === r} onClick={() => setRound(r)}>
              {t(`rounds.${r}`)}
            </button>
          ))}
        </div>
      </div>
      <DesignFields
        columns={ds.columns.map((c) => c.name)}
        design={design}
        onChange={setDesign}
        idCol={idCol}
        onIdCol={setIdCol}
      />
    </Panel>
  );
}

export function useRuleText() {
  const { t, number } = useI18n();
  return (r: Rule) => {
    const q = (v: string | null | undefined) =>
      v === null || v === undefined ? t("cleaning.missing") : t("cleaning.quote", { v });
    switch (r.kind) {
      case "duplicates":
        return t("cleaning.text_duplicates", { columns: (r.columns ?? []).join(", ") });
      case "recode":
        return t("cleaning.text_recode", {
          column: r.column ?? "",
          from: (r.from ?? []).map(q).join(", "),
          to: q(r.to ?? null),
        });
      case "range":
        return t("cleaning.text_range", {
          column: r.column ?? "",
          min: r.min === null || r.min === undefined ? "−∞" : number(r.min, 2),
          max: r.max === null || r.max === undefined ? "+∞" : number(r.max, 2),
        });
      case "exclude":
        return t("cleaning.text_exclude", { column: r.column ?? "", values: (r.values ?? []).map(q).join(", ") });
    }
  };
}

function Journal({ ds }: { ds: Dataset }) {
  const { t, tn, number } = useI18n();
  const { run } = useProject();
  const [adding, setAdding] = useState(false);
  const text = useRuleText();
  const effect = (r: Rule) => {
    if (!r.enabled) return t("cleaning.disabled");
    const e = r.effect;
    if (!e) return "";
    const parts = [];
    if (e.rows_removed) parts.push(tn("cleaning.rowsRemoved", e.rows_removed));
    if (e.cells_changed) parts.push(tn("cleaning.cellsChanged", e.cells_changed));
    return parts.join(", ") || t("cleaning.noChange");
  };
  return (
    <section className="stack">
      <div className="section-head">
        <p className="muted" style={{ margin: 0 }}>
          {t("cleaning.lead")}
        </p>
        <button className="btn primary" onClick={() => setAdding(true)} data-testid="add-rule">
          {t("cleaning.add")}
        </button>
      </div>
      {ds.rules.length === 0 ? (
        <Empty icon="check" title={t("cleaning.emptyTitle")} text={t("cleaning.emptyText")} />
      ) : (
        <ol className="journal" data-testid="journal">
          {ds.rules.map((r, i) => (
            <li key={r.id} className={`journal-row${r.enabled ? "" : " off"}`}>
              <span className="journal-n">{i + 1}</span>
              <div className="journal-main">
                <div className="journal-text">{text(r)}</div>
                {r.note && <div className="journal-note">{r.note}</div>}
              </div>
              <span className="journal-effect">{effect(r)}</span>
              <div className="row-tools">
                <label className="switch" title={r.enabled ? t("cleaning.turnOff") : t("cleaning.turnOn")}>
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={(e) => run("cleaning.update", { id: r.id, rule: { enabled: e.target.checked } })}
                    aria-label={r.enabled ? t("cleaning.turnOff") : t("cleaning.turnOn")}
                  />
                  <span aria-hidden="true" />
                </label>
                <IconButton
                  icon="up"
                  label={t("common.moveUp")}
                  onClick={() => run("cleaning.move", { id: r.id, direction: -1 })}
                />
                <IconButton
                  icon="down"
                  label={t("common.moveDown")}
                  onClick={() => run("cleaning.move", { id: r.id, direction: 1 })}
                />
                <IconButton
                  icon="trash"
                  label={t("common.delete")}
                  onClick={() => run("cleaning.delete", { id: r.id })}
                />
              </div>
            </li>
          ))}
        </ol>
      )}
      <p className="muted small">
        {t("cleaning.summary", { rows: number(ds.rows, 0), clean: number(ds.clean_rows, 0) })}
      </p>
      {adding && <RulePanel ds={ds} onClose={() => setAdding(false)} />}
    </section>
  );
}

function RulePanel({ ds, onClose }: { ds: Dataset; onClose: () => void }) {
  const { t, number } = useI18n();
  const { run } = useProject();
  const { valText, val } = useLabels();
  const [kind, setKind] = useState<RuleKind>("recode");
  const [column, setColumn] = useState<string>("");
  const [selected, setSelected] = useState<(string | null)[]>([]);
  const [to, setTo] = useState("");
  const [toMissing, setToMissing] = useState(true);
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [dupCols, setDupCols] = useState<string[]>(ds.id_column ? [ds.id_column] : []);
  const [note, setNote] = useState("");
  const [values, setValues] = useState<{ value: string | null; n: number }[]>([]);
  const [stats, setStats] = useState<{ min: number; max: number } | null>(null);

  useEffect(() => {
    if (!column) return;
    call<{ values: { value: string | null; n: number }[]; stats: { min: number; max: number } | null }>(
      "dataset.column_values",
      { id: ds.id, column },
    )
      .then((r) => {
        setValues(r.values);
        setStats(r.stats);
      })
      .catch(() => setValues([]));
  }, [column, ds.id]);

  const num = (s: string) => (s.trim() === "" ? null : Number(s.replace(",", ".")));
  const rule = useMemo(() => {
    if (kind === "duplicates") return { kind, columns: dupCols, note };
    if (kind === "recode")
      return { kind, column, from: selected.filter((v) => v !== null), to: toMissing ? null : to, note };
    if (kind === "range") return { kind, column, min: num(min), max: num(max), note };
    return { kind, column, values: selected, note };
  }, [kind, dupCols, column, selected, to, toMissing, min, max, note]);

  const valid =
    kind === "duplicates"
      ? dupCols.length > 0
      : !!column && (kind === "range" ? min.trim() !== "" || max.trim() !== "" : selected.length > 0);

  const save = async () => {
    if (await run("cleaning.add", { dataset_id: ds.id, rule })) onClose();
  };

  return (
    <Panel
      title={t("cleaning.add")}
      onClose={onClose}
      testId="rule-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} disabled={!valid} data-testid="rule-save">
            {t("cleaning.addAction")}
          </button>
        </>
      }
    >
      <div className="kind-grid">
        {(["recode", "exclude", "range", "duplicates"] as RuleKind[]).map((k) => (
          <button
            key={k}
            className="kind"
            aria-pressed={kind === k}
            onClick={() => setKind(k)}
            data-testid={`kind-${k}`}
          >
            <span className="kind-title">{t(`cleaning.kind_${k}`)}</span>
            <span className="kind-text">{t(`cleaning.kindText_${k}`)}</span>
          </button>
        ))}
      </div>

      {kind === "duplicates" ? (
        <div className="field">
          <span className="label">{t("cleaning.dupColumns")}</span>
          <div className="chips">
            {dupCols.map((c) => (
              <button
                key={c}
                className="chip"
                aria-pressed="true"
                onClick={() => setDupCols(dupCols.filter((x) => x !== c))}
              >
                {c} ×
              </button>
            ))}
            <select
              className="input inline"
              value=""
              onChange={(e) => e.target.value && setDupCols([...dupCols, e.target.value])}
              aria-label={t("cleaning.addColumn")}
            >
              <option value="">{t("cleaning.addColumn")}</option>
              {ds.columns
                .filter((c) => !dupCols.includes(c.name))
                .map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
            </select>
          </div>
        </div>
      ) : (
        <Field label={t("cleaning.column")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={column}
              onChange={(e) => {
                setColumn(e.target.value);
                setSelected([]);
                setValues([]);
              }}
              data-testid="rule-column"
            >
              <option value="">{t("common.choose")}</option>
              {ds.columns
                .filter((c) => kind !== "range" || c.type === "number")
                .map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
            </select>
          )}
        </Field>
      )}

      {(kind === "recode" || kind === "exclude") && column && (
        <div className="field">
          <span className="label">
            {kind === "recode" ? t("cleaning.valuesToReplace") : t("cleaning.valuesToExclude")}
          </span>
          <div className="value-list" data-testid="rule-values">
            {values
              .filter((v) => kind === "exclude" || v.value !== null)
              .map((v) => (
                <label key={String(v.value)} className="check">
                  <input
                    type="checkbox"
                    data-testid={`rvalue-${v.value ?? "NA"}`}
                    checked={selected.includes(v.value)}
                    onChange={(e) =>
                      setSelected(e.target.checked ? [...selected, v.value] : selected.filter((x) => x !== v.value))
                    }
                  />
                  <span className="check-text">
                    {v.value === null ? t("cleaning.missing") : valText(column, v.value, ds)}
                    {v.value !== null && val(column, v.value, ds) && <span className="code"> {v.value}</span>}
                  </span>
                  <span className="muted small">{number(v.n, 0)}</span>
                </label>
              ))}
          </div>
        </div>
      )}

      {kind === "recode" && column && (
        <div className="field">
          <span className="label">{t("cleaning.replaceBy")}</span>
          <label className="check">
            <input type="checkbox" checked={toMissing} onChange={(e) => setToMissing(e.target.checked)} />
            <span className="check-text">{t("cleaning.missing")}</span>
          </label>
          {!toMissing && (
            <input
              className="input"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              aria-label={t("cleaning.newValue")}
              placeholder={t("cleaning.newValue")}
            />
          )}
        </div>
      )}

      {kind === "range" && column && (
        <>
          {stats && (
            <p className="muted small">
              {t("cleaning.observed", { min: number(stats.min, 2), max: number(stats.max, 2) })}
            </p>
          )}
          <div className="field-row">
            <Field label={t("cleaning.min")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  inputMode="decimal"
                  value={min}
                  onChange={(e) => setMin(e.target.value)}
                />
              )}
            </Field>
            <Field label={t("cleaning.max")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  inputMode="decimal"
                  value={max}
                  onChange={(e) => setMax(e.target.value)}
                />
              )}
            </Field>
          </div>
        </>
      )}

      <Field label={t("cleaning.note")} hint={t("cleaning.noteHint")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            data-testid="rule-note"
          />
        )}
      </Field>
    </Panel>
  );
}

function Preview({ ds }: { ds: Dataset }) {
  const { t, number } = useI18n();
  const { describe } = useProject();
  const [cleaned, setCleaned] = useState(true);
  const [showLabels, setShowLabels] = useState(false);
  const { col, val } = useLabels();
  const hasLabels = Object.keys(ds.labels?.values ?? {}).length > 0 || Object.keys(ds.labels?.columns ?? {}).length > 0;
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<{ total: number; columns: string[]; rows: (string | null)[][] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const stamp = `${ds.id}-${ds.clean_rows}-${ds.rules.length}`;
  useEffect(() => {
    call<{ total: number; columns: string[]; rows: (string | null)[][] }>("dataset.preview", {
      id: ds.id,
      cleaned,
      offset,
      limit: 50,
    })
      .then(setPage)
      .catch((e) => setErr(describe(e)));
  }, [ds.id, cleaned, offset, stamp, describe]);
  return (
    <section className="stack">
      <div className="section-head">
        <div className="chips">
          <button className="chip" aria-pressed={cleaned} onClick={() => (setCleaned(true), setOffset(0))}>
            {t("data.cleaned")}
          </button>
          <button className="chip" aria-pressed={!cleaned} onClick={() => (setCleaned(false), setOffset(0))}>
            {t("data.raw")}
          </button>
          {hasLabels && (
            <label className="check inline-check">
              <input
                type="checkbox"
                checked={showLabels}
                onChange={(e) => setShowLabels(e.target.checked)}
                data-testid="show-labels"
              />
              <span className="check-text">{t("data.showLabels")}</span>
            </label>
          )}
        </div>
        {page && (
          <div className="pager">
            <span className="muted small">
              {t("data.pageInfo", {
                from: number(offset + 1, 0),
                to: number(Math.min(offset + 50, page.total), 0),
                total: number(page.total, 0),
              })}
            </span>
            <IconButton
              icon="up"
              label={t("data.previous")}
              onClick={() => setOffset(Math.max(0, offset - 50))}
              disabled={offset === 0}
            />
            <IconButton
              icon="down"
              label={t("data.next")}
              onClick={() => setOffset(offset + 50)}
              disabled={offset + 50 >= page.total}
            />
          </div>
        )}
      </div>
      {err && <Notice kind="error">{err}</Notice>}
      {page && (
        <div className="grid-wrap" data-testid="preview-grid">
          <table className="table compact grid">
            <thead>
              <tr>
                <th className="rownum">#</th>
                {page.columns.map((c) => (
                  <th key={c} title={col(c, ds) ? `${col(c, ds)} (${c})` : c}>
                    {showLabels ? (col(c, ds) ?? c) : c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.rows.map((r, i) => (
                <tr key={i}>
                  <td className="rownum">{offset + i + 1}</td>
                  {r.map((v, j) => (
                    <td key={j} className={v === null ? "na" : undefined}>
                      {v === null ? t("data.na") : showLabels ? (val(page.columns[j], v, ds) ?? v) : v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Columns({ ds }: { ds: Dataset }) {
  const { t, number, percent } = useI18n();
  const { col } = useLabels();
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const list = ds.columns.filter((c) => {
    const needle = q.toLowerCase();
    return c.name.toLowerCase().includes(needle) || (col(c.name, ds) ?? "").toLowerCase().includes(needle);
  });
  return (
    <section className="stack">
      <input
        className="input"
        placeholder={t("data.searchColumns")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label={t("data.searchColumns")}
      />
      <div className="table-wrap">
        <table className="table compact">
          <thead>
            <tr>
              <th>{t("data.colName")}</th>
              <th>{t("data.colLabel")}</th>
              <th>{t("data.colType")}</th>
              <th className="num">{t("data.colMissing")}</th>
              <th className="num">{t("data.colDistinct")}</th>
              <th className="num">{t("data.colRange")}</th>
            </tr>
          </thead>
          <tbody>
            {list.slice(0, 500).map((c) => (
              <tr key={c.name}>
                <td className="mono">{c.name}</td>
                <td>
                  <button
                    className="link label-edit"
                    onClick={() => setEditing(c.name)}
                    data-testid={`label-${c.name}`}
                  >
                    {col(c.name, ds) ?? <span className="muted">{t("data.addLabel")}</span>}
                  </button>
                </td>
                <td>{t(`data.type_${c.type}`)}</td>
                <td className="num">{percent(c.rows ? c.missing / c.rows : 0, 0)}</td>
                <td className="num">{number(c.distinct, 0)}</td>
                <td className="num">
                  {c.type === "number" ? `${number(c.min ?? 0, 2)} ; ${number(c.max ?? 0, 2)}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">{t("data.columnsNote")}</p>
      {editing && <LabelPanel ds={ds} column={editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

/** Labels of one column and of its most frequent codes, in the interface language. */
function LabelPanel({ ds, column, onClose }: { ds: Dataset; column: string; onClose: () => void }) {
  const { t, lang, number } = useI18n();
  const { run } = useProject();
  const current = ds.labels?.columns?.[column];
  const [label, setLabel] = useState(current?.[lang] ?? pickLabel(current, lang) ?? "");
  const [codes, setCodes] = useState<{ value: string | null; n: number }[] | null>(null);
  const [texts, setTexts] = useState<Record<string, string>>({});
  useEffect(() => {
    call<{ values: { value: string | null; n: number }[] }>("dataset.column_values", {
      id: ds.id,
      column,
      cleaned: false,
    })
      .then((r) => {
        setCodes(r.values);
        const init: Record<string, string> = {};
        for (const v of r.values)
          if (v.value !== null) init[v.value] = pickLabel(ds.labels?.values?.[column]?.[v.value], lang) ?? "";
        setTexts(init);
      })
      .catch(() => setCodes([]));
  }, [ds.id, column, ds.labels, lang]);
  const save = async () => {
    if (await run("dataset.set_labels", { id: ds.id, column, lang, label, values: texts })) onClose();
  };
  const fewValues = (codes?.length ?? 0) <= 40;
  return (
    <Panel
      title={t("data.labelsTitle", { column })}
      onClose={onClose}
      testId="label-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} data-testid="label-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <p className="muted small">{t("data.labelsHelp")}</p>
      <Field label={t("data.columnLabel")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            data-testid="column-label"
          />
        )}
      </Field>
      {codes && fewValues && codes.some((c) => c.value !== null) && (
        <div className="field">
          <span className="label">{t("data.valueLabels")}</span>
          <div className="value-labels">
            {codes
              .filter((c) => c.value !== null)
              .map((c) => (
                <div key={c.value} className="value-label-row">
                  <span className="mono">{c.value}</span>
                  <span className="muted small">{number(c.n, 0)}</span>
                  <input
                    className="input"
                    value={texts[c.value!] ?? ""}
                    onChange={(e) => setTexts({ ...texts, [c.value!]: e.target.value })}
                    aria-label={t("data.valueLabelFor", { code: c.value! })}
                    data-testid={`value-label-${c.value}`}
                  />
                </div>
              ))}
          </div>
        </div>
      )}
      {codes && !fewValues && <p className="muted small">{t("data.tooManyValues")}</p>}
    </Panel>
  );
}
