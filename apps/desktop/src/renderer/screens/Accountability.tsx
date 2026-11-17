// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Accountability and learning (module M11): feedback and complaints with their
// answer deadlines, recommendations and the follow-up given, risks and
// assumptions, learning questions, lessons and review meetings.

import { useState } from "react";
import {
  ACTION_STATES,
  call,
  CHANNELS,
  Decision,
  Feedback,
  FeedbackCategory,
  FEEDBACK_STATES,
  LearningQuestion,
  Lesson,
  Meeting,
  MEETING_KINDS,
  REC_SOURCES,
  RecAction,
  Recommendation,
  RESPONSES,
  REVIEW_MONTHS,
  Risk,
  SENSITIVITY,
  Snapshot,
} from "../api";
import { useI18n } from "../i18n";
import { Attachments } from "../Attachments";
import { useProject } from "../state";
import { Confirm, Empty, Field, Icon, IconButton, Notice, Panel, rowOpen } from "../ui";

type Tab = "feedback" | "recommendations" | "risks" | "learning";
const TABS: Tab[] = ["feedback", "recommendations", "risks", "learning"];

export function Accountability() {
  const { t } = useI18n();
  const { snap, focus } = useProject();
  const [tab, setTab] = useState<Tab>(TABS.includes(focus as Tab) ? (focus as Tab) : "feedback");
  if (!snap) return null;
  const counts: Record<Tab, number> = {
    feedback: snap.feedback.filter((f) => f.overdue).length,
    recommendations: snap.recommendations.filter((r) => r.late_actions.length).length,
    risks: snap.risks.filter((r) => r.review_late).length,
    learning: 0,
  };
  return (
    <div className="inner wide stack-lg">
      <div>
        <h1>{t("acc.title")}</h1>
        <p className="lead">{t("acc.lead")}</p>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map((k) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            className="tab"
            onClick={() => setTab(k)}
            data-testid={`acc-tab-${k}`}
          >
            {t(`acc.tab_${k}`)}
            {!!counts[k] && <span className="tab-count warn">{counts[k]}</span>}
          </button>
        ))}
      </div>
      {tab === "feedback" && <FeedbackTab />}
      {tab === "recommendations" && <Recommendations />}
      {tab === "risks" && <Risks />}
      {tab === "learning" && <Learning />}
    </div>
  );
}

export function useCategoryName() {
  const { t } = useI18n();
  const { snap } = useProject();
  return (key: string) => {
    const c = snap?.feedback_categories.find((x) => x.key === key);
    return c?.name || t(`fb.cat_${key}`);
  };
}

// ----- feedback and complaints ---------------------------------------------------------------

function FeedbackTab() {
  const { t, day, percent } = useI18n();
  const { snap } = useProject();
  const catName = useCategoryName();
  const [show, setShow] = useState<"open" | "all">("open");
  const [editing, setEditing] = useState<Feedback | "new" | null>(null);
  const [cats, setCats] = useState(false);
  if (!snap) return null;
  const fb = snap.feedback;
  const open = fb.filter((f) => ["received", "forwarded", "in_progress"].includes(f.status));
  const answered = fb.filter((f) => f.answered_at);
  const onTime = answered.filter((f) => (f.answered_at ?? "").slice(0, 10) <= f.deadline);
  const list = [...(show === "open" ? open : fb)].sort((a, b) => b.received.localeCompare(a.received));
  const place = new Map(snap.places.map((p) => [p.id, p.name]));
  return (
    <div className="stack" data-testid="acc-feedback">
      <div className="kpis">
        <div className="kpi">
          <span className="kpi-label">{t("fb.total")}</span>
          <span className="kpi-value">{fb.length}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("fb.open")}</span>
          <span className="kpi-value">{open.length}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("fb.overdue")}</span>
          <span className="kpi-value" data-testid="fb-overdue">
            {fb.filter((f) => f.overdue).length}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("fb.onTime")}</span>
          <span className="kpi-value">{answered.length ? percent(onTime.length / answered.length, 0) : "-"}</span>
          <span className="kpi-sub">{t("fb.answeredN", { n: answered.length })}</span>
        </div>
      </div>
      <div className="row-between">
        <div className="chips">
          {(["open", "all"] as const).map((k) => (
            <button key={k} className="chip" aria-pressed={show === k} onClick={() => setShow(k)}>
              {t(`fb.show_${k}`)}
            </button>
          ))}
        </div>
        <div className="row-actions">
          <button className="btn" onClick={() => setCats(true)} data-testid="fb-categories">
            {t("fb.categories")}
          </button>
          <button className="btn primary" onClick={() => setEditing("new")} data-testid="fb-add">
            <Icon name="plus" /> {t("fb.add")}
          </button>
        </div>
      </div>
      {list.length === 0 ? (
        <Empty icon="people" title={t(show === "open" ? "fb.noneOpen" : "fb.none")} text={t("fb.noneText")} />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("fb.received")}</th>
                <th>{t("fb.category")}</th>
                <th>{t("fb.summary")}</th>
                <th>{t("fb.channel")}</th>
                <th>{t("fb.place")}</th>
                <th>{t("fb.status")}</th>
                <th>{t("fb.deadline")}</th>
              </tr>
            </thead>
            <tbody>
              {list.map((f) => (
                <tr key={f.id} className="clickable" {...rowOpen(() => setEditing(f))} data-testid="fb-row">
                  <td className="small">{day(f.received)}</td>
                  <td>{catName(f.category)}</td>
                  <td>
                    {f.sensitive ? (
                      <span className="muted">
                        <Icon name="lock" size={14} /> {t("fb.sensitiveCase")}
                      </span>
                    ) : (
                      f.summary
                    )}
                  </td>
                  <td className="small">{t(`fb.channel_${f.channel}`)}</td>
                  <td className="small">{f.place_id ? place.get(f.place_id) : ""}</td>
                  <td>
                    <span className={`status-chip fb-${f.status}`}>{t(`fb.state_${f.status}`)}</span>
                  </td>
                  <td className="small">
                    {day(f.deadline)} {f.overdue && <span className="tag warn">{t("fb.late")}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small">{t("fb.sensitiveNote")}</p>
      {editing && <FeedbackPanel item={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {cats && <CategoriesPanel onClose={() => setCats(false)} />}
    </div>
  );
}

function FeedbackPanel({ item, onClose }: { item: Feedback | null; onClose: () => void }) {
  const { t, date } = useI18n();
  const { snap, run } = useProject();
  const catName = useCategoryName();
  const [f, setF] = useState({
    received: item?.received ?? new Date().toISOString().slice(0, 10),
    channel: item?.channel ?? "hotline",
    place_id: item?.place_id ?? null,
    category: item?.category ?? snap?.feedback_categories[0]?.key ?? "other",
    sensitivity: item?.sensitivity ?? "",
    sensitive: item?.sensitive ?? false,
    summary: item?.summary ?? "",
    detail: item?.detail ?? "",
    response: item?.response ?? "",
    status: item?.status ?? "received",
    status_note: "",
    person: "",
  });
  const [revealed, setRevealed] = useState(!item?.sensitive);
  const [confirm, setConfirm] = useState(false);
  if (!snap) return null;
  const set = (patch: Partial<typeof f>) => setF({ ...f, ...patch });
  const cat = snap.feedback_categories.find((c) => c.key === f.category);
  const save = async () => {
    const s = await run("feedback.save", { id: item?.id, feedback: f });
    if (s) onClose();
  };
  return (
    <Panel
      title={item ? (item.sensitive && !revealed ? t("fb.sensitiveCase") : item.summary) : t("fb.add")}
      onClose={onClose}
      testId="fb-panel"
      footer={
        <>
          {item && revealed && (
            <button className="btn" onClick={() => setConfirm(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          {revealed && (
            <button className="btn primary" onClick={save} disabled={!f.summary.trim()} data-testid="fb-save">
              {t("common.save")}
            </button>
          )}
        </>
      }
    >
      {!revealed ? (
        <div className="stack">
          <Notice>{t(item?.masked ? "fb.maskedText" : "fb.sensitiveHidden")}</Notice>
          {!item?.masked && (
            <div>
              <button
                className="btn"
                onClick={async () => {
                  // Each reading of a sensitive case is written in the audit trail.
                  await call("feedback.reveal", { id: item!.id });
                  setRevealed(true);
                }}
                data-testid="fb-reveal"
              >
                {t("fb.reveal")}
              </button>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="grid-2">
            <Field label={t("fb.received")}>
              {(id) => (
                <input
                  id={id}
                  type="date"
                  className="input"
                  value={f.received}
                  onChange={(e) => set({ received: e.target.value })}
                />
              )}
            </Field>
            <Field label={t("fb.channel")}>
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={f.channel}
                  onChange={(e) => set({ channel: e.target.value as Feedback["channel"] })}
                >
                  {CHANNELS.map((c) => (
                    <option key={c} value={c}>
                      {t(`fb.channel_${c}`)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <div className="grid-2">
            <Field label={t("fb.category")} hint={cat ? t("fb.daysHint", { n: cat.days }) : undefined}>
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={f.category}
                  onChange={(e) => set({ category: e.target.value })}
                  data-testid="fb-category"
                >
                  {snap.feedback_categories.map((c) => (
                    <option key={c.key} value={c.key}>
                      {catName(c.key)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label={t("fb.sensitivity")}>
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={f.sensitivity}
                  onChange={(e) => set({ sensitivity: e.target.value as Feedback["sensitivity"] })}
                >
                  {SENSITIVITY.map((s) => (
                    <option key={s} value={s}>
                      {t(`fb.sens_${s || "none"}`)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={f.sensitive || !!cat?.sensitive || !!f.sensitivity}
              disabled={!!cat?.sensitive || !!f.sensitivity}
              onChange={(e) => set({ sensitive: e.target.checked })}
            />{" "}
            {t("fb.sensitive")}
          </label>
          {snap.places.length > 0 && (
            <Field label={t("fb.place")}>
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={f.place_id ?? ""}
                  onChange={(e) => set({ place_id: e.target.value || null })}
                >
                  <option value="" />
                  {snap.places.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          )}
          <Field label={t("fb.person")} hint={item?.person ? t("fb.personKept") : t("fb.personHint")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={f.person}
                onChange={(e) => set({ person: e.target.value })}
                autoComplete="off"
              />
            )}
          </Field>
          <Field label={t("fb.summary")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={f.summary}
                onChange={(e) => set({ summary: e.target.value })}
                data-testid="fb-summary"
              />
            )}
          </Field>
          <Field label={t("fb.detail")}>
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={4}
                value={f.detail}
                onChange={(e) => set({ detail: e.target.value })}
              />
            )}
          </Field>
          <h3>{t("fb.circuit")}</h3>
          <div className="chips">
            {FEEDBACK_STATES.map((s) => (
              <button
                key={s}
                className="chip small"
                aria-pressed={f.status === s}
                onClick={() => set({ status: s })}
                data-testid={`fb-state-${s}`}
              >
                {t(`fb.state_${s}`)}
              </button>
            ))}
          </div>
          {item && f.status !== item.status && (
            <Field label={t("fb.statusNote")}>
              {(id) => (
                <input
                  id={id}
                  className="input"
                  value={f.status_note}
                  onChange={(e) => set({ status_note: e.target.value })}
                />
              )}
            </Field>
          )}
          <Field label={t("fb.response")}>
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={3}
                value={f.response}
                onChange={(e) => set({ response: e.target.value })}
              />
            )}
          </Field>
          {item && item.history.length > 0 && (
            <ul className="plain small muted">
              {item.history.map((h, i) => (
                <li key={i}>
                  {date(h.at)} : {t(`fb.state_${h.status}`)}
                  {h.note ? `, ${h.note}` : ""}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {revealed && <Attachments kind="feedback" id={item?.id} />}
      {confirm && (
        <Confirm
          text={t("fb.deleteConfirm")}
          confirmLabel={t("common.delete")}
          onConfirm={async () => (await run("feedback.delete", { id: item!.id })) && onClose()}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

function CategoriesPanel({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [cats, setCats] = useState<FeedbackCategory[]>(snap?.feedback_categories ?? []);
  if (!snap) return null;
  const set = (i: number, patch: Partial<FeedbackCategory>) =>
    setCats(cats.map((c, k) => (k === i ? { ...c, ...patch } : c)));
  const used = new Set(snap.feedback.map((f) => f.category));
  const save = async () => {
    const s = await run("feedback.categories", { categories: cats });
    if (s) onClose();
  };
  return (
    <Panel
      wide
      title={t("fb.categories")}
      onClose={onClose}
      testId="fb-categories-panel"
      footer={
        <>
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save}>
            {t("common.save")}
          </button>
        </>
      }
    >
      <p className="muted small">{t("fb.categoriesLead")}</p>
      <table className="table compact">
        <thead>
          <tr>
            <th>{t("fb.category")}</th>
            <th className="num">{t("fb.days")}</th>
            <th>{t("fb.sensitive")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {cats.map((c, i) => (
            <tr key={c.key}>
              <td>
                <input
                  className="input"
                  value={c.name}
                  placeholder={t(`fb.cat_${c.key}`)}
                  onChange={(e) => set(i, { name: e.target.value })}
                />
              </td>
              <td className="num">
                <input
                  className="input num"
                  style={{ maxWidth: 80 }}
                  inputMode="numeric"
                  value={String(c.days)}
                  onChange={(e) => set(i, { days: Number(e.target.value.replace(/\D/g, "")) || 0 })}
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={c.sensitive}
                  onChange={(e) => set(i, { sensitive: e.target.checked })}
                />
              </td>
              <td>
                <IconButton
                  icon="trash"
                  label={t("common.delete")}
                  disabled={used.has(c.key)}
                  onClick={() => setCats(cats.filter((_, k) => k !== i))}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div>
        <button
          className="btn small"
          onClick={() =>
            setCats([
              ...cats,
              { key: `c_${Math.random().toString(16).slice(2, 10)}`, name: "", days: 14, sensitive: false },
            ])
          }
        >
          <Icon name="plus" /> {t("fb.addCategory")}
        </button>
      </div>
    </Panel>
  );
}

// ----- recommendations ----------------------------------------------------------------------------

function Recommendations() {
  const { t } = useI18n();
  const { snap } = useProject();
  const [editing, setEditing] = useState<Recommendation | "new" | null>(null);
  if (!snap) return null;
  const evals = new Map(snap.evaluations.map((e) => [e.id, e.title]));
  return (
    <div className="stack" data-testid="acc-recommendations">
      <div className="row-actions start">
        <button className="btn primary" onClick={() => setEditing("new")} data-testid="rec-add">
          <Icon name="plus" /> {t("recs.add")}
        </button>
      </div>
      {snap.recommendations.length === 0 ? (
        <Empty icon="doc" title={t("recs.none")} text={t("recs.noneText")} />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("recs.text")}</th>
                <th>{t("recs.source")}</th>
                <th>{t("recs.response")}</th>
                <th>{t("recs.actions")}</th>
                <th>{t("recs.status")}</th>
              </tr>
            </thead>
            <tbody>
              {snap.recommendations.map((r) => (
                <tr key={r.id} className="clickable" {...rowOpen(() => setEditing(r))} data-testid="rec-row">
                  <td>{r.text}</td>
                  <td className="small">
                    {t(`recs.src_${r.source}`)}
                    {r.evaluation_id && evals.get(r.evaluation_id) ? `, ${evals.get(r.evaluation_id)}` : ""}
                    {r.source_ref ? `, ${r.source_ref}` : ""}
                  </td>
                  <td className="small">{t(`recs.resp_${r.response}`)}</td>
                  <td className="small">
                    {r.actions.filter((a) => a.status === "done").length}/{r.actions.length}{" "}
                    {r.late_actions.length > 0 && (
                      <span className="tag warn">{t("recs.lateN", { n: r.late_actions.length })}</span>
                    )}
                  </td>
                  <td>
                    <span className={`status-chip rec-${r.status}`}>{t(`recs.state_${r.status}`)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <RecommendationPanel item={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

export function RecommendationPanel({
  item,
  evaluationId,
  onClose,
}: {
  item: Recommendation | null;
  evaluationId?: string;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [r, setR] = useState({
    source: item?.source ?? (evaluationId ? "evaluation" : "mission"),
    evaluation_id: item?.evaluation_id ?? evaluationId ?? null,
    source_ref: item?.source_ref ?? "",
    date: item?.date ?? "",
    text: item?.text ?? "",
    response: item?.response ?? "pending",
    response_reason: item?.response_reason ?? "",
    actions: item?.actions ?? ([] as RecAction[]),
  });
  const [confirm, setConfirm] = useState(false);
  if (!snap) return null;
  const set = (patch: Partial<typeof r>) => setR({ ...r, ...patch });
  const setAction = (i: number, patch: Partial<RecAction>) =>
    set({ actions: r.actions.map((a, k) => (k === i ? { ...a, ...patch } : a)) });
  const save = async () => {
    const s = await run("recommendation.save", { id: item?.id, recommendation: r });
    if (s) onClose();
  };
  return (
    <Panel
      wide
      title={item ? t("recs.edit") : t("recs.add")}
      onClose={onClose}
      testId="rec-panel"
      footer={
        <>
          {item && (
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
            disabled={!r.text.trim() || r.actions.some((a) => !a.text.trim())}
            data-testid="rec-save"
          >
            {t("common.save")}
          </button>
        </>
      }
    >
      <Field label={t("recs.text")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={3}
            value={r.text}
            onChange={(e) => set({ text: e.target.value })}
            data-testid="rec-text"
          />
        )}
      </Field>
      <div className="grid-2">
        <Field label={t("recs.source")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={r.source}
              onChange={(e) => set({ source: e.target.value as Recommendation["source"] })}
            >
              {REC_SOURCES.map((s) => (
                <option key={s} value={s}>
                  {t(`recs.src_${s}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
        {r.source === "evaluation" ? (
          <Field label={t("recs.evaluation")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={r.evaluation_id ?? ""}
                onChange={(e) => set({ evaluation_id: e.target.value || null })}
              >
                <option value="" />
                {snap.evaluations.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title}
                  </option>
                ))}
              </select>
            )}
          </Field>
        ) : (
          <Field label={t("recs.sourceRef")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={r.source_ref}
                onChange={(e) => set({ source_ref: e.target.value })}
              />
            )}
          </Field>
        )}
      </div>
      <Field label={t("recs.date")}>
        {(id) => (
          <input id={id} type="date" className="input" value={r.date} onChange={(e) => set({ date: e.target.value })} />
        )}
      </Field>
      <h3>{t("recs.response")}</h3>
      <div className="chips">
        {RESPONSES.map((x) => (
          <button
            key={x}
            className="chip small"
            aria-pressed={r.response === x}
            onClick={() => set({ response: x })}
            data-testid={`rec-resp-${x}`}
          >
            {t(`recs.resp_${x}`)}
          </button>
        ))}
      </div>
      {(r.response === "rejected" || r.response === "partial") && (
        <Field label={t("recs.reason")}>
          {(id) => (
            <textarea
              id={id}
              className="input"
              rows={2}
              value={r.response_reason}
              onChange={(e) => set({ response_reason: e.target.value })}
            />
          )}
        </Field>
      )}
      {r.response !== "rejected" && (
        <>
          <h3>{t("recs.actions")}</h3>
          <p className="muted small">{t("recs.actionsHint")}</p>
          {r.actions.map((a, i) => (
            <div key={a.id ?? i} className="box stack-sm">
              <div className="row-between">
                <input
                  className="input"
                  value={a.text}
                  placeholder={t("recs.actionText")}
                  onChange={(e) => setAction(i, { text: e.target.value })}
                  data-testid="rec-action-text"
                />
                <IconButton
                  icon="trash"
                  label={t("common.delete")}
                  onClick={() => set({ actions: r.actions.filter((_, k) => k !== i) })}
                />
              </div>
              <div className="grid-3">
                <input
                  className="input"
                  value={a.responsible}
                  placeholder={t("recs.responsible")}
                  onChange={(e) => setAction(i, { responsible: e.target.value })}
                />
                <input
                  className="input"
                  type="date"
                  value={a.due}
                  aria-label={t("recs.due")}
                  onChange={(e) => setAction(i, { due: e.target.value })}
                  data-testid="rec-action-due"
                />
                <select
                  className="input"
                  value={a.status}
                  aria-label={t("recs.status")}
                  onChange={(e) => setAction(i, { status: e.target.value as RecAction["status"] })}
                >
                  {ACTION_STATES.map((s) => (
                    <option key={s} value={s}>
                      {t(`recs.action_${s}`)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ))}
          <div>
            <button
              className="btn small"
              onClick={() => set({ actions: [...r.actions, { text: "", responsible: "", due: "", status: "todo" }] })}
              data-testid="rec-action-add"
            >
              <Icon name="plus" /> {t("recs.addAction")}
            </button>
          </div>
        </>
      )}
      <Attachments kind="recommendation" id={item?.id} />
      {confirm && (
        <Confirm
          text={t("recs.deleteConfirm")}
          confirmLabel={t("common.delete")}
          onConfirm={async () => (await run("recommendation.delete", { id: item!.id })) && onClose()}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

// ----- risks and assumptions ---------------------------------------------------------------------

function Risks() {
  const { t, day } = useI18n();
  const { snap, run } = useProject();
  const [editing, setEditing] = useState<Risk | "new" | null>(null);
  const [note, setNote] = useState<string | null>(null);
  if (!snap) return null;
  const node = new Map(snap.framework.map((n) => [n.id, `${n.code ? n.code + " " : ""}${n.title}`]));
  const active = snap.risks.filter((r) => r.status === "active");
  const cell = (p: number, i: number) => active.filter((r) => r.probability === p && r.impact === i).length;
  const fromLogframe = async () => {
    const r = await run<Snapshot & { added: number }>("risk.from_assumptions", {});
    if (r) setNote(t("risk.fromLogframeDone", { n: r.added }));
  };
  const sorted = [...snap.risks].sort(
    (a, b) =>
      Number(a.status === "closed") - Number(b.status === "closed") ||
      b.probability * b.impact - a.probability * a.impact,
  );
  return (
    <div className="stack" data-testid="acc-risks">
      <div className="row-between">
        <p className="muted small">{t("risk.lead")}</p>
        <div className="row-actions">
          <button className="btn" onClick={fromLogframe} data-testid="risk-from-logframe">
            {t("risk.fromLogframe")}
          </button>
          <button className="btn primary" onClick={() => setEditing("new")} data-testid="risk-add">
            <Icon name="plus" /> {t("risk.add")}
          </button>
        </div>
      </div>
      {note && <Notice kind="ok">{note}</Notice>}
      {snap.risks.length === 0 ? (
        <Empty icon="scale" title={t("risk.none")} text={t("risk.noneText")} />
      ) : (
        <div className="risk-layout">
          <table className="risk-matrix" aria-label={t("risk.matrix")}>
            <tbody>
              {[5, 4, 3, 2, 1].map((p) => (
                <tr key={p}>
                  <th className="small">{p}</th>
                  {[1, 2, 3, 4, 5].map((i) => {
                    const score = p * i;
                    const level = score >= 15 ? "high" : score >= 6 ? "medium" : "low";
                    return (
                      <td key={i} className={`risk-cell risk-${level}`}>
                        {cell(p, i) || ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr>
                <th />
                {[1, 2, 3, 4, 5].map((i) => (
                  <th key={i} className="small">
                    {i}
                  </th>
                ))}
              </tr>
            </tbody>
            <caption className="small muted">{t("risk.matrixCaption")}</caption>
          </table>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("risk.titleCol")}</th>
                  <th>{t("risk.result")}</th>
                  <th>{t("risk.level")}</th>
                  <th>{t("risk.responsible")}</th>
                  <th>{t("risk.nextReview")}</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr
                    key={r.id}
                    className={`clickable${r.status === "closed" ? " muted" : ""}`}
                    {...rowOpen(() => setEditing(r))}
                    data-testid="risk-row"
                  >
                    <td>
                      {r.title} {r.kind === "assumption" && <span className="tag">{t("risk.assumptionTag")}</span>}
                    </td>
                    <td className="small">{r.node_id ? node.get(r.node_id) : ""}</td>
                    <td>
                      <span className={`risk-tag risk-${r.level}`}>
                        {t(`risk.level_${r.level}`)} ({r.probability}x{r.impact})
                      </span>
                    </td>
                    <td className="small">{r.responsible}</td>
                    <td className="small">
                      {day(r.review_due)} {r.review_late && <span className="tag warn">{t("risk.reviewLate")}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {editing && <RiskPanel item={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function RiskPanel({ item, onClose }: { item: Risk | null; onClose: () => void }) {
  const { t, day } = useI18n();
  const { snap, run } = useProject();
  const [r, setR] = useState({
    kind: item?.kind ?? "risk",
    node_id: item?.node_id ?? null,
    title: item?.title ?? "",
    description: item?.description ?? "",
    probability: item?.probability ?? 3,
    impact: item?.impact ?? 3,
    measures: item?.measures ?? "",
    responsible: item?.responsible ?? "",
    review_months: item?.review_months ?? 3,
    status: item?.status ?? "active",
  });
  const [review, setReview] = useState<{ date: string; probability: number; impact: number; note: string } | null>(
    null,
  );
  const [confirm, setConfirm] = useState(false);
  if (!snap) return null;
  const set = (patch: Partial<typeof r>) => setR({ ...r, ...patch });
  const save = async () => {
    const s = await run("risk.save", { id: item?.id, risk: r });
    if (s) onClose();
  };
  const saveReview = async () => {
    const s = await run("risk.review", { id: item!.id, review });
    if (s) onClose();
  };
  const scale = (field: "probability" | "impact") => (
    <select className="input" value={r[field]} onChange={(e) => set({ [field]: Number(e.target.value) })}>
      {[1, 2, 3, 4, 5].map((n) => (
        <option key={n} value={n}>
          {n} {t(`risk.${field}_${n}`)}
        </option>
      ))}
    </select>
  );
  return (
    <Panel
      title={item ? item.title : t("risk.add")}
      onClose={onClose}
      testId="risk-panel"
      footer={
        <>
          {item && (
            <button className="btn" onClick={() => setConfirm(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} disabled={!r.title.trim()} data-testid="risk-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <div className="chips">
        {(["risk", "assumption"] as const).map((k) => (
          <button key={k} className="chip" aria-pressed={r.kind === k} onClick={() => set({ kind: k })}>
            {t(`risk.kind_${k}`)}
          </button>
        ))}
      </div>
      <Field label={t("risk.titleCol")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={r.title}
            onChange={(e) => set({ title: e.target.value })}
            data-testid="risk-title"
          />
        )}
      </Field>
      <Field label={t("risk.result")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={r.node_id ?? ""}
            onChange={(e) => set({ node_id: e.target.value || null })}
          >
            <option value="" />
            {snap.framework.map((n) => (
              <option key={n.id} value={n.id}>
                {" ".repeat(n.depth * 3)}
                {n.code} {n.title}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label={t("risk.description")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={2}
            value={r.description}
            onChange={(e) => set({ description: e.target.value })}
          />
        )}
      </Field>
      <div className="grid-2">
        <Field label={t("risk.probability")}>{() => scale("probability")}</Field>
        <Field label={t("risk.impact")}>{() => scale("impact")}</Field>
      </div>
      <Field label={t("risk.measures")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={3}
            value={r.measures}
            onChange={(e) => set({ measures: e.target.value })}
          />
        )}
      </Field>
      <div className="grid-2">
        <Field label={t("risk.responsible")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={r.responsible}
              onChange={(e) => set({ responsible: e.target.value })}
            />
          )}
        </Field>
        <Field label={t("risk.reviewEvery")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={r.review_months}
              onChange={(e) => set({ review_months: Number(e.target.value) })}
            >
              {REVIEW_MONTHS.map((m) => (
                <option key={m} value={m}>
                  {t(`risk.every_${m}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={r.status === "closed"}
          onChange={(e) => set({ status: e.target.checked ? "closed" : "active" })}
        />{" "}
        {t("risk.closed")}
      </label>
      {item && (
        <div className="box stack-sm">
          <div className="row-between">
            <h3>{t("risk.reviews")}</h3>
            {!review && (
              <button
                className="btn small"
                onClick={() =>
                  setReview({
                    date: new Date().toISOString().slice(0, 10),
                    probability: item.probability,
                    impact: item.impact,
                    note: "",
                  })
                }
                data-testid="risk-review"
              >
                {t("risk.addReview")}
              </button>
            )}
          </div>
          {review && (
            <div className="stack-sm">
              <div className="grid-3">
                <input
                  className="input"
                  type="date"
                  value={review.date}
                  aria-label={t("risk.reviewDate")}
                  onChange={(e) => setReview({ ...review, date: e.target.value })}
                />
                <select
                  className="input"
                  value={review.probability}
                  aria-label={t("risk.probability")}
                  onChange={(e) => setReview({ ...review, probability: Number(e.target.value) })}
                >
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {t("risk.probability")} {n}
                    </option>
                  ))}
                </select>
                <select
                  className="input"
                  value={review.impact}
                  aria-label={t("risk.impact")}
                  onChange={(e) => setReview({ ...review, impact: Number(e.target.value) })}
                >
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {t("risk.impact")} {n}
                    </option>
                  ))}
                </select>
              </div>
              <textarea
                className="input"
                rows={2}
                placeholder={t("risk.reviewNote")}
                value={review.note}
                onChange={(e) => setReview({ ...review, note: e.target.value })}
              />
              <div className="row-actions start">
                <button className="btn small primary" onClick={saveReview} data-testid="risk-review-save">
                  {t("risk.saveReview")}
                </button>
                <button className="btn small" onClick={() => setReview(null)}>
                  {t("common.cancel")}
                </button>
              </div>
            </div>
          )}
          {item.reviews.length === 0 ? (
            <p className="muted small">{t("risk.noReview")}</p>
          ) : (
            <ul className="plain small">
              {[...item.reviews].reverse().map((v, i) => (
                <li key={i}>
                  {day(v.date)} : {v.probability}x{v.impact}
                  {v.note ? `, ${v.note}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {confirm && (
        <Confirm
          text={t("risk.deleteConfirm")}
          confirmLabel={t("common.delete")}
          onConfirm={async () => (await run("risk.delete", { id: item!.id })) && onClose()}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

// ----- learning --------------------------------------------------------------------------------------

function Learning() {
  const { t, day } = useI18n();
  const { snap } = useProject();
  const [question, setQuestion] = useState<LearningQuestion | "new" | null>(null);
  const [lesson, setLesson] = useState<Lesson | "new" | null>(null);
  const [meeting, setMeeting] = useState<Meeting | "new" | null>(null);
  if (!snap) return null;
  return (
    <div className="stack-lg" data-testid="acc-learning">
      <section className="box stack">
        <div className="row-between">
          <h2>{t("learn.questions")}</h2>
          <button className="btn small" onClick={() => setQuestion("new")} data-testid="lq-add">
            <Icon name="plus" /> {t("learn.addQuestion")}
          </button>
        </div>
        {snap.learning_questions.length === 0 ? (
          <p className="muted small">{t("learn.noQuestions")}</p>
        ) : (
          <ul className="plain">
            {snap.learning_questions.map((q) => (
              <li key={q.id}>
                <button className="link" onClick={() => setQuestion(q)}>
                  {q.text}
                </button>{" "}
                <span className={`tag${q.status === "open" ? "" : " ok"}`}>{t(`learn.q_${q.status}`)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="box stack">
        <div className="row-between">
          <h2>{t("learn.lessons")}</h2>
          <button className="btn small" onClick={() => setLesson("new")} data-testid="lesson-add">
            <Icon name="plus" /> {t("learn.addLesson")}
          </button>
        </div>
        {snap.lessons.length === 0 ? (
          <p className="muted small">{t("learn.noLessons")}</p>
        ) : (
          <ul className="plain stack-sm">
            {snap.lessons.map((l) => (
              <li key={l.id}>
                <button className="link" onClick={() => setLesson(l)}>
                  <strong>{l.title}</strong>
                </button>
                {l.date && <span className="muted small"> {day(l.date)}</span>}
                {l.lesson && <div className="small">{l.lesson}</div>}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="box stack">
        <div className="row-between">
          <h2>{t("learn.meetings")}</h2>
          <button className="btn small" onClick={() => setMeeting("new")} data-testid="meeting-add">
            <Icon name="plus" /> {t("learn.addMeeting")}
          </button>
        </div>
        {snap.meetings.length === 0 ? (
          <p className="muted small">{t("learn.noMeetings")}</p>
        ) : (
          <ul className="plain">
            {[...snap.meetings]
              .sort((a, b) => b.date.localeCompare(a.date))
              .map((m) => (
                <li key={m.id}>
                  <span className="muted small">{day(m.date)}</span>{" "}
                  <button className="link" onClick={() => setMeeting(m)}>
                    {m.title}
                  </button>{" "}
                  <span className="muted small">{t("learn.decisionsN", { n: m.decisions.length })}</span>
                </li>
              ))}
          </ul>
        )}
      </section>
      {question && <QuestionPanel item={question === "new" ? null : question} onClose={() => setQuestion(null)} />}
      {lesson && <LessonPanel item={lesson === "new" ? null : lesson} onClose={() => setLesson(null)} />}
      {meeting && <MeetingPanel item={meeting === "new" ? null : meeting} onClose={() => setMeeting(null)} />}
    </div>
  );
}

function Footer({
  onDelete,
  onClose,
  onSave,
  canSave,
  testId,
}: {
  onDelete?: () => void;
  onClose: () => void;
  onSave: () => void;
  canSave: boolean;
  testId: string;
}) {
  const { t } = useI18n();
  return (
    <>
      {onDelete && (
        <button className="btn" onClick={onDelete}>
          {t("common.delete")}
        </button>
      )}
      <span className="spacer" />
      <button className="btn" onClick={onClose}>
        {t("common.cancel")}
      </button>
      <button className="btn primary" onClick={onSave} disabled={!canSave} data-testid={testId}>
        {t("common.save")}
      </button>
    </>
  );
}

function QuestionPanel({ item, onClose }: { item: LearningQuestion | null; onClose: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [q, setQ] = useState({
    text: item?.text ?? "",
    status: item?.status ?? "open",
    answer: item?.answer ?? "",
    node_id: item?.node_id ?? null,
  });
  const save = async () => (await run("learning_question.save", { id: item?.id, question: q })) && onClose();
  return (
    <Panel
      title={t(item ? "learn.question" : "learn.addQuestion")}
      onClose={onClose}
      footer={
        <Footer
          onDelete={
            item ? async () => (await run("learning_question.delete", { id: item.id })) && onClose() : undefined
          }
          onClose={onClose}
          onSave={save}
          canSave={!!q.text.trim()}
          testId="lq-save"
        />
      }
    >
      <Field label={t("learn.question")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={2}
            value={q.text}
            onChange={(e) => setQ({ ...q, text: e.target.value })}
            data-testid="lq-text"
          />
        )}
      </Field>
      <div className="chips">
        {(["open", "answered"] as const).map((s) => (
          <button
            key={s}
            className="chip small"
            aria-pressed={q.status === s}
            onClick={() => setQ({ ...q, status: s })}
          >
            {t(`learn.q_${s}`)}
          </button>
        ))}
      </div>
      <Field label={t("learn.answer")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={5}
            value={q.answer}
            onChange={(e) => setQ({ ...q, answer: e.target.value })}
          />
        )}
      </Field>
    </Panel>
  );
}

function LessonPanel({ item, onClose }: { item: Lesson | null; onClose: () => void }) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [l, setL] = useState({
    date: item?.date ?? new Date().toISOString().slice(0, 10),
    title: item?.title ?? "",
    context: item?.context ?? "",
    finding: item?.finding ?? "",
    lesson: item?.lesson ?? "",
    use: item?.use ?? "",
    question_id: item?.question_id ?? null,
    tags: item?.tags ?? [],
  });
  const [tags, setTags] = useState(l.tags.join(", "));
  if (!snap) return null;
  const save = async () =>
    (await run("lesson.save", {
      id: item?.id,
      lesson: {
        ...l,
        tags: tags
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
      },
    })) && onClose();
  const area = (k: "context" | "finding" | "lesson" | "use") => (
    <Field label={t(`learn.${k}`)}>
      {(id) => (
        <textarea
          id={id}
          className="input"
          rows={2}
          value={l[k]}
          onChange={(e) => setL({ ...l, [k]: e.target.value })}
        />
      )}
    </Field>
  );
  return (
    <Panel
      title={item ? item.title : t("learn.addLesson")}
      onClose={onClose}
      footer={
        <Footer
          onDelete={item ? async () => (await run("lesson.delete", { id: item.id })) && onClose() : undefined}
          onClose={onClose}
          onSave={save}
          canSave={!!l.title.trim()}
          testId="lesson-save"
        />
      }
    >
      <Field label={t("learn.lessonTitle")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={l.title}
            onChange={(e) => setL({ ...l, title: e.target.value })}
            data-testid="lesson-title"
          />
        )}
      </Field>
      <Field label={t("learn.date")}>
        {(id) => (
          <input
            id={id}
            type="date"
            className="input"
            value={l.date}
            onChange={(e) => setL({ ...l, date: e.target.value })}
          />
        )}
      </Field>
      {area("context")}
      {area("finding")}
      {area("lesson")}
      {area("use")}
      {snap.learning_questions.length > 0 && (
        <Field label={t("learn.linkedQuestion")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={l.question_id ?? ""}
              onChange={(e) => setL({ ...l, question_id: e.target.value || null })}
            >
              <option value="" />
              {snap.learning_questions.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.text}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}
      <Field label={t("learn.tags")} hint={t("learn.tagsHint")}>
        {(id) => <input id={id} className="input" value={tags} onChange={(e) => setTags(e.target.value)} />}
      </Field>
    </Panel>
  );
}

function MeetingPanel({ item, onClose }: { item: Meeting | null; onClose: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [m, setM] = useState({
    date: item?.date ?? new Date().toISOString().slice(0, 10),
    title: item?.title ?? "",
    kind: item?.kind ?? "quarterly",
    participants: item?.participants ?? "",
    notes: item?.notes ?? "",
    decisions: item?.decisions ?? ([] as Decision[]),
  });
  const setDecision = (i: number, patch: Partial<Decision>) =>
    setM({ ...m, decisions: m.decisions.map((d, k) => (k === i ? { ...d, ...patch } : d)) });
  const save = async () => (await run("meeting.save", { id: item?.id, meeting: m })) && onClose();
  return (
    <Panel
      wide
      title={item ? item.title : t("learn.addMeeting")}
      onClose={onClose}
      testId="meeting-panel"
      footer={
        <Footer
          onDelete={item ? async () => (await run("meeting.delete", { id: item.id })) && onClose() : undefined}
          onClose={onClose}
          onSave={save}
          canSave={!!m.title.trim() && m.decisions.every((d) => d.text.trim())}
          testId="meeting-save"
        />
      }
    >
      <div className="grid-3">
        <Field label={t("learn.meetingTitle")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={m.title}
              onChange={(e) => setM({ ...m, title: e.target.value })}
              data-testid="meeting-title"
            />
          )}
        </Field>
        <Field label={t("learn.date")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={m.date}
              onChange={(e) => setM({ ...m, date: e.target.value })}
            />
          )}
        </Field>
        <Field label={t("learn.meetingKind")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={m.kind}
              onChange={(e) => setM({ ...m, kind: e.target.value as Meeting["kind"] })}
            >
              {MEETING_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`learn.mk_${k}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <Field label={t("learn.participants")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={m.participants}
            onChange={(e) => setM({ ...m, participants: e.target.value })}
          />
        )}
      </Field>
      <Field label={t("learn.notes")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={6}
            value={m.notes}
            onChange={(e) => setM({ ...m, notes: e.target.value })}
          />
        )}
      </Field>
      <h3>{t("learn.decisions")}</h3>
      {m.decisions.map((d, i) => (
        <div key={d.id ?? i} className="box stack-sm">
          <div className="row-between">
            <input
              className="input"
              value={d.text}
              placeholder={t("learn.decision")}
              onChange={(e) => setDecision(i, { text: e.target.value })}
              data-testid="decision-text"
            />
            <IconButton
              icon="trash"
              label={t("common.delete")}
              onClick={() => setM({ ...m, decisions: m.decisions.filter((_, k) => k !== i) })}
            />
          </div>
          <div className="grid-3">
            <input
              className="input"
              value={d.responsible}
              placeholder={t("recs.responsible")}
              onChange={(e) => setDecision(i, { responsible: e.target.value })}
            />
            <input
              className="input"
              type="date"
              value={d.due}
              aria-label={t("recs.due")}
              onChange={(e) => setDecision(i, { due: e.target.value })}
            />
            <select
              className="input"
              value={d.status}
              aria-label={t("recs.status")}
              onChange={(e) => setDecision(i, { status: e.target.value as Decision["status"] })}
            >
              {ACTION_STATES.map((s) => (
                <option key={s} value={s}>
                  {t(`recs.action_${s}`)}
                </option>
              ))}
            </select>
          </div>
          <label className="check small">
            <input
              type="checkbox"
              checked={d.as_task}
              onChange={(e) => setDecision(i, { as_task: e.target.checked })}
              data-testid="decision-task"
            />{" "}
            {t("learn.asTask")}
          </label>
        </div>
      ))}
      <div>
        <button
          className="btn small"
          onClick={() =>
            setM({
              ...m,
              decisions: [...m.decisions, { text: "", responsible: "", due: "", as_task: true, status: "todo" }],
            })
          }
          data-testid="decision-add"
        >
          <Icon name="plus" /> {t("learn.addDecision")}
        </button>
      </div>
    </Panel>
  );
}
