// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Evaluations (module M10): the evaluation sheet and its steps, evaluation
// questions by criterion with the evaluation matrix, the recommendations made,
// and qualitative notes coded by theme. No automatic analysis of the text.

import { useMemo, useRef, useState } from "react";
import {
  CRITERIA,
  EVAL_KINDS,
  EVAL_STEPS,
  EvalQuestion,
  Evaluation,
  Excerpt,
  NOTE_KINDS,
  QualNote,
  QualTheme,
} from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Confirm, Empty, Field, Icon, IconButton, Panel } from "../ui";
import { RecommendationPanel } from "./Accountability";

export function Evaluations() {
  const { t, day } = useI18n();
  const { snap, run, focus } = useProject();
  const [open, setOpen] = useState<string | null>(
    focus && snap?.evaluations.some((e) => e.id === focus) ? focus : null,
  );
  const [adding, setAdding] = useState(false);
  if (!snap) return null;
  const current = snap.evaluations.find((e) => e.id === open);
  if (current) return <EvaluationView ev={current} onBack={() => setOpen(null)} />;
  return (
    <div className="inner wide stack-lg">
      <div className="row-between">
        <div>
          <h1>{t("ev.title")}</h1>
          <p className="lead">{t("ev.lead")}</p>
        </div>
        <button className="btn primary" onClick={() => setAdding(true)} data-testid="ev-add">
          <Icon name="plus" /> {t("ev.add")}
        </button>
      </div>
      {snap.evaluations.length === 0 ? (
        <Empty icon="scale" title={t("ev.none")} text={t("ev.noneText")} />
      ) : (
        <div className="cards">
          {snap.evaluations.map((e) => {
            const done = EVAL_STEPS.filter((s) => e.steps[s].done).length;
            const recs = snap.recommendations.filter((r) => r.evaluation_id === e.id).length;
            return (
              <button key={e.id} className="card" onClick={() => setOpen(e.id)} data-testid={`ev-${e.title}`}>
                <span className="tag">{t(`ev.kind_${e.kind}`)}</span>
                <strong>{e.title}</strong>
                <span className="muted small">
                  {[day(e.start), day(e.end)].filter(Boolean).join(" - ")}
                  {e.evaluator ? `, ${e.evaluator}` : ""}
                </span>
                <span className="small">
                  {t("ev.stepsDone", { n: done, total: EVAL_STEPS.length })},{" "}
                  {t("ev.questionsN", { n: e.questions.length })}, {t("ev.recsN", { n: recs })}
                </span>
              </button>
            );
          })}
        </div>
      )}
      <QualitativeAll />
      {adding && (
        <SheetPanel
          ev={null}
          onClose={() => setAdding(false)}
          onSaved={(id) => {
            setAdding(false);
            setOpen(id);
          }}
          run={run}
        />
      )}
    </div>
  );
}

/** Notes not tied to an evaluation, and the themes shared by all notes. */
function QualitativeAll() {
  const { t } = useI18n();
  const { snap } = useProject();
  if (!snap) return null;
  return (
    <section className="stack">
      <h2>{t("ev.qualAll")}</h2>
      <Qualitative evaluationId={null} />
      {!snap.qual_notes.some((n) => !n.evaluation_id) && <p className="muted small">{t("ev.qualAllHint")}</p>}
    </section>
  );
}

type Tab = "sheet" | "questions" | "recommendations" | "qualitative";
const TABS: Tab[] = ["sheet", "questions", "recommendations", "qualitative"];

function EvaluationView({ ev, onBack }: { ev: Evaluation; onBack: () => void }) {
  const { t, day, number } = useI18n();
  const { snap, run } = useProject();
  const [tab, setTab] = useState<Tab>("sheet");
  const [editing, setEditing] = useState(false);
  if (!snap) return null;
  const toggleStep = (s: (typeof EVAL_STEPS)[number]) =>
    run("evaluation.save", {
      id: ev.id,
      evaluation: { ...ev, steps: { ...ev.steps, [s]: { ...ev.steps[s], done: !ev.steps[s].done } } },
    });
  return (
    <div className="inner wide stack-lg" data-testid="ev-view">
      <div>
        <button className="link small" onClick={onBack}>
          {t("ev.back")}
        </button>
        <div className="row-between">
          <h1>{ev.title}</h1>
          <button className="btn" onClick={() => setEditing(true)} data-testid="ev-edit">
            <Icon name="edit" /> {t("ev.editSheet")}
          </button>
        </div>
        <p className="lead">
          {t(`ev.kind_${ev.kind}`)}
          {ev.start ? `, ${day(ev.start)} - ${day(ev.end)}` : ""}
          {ev.evaluator ? `, ${ev.evaluator}` : ""}
          {ev.budget ? `, ${number(ev.budget, 0)} ${snap.profile.currency}` : ""}
        </p>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map((k) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            className="tab"
            onClick={() => setTab(k)}
            data-testid={`ev-tab-${k}`}
          >
            {t(`ev.tab_${k}`)}
          </button>
        ))}
      </div>
      {tab === "sheet" && (
        <div className="stack">
          <div className="box stack-sm">
            <h2>{t("ev.steps")}</h2>
            <ol className="steps-list">
              {EVAL_STEPS.map((s) => (
                <li key={s} className={ev.steps[s].done ? "done" : ""}>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={ev.steps[s].done}
                      onChange={() => toggleStep(s)}
                      data-testid={`ev-step-${s}`}
                    />{" "}
                    {t(`ev.step_${s}`)}
                  </label>
                  <span className="muted small">{ev.steps[s].date ? day(ev.steps[s].date) : t("ev.noDate")}</span>
                </li>
              ))}
            </ol>
            <p className="muted small">{t("ev.stepsHint")}</p>
          </div>
          {ev.tor && (
            <div className="box">
              <h2>{t("ev.tor")}</h2>
              <p className="pre-wrap">{ev.tor}</p>
            </div>
          )}
          <div className="box">
            <h2>{t("ev.conclusions")}</h2>
            {ev.conclusions ? (
              <p className="pre-wrap">{ev.conclusions}</p>
            ) : (
              <p className="muted small">{t("ev.noConclusions")}</p>
            )}
          </div>
        </div>
      )}
      {tab === "questions" && <Questions ev={ev} />}
      {tab === "recommendations" && <EvalRecommendations ev={ev} />}
      {tab === "qualitative" && <Qualitative evaluationId={ev.id} questions={ev.questions} />}
      {editing && (
        <SheetPanel
          ev={ev}
          onClose={() => setEditing(false)}
          onSaved={() => setEditing(false)}
          run={run}
          onDeleted={onBack}
        />
      )}
    </div>
  );
}

function SheetPanel({
  ev,
  onClose,
  onSaved,
  onDeleted,
  run,
}: {
  ev: Evaluation | null;
  onClose: () => void;
  onSaved: (id: string) => void;
  onDeleted?: () => void;
  run: ReturnType<typeof useProject>["run"];
}) {
  const { t } = useI18n();
  const blank = Object.fromEntries(EVAL_STEPS.map((s) => [s, { date: "", done: false }])) as Evaluation["steps"];
  const [e, setE] = useState({
    title: ev?.title ?? "",
    kind: ev?.kind ?? "midterm",
    start: ev?.start ?? "",
    end: ev?.end ?? "",
    evaluator: ev?.evaluator ?? "",
    budget: ev?.budget != null ? String(ev.budget) : "",
    tor: ev?.tor ?? "",
    steps: ev?.steps ?? blank,
    questions: ev?.questions ?? [],
    conclusions: ev?.conclusions ?? "",
  });
  const [confirm, setConfirm] = useState(false);
  const save = async () => {
    const s = await run<{ created?: string }>("evaluation.save", { id: ev?.id, evaluation: e });
    if (s) onSaved(ev?.id ?? s.created ?? "");
  };
  return (
    <Panel
      wide
      title={ev ? ev.title : t("ev.add")}
      onClose={onClose}
      testId="ev-panel"
      footer={
        <>
          {ev && (
            <button className="btn" onClick={() => setConfirm(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} disabled={!e.title.trim()} data-testid="ev-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <div className="grid-2">
        <Field label={t("ev.titleField")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={e.title}
              onChange={(x) => setE({ ...e, title: x.target.value })}
              data-testid="ev-title"
            />
          )}
        </Field>
        <Field label={t("ev.kind")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={e.kind}
              onChange={(x) => setE({ ...e, kind: x.target.value as Evaluation["kind"] })}
            >
              {EVAL_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`ev.kind_${k}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <div className="grid-3">
        <Field label={t("ev.start")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={e.start}
              onChange={(x) => setE({ ...e, start: x.target.value })}
            />
          )}
        </Field>
        <Field label={t("ev.end")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={e.end}
              onChange={(x) => setE({ ...e, end: x.target.value })}
            />
          )}
        </Field>
        <Field label={t("ev.budget")}>
          {(id) => (
            <input
              id={id}
              className="input num"
              inputMode="decimal"
              value={e.budget}
              onChange={(x) => setE({ ...e, budget: x.target.value })}
            />
          )}
        </Field>
      </div>
      <Field label={t("ev.evaluator")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={e.evaluator}
            onChange={(x) => setE({ ...e, evaluator: x.target.value })}
          />
        )}
      </Field>
      <h3>{t("ev.steps")}</h3>
      <div className="grid-2">
        {EVAL_STEPS.map((s) => (
          <Field key={s} label={t(`ev.step_${s}`)}>
            {(id) => (
              <input
                id={id}
                type="date"
                className="input"
                value={e.steps[s].date}
                onChange={(x) => setE({ ...e, steps: { ...e.steps, [s]: { ...e.steps[s], date: x.target.value } } })}
                data-testid={`ev-date-${s}`}
              />
            )}
          </Field>
        ))}
      </div>
      <Field label={t("ev.tor")} hint={t("ev.torHint")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={5}
            value={e.tor}
            onChange={(x) => setE({ ...e, tor: x.target.value })}
          />
        )}
      </Field>
      <Field label={t("ev.conclusions")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={5}
            value={e.conclusions}
            onChange={(x) => setE({ ...e, conclusions: x.target.value })}
          />
        )}
      </Field>
      {confirm && ev && (
        <Confirm
          text={t("ev.deleteConfirm")}
          confirmLabel={t("common.delete")}
          onConfirm={async () => {
            if (await run("evaluation.delete", { id: ev.id })) onDeleted?.();
          }}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

// ----- questions and the evaluation matrix --------------------------------------------------------

function Questions({ ev }: { ev: Evaluation }) {
  const { t } = useI18n();
  const { snap } = useProject();
  const [editing, setEditing] = useState<number | "new" | null>(null);
  if (!snap) return null;
  const ind = new Map(snap.indicators.map((i) => [i.id, i.name]));
  const ana = new Map(snap.analyses.map((a) => [a.id, a.title || a.id]));
  return (
    <div className="stack" data-testid="ev-questions">
      <div className="row-between">
        <p className="muted small">{t("ev.matrixLead")}</p>
        <button className="btn primary" onClick={() => setEditing("new")} data-testid="evq-add">
          <Icon name="plus" /> {t("ev.addQuestion")}
        </button>
      </div>
      {ev.questions.length === 0 ? (
        <Empty icon="target" title={t("ev.noQuestions")} text={t("ev.noQuestionsText")} />
      ) : (
        <div className="table-wrap">
          <table className="table matrix">
            <thead>
              <tr>
                <th>{t("ev.criterion")}</th>
                <th>{t("ev.question")}</th>
                <th>{t("ev.indicators")}</th>
                <th>{t("ev.sources")}</th>
                <th>{t("ev.methods")}</th>
                <th>{t("ev.findings")}</th>
              </tr>
            </thead>
            <tbody>
              {CRITERIA.flatMap((c) =>
                ev.questions
                  .map((q, i) => ({ q, i }))
                  .filter(({ q }) => q.criterion === c)
                  .map(({ q, i }) => (
                    <tr key={q.id ?? i} className="clickable" onClick={() => setEditing(i)} data-testid="evq-row">
                      <td className="small">{t(`ev.crit_${c}`)}</td>
                      <td>{q.text}</td>
                      <td className="small">
                        {[...q.indicator_ids.map((x) => ind.get(x)), ...q.analysis_ids.map((x) => ana.get(x))]
                          .filter(Boolean)
                          .join(", ")}
                      </td>
                      <td className="small pre-wrap">{q.sources}</td>
                      <td className="small pre-wrap">{q.methods}</td>
                      <td className="small pre-wrap">{q.findings}</td>
                    </tr>
                  )),
              )}
            </tbody>
          </table>
        </div>
      )}
      {editing !== null && (
        <QuestionPanel ev={ev} index={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

function QuestionPanel({ ev, index, onClose }: { ev: Evaluation; index: number | null; onClose: () => void }) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [q, setQ] = useState<EvalQuestion>(
    index !== null
      ? ev.questions[index]
      : {
          criterion: "effectiveness",
          text: "",
          indicator_ids: [],
          sources: "",
          methods: "",
          analysis_ids: [],
          findings: "",
          conclusion: "",
        },
  );
  if (!snap) return null;
  const write = async (questions: EvalQuestion[]) =>
    (await run("evaluation.save", { id: ev.id, evaluation: { ...ev, questions } })) && onClose();
  const save = () => write(index === null ? [...ev.questions, q] : ev.questions.map((x, k) => (k === index ? q : x)));
  const multi = (field: "indicator_ids" | "analysis_ids", options: { id: string; label: string }[]) => (
    <select
      className="input"
      multiple
      size={Math.min(6, Math.max(2, options.length))}
      value={q[field]}
      onChange={(e) => setQ({ ...q, [field]: Array.from(e.target.selectedOptions).map((o) => o.value) })}
    >
      {options.map((o) => (
        <option key={o.id} value={o.id}>
          {o.label}
        </option>
      ))}
    </select>
  );
  const area = (k: "sources" | "methods" | "findings" | "conclusion", rows = 2) => (
    <Field label={t(`ev.${k}`)}>
      {(id) => (
        <textarea
          id={id}
          className="input"
          rows={rows}
          value={q[k]}
          onChange={(e) => setQ({ ...q, [k]: e.target.value })}
        />
      )}
    </Field>
  );
  return (
    <Panel
      wide
      title={index === null ? t("ev.addQuestion") : t("ev.question")}
      onClose={onClose}
      testId="evq-panel"
      footer={
        <>
          {index !== null && (
            <button className="btn" onClick={() => write(ev.questions.filter((_, k) => k !== index))}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} disabled={!q.text.trim()} data-testid="evq-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <div className="chips">
        {CRITERIA.map((c) => (
          <button
            key={c}
            className="chip small"
            aria-pressed={q.criterion === c}
            onClick={() => setQ({ ...q, criterion: c })}
          >
            {t(`ev.crit_${c}`)}
          </button>
        ))}
      </div>
      <Field label={t("ev.question")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={2}
            value={q.text}
            onChange={(e) => setQ({ ...q, text: e.target.value })}
            data-testid="evq-text"
          />
        )}
      </Field>
      <div className="grid-2">
        <Field label={t("ev.indicators")}>
          {() =>
            multi(
              "indicator_ids",
              snap.indicators.map((i) => ({ id: i.id, label: i.name })),
            )
          }
        </Field>
        <Field label={t("ev.analyses")}>
          {() =>
            multi(
              "analysis_ids",
              snap.analyses.map((a) => ({ id: a.id, label: a.title || a.id })),
            )
          }
        </Field>
      </div>
      {area("sources")}
      {area("methods")}
      {area("findings", 4)}
      {area("conclusion", 3)}
    </Panel>
  );
}

// ----- recommendations of the evaluation ------------------------------------------------------------

function EvalRecommendations({ ev }: { ev: Evaluation }) {
  const { t } = useI18n();
  const { snap } = useProject();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  if (!snap) return null;
  const recs = snap.recommendations.filter((r) => r.evaluation_id === ev.id);
  return (
    <div className="stack" data-testid="ev-recs">
      <div className="row-between">
        <p className="muted small">{t("ev.recsLead")}</p>
        <button className="btn primary" onClick={() => setEditing("new")} data-testid="ev-rec-add">
          <Icon name="plus" /> {t("recs.add")}
        </button>
      </div>
      {recs.length === 0 ? (
        <p className="muted">{t("ev.noRecs")}</p>
      ) : (
        <ul className="plain stack-sm">
          {recs.map((r) => (
            <li key={r.id} className="box">
              <button className="link" onClick={() => setEditing(r.id)}>
                {r.text}
              </button>
              <div className="small muted">
                {t(`recs.resp_${r.response}`)}, {t(`recs.state_${r.status}`)},{" "}
                {r.actions.filter((a) => a.status === "done").length}/{r.actions.length} {t("recs.actionsShort")}
              </div>
            </li>
          ))}
        </ul>
      )}
      {editing && (
        <RecommendationPanel
          item={editing === "new" ? null : (recs.find((r) => r.id === editing) ?? null)}
          evaluationId={ev.id}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

// ----- qualitative notes and coding ---------------------------------------------------------------

function Qualitative({ evaluationId, questions = [] }: { evaluationId: string | null; questions?: EvalQuestion[] }) {
  const { t, day } = useI18n();
  const { snap } = useProject();
  const [note, setNote] = useState<QualNote | "new" | null>(null);
  const [coding, setCoding] = useState<string | null>(null);
  const [themes, setThemes] = useState(false);
  if (!snap) return null;
  const notes = snap.qual_notes.filter((n) => (n.evaluation_id ?? null) === evaluationId);
  const codingNote = snap.qual_notes.find((n) => n.id === coding);
  return (
    <div className="stack" data-testid="ev-qual">
      <div className="row-between">
        <p className="muted small">{t("ev.qualLead")}</p>
        <div className="row-actions">
          <button className="btn" onClick={() => setThemes(true)} data-testid="themes-open">
            {t("ev.themes")} ({snap.qual_themes.length})
          </button>
          <button className="btn primary" onClick={() => setNote("new")} data-testid="note-add">
            <Icon name="plus" /> {t("ev.addNote")}
          </button>
        </div>
      </div>
      {notes.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>{t("ev.noteTitle")}</th>
              <th>{t("ev.noteKind")}</th>
              <th>{t("ev.noteDate")}</th>
              <th>{t("ev.excerpts")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {notes.map((n) => (
              <tr key={n.id}>
                <td>
                  <button className="link" onClick={() => setCoding(n.id)} data-testid={`note-${n.title}`}>
                    {n.title}
                  </button>
                </td>
                <td className="small">{t(`ev.nk_${n.kind}`)}</td>
                <td className="small">{day(n.date)}</td>
                <td className="small">{n.excerpts.length}</td>
                <td className="row-actions">
                  <IconButton icon="edit" label={t("common.edit")} onClick={() => setNote(n)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {notes.length > 0 && <ThemeSummary notes={notes} questions={questions} />}
      {note && (
        <NotePanel item={note === "new" ? null : note} evaluationId={evaluationId} onClose={() => setNote(null)} />
      )}
      {codingNote && <CodingPanel note={codingNote} questions={questions} onClose={() => setCoding(null)} />}
      {themes && <ThemesPanel onClose={() => setThemes(false)} />}
    </div>
  );
}

function ThemeSummary({ notes, questions }: { notes: QualNote[]; questions: EvalQuestion[] }) {
  const { t } = useI18n();
  const { snap } = useProject();
  const [by, setBy] = useState<"theme" | "question">("theme");
  if (!snap) return null;
  const all = notes.flatMap((n) => n.excerpts.map((x) => ({ ...x, note: n.title })));
  if (!all.length) return null;
  const groups =
    by === "theme"
      ? snap.qual_themes.map((th) => ({
          key: th.id,
          title: th.name,
          items: all.filter((x) => x.theme_ids.includes(th.id)),
        }))
      : questions.map((q) => ({
          key: q.id ?? q.text,
          title: q.text,
          items: all.filter((x) => x.question_id === q.id),
        }));
  return (
    <div className="box stack-sm" data-testid="theme-summary">
      <div className="row-between">
        <h2>{t("ev.coded")}</h2>
        {questions.length > 0 && (
          <div className="chips">
            {(["theme", "question"] as const).map((k) => (
              <button key={k} className="chip small" aria-pressed={by === k} onClick={() => setBy(k)}>
                {t(`ev.by_${k}`)}
              </button>
            ))}
          </div>
        )}
      </div>
      {groups
        .filter((g) => g.items.length)
        .map((g) => (
          <details key={g.key}>
            <summary>
              <strong>{g.title}</strong> <span className="muted small">{t("ev.excerptsN", { n: g.items.length })}</span>
            </summary>
            <ul className="plain stack-sm">
              {g.items.map((x, i) => (
                <li key={i} className="quote">
                  {x.text}
                  <div className="muted small">{x.note}</div>
                </li>
              ))}
            </ul>
          </details>
        ))}
    </div>
  );
}

function NotePanel({
  item,
  evaluationId,
  onClose,
}: {
  item: QualNote | null;
  evaluationId: string | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [n, setN] = useState({
    title: item?.title ?? "",
    kind: item?.kind ?? "interview",
    evaluation_id: item?.evaluation_id ?? evaluationId,
    date: item?.date ?? new Date().toISOString().slice(0, 10),
    place: item?.place ?? "",
    participants: item?.participants ?? "",
    text: item?.text ?? "",
    excerpts: item?.excerpts ?? [],
  });
  const [confirm, setConfirm] = useState(false);
  if (!snap) return null;
  // Editing the text moves the excerpts: those that no longer match are dropped.
  const kept = n.excerpts.filter((x) => n.text.slice(x.start, x.end) === x.text);
  const save = async () => (await run("qual_note.save", { id: item?.id, note: { ...n, excerpts: kept } })) && onClose();
  return (
    <Panel
      wide
      title={item ? item.title : t("ev.addNote")}
      onClose={onClose}
      testId="note-panel"
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
          <button className="btn primary" onClick={save} disabled={!n.title.trim()} data-testid="note-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <div className="grid-3">
        <Field label={t("ev.noteTitle")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={n.title}
              onChange={(e) => setN({ ...n, title: e.target.value })}
              data-testid="note-title"
            />
          )}
        </Field>
        <Field label={t("ev.noteKind")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={n.kind}
              onChange={(e) => setN({ ...n, kind: e.target.value as QualNote["kind"] })}
            >
              {NOTE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`ev.nk_${k}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("ev.noteDate")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={n.date}
              onChange={(e) => setN({ ...n, date: e.target.value })}
            />
          )}
        </Field>
      </div>
      <div className="grid-2">
        <Field label={t("ev.notePlace")}>
          {(id) => (
            <input id={id} className="input" value={n.place} onChange={(e) => setN({ ...n, place: e.target.value })} />
          )}
        </Field>
        <Field label={t("ev.participants")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={n.participants}
              onChange={(e) => setN({ ...n, participants: e.target.value })}
            />
          )}
        </Field>
      </div>
      {snap.evaluations.length > 0 && (
        <Field label={t("ev.linkedEvaluation")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={n.evaluation_id ?? ""}
              onChange={(e) => setN({ ...n, evaluation_id: e.target.value || null })}
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
      )}
      <Field label={t("ev.noteText")} hint={t("ev.noteTextHint")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={14}
            value={n.text}
            onChange={(e) => setN({ ...n, text: e.target.value })}
            data-testid="note-text"
          />
        )}
      </Field>
      {kept.length < n.excerpts.length && (
        <p className="small warn-text">{t("ev.excerptsLost", { n: n.excerpts.length - kept.length })}</p>
      )}
      {confirm && item && (
        <Confirm
          text={t("ev.deleteNote")}
          confirmLabel={t("common.delete")}
          onConfirm={async () => (await run("qual_note.delete", { id: item.id })) && onClose()}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

/** Pieces of the text, each with the excerpts covering it, for highlighting. */
function segments(text: string, excerpts: Excerpt[]) {
  const cuts = new Set([0, text.length]);
  for (const x of excerpts) {
    cuts.add(x.start);
    cuts.add(x.end);
  }
  const points = [...cuts].sort((a, b) => a - b);
  const out: { start: number; end: number; covering: number[] }[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [a, b] = [points[i], points[i + 1]];
    out.push({
      start: a,
      end: b,
      covering: excerpts.map((x, k) => (x.start <= a && x.end >= b ? k : -1)).filter((k) => k >= 0),
    });
  }
  return out;
}

function CodingPanel({ note, questions, onClose }: { note: QualNote; questions: EvalQuestion[]; onClose: () => void }) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const textRef = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState<{ start: number; end: number } | null>(null);
  const [themeIds, setThemeIds] = useState<string[]>([]);
  const [question, setQuestion] = useState<string>("");
  const [active, setActive] = useState<number | null>(null);
  const parts = useMemo(() => segments(note.text, note.excerpts), [note]);
  if (!snap) return null;
  const themeName = new Map(snap.qual_themes.map((th) => [th.id, th.name]));
  const readSelection = () => {
    const s = window.getSelection();
    const box = textRef.current;
    if (!s || s.rangeCount === 0 || !box || s.isCollapsed) return setSel(null);
    const r = s.getRangeAt(0);
    if (!box.contains(r.startContainer) || !box.contains(r.endContainer)) return setSel(null);
    const before = document.createRange();
    before.selectNodeContents(box);
    before.setEnd(r.startContainer, r.startOffset);
    const start = before.toString().length;
    const end = start + r.toString().length;
    if (end > start) setSel({ start, end });
  };
  const write = (excerpts: Excerpt[]) => run("qual_note.save", { id: note.id, note: { ...note, excerpts } });
  const code = async () => {
    if (!sel) return;
    await write([
      ...note.excerpts,
      { start: sel.start, end: sel.end, theme_ids: themeIds, question_id: question || null, memo: "" },
    ]);
    setSel(null);
    window.getSelection()?.removeAllRanges();
  };
  return (
    <Panel wide title={note.title} onClose={onClose} testId="coding-panel">
      <p className="muted small">{t("ev.codingLead")}</p>
      <div className="coding">
        <div
          className="coding-text"
          ref={textRef}
          onMouseUp={readSelection}
          onKeyUp={readSelection}
          data-testid="coding-text"
        >
          {parts.map((p, i) =>
            p.covering.length ? (
              <mark
                key={i}
                className={p.covering.includes(active ?? -1) ? "on" : ""}
                onClick={() => setActive(p.covering[p.covering.length - 1])}
                title={p.covering.flatMap((k) => note.excerpts[k].theme_ids.map((id) => themeName.get(id))).join(", ")}
              >
                {note.text.slice(p.start, p.end)}
              </mark>
            ) : (
              <span key={i}>{note.text.slice(p.start, p.end)}</span>
            ),
          )}
        </div>
        <div className="coding-side stack">
          {sel ? (
            <div className="box stack-sm">
              <strong>{t("ev.codeSelection")}</strong>
              <div className="quote small">{note.text.slice(sel.start, sel.end)}</div>
              {snap.qual_themes.length === 0 && <p className="muted small">{t("ev.noThemes")}</p>}
              {snap.qual_themes.map((th) => (
                <label key={th.id} className="check small">
                  <input
                    type="checkbox"
                    checked={themeIds.includes(th.id)}
                    onChange={() =>
                      setThemeIds(themeIds.includes(th.id) ? themeIds.filter((x) => x !== th.id) : [...themeIds, th.id])
                    }
                    data-testid={`code-theme-${th.name}`}
                  />{" "}
                  {th.name}
                </label>
              ))}
              {questions.length > 0 && (
                <select
                  className="input"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  aria-label={t("ev.question")}
                >
                  <option value="">{t("ev.noQuestion")}</option>
                  {questions.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.text}
                    </option>
                  ))}
                </select>
              )}
              <button
                className="btn primary small"
                onClick={code}
                disabled={!themeIds.length && !question}
                data-testid="code-save"
              >
                {t("ev.code")}
              </button>
            </div>
          ) : (
            <p className="muted small">{t("ev.selectHint")}</p>
          )}
          {active !== null && note.excerpts[active] && (
            <div className="box stack-sm">
              <div className="quote small">{note.excerpts[active].text}</div>
              <div className="small">
                {note.excerpts[active].theme_ids.map((id) => themeName.get(id)).join(", ") || t("ev.noTheme")}
              </div>
              <button
                className="btn small"
                onClick={async () => {
                  await write(note.excerpts.filter((_, k) => k !== active));
                  setActive(null);
                }}
              >
                {t("ev.uncode")}
              </button>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function ThemesPanel({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<QualTheme | null>(null);
  if (!snap) return null;
  const count = (id: string) =>
    snap.qual_notes.reduce((n, x) => n + x.excerpts.filter((e) => e.theme_ids.includes(id)).length, 0);
  const add = async () => {
    if (await run("qual_theme.save", { theme: { name, description: "" } })) setName("");
  };
  return (
    <Panel title={t("ev.themes")} onClose={onClose} testId="themes-panel">
      <p className="muted small">{t("ev.themesLead")}</p>
      <div className="row-actions start">
        <input
          className="input"
          value={name}
          placeholder={t("ev.themeName")}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && name.trim() && void add()}
          data-testid="theme-name"
        />
        <button className="btn" onClick={add} disabled={!name.trim()} data-testid="theme-add">
          {t("ev.addTheme")}
        </button>
      </div>
      <ul className="plain stack-sm">
        {snap.qual_themes.map((th) =>
          editing?.id === th.id ? (
            <li key={th.id} className="row-actions start">
              <input
                className="input"
                value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              />
              <button
                className="btn small"
                onClick={async () => (await run("qual_theme.save", { id: th.id, theme: editing })) && setEditing(null)}
              >
                {t("common.save")}
              </button>
            </li>
          ) : (
            <li key={th.id} className="row-between">
              <span>
                {th.name} <span className="muted small">{t("ev.excerptsN", { n: count(th.id) })}</span>
              </span>
              <span className="row-actions">
                <IconButton icon="edit" label={t("common.edit")} onClick={() => setEditing(th)} />
                <IconButton
                  icon="trash"
                  label={t("common.delete")}
                  onClick={() => run("qual_theme.delete", { id: th.id })}
                />
              </span>
            </li>
          ),
        )}
      </ul>
    </Panel>
  );
}
