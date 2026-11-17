// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Reception: who has sent the data of a period, entering or importing them,
// the checks on receipt, and validation up to locking the period.

import { Fragment, useEffect, useMemo, useState } from "react";
import {
  call,
  Cell,
  EngineCallError,
  Indicator,
  isEntry,
  pick,
  ReportingUnit,
  Snapshot,
  Submission,
  SubmissionDetail,
} from "../api";
import { useLevels } from "../frameworks";
import { useI18n } from "../i18n";
import { cellsOf, defaultPeriod, entryKind, periodLabel, toNumber, todayIso, unitKey, unitName } from "../monitoring";
import { useProject } from "../state";
import { Empty, Field, Icon, Notice, Panel } from "../ui";
import { ConnectionsPanel } from "./Connections";
import { Attachments } from "../Attachments";

export function Reception() {
  const { t, lang, day } = useI18n();
  const { snap, setSnap, go, describe, focus } = useProject();
  const [chosen, setPeriod] = useState<string | null>(null);
  const [seenFocus, setSeenFocus] = useState<string | null>(null);
  const [open, setOpen] = useState<{ unit: ReportingUnit; id: string | null } | null>(null);
  const [note, setNote] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [reason, setReason] = useState<"unlock" | null>(null);
  const [revision, setRevision] = useState<{
    changes: { indicator_id: string; cats: Record<string, string>; before: Cell; after: Cell }[];
    name: string;
    token: string;
  } | null>(null);
  const [applying, setApplying] = useState(false);
  const [servers, setServers] = useState(false);

  // Opened from a task: the submission to look at.
  if (snap && focus && focus !== seenFocus) {
    setSeenFocus(focus);
    const sub = snap.submissions.find((s) => s.id === focus);
    if (sub) {
      setPeriod(sub.period);
      setOpen({ unit: { place_id: sub.place_id, partner_id: sub.partner_id }, id: sub.id });
    }
  }

  if (!snap) return null;
  const period = chosen ?? defaultPeriod(snap.periods);
  const entry = snap.indicators.filter(isEntry);
  const per = snap.periods.find((p) => p.code === period);
  const subs = snap.submissions.filter((s) => s.period === period);
  const whole = t("rec.wholeProject");
  const byUnit = new Map(subs.map((s) => [unitKey(s), s]));
  const extra = subs.filter((s) => !snap.units.some((u) => unitKey(u) === unitKey(s)));
  const rows: { unit: ReportingUnit; sub: Submission | undefined }[] = [
    ...snap.units.map((u) => ({ unit: u, sub: byUnit.get(unitKey(u)) })),
    ...extra.map((s) => ({ unit: { place_id: s.place_id, partner_id: s.partner_id }, sub: s })),
  ];
  const validated = rows.filter((r) => r.sub && ["validated", "locked"].includes(r.sub.status)).length;

  const safe = async <T,>(fn: () => Promise<T>) => {
    setNote(null);
    try {
      return await fn();
    } catch (e) {
      setNote({ kind: "error", text: describe(e) });
      return null;
    }
  };

  const templates = async () => {
    const folder = await pick("folder");
    if (!folder || !period) return;
    const r = await safe(() => call<{ files: string[] }>("canevas.write", { file_token: folder.token, period, lang }));
    if (r) setNote({ kind: "ok", text: t("rec.templatesDone", { n: r.files.length, folder: folder.name }) });
  };
  const receive = async () => {
    const file = await pick("xlsx-open");
    if (!file) return;
    const r = await safe(() =>
      call<
        Snapshot & {
          revision: boolean;
          changes: { indicator_id: string; cats: Record<string, string>; before: Cell; after: Cell }[];
          applied: boolean;
          submission_id: string;
        }
      >("canevas.receive", { file_token: file.token }),
    );
    if (!r) return;
    setSnap(r);
    if (r.revision) setRevision({ changes: r.changes, name: file.name, token: file.token });
    else {
      const sub = r.submissions.find((s) => s.id === r.submission_id);
      if (sub) setPeriod(sub.period);
      setNote({ kind: "ok", text: t("rec.received", { name: file.name }) });
    }
  };
  const lock = async (state: "locked" | "open", why = "") => {
    if (!per) return;
    const s = await safe(() => call<Snapshot>("period.set_state", { id: per.id, state, reason: why }));
    if (s) setSnap(s);
  };

  if (!snap.periods.length)
    return (
      <div className="inner">
        <h1>{t("nav.reception")}</h1>
        <Notice>
          {t("rec.noCalendar")}{" "}
          <button className="link" onClick={() => go("setup")}>
            {t("mplan.openSetup")}
          </button>
        </Notice>
      </div>
    );

  return (
    <div className="inner wide">
      <div className="page-head">
        <div>
          <h1>{t("nav.reception")}</h1>
          <p className="lead">{t("rec.lead")}</p>
        </div>
        <div className="row-actions">
          <button className="btn" onClick={() => setServers(true)} data-testid="rec-servers">
            {t("cx.open")}
          </button>
          <button className="btn" onClick={templates} disabled={!entry.length} data-testid="rec-templates">
            <Icon name="download" /> {t("rec.templates")}
          </button>
          <button className="btn" onClick={receive} disabled={!entry.length} data-testid="rec-receive">
            <Icon name="open" /> {t("rec.receive")}
          </button>
        </div>
      </div>

      {note && <Notice kind={note.kind}>{note.text}</Notice>}
      {revision && (
        <section className="box stack" data-testid="rec-revision">
          <p>{t("rec.revision", { name: revision.name, n: revision.changes.length })}</p>
          {revision.changes.length > 0 && (
            <table className="table compact">
              <thead>
                <tr>
                  <th>{t("mplan.indicator")}</th>
                  <th>{t("rec.category")}</th>
                  <th>{t("rec.before")}</th>
                  <th>{t("rec.after")}</th>
                </tr>
              </thead>
              <tbody>
                {revision.changes.map((c, i) => {
                  const ind = snap.indicators.find((x) => x.id === c.indicator_id);
                  const cell = (x: Cell) =>
                    x[1] !== null
                      ? `${x[1]} / ${x[2] ?? ""}`
                      : x[0] === null
                        ? ""
                        : String(+(ind?.unit === "percent" ? x[0] * 100 : x[0]).toFixed(4));
                  const cat = Object.entries(c.cats)
                    .map(([k, code]) => {
                      const d = snap.disaggregations.find((x) => x.key === k);
                      const found = d?.categories.find((x) => x.code === code);
                      return found ? (lang === "en" ? found.en : found.fr) : t("setup.unspecified");
                    })
                    .join(", ");
                  return (
                    <tr key={i}>
                      <td>{ind?.name}</td>
                      <td>{cat || t("rec.total")}</td>
                      <td className="num">{cell(c.before)}</td>
                      <td className="num">
                        <strong>{cell(c.after)}</strong>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <div className="row-actions start">
            {revision.changes.length > 0 && (
              <button className="btn primary" onClick={() => setApplying(true)} data-testid="rec-apply-revision">
                {t("rec.applyRevision")}
              </button>
            )}
            <button className="btn" onClick={() => setRevision(null)}>
              {t("common.close")}
            </button>
          </div>
        </section>
      )}
      {applying && revision && (
        <ReasonDialog
          title={t("rec.applyRevision")}
          onCancel={() => setApplying(false)}
          onConfirm={async (why) => {
            setApplying(false);
            const r = await safe(() =>
              call<Snapshot>("canevas.receive", { file_token: revision.token, apply: true, reason: why }),
            );
            if (r) {
              setSnap(r);
              setRevision(null);
              setNote({ kind: "ok", text: t("rec.revisionApplied") });
            }
          }}
        />
      )}
      {!entry.length && (
        <Empty
          icon="target"
          title={t("rec.noIndicators")}
          text={t("rec.noIndicatorsText")}
          action={
            <button className="btn" onClick={() => go("indicators")}>
              {t("nav.indicators")}
            </button>
          }
        />
      )}

      <div className="period-bar" role="tablist" aria-label={t("setup.period")}>
        {snap.periods.map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={p.code === period}
            className={`period-tab${p.end < todayIso() ? " past" : ""}`}
            onClick={() => setPeriod(p.code)}
            data-testid={`rec-period-${p.code}`}
          >
            {periodLabel(p, lang)}
            {p.state === "locked" && <Icon name="lock" size={12} />}
          </button>
        ))}
      </div>

      {per && (
        <div className="box row-between">
          <div className="small">
            <strong>{periodLabel(per, lang)}</strong> {t("ws.dates", { start: day(per.start), end: day(per.end) })}
            <br />
            <span className="muted">{t("rec.due", { date: day(per.data_due) })}</span>
          </div>
          <div className="row-actions">
            <span className="muted small">{t("rec.validatedCount", { n: validated, total: rows.length })}</span>
            {per.state === "locked" ? (
              <button className="btn" onClick={() => setReason("unlock")} data-testid="rec-unlock">
                {t("rec.unlock")}
              </button>
            ) : (
              <button
                className="btn"
                onClick={() => lock("locked")}
                disabled={validated < rows.filter((r) => r.sub).length || !rows.some((r) => r.sub)}
                data-testid="rec-lock"
              >
                <Icon name="lock" /> {t("rec.lock")}
              </button>
            )}
          </div>
        </div>
      )}

      {entry.length > 0 && (
        <table className="table" data-testid="rec-units">
          <thead>
            <tr>
              <th>{t("rec.unit")}</th>
              <th>{t("setup.state")}</th>
              <th>{t("rec.receivedOn")}</th>
              <th>{t("rec.channel")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map(({ unit, sub }) => (
              <tr key={unitKey(unit)} data-testid={`rec-row-${unitName(snap, unit, whole)}`}>
                <td>
                  <strong>{unitName(snap, unit, whole)}</strong>
                  {sub?.status === "returned" && sub.comment && <div className="muted small">{sub.comment}</div>}
                </td>
                <td>
                  <SubStatus status={sub?.status} late={!sub && !!per && per.data_due < todayIso()} />
                </td>
                <td className="small">{sub?.submitted_at ? day(sub.submitted_at) : ""}</td>
                <td className="small muted">{sub ? t(`rec.channel_${sub.channel}`) : ""}</td>
                <td className="row-actions">
                  <button
                    className="btn small"
                    onClick={() => setOpen({ unit, id: sub?.id ?? null })}
                    disabled={!sub && per?.state === "locked"}
                    data-testid="rec-open"
                  >
                    {sub && ["validated", "locked"].includes(sub.status) ? t("rec.view") : t("rec.enter")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {open && period && (
        <EntryPanel period={period} unit={open.unit} id={open.id} indicators={entry} onClose={() => setOpen(null)} />
      )}
      {servers && <ConnectionsPanel onClose={() => setServers(false)} />}
      {reason && (
        <ReasonDialog
          title={t("rec.unlockTitle")}
          onCancel={() => setReason(null)}
          onConfirm={(why) => {
            setReason(null);
            void lock("open", why);
          }}
        />
      )}
    </div>
  );
}

export function SubStatus({ status, late }: { status: string | undefined; late?: boolean }) {
  const { t } = useI18n();
  const s = status ?? (late ? "missing" : "expected");
  return (
    <span className={`sub-status st-${s}`} data-testid="sub-status">
      {t(`rec.status_${s}`)}
    </span>
  );
}

function ReasonDialog({
  title,
  onCancel,
  onConfirm,
}: {
  title: string;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  return (
    <Panel
      title={title}
      onClose={onCancel}
      testId="reason-dialog"
      footer={
        <>
          <button className="btn" onClick={onCancel}>
            {t("common.cancel")}
          </button>
          <button
            className="btn primary"
            disabled={!text.trim()}
            onClick={() => onConfirm(text)}
            data-testid="reason-dialog-ok"
          >
            {t("common.confirm")}
          </button>
        </>
      }
    >
      <Field label={t("rec.reason")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            data-testid="reason-dialog-text"
          />
        )}
      </Field>
    </Panel>
  );
}

// ----- one submission ----------------------------------------------------------------------------

type Typed = Record<string, Record<string, { v: string; n: string; d: string }>>;

const show = (x: number | null | undefined, percent = false) =>
  x === null || x === undefined ? "" : String(+(percent ? x * 100 : x).toFixed(6));

function typedFrom(cells: SubmissionDetail["cells"], inds: Indicator[]): Typed {
  const out: Typed = {};
  for (const ind of inds) {
    out[ind.id] = {};
    for (const [key, c] of Object.entries(cells[ind.id] ?? {})) {
      const [v, n, d] = c as Cell;
      const fraction = entryKind(ind.unit) === "fraction";
      out[ind.id][key] = {
        v: fraction && n !== null ? "" : show(v, ind.unit === "percent"),
        n: show(n),
        d: show(d),
      };
    }
  }
  return out;
}

function EntryPanel({
  period,
  unit,
  id,
  indicators,
  onClose,
}: {
  period: string;
  unit: ReportingUnit;
  id: string | null;
  indicators: Indicator[];
  onClose: () => void;
}) {
  const { t, lang, date } = useI18n();
  const { snap, setSnap, describe } = useProject();
  const levels = useLevels();
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [typed, setTyped] = useState<Typed>({});
  const [source, setSource] = useState("");
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState<"return" | "reopen" | null>(null);
  const [justifying, setJustifying] = useState<Record<string, string>>({});
  const [subId, setSubId] = useState(id);
  const [pasting, setPasting] = useState<{ ind: Indicator; key: string } | null>(null);

  const load = (d: SubmissionDetail) => {
    setDetail(d);
    setTyped(typedFrom(d.cells, indicators));
    setSource(d.submission.source_ref ?? "");
    setDirty(false);
  };

  useEffect(() => {
    if (!subId) return;
    call<SubmissionDetail>("submission.get", { id: subId })
      .then(load)
      .catch((e) => setError(describe(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subId]);

  const groups = useMemo(() => {
    if (!snap) return [];
    return snap.framework
      .filter((n) => levels.carries(n.level))
      .map((node) => ({ node, list: indicators.filter((i) => i.node_id === node.id) }))
      .filter((g) => g.list.length);
  }, [snap, indicators, levels]);

  if (!snap) return null;
  const status = detail?.submission.status ?? "draft";
  const readOnly = ["validated", "locked"].includes(status);
  const whole = t("rec.wholeProject");
  const unspecified = t("setup.unspecified");

  const set = (indId: string, key: string, field: "v" | "n" | "d", value: string) => {
    setTyped((prev) => ({
      ...prev,
      [indId]: { ...prev[indId], [key]: { ...{ v: "", n: "", d: "" }, ...prev[indId]?.[key], [field]: value } },
    }));
    setDirty(true);
  };

  const values = () => {
    const out: Record<string, unknown>[] = [];
    for (const ind of indicators) {
      for (const [key, x] of Object.entries(typed[ind.id] ?? {})) {
        const cats = Object.fromEntries(
          key
            .split(";")
            .filter(Boolean)
            .map((p) => p.split("=")),
        );
        out.push({ indicator_id: ind.id, cats, value: x.v, numerator: x.n, denominator: x.d });
      }
      // Indicators left empty are cleared too.
      if (!Object.keys(typed[ind.id] ?? {}).length) out.push({ indicator_id: ind.id, cats: {}, value: "" });
    }
    return out;
  };

  const ensure = async (): Promise<string | null> => {
    if (subId) return subId;
    const r = await call<Snapshot & { created: string }>("submission.open", { period, ...unit });
    setSnap(r);
    setSubId(r.created);
    return r.created;
  };

  const save = async () => {
    setError(null);
    try {
      const sid = await ensure();
      if (!sid) return null;
      const r = await call<Snapshot & SubmissionDetail>("submission.save", {
        id: sid,
        values: values(),
        source_ref: source,
      });
      setSnap(r);
      load(r);
      return r;
    } catch (e) {
      setError(describe(e));
      return null;
    }
  };

  const act = async (action: string, comment = "") => {
    setError(null);
    try {
      if (dirty && !readOnly && !(await save())) return;
      const sid = await ensure();
      const r = await call<Snapshot & SubmissionDetail>("submission.act", { id: sid, action, comment });
      setSnap(r);
      load(r);
    } catch (e) {
      setError(e instanceof EngineCallError && e.key === "alerts_open" ? t("rec.alertsOpen") : describe(e));
    }
  };

  const justify = async (key: string) => {
    const text = justifying[key] ?? "";
    try {
      const r = await call<Snapshot & SubmissionDetail>("alert.justify", { key, text });
      setSnap(r);
      setDetail(r);
      setJustifying({ ...justifying, [key]: "" });
    } catch (e) {
      setError(describe(e));
    }
  };

  const remove = async () => {
    if (!subId) return onClose();
    try {
      setSnap(await call<Snapshot>("submission.delete", { id: subId }));
      onClose();
    } catch (e) {
      setError(describe(e));
    }
  };

  const nameOf = (indId: string) => indicators.find((i) => i.id === indId)?.name ?? "";
  const alertText = (a: SubmissionDetail["alerts"][number]) =>
    t(`rec.check_${a.check}`, {
      indicator: nameOf(a.indicator_id),
      ...Object.fromEntries(Object.entries(a.info).map(([k, v]) => [k, String(v ?? "")])),
    });

  const inputs = (ind: Indicator, key: string) => {
    const x = typed[ind.id]?.[key] ?? { v: "", n: "", d: "" };
    const kind = entryKind(ind.unit);
    const label = `${ind.name} ${key}`;
    if (kind === "fraction")
      return (
        <>
          <td>
            <input
              className="input cell"
              inputMode="decimal"
              value={x.n}
              disabled={readOnly}
              aria-label={`${label} ${t("rec.numerator")}`}
              onChange={(e) => set(ind.id, key, "n", e.target.value)}
              data-testid={`cell-${ind.name}-${key || "total"}-n`}
            />
          </td>
          <td>
            <input
              className="input cell"
              inputMode="decimal"
              value={x.d}
              disabled={readOnly}
              aria-label={`${label} ${t("rec.denominator")}`}
              onChange={(e) => set(ind.id, key, "d", e.target.value)}
              data-testid={`cell-${ind.name}-${key || "total"}-d`}
            />
          </td>
          <td className="num muted small">
            {(() => {
              const n = toNumber(x.n);
              const d = toNumber(x.d);
              if (n === null || !d) return x.v ? x.v + (ind.unit === "percent" ? " %" : "") : "";
              const v = (n / d) * (ind.unit === "percent" ? 100 : ind.multiplier || 1);
              return `${+v.toFixed(2)}${ind.unit === "percent" ? " %" : ""}`;
            })()}
          </td>
        </>
      );
    if (kind === "milestone")
      return (
        <td colSpan={3}>
          <select
            className="input"
            value={x.v}
            disabled={readOnly}
            aria-label={label}
            onChange={(e) => set(ind.id, key, "v", e.target.value)}
            data-testid={`cell-${ind.name}-${key || "total"}`}
          >
            <option value="">{t("rec.notGiven")}</option>
            <option value="1">{t("rec.done")}</option>
            <option value="0">{t("rec.notDone")}</option>
          </select>
        </td>
      );
    return (
      <td colSpan={3}>
        <input
          className="input cell wide"
          inputMode="decimal"
          value={x.v}
          disabled={readOnly}
          aria-label={label}
          onChange={(e) => set(ind.id, key, "v", e.target.value)}
          data-testid={`cell-${ind.name}-${key || "total"}`}
        />
        {ind.people === "unique" && !readOnly && (
          <button
            className="link small"
            onClick={() => setPasting({ ind, key })}
            data-testid={`people-${ind.name}-${key || "total"}`}
          >
            {t("rec.pastePeople")}
          </button>
        )}
      </td>
    );
  };

  const savePeople = async (text: string) => {
    if (!pasting) return;
    setError(null);
    try {
      if (dirty && !(await save())) return;
      const sid = await ensure();
      const cats = Object.fromEntries(
        pasting.key
          .split(";")
          .filter(Boolean)
          .map((p) => p.split("=")),
      );
      const ids = text
        .split(/[\n\r,;\t]+/)
        .map((x) => x.trim())
        .filter(Boolean);
      const r = await call<Snapshot & SubmissionDetail>("people.save", {
        id: sid,
        indicator_id: pasting.ind.id,
        ids,
        cats,
      });
      setSnap(r);
      load(r);
      setPasting(null);
    } catch (e) {
      setError(describe(e));
    }
  };

  const alerts = detail?.alerts ?? [];
  return (
    <Panel
      wide
      title={t("rec.entryTitle", {
        unit: unitName(snap, unit, whole),
        period: periodLabel(
          snap.periods.find((p) => p.code === period),
          lang,
        ),
      })}
      onClose={onClose}
      testId="entry-panel"
      footer={
        <>
          {!readOnly && status === "draft" && (
            <button className="btn" onClick={remove} data-testid="entry-delete">
              {t("rec.deleteDraft")}
            </button>
          )}
          <span className="spacer" />
          {!readOnly && (
            <button className="btn" onClick={() => void save()} disabled={!dirty} data-testid="entry-save">
              {t("common.save")}
            </button>
          )}
          {["draft", "returned"].includes(status) && (
            <button className="btn" onClick={() => act("submit")} data-testid="entry-submit">
              {t("rec.submit")}
            </button>
          )}
          {["submitted", "review"].includes(status) && (
            <button className="btn" onClick={() => setAsking("return")} data-testid="entry-return">
              {t("rec.return")}
            </button>
          )}
          {!readOnly && (
            <button className="btn primary" onClick={() => act("validate")} data-testid="entry-validate">
              {t("rec.validate")}
            </button>
          )}
          {status === "validated" && (
            <button className="btn" onClick={() => setAsking("reopen")} data-testid="entry-reopen">
              {t("rec.reopen")}
            </button>
          )}
        </>
      }
    >
      <div className="row-between">
        <SubStatus status={detail ? status : undefined} />
        {detail?.submission.status === "returned" && detail.submission.comment && (
          <span className="small">{t("rec.returnedBecause", { comment: detail.submission.comment })}</span>
        )}
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {status === "locked" && <Notice>{t("rec.lockedText")}</Notice>}

      <table className="table entry-grid" data-testid="entry-grid">
        <thead>
          <tr>
            <th>{t("mplan.indicator")}</th>
            <th>{t("rec.category")}</th>
            <th colSpan={3}>{t("rec.values")}</th>
          </tr>
        </thead>
        <tbody>
          {groups.map(({ node, list }) => (
            <Fragment key={node.id}>
              <tr className="group-row">
                <td colSpan={5}>
                  {t("common.labelled", {
                    a: [levels.name(node.level), node.code].filter(Boolean).join(" "),
                    b: node.title,
                  })}
                </td>
              </tr>
              {list.map((ind) => {
                const cells = cellsOf(ind, snap.disaggregations, lang, unspecified);
                const fraction = entryKind(ind.unit) === "fraction";
                const head = (
                  <td rowSpan={cells.length ? cells.length + 1 : 1} className="entry-ind">
                    <strong>{ind.name}</strong>
                    <div className="muted small">
                      {t(`indicators.unit_${ind.unit}`)}
                      {fraction && ` (${t("rec.numerator")} / ${t("rec.denominator")})`}
                    </div>
                  </td>
                );
                if (!cells.length)
                  return (
                    <tr key={ind.id}>
                      {head}
                      <td className="muted small">{t("rec.total")}</td>
                      {inputs(ind, "")}
                    </tr>
                  );
                return (
                  <Fragment key={ind.id}>
                    {cells.map((c, i) => (
                      <tr key={c.key}>
                        {i === 0 && head}
                        <td className="small">{c.label}</td>
                        {inputs(ind, c.key)}
                      </tr>
                    ))}
                    <tr>
                      <td className="small muted">{t("rec.totalOptional")}</td>
                      {inputs(ind, "")}
                    </tr>
                  </Fragment>
                );
              })}
            </Fragment>
          ))}
        </tbody>
      </table>

      <Field label={t("rec.sourceRef")} hint={t("rec.sourceRefHint")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={source}
            disabled={readOnly}
            onChange={(e) => {
              setSource(e.target.value);
              setDirty(true);
            }}
            data-testid="entry-source"
          />
        )}
      </Field>

      {alerts.length > 0 && (
        <section className="stack" data-testid="entry-alerts">
          <h3 className="panel-section">{t("rec.checks")}</h3>
          {alerts.map((a) => (
            <div key={a.key} className={`alert sev-${a.severity}`} data-testid={`alert-${a.check}`}>
              <div>
                <strong>{t(`rec.sev_${a.severity}`)}</strong> {alertText(a)}
              </div>
              {a.severity === "review" && !readOnly && (
                <div className="row-actions start">
                  {a.justification ? (
                    <span className="small">
                      {t("rec.justified", { text: a.justification })}{" "}
                      <button className="link" onClick={() => justify(a.key)}>
                        {t("rec.unjustify")}
                      </button>
                    </span>
                  ) : (
                    <>
                      <input
                        className="input"
                        placeholder={t("rec.justifyPlaceholder")}
                        aria-label={t("rec.justifyPlaceholder")}
                        value={justifying[a.key] ?? ""}
                        onChange={(e) => setJustifying({ ...justifying, [a.key]: e.target.value })}
                        data-testid="alert-justify-text"
                      />
                      <button
                        className="btn small"
                        disabled={!(justifying[a.key] ?? "").trim()}
                        onClick={() => justify(a.key)}
                        data-testid="alert-justify"
                      >
                        {t("rec.justify")}
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </section>
      )}

      {detail && detail.submission.history.length > 0 && (
        <details className="small">
          <summary>{t("rec.history")}</summary>
          <ul className="plain">
            {detail.submission.history.map((h, i) => (
              <li key={i}>
                {date(h.at)} : {t(`rec.action_${h.action}`)}
                {h.comment ? `. ${h.comment}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}

      {asking && (
        <ReasonDialog
          title={t(asking === "return" ? "rec.returnTitle" : "rec.reopenTitle")}
          onCancel={() => setAsking(null)}
          onConfirm={(why) => {
            const a = asking;
            setAsking(null);
            void act(a, why);
          }}
        />
      )}
      <Attachments kind="submission" id={subId} />
      {pasting && (
        <PeopleDialog
          name={pasting.ind.name}
          onCancel={() => setPasting(null)}
          onConfirm={(text) => void savePeople(text)}
        />
      )}
    </Panel>
  );
}

/** Identifiers of the people of one cell (card or register numbers), one per line.
 * They are kept only as pseudonyms, so the same person is counted once. */
function PeopleDialog({
  name,
  onCancel,
  onConfirm,
}: {
  name: string;
  onCancel: () => void;
  onConfirm: (text: string) => void;
}) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const n = new Set(
    text
      .split(/[\n\r,;\t]+/)
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean),
  ).size;
  return (
    <Panel
      title={t("rec.peopleTitle", { name })}
      onClose={onCancel}
      testId="people-dialog"
      footer={
        <>
          <button className="btn" onClick={onCancel}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" disabled={!n} onClick={() => onConfirm(text)} data-testid="people-ok">
            {t("rec.peopleSave", { n })}
          </button>
        </>
      }
    >
      <p className="muted small">{t("rec.peopleHint")}</p>
      <Field label={t("rec.peopleIds")}>
        {(id) => (
          <textarea
            id={id}
            className="input mono"
            rows={10}
            value={text}
            onChange={(e) => setText(e.target.value)}
            data-testid="people-text"
          />
        )}
      </Field>
    </Panel>
  );
}
