// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Periodic reports (module M12): a donor's format, the periods covered, the text
// written by the user section by section, then the Word file. Also the exports
// of the monitoring data.

import { useEffect, useMemo, useState } from "react";
import { call, openFile, pick, ReportFormat, FormatSection, SECTION_KINDS, SectionKind } from "../api";
import { Lang, useI18n } from "../i18n";
import { periodLabel } from "../monitoring";
import { useProject } from "../state";
import { Confirm, Field, Icon, IconButton, Notice, Panel } from "../ui";

export function formatName(f: ReportFormat, lang: Lang) {
  return f.builtin ? ((lang === "en" ? f.en : f.fr) ?? f.id) : (f.name ?? f.id);
}

export function PeriodicReports() {
  const { t, lang } = useI18n();
  const { snap, run, busy, describe } = useProject();
  const [formats, setFormats] = useState<ReportFormat[] | null>(null);
  const [fid, setFid] = useState("generic");
  const periods = useMemo(() => snap?.periods ?? [], [snap]);
  const today = new Date().toISOString().slice(0, 10);
  const lastEnded = [...periods].reverse().find((p) => p.end < today) ?? periods[0];
  const [from, setFrom] = useState(lastEnded?.code ?? "");
  const [to, setTo] = useState(lastEnded?.code ?? "");
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [loadedFor, setLoadedFor] = useState("");
  const [reportLang, setReportLang] = useState<Lang>(lang);
  const [done, setDone] = useState<{ token: string; name: string } | null>(null);
  const [editing, setEditing] = useState<ReportFormat | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const formatsStamp = snap?.project.updated_at;

  useEffect(() => {
    call<{ formats: ReportFormat[] }>("reports.formats")
      .then((r) => setFormats(r.formats))
      .catch((e) => setError(describe(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formatsStamp]);

  const key = `${fid}|${from}|${to}`;
  useEffect(() => {
    if (!periods.length || !from || !to) return;
    let live = true;
    call<{ texts: Record<string, string> }>("report_doc.get", { format: fid, from, to })
      .then((r) => {
        if (!live) return;
        setTexts(r.texts);
        setLoadedFor(key);
      })
      .catch((e) => live && setError(describe(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!snap) return null;
  if (!periods.length) return <Notice>{t("rep.needCalendar")}</Notice>;
  const fmt = formats?.find((f) => f.id === fid);
  const saveTexts = (next: Record<string, string>) => {
    setTexts(next);
    void call("report_doc.save", { format: fid, from, to, texts: next }).catch((e) => setError(describe(e)));
  };
  const codes = periods.map((p) => p.code);
  const setScope = (a: string, b: string) => {
    setFrom(a);
    setTo(b);
    setDone(null);
  };
  const year = (() => {
    const end = periods.find((p) => p.code === to);
    if (!end) return [to, to];
    const fy = periods.filter(
      (p) => p.end <= end.end && p.start > `${Number(end.end.slice(0, 4)) - 1}${end.end.slice(4)}`,
    );
    return [fy[0]?.code ?? to, to];
  })();
  const generate = async () => {
    setDone(null);
    const name = `${snap.project.name.slice(0, 40)} ${to}.docx`;
    const file = await pick("report-save", name);
    if (!file) return;
    const r = await run(
      "reports.generate",
      { file_token: file.token, lang: reportLang, format: fid, from, to },
      "periodic",
    );
    if (r) setDone(file);
  };
  const groups: { label: string; items: ReportFormat[] }[] = formats
    ? [
        { label: t("rep.groupGeneral"), items: formats.filter((f) => f.builtin && !f.donor) },
        { label: t("rep.groupDonors"), items: formats.filter((f) => f.builtin && f.donor) },
        { label: t("rep.groupMine"), items: formats.filter((f) => !f.builtin) },
      ].filter((g) => g.items.length)
    : [];
  const ready = loadedFor === key;
  return (
    <div className="stack-lg" data-testid="periodic">
      {error && <Notice kind="error">{error}</Notice>}
      <section className="stack">
        <h2>{t("rep.format")}</h2>
        <div className="row-actions start wrap">
          <select
            className="input"
            style={{ maxWidth: 460 }}
            value={fid}
            onChange={(e) => {
              setFid(e.target.value);
              setDone(null);
            }}
            data-testid="rep-format"
          >
            {groups.map((g) => (
              <optgroup key={g.label} label={g.label}>
                {g.items.map((f) => (
                  <option key={f.id} value={f.id}>
                    {formatName(f, lang)}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {fmt && !fmt.builtin && (
            <button className="btn" onClick={() => setEditing(fmt)}>
              <Icon name="edit" /> {t("rep.editFormat")}
            </button>
          )}
          <button className="btn" onClick={() => setEditing("new")} data-testid="rep-new-format">
            {t("rep.newFormat")}
          </button>
        </div>
        <p className="muted small">{t("rep.formatHint")}</p>
      </section>

      <section className="stack">
        <h2>{t("rep.scope")}</h2>
        <div className="row-actions start wrap">
          <Field label={t("rep.from")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={from}
                onChange={(e) =>
                  setScope(e.target.value, codes.indexOf(e.target.value) > codes.indexOf(to) ? e.target.value : to)
                }
                data-testid="rep-from"
              >
                {periods.map((p) => (
                  <option key={p.id} value={p.code}>
                    {periodLabel(p, lang)}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t("rep.to")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={to}
                onChange={(e) =>
                  setScope(codes.indexOf(e.target.value) < codes.indexOf(from) ? e.target.value : from, e.target.value)
                }
                data-testid="rep-to"
              >
                {periods.map((p) => (
                  <option key={p.id} value={p.code}>
                    {periodLabel(p, lang)}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
        <div className="chips">
          <button className="chip small" onClick={() => setScope(to, to)}>
            {t("rep.onePeriod")}
          </button>
          <button className="chip small" onClick={() => setScope(year[0], year[1])}>
            {t("rep.year")}
          </button>
          <button className="chip small" onClick={() => setScope(codes[0], codes[codes.length - 1])}>
            {t("rep.whole")}
          </button>
        </div>
      </section>

      {fmt && (
        <section className="stack" data-testid="rep-sections">
          <h2>{t("rep.sections")}</h2>
          <p className="muted small">{t("rep.sectionsHint")}</p>
          <ol className="report-sections">
            {fmt.sections.map((s) => (
              <li key={s.key}>
                <div className="row-between">
                  <strong>{lang === "en" ? s.en : s.fr}</strong>
                  <span className="tag">{t(`rep.kind_${s.kind}`)}</span>
                </div>
                {s.kind === "text" ? (
                  <textarea
                    className="input"
                    rows={4}
                    disabled={!ready}
                    placeholder={(lang === "en" ? s.hint_en : s.hint_fr) || t("rep.writeHere")}
                    value={texts[s.key] ?? ""}
                    onChange={(e) => setTexts({ ...texts, [s.key]: e.target.value })}
                    onBlur={() => saveTexts(texts)}
                    data-testid={`rep-text-${s.key}`}
                  />
                ) : (
                  <p className="muted small">{t(`rep.fills_${s.kind}`)}</p>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="stack">
        <h2>{t("report.language")}</h2>
        <div className="chips">
          {(["fr", "en"] as Lang[]).map((l) => (
            <button key={l} className="chip" aria-pressed={reportLang === l} onClick={() => setReportLang(l)}>
              {t(`report.lang_${l}`)}
            </button>
          ))}
        </div>
        <p className="muted small">
          {snap.project.report_template
            ? t("rep.templateUsed", { name: snap.project.report_template })
            : t("rep.templateNone")}
        </p>
      </section>

      <div className="row-actions start">
        <button
          className="btn primary big"
          onClick={generate}
          disabled={!fmt || busy === "periodic"}
          data-testid="rep-generate"
        >
          <Icon name="doc" /> {busy === "periodic" ? t("report.generating") : t("rep.generate")}
        </button>
      </div>
      {done && (
        <Notice kind="ok">
          <span data-testid="rep-done">{t("report.done", { name: done.name })}</span>{" "}
          <button className="link" onClick={() => openFile(done.token)}>
            {t("report.open")}
          </button>
        </Notice>
      )}
      {editing && (
        <FormatPanel
          base={editing === "new" ? (fmt ?? null) : editing}
          editing={editing !== "new"}
          onClose={() => setEditing(null)}
          onSaved={(id) => {
            setEditing(null);
            if (id) setFid(id);
          }}
        />
      )}
    </div>
  );
}

interface Draft {
  key: string;
  kind: SectionKind;
  label: string;
}

/** A format of one's own, started from the format on screen or from scratch. */
function FormatPanel({
  base,
  editing,
  onClose,
  onSaved,
}: {
  base: ReportFormat | null;
  editing: boolean;
  onClose: () => void;
  onSaved: (id: string | null) => void;
}) {
  const { t, lang } = useI18n();
  const { run } = useProject();
  const [name, setName] = useState(
    editing && base ? formatName(base, lang) : base ? `${formatName(base, lang)} ${t("rep.copySuffix")}` : "",
  );
  const [donor, setDonor] = useState(base?.donor ?? "");
  const [sections, setSections] = useState<Draft[]>(
    (base?.sections ?? []).map((s: FormatSection) => ({
      key: s.key,
      kind: s.kind,
      label: lang === "en" ? s.en : s.fr,
    })),
  );
  const [confirm, setConfirm] = useState(false);
  const move = (i: number, d: number) => {
    const j = i + d;
    if (j < 0 || j >= sections.length) return;
    const next = [...sections];
    [next[i], next[j]] = [next[j], next[i]];
    setSections(next);
  };
  const set = (i: number, patch: Partial<Draft>) =>
    setSections(sections.map((s, k) => (k === i ? { ...s, ...patch } : s)));
  const save = async () => {
    const r = await run<{ created?: string }>("report_format.save", {
      id: editing ? base?.id : undefined,
      format: { name, donor, sections },
    });
    if (r) onSaved(editing ? (base?.id ?? null) : (r.created ?? null));
  };
  return (
    <Panel
      wide
      title={editing ? t("rep.editFormat") : t("rep.newFormat")}
      onClose={onClose}
      testId="format-panel"
      footer={
        <>
          {editing && (
            <button className="btn" onClick={() => setConfirm(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button
            className="btn primary"
            onClick={save}
            disabled={!name.trim() || !sections.length || sections.some((s) => !s.label.trim())}
            data-testid="format-save"
          >
            {t("common.save")}
          </button>
        </>
      }
    >
      <p className="muted small">{t("rep.formatPanelLead")}</p>
      <div className="grid-2">
        <Field label={t("rep.formatName")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              data-testid="format-name"
            />
          )}
        </Field>
        <Field label={t("rep.donor")}>
          {(id) => <input id={id} className="input" value={donor} onChange={(e) => setDonor(e.target.value)} />}
        </Field>
      </div>
      <table className="table compact">
        <thead>
          <tr>
            <th>{t("rep.sectionTitle")}</th>
            <th>{t("rep.sectionKind")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {sections.map((s, i) => (
            <tr key={`${s.key}-${i}`}>
              <td>
                <input className="input" value={s.label} onChange={(e) => set(i, { label: e.target.value })} />
              </td>
              <td>
                <select
                  className="input"
                  value={s.kind}
                  onChange={(e) =>
                    set(i, {
                      kind: e.target.value as SectionKind,
                      key: e.target.value === "text" ? `t_${i}` : e.target.value,
                    })
                  }
                >
                  {SECTION_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {t(`rep.kind_${k}`)}
                    </option>
                  ))}
                </select>
              </td>
              <td className="row-actions">
                <IconButton icon="up" label={t("common.moveUp")} onClick={() => move(i, -1)} />
                <IconButton icon="down" label={t("common.moveDown")} onClick={() => move(i, 1)} />
                <IconButton
                  icon="trash"
                  label={t("common.delete")}
                  onClick={() => setSections(sections.filter((_, k) => k !== i))}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div>
        <button
          className="btn small"
          onClick={() => setSections([...sections, { key: `t_${Date.now().toString(36)}`, kind: "text", label: "" }])}
          data-testid="format-add-section"
        >
          <Icon name="plus" /> {t("rep.addSection")}
        </button>
      </div>
      {confirm && base && (
        <Confirm
          text={t("rep.deleteFormat")}
          confirmLabel={t("common.delete")}
          onConfirm={async () => {
            if (await run("report_format.delete", { id: base.id })) onSaved("generic");
          }}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

// ----- exports ------------------------------------------------------------------------------------

export function Exports() {
  const { t, lang } = useI18n();
  const { snap, run, busy } = useProject();
  const [note, setNote] = useState<{ token: string; name: string; what: string } | null>(null);
  const periods = snap?.periods ?? [];
  const today = new Date().toISOString().slice(0, 10);
  const [period, setPeriod] = useState(([...periods].reverse().find((p) => p.end < today) ?? periods[0])?.code ?? "");
  if (!snap) return null;
  const base = snap.project.name.slice(0, 40);
  const go = async (
    what: string,
    kind: Parameters<typeof pick>[0],
    fileName: string,
    method: string,
    extra: Record<string, unknown> = {},
  ) => {
    setNote(null);
    const file = await pick(kind, fileName);
    if (!file) return;
    const r = await run(method, { file_token: file.token, lang, ...extra }, what);
    if (r) setNote({ ...file, what });
  };
  return (
    <div className="stack-lg" data-testid="exports">
      <section className="box stack-sm">
        <h2>{t("exp.tracking")}</h2>
        <p className="muted small">{t("exp.trackingText")}</p>
        <div className="row-actions start">
          <select
            className="input"
            style={{ maxWidth: 220 }}
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            aria-label={t("rep.to")}
          >
            {periods.map((p) => (
              <option key={p.id} value={p.code}>
                {periodLabel(p, lang)}
              </option>
            ))}
          </select>
          <button
            className="btn"
            disabled={!periods.length || busy === "tracking"}
            onClick={() => go("tracking", "xlsx-save", `${base} suivi ${period}.xlsx`, "export.tracking", { period })}
            data-testid="exp-tracking"
          >
            <Icon name="download" /> {t("exp.excel")}
          </button>
        </div>
      </section>
      <section className="box stack-sm">
        <h2>{t("exp.values")}</h2>
        <p className="muted small">{t("exp.valuesText")}</p>
        <div className="row-actions start">
          <button
            className="btn"
            onClick={() => go("values", "xlsx-save", `${base} valeurs.xlsx`, "export.values", { kind: "xlsx" })}
            data-testid="exp-values"
          >
            <Icon name="download" /> {t("exp.excel")}
          </button>
          <button
            className="btn"
            onClick={() => go("values", "csv-save", `${base} valeurs.csv`, "export.values", { kind: "csv" })}
          >
            <Icon name="download" /> CSV
          </button>
        </div>
      </section>
      <section className="box stack-sm">
        <h2>{t("exp.pack")}</h2>
        <p className="muted small">{t("exp.packText")}</p>
        <div className="row-actions start">
          <button
            className="btn"
            onClick={() => go("pack", "pack-save", `${base}.smepack`, "export.pack")}
            data-testid="exp-pack"
          >
            <Icon name="download" /> {t("exp.packAction")}
          </button>
        </div>
      </section>
      <section className="box stack-sm">
        <h2>{t("exp.plan")}</h2>
        <p className="muted small">{t("exp.planText")}</p>
        <div className="row-actions start">
          <button className="btn" onClick={() => go("plan", "xlsx-save", `${base} plan de suivi.xlsx`, "report.plan")}>
            <Icon name="download" /> {t("exp.excel")}
          </button>
        </div>
      </section>
      {note && (
        <Notice kind="ok">
          <span data-testid="exp-done">{t("exp.done", { name: note.name })}</span>{" "}
          {note.what !== "pack" && (
            <button className="link" onClick={() => openFile(note.token)}>
              {t("report.open")}
            </button>
          )}
        </Notice>
      )}
    </div>
  );
}
