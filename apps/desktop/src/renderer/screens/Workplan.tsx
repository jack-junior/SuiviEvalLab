// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Activities and budget (module M9): the work plan as a list and as a timeline,
// and a simple follow-up of the budget, with time, physical and financial progress
// side by side.

import { useMemo, useState } from "react";
import { Activity, ACTIVITY_STATES, BudgetLine, call, Expense, ExpenseImport, ME_KINDS, pick, Snapshot } from "../api";
import { useI18n } from "../i18n";
import { Attachments } from "../Attachments";
import { periodLabel } from "../monitoring";
import { useProject } from "../state";
import { Confirm, Empty, Field, Icon, IconButton, Notice, Panel, Progress } from "../ui";

type Tab = "plan" | "timeline" | "budget";
const TABS: Tab[] = ["plan", "timeline", "budget"];

export function Workplan() {
  const { t, percent } = useI18n();
  const { snap } = useProject();
  const [tab, setTab] = useState<Tab>("plan");
  if (!snap) return null;
  const w = snap.workplan;
  const pc = (x: number | null) => (x === null ? "" : percent(x, 0));
  return (
    <div className="inner wide stack-lg">
      <div>
        <h1>{t("wp.title")}</h1>
        <p className="lead">{t("wp.lead")}</p>
      </div>
      <div className="kpis" data-testid="wp-kpis">
        <div className="kpi">
          <span className="kpi-label">{t("wp.time")}</span>
          <span className="kpi-value">{pc(w.time) || "-"}</span>
          <span className="kpi-sub">{t("wp.timeSub")}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("wp.physical")}</span>
          <span className="kpi-value" data-testid="wp-physical">
            {pc(w.physical) || "-"}
          </span>
          <span className="kpi-sub">{w.expected !== null ? t("wp.expectedSub", { x: pc(w.expected) }) : ""}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("wp.financial")}</span>
          <span className="kpi-value" data-testid="wp-financial">
            {pc(w.budget.financial) || "-"}
          </span>
          <span className="kpi-sub">
            {w.financial_ahead !== null && w.financial_ahead > 0.1
              ? t("wp.spendingAhead", { x: pc(w.financial_ahead) })
              : ""}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">{t("wp.lateActivities")}</span>
          <span className="kpi-value">{w.late}</span>
          <span className="kpi-sub">{t("wp.ofActivities", { n: w.activities })}</span>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map((k) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            className="tab"
            onClick={() => setTab(k)}
            data-testid={`wp-tab-${k}`}
          >
            {t(`wp.tab_${k}`)}
          </button>
        ))}
      </div>
      {tab === "plan" && <PlanList />}
      {tab === "timeline" && <Timeline />}
      {tab === "budget" && <Budget />}
    </div>
  );
}

// ----- the work plan as a list ---------------------------------------------------------------

type Family = "all" | "project" | "me";

/** Activities in plan order: grouped by result, each parent followed by its sub-activities. */
function useOrdered(family: Family) {
  const { snap } = useProject();
  return useMemo(() => {
    if (!snap) return [];
    const acts = snap.activities.filter((a) => family === "all" || a.family === family);
    const kids = new Map<string, Activity[]>();
    for (const a of acts) if (a.parent_id) kids.set(a.parent_id, [...(kids.get(a.parent_id) ?? []), a]);
    const tops = acts.filter((a) => !a.parent_id || !acts.some((p) => p.id === a.parent_id));
    const nodes = [...snap.framework.map((n) => n.id), null];
    const groups: { node: string | null; rows: { a: Activity; depth: number }[] }[] = [];
    for (const n of nodes) {
      const mine = tops.filter(
        (a) => (a.node_id ?? null) === n || (n === null && !snap.framework.some((f) => f.id === a.node_id)),
      );
      if (!mine.length) continue;
      const rows: { a: Activity; depth: number }[] = [];
      for (const a of mine) {
        rows.push({ a, depth: 0 });
        for (const k of kids.get(a.id) ?? []) rows.push({ a: k, depth: 1 });
      }
      groups.push({ node: n, rows });
    }
    return groups;
  }, [snap, family]);
}

function PlanList() {
  const { t, day, lang } = useI18n();
  const { snap, run } = useProject();
  const [family, setFamily] = useState<Family>("all");
  const [editing, setEditing] = useState<Activity | "new" | { parent: Activity } | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const groups = useOrdered(family);
  if (!snap) return null;
  const nodeName = (id: string | null) => {
    const n = snap.framework.find((x) => x.id === id);
    return n ? `${n.code ? n.code + " " : ""}${n.title}` : t("wp.noResult");
  };
  const generate = async () => {
    const r = await run<Snapshot & { added: number }>("activity.generate_me", { lang });
    if (r) setNote(t("wp.generated", { n: r.added }));
  };
  return (
    <div className="stack" data-testid="wp-plan">
      <div className="row-between">
        <div className="chips">
          {(["all", "project", "me"] as Family[]).map((f) => (
            <button key={f} className="chip" aria-pressed={family === f} onClick={() => setFamily(f)}>
              {t(`wp.family_${f}`)}
            </button>
          ))}
        </div>
        <div className="row-actions">
          <button className="btn" onClick={generate} data-testid="wp-generate">
            {t("wp.generateMe")}
          </button>
          <button className="btn primary" onClick={() => setEditing("new")} data-testid="wp-add">
            <Icon name="plus" /> {t("wp.add")}
          </button>
        </div>
      </div>
      {note && <Notice kind="ok">{note}</Notice>}
      {groups.length === 0 ? (
        <Empty icon="plan" title={t("wp.none")} text={t("wp.noneText")} />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("wp.activity")}</th>
                <th>{t("wp.dates")}</th>
                <th>{t("wp.responsible")}</th>
                <th>{t("wp.status")}</th>
                <th>{t("wp.progress")}</th>
                <th />
              </tr>
            </thead>
            {groups.map((g) => (
              <tbody key={g.node ?? "none"}>
                <tr className="group-row">
                  <td colSpan={6}>{nodeName(g.node)}</td>
                </tr>
                {g.rows.map(({ a, depth }) => (
                  <tr key={a.id} className="clickable" onClick={() => setEditing(a)} data-testid={`act-${a.title}`}>
                    <td style={{ paddingLeft: 12 + depth * 22 }}>
                      {a.code && <span className="muted">{a.code} </span>}
                      {a.title} {a.family === "me" && <span className="tag">{t("wp.meTag")}</span>}{" "}
                      {a.milestone && <span className="tag">{t("wp.milestoneTag")}</span>}{" "}
                      {a.late && <span className="tag warn">{t(`wp.${a.late}`)}</span>}
                    </td>
                    <td className="small">
                      {day(a.start)}
                      {a.end && a.end !== a.start ? ` - ${day(a.end)}` : ""}
                    </td>
                    <td className="small">{a.responsible}</td>
                    <td>
                      <span className={`status-chip act-${a.status}`}>{t(`wp.state_${a.status}`)}</span>
                    </td>
                    <td>
                      <Progress value={a.progress / 100} />
                    </td>
                    <td className="row-actions" onClick={(e) => e.stopPropagation()}>
                      {!a.parent_id && (
                        <IconButton icon="plus" label={t("wp.addSub")} onClick={() => setEditing({ parent: a })} />
                      )}
                      <IconButton
                        icon="up"
                        label={t("common.moveUp")}
                        onClick={() => run("activity.move", { id: a.id, direction: -1 })}
                      />
                      <IconButton
                        icon="down"
                        label={t("common.moveDown")}
                        onClick={() => run("activity.move", { id: a.id, direction: 1 })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
      )}
      {editing && (
        <ActivityPanel
          activity={editing === "new" || "parent" in editing ? null : editing}
          parent={editing !== "new" && "parent" in editing ? editing.parent : null}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

const EMPTY_ACTIVITY: Omit<Activity, "id" | "expected" | "late"> = {
  title: "",
  code: "",
  family: "project",
  me_kind: "",
  node_id: null,
  parent_id: null,
  start: "",
  end: "",
  actual_start: "",
  actual_end: "",
  status: "not_started",
  progress: 0,
  responsible: "",
  place_ids: [],
  partner_id: null,
  milestone: false,
  comment: "",
  origin: "",
};

function ActivityPanel({
  activity,
  parent,
  onClose,
}: {
  activity: Activity | null;
  parent: Activity | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [a, setA] = useState(
    activity ?? {
      ...EMPTY_ACTIVITY,
      parent_id: parent?.id ?? null,
      node_id: parent?.node_id ?? null,
      family: parent?.family ?? "project",
    },
  );
  const [confirm, setConfirm] = useState(false);
  if (!snap) return null;
  const set = (patch: Partial<Activity>) => setA({ ...a, ...patch });
  const hasKids = !!activity && snap.activities.some((x) => x.parent_id === activity.id);
  const save = async () => {
    const s = await run("activity.save", { id: activity?.id, activity: a });
    if (s) onClose();
  };
  const remove = async () => {
    const s = await run("activity.delete", { id: activity!.id });
    if (s) onClose();
  };
  const parents = snap.activities.filter((x) => !x.parent_id && x.id !== activity?.id);
  return (
    <Panel
      title={activity ? activity.title : parent ? t("wp.addSub") : t("wp.add")}
      onClose={onClose}
      testId="activity-panel"
      footer={
        <>
          {activity && (
            <button className="btn" onClick={() => setConfirm(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} disabled={!a.title.trim()} data-testid="activity-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <div className="chips">
        {(["project", "me"] as const).map((f) => (
          <button key={f} className="chip" aria-pressed={a.family === f} onClick={() => set({ family: f })}>
            {t(`wp.family_${f}`)}
          </button>
        ))}
      </div>
      <Field label={t("wp.activityTitle")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={a.title}
            onChange={(e) => set({ title: e.target.value })}
            data-testid="activity-title"
          />
        )}
      </Field>
      <div className="grid-2">
        <Field label={t("wp.code")}>
          {(id) => <input id={id} className="input" value={a.code} onChange={(e) => set({ code: e.target.value })} />}
        </Field>
        {a.family === "me" && (
          <Field label={t("wp.meKind")}>
            {(id) => (
              <select id={id} className="input" value={a.me_kind} onChange={(e) => set({ me_kind: e.target.value })}>
                <option value="" />
                {ME_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {t(`wp.me_${k}`)}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
      </div>
      {!hasKids && (
        <Field label={t("wp.parent")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={a.parent_id ?? ""}
              onChange={(e) => set({ parent_id: e.target.value || null })}
            >
              <option value="">{t("wp.noParent")}</option>
              {parents.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}
      <Field label={t("wp.result")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={a.node_id ?? ""}
            onChange={(e) => set({ node_id: e.target.value || null })}
          >
            <option value="">{t("wp.noResult")}</option>
            {snap.framework.map((n) => (
              <option key={n.id} value={n.id}>
                {" ".repeat(n.depth * 3)}
                {n.code} {n.title}
              </option>
            ))}
          </select>
        )}
      </Field>
      <div className="grid-2">
        <Field label={t("wp.start")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={a.start}
              onChange={(e) => set({ start: e.target.value })}
              data-testid="activity-start"
            />
          )}
        </Field>
        <Field label={t("wp.end")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={a.end}
              onChange={(e) => set({ end: e.target.value })}
              data-testid="activity-end"
            />
          )}
        </Field>
      </div>
      <label className="check">
        <input type="checkbox" checked={a.milestone} onChange={(e) => set({ milestone: e.target.checked })} />{" "}
        {t("wp.milestone")}
      </label>
      <div className="grid-2">
        <Field label={t("wp.responsible")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={a.responsible}
              onChange={(e) => set({ responsible: e.target.value })}
            />
          )}
        </Field>
        <Field label={t("wp.partner")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={a.partner_id ?? ""}
              onChange={(e) => set({ partner_id: e.target.value || null })}
            >
              <option value="" />
              {snap.partners.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.acronym || p.name}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      {snap.places.length > 0 && (
        <Field label={t("wp.places")}>
          {(id) => (
            <select
              id={id}
              className="input"
              multiple
              size={Math.min(6, snap.places.length)}
              value={a.place_ids}
              onChange={(e) => set({ place_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}
            >
              {snap.places.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}
      <h3>{t("wp.followUp")}</h3>
      {hasKids ? (
        <p className="muted small">{t("wp.parentFollows")}</p>
      ) : (
        <>
          <div className="chips">
            {ACTIVITY_STATES.map((s) => (
              <button
                key={s}
                className="chip small"
                aria-pressed={a.status === s}
                onClick={() => set({ status: s, progress: s === "done" ? 100 : a.progress })}
                data-testid={`activity-state-${s}`}
              >
                {t(`wp.state_${s}`)}
              </button>
            ))}
          </div>
          <Field label={t("wp.progressField", { x: a.progress })}>
            {(id) => (
              <input
                id={id}
                type="range"
                min={0}
                max={100}
                step={5}
                value={a.progress}
                onChange={(e) => set({ progress: Number(e.target.value) })}
                data-testid="activity-progress"
              />
            )}
          </Field>
          <div className="grid-2">
            <Field label={t("wp.actualStart")}>
              {(id) => (
                <input
                  id={id}
                  type="date"
                  className="input"
                  value={a.actual_start}
                  onChange={(e) => set({ actual_start: e.target.value })}
                />
              )}
            </Field>
            <Field label={t("wp.actualEnd")}>
              {(id) => (
                <input
                  id={id}
                  type="date"
                  className="input"
                  value={a.actual_end}
                  onChange={(e) => set({ actual_end: e.target.value })}
                />
              )}
            </Field>
          </div>
        </>
      )}
      <Field label={t("wp.comment")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={3}
            value={a.comment}
            onChange={(e) => set({ comment: e.target.value })}
          />
        )}
      </Field>
      <Attachments kind="activity" id={activity?.id} />
      {confirm && (
        <Confirm
          text={hasKids ? t("wp.deleteWithSubs") : t("wp.deleteOne")}
          confirmLabel={t("common.delete")}
          onConfirm={remove}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

// ----- timeline (Gantt chart) --------------------------------------------------------------------

function Timeline() {
  const { t, lang, day } = useI18n();
  const { snap } = useProject();
  const [family, setFamily] = useState<Family>("all");
  const [editing, setEditing] = useState<Activity | null>(null);
  const groups = useOrdered(family);
  if (!snap) return null;
  const rows = groups.flatMap((g) => g.rows).filter(({ a }) => a.start && a.end);
  if (!rows.length) return <Empty icon="calendar" title={t("wp.noDates")} text={t("wp.noDatesText")} />;
  const first = [snap.profile.start, ...rows.map((r) => r.a.start)].filter(Boolean).sort()[0];
  const last = [snap.profile.end, ...rows.map((r) => r.a.end)].filter(Boolean).sort().slice(-1)[0];
  const from = new Date(`${first.slice(0, 7)}-01T00:00:00`);
  const until = new Date(`${last}T00:00:00`);
  const months: Date[] = [];
  for (let d = new Date(from); d <= until; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) months.push(d);
  const end = new Date(months[months.length - 1].getFullYear(), months[months.length - 1].getMonth() + 1, 1);
  const span = end.getTime() - from.getTime();
  const x = (iso: string, endOfDay = false) =>
    ((new Date(`${iso}T00:00:00`).getTime() + (endOfDay ? 86_400_000 : 0) - from.getTime()) / span) * 100;
  const today = new Date().toISOString().slice(0, 10);
  const fmt = new Intl.DateTimeFormat(lang === "en" ? "en-GB" : "fr-FR", { month: "short" });
  return (
    <div className="stack" data-testid="wp-timeline">
      <div className="chips">
        {(["all", "project", "me"] as Family[]).map((f) => (
          <button key={f} className="chip" aria-pressed={family === f} onClick={() => setFamily(f)}>
            {t(`wp.family_${f}`)}
          </button>
        ))}
      </div>
      <div className="gantt" style={{ ["--months" as string]: months.length }}>
        <div className="gantt-row gantt-head">
          <div className="gantt-label" />
          <div className="gantt-track">
            {months.map((m, i) => (
              <span key={i} className="gantt-month" style={{ left: `${x(m.toISOString().slice(0, 10))}%` }}>
                {fmt.format(m)}
                {m.getMonth() === 0 || i === 0 ? ` ${String(m.getFullYear()).slice(2)}` : ""}
              </span>
            ))}
          </div>
        </div>
        {rows.map(({ a, depth }) => (
          <div key={a.id} className="gantt-row">
            <button className="gantt-label link" style={{ paddingLeft: depth * 16 }} onClick={() => setEditing(a)}>
              {a.title}
            </button>
            <div className="gantt-track">
              {today >= first && today <= last && <span className="gantt-today" style={{ left: `${x(today)}%` }} />}
              {a.milestone ? (
                <span
                  className={`gantt-milestone act-${a.status}`}
                  style={{ left: `${x(a.end)}%` }}
                  title={`${a.title}, ${day(a.end)}`}
                />
              ) : (
                <span
                  className={`gantt-bar act-${a.status}${a.late ? " late" : ""}`}
                  style={{ left: `${x(a.start)}%`, width: `${Math.max(0.5, x(a.end, true) - x(a.start))}%` }}
                  title={`${a.title}, ${day(a.start)} - ${day(a.end)}, ${a.progress} %`}
                >
                  <span className="gantt-fill" style={{ width: `${a.progress}%` }} />
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      {editing && <ActivityPanel activity={editing} parent={null} onClose={() => setEditing(null)} />}
    </div>
  );
}

// ----- budget --------------------------------------------------------------------------------------

function Budget() {
  const { t, number, percent, day, lang } = useI18n();
  const { snap, run } = useProject();
  const [line, setLine] = useState<BudgetLine | "new" | null>(null);
  const [expense, setExpense] = useState<Expense | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  if (!snap) return null;
  const b = snap.workplan.budget;
  const cur = snap.workplan.currency;
  const money = (x: number) => `${number(x, 0)}${cur ? ` ${cur}` : ""}`;
  const rate = (x: number | null) => (x === null ? "" : percent(x, 0));
  const lineName = new Map(snap.budget_lines.map((l) => [l.id, l.code ? `${l.code} ${l.name}` : l.name]));
  const actName = new Map(snap.activities.map((a) => [a.id, a.title]));
  const recent = [...snap.expenses].sort((x, y) => y.date.localeCompare(x.date)).slice(0, 50);
  return (
    <div className="stack-lg" data-testid="wp-budget">
      <div className="row-between">
        <p className="muted small">{t("wp.budgetLead")}</p>
        <div className="row-actions">
          <button
            className="btn"
            onClick={() => setImporting(true)}
            disabled={!snap.budget_lines.length}
            data-testid="expense-import"
          >
            {t("wp.importExpenses")}
          </button>
          <button
            className="btn"
            onClick={() => setExpense("new")}
            disabled={!snap.budget_lines.length}
            data-testid="expense-add"
          >
            {t("wp.addExpense")}
          </button>
          <button
            className="btn primary"
            onClick={() => setLine("new")}
            disabled={!snap.periods.length}
            data-testid="line-add"
          >
            <Icon name="plus" /> {t("wp.addLine")}
          </button>
        </div>
      </div>
      {!snap.periods.length && <Notice>{t("wp.needCalendar")}</Notice>}
      {snap.budget_lines.length === 0 ? (
        <Empty icon="calc" title={t("wp.noLines")} text={t("wp.noLinesText")} />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("wp.line")}</th>
                <th>{t("wp.linkedActivity")}</th>
                <th className="num">{t("wp.planned")}</th>
                <th className="num">{t("wp.plannedToDate")}</th>
                <th className="num">{t("wp.spent")}</th>
                <th className="num">{t("wp.rate")}</th>
                <th className="num">{t("wp.rateToDate")}</th>
              </tr>
            </thead>
            <tbody>
              {snap.budget_lines.map((l) => {
                const r = b.lines.find((x) => x.line_id === l.id)!;
                return (
                  <tr key={l.id} className="clickable" onClick={() => setLine(l)} data-testid={`line-${l.name}`}>
                    <td>{lineName.get(l.id)}</td>
                    <td className="small">{l.activity_id ? actName.get(l.activity_id) : ""}</td>
                    <td className="num">{money(r.planned)}</td>
                    <td className="num">{money(r.planned_to_date)}</td>
                    <td className="num">{money(r.spent)}</td>
                    <td className="num">{rate(r.rate)}</td>
                    <td className={`num${r.rate_to_date !== null && r.rate_to_date > 1 ? " warn-text" : ""}`}>
                      {rate(r.rate_to_date)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <th colSpan={2}>{t("wp.total")}</th>
                <th className="num">{money(b.planned)}</th>
                <th className="num">{money(b.planned_to_date)}</th>
                <th className="num" data-testid="budget-spent">
                  {money(b.spent)}
                </th>
                <th className="num">{rate(b.financial)}</th>
                <th className="num">{rate(b.planned_to_date ? b.spent / b.planned_to_date : null)}</th>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      {b.by_period.length > 0 && (
        <div className="box">
          <h2>{t("wp.byPeriod")}</h2>
          <table className="table compact">
            <thead>
              <tr>
                <th>{t("wp.period")}</th>
                <th className="num">{t("wp.planned")}</th>
                <th className="num">{t("wp.spent")}</th>
              </tr>
            </thead>
            <tbody>
              {b.by_period.map((r) => {
                const p = snap.periods.find((x) => x.code === r.period);
                return (
                  <tr key={r.period}>
                    <td>{p ? periodLabel(p, lang) : r.period}</td>
                    <td className="num">{money(r.planned)}</td>
                    <td className="num">{money(r.spent)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {recent.length > 0 && (
        <div className="box">
          <h2>{t("wp.expenses")}</h2>
          <table className="table compact">
            <thead>
              <tr>
                <th>{t("wp.date")}</th>
                <th>{t("wp.line")}</th>
                <th>{t("wp.label")}</th>
                <th>{t("wp.ref")}</th>
                <th className="num">{t("wp.amount")}</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((e) => (
                <tr key={e.id} className="clickable" onClick={() => setExpense(e)}>
                  <td>{day(e.date)}</td>
                  <td>{lineName.get(e.line_id)}</td>
                  <td>{e.label}</td>
                  <td>{e.ref}</td>
                  <td className="num">{money(e.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {snap.expenses.length > recent.length && (
            <p className="muted small">{t("wp.moreExpenses", { n: snap.expenses.length - recent.length })}</p>
          )}
        </div>
      )}
      {line && <LinePanel line={line === "new" ? null : line} onClose={() => setLine(null)} />}
      {expense && (
        <ExpensePanel expense={expense === "new" ? null : expense} onClose={() => setExpense(null)} run={run} />
      )}
      {importing && <ExpenseImportPanel onClose={() => setImporting(false)} />}
    </div>
  );
}

function LinePanel({ line, onClose }: { line: BudgetLine | null; onClose: () => void }) {
  const { t, lang } = useI18n();
  const { snap, run } = useProject();
  const [l, setL] = useState<Omit<BudgetLine, "id">>(
    line ?? { code: "", name: "", activity_id: null, planned: {}, note: "" },
  );
  const [amounts, setAmounts] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(line?.planned ?? {}).map(([k, v]) => [k, String(v)])),
  );
  const [spread, setSpread] = useState("");
  const [confirm, setConfirm] = useState(false);
  if (!snap) return null;
  const save = async () => {
    const planned = Object.fromEntries(Object.entries(amounts).filter(([, v]) => v.trim()));
    const s = await run("budget_line.save", { id: line?.id, line: { ...l, planned } });
    if (s) onClose();
  };
  const spreadEvenly = () => {
    const total = Number(spread.replace(/\s/g, "").replace(",", "."));
    if (!total || !snap.periods.length) return;
    const each = Math.round((total / snap.periods.length) * 100) / 100;
    setAmounts(Object.fromEntries(snap.periods.map((p) => [p.code, String(each)])));
  };
  return (
    <Panel
      wide
      title={line ? line.name : t("wp.addLine")}
      onClose={onClose}
      testId="line-panel"
      footer={
        <>
          {line && (
            <button className="btn" onClick={() => setConfirm(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} disabled={!l.name.trim()} data-testid="line-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <div className="grid-2">
        <Field label={t("wp.lineCode")}>
          {(id) => (
            <input id={id} className="input" value={l.code} onChange={(e) => setL({ ...l, code: e.target.value })} />
          )}
        </Field>
        <Field label={t("wp.lineName")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={l.name}
              onChange={(e) => setL({ ...l, name: e.target.value })}
              data-testid="line-name"
            />
          )}
        </Field>
      </div>
      <Field label={t("wp.linkedActivity")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={l.activity_id ?? ""}
            onChange={(e) => setL({ ...l, activity_id: e.target.value || null })}
          >
            <option value="" />
            {snap.activities.map((a) => (
              <option key={a.id} value={a.id}>
                {a.parent_id ? "   " : ""}
                {a.title}
              </option>
            ))}
          </select>
        )}
      </Field>
      <div className="row-actions start">
        <input
          className="input"
          style={{ maxWidth: 180 }}
          placeholder={t("wp.totalToSpread")}
          value={spread}
          onChange={(e) => setSpread(e.target.value)}
        />
        <button className="btn small" onClick={spreadEvenly} disabled={!spread.trim()}>
          {t("wp.spread")}
        </button>
      </div>
      <div className="period-grid">
        {snap.periods.map((p) => (
          <Field key={p.id} label={periodLabel(p, lang)}>
            {(id) => (
              <input
                id={id}
                className="input num"
                inputMode="decimal"
                value={amounts[p.code] ?? ""}
                onChange={(e) => setAmounts({ ...amounts, [p.code]: e.target.value })}
                data-testid={`line-amount-${p.code}`}
              />
            )}
          </Field>
        ))}
      </div>
      <Field label={t("wp.note")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={2}
            value={l.note}
            onChange={(e) => setL({ ...l, note: e.target.value })}
          />
        )}
      </Field>
      {confirm && (
        <Confirm
          text={t("wp.deleteLine")}
          confirmLabel={t("common.delete")}
          onConfirm={async () => (await run("budget_line.delete", { id: line!.id })) && onClose()}
          onCancel={() => setConfirm(false)}
        />
      )}
    </Panel>
  );
}

function ExpensePanel({
  expense,
  onClose,
  run,
}: {
  expense: Expense | null;
  onClose: () => void;
  run: ReturnType<typeof useProject>["run"];
}) {
  const { t } = useI18n();
  const { snap } = useProject();
  const [e, setE] = useState({
    line_id: expense?.line_id ?? snap?.budget_lines[0]?.id ?? "",
    date: expense?.date ?? new Date().toISOString().slice(0, 10),
    amount: expense ? String(expense.amount) : "",
    label: expense?.label ?? "",
    ref: expense?.ref ?? "",
  });
  if (!snap) return null;
  const save = async () => {
    const s = await run("expense.save", { id: expense?.id, expense: e });
    if (s) onClose();
  };
  return (
    <Panel
      title={expense ? t("wp.expense") : t("wp.addExpense")}
      onClose={onClose}
      testId="expense-panel"
      footer={
        <>
          {expense && (
            <button
              className="btn"
              onClick={async () => (await run("expense.delete", { id: expense.id })) && onClose()}
            >
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
            disabled={!e.amount.trim() || !e.line_id}
            data-testid="expense-save"
          >
            {t("common.save")}
          </button>
        </>
      }
    >
      <Field label={t("wp.line")}>
        {(id) => (
          <select id={id} className="input" value={e.line_id} onChange={(x) => setE({ ...e, line_id: x.target.value })}>
            {snap.budget_lines.map((l) => (
              <option key={l.id} value={l.id}>
                {l.code ? `${l.code} ` : ""}
                {l.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <div className="grid-2">
        <Field label={t("wp.date")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={e.date}
              onChange={(x) => setE({ ...e, date: x.target.value })}
            />
          )}
        </Field>
        <Field label={t("wp.amount")}>
          {(id) => (
            <input
              id={id}
              className="input num"
              inputMode="decimal"
              value={e.amount}
              onChange={(x) => setE({ ...e, amount: x.target.value })}
              data-testid="expense-amount"
            />
          )}
        </Field>
      </div>
      <Field label={t("wp.label")}>
        {(id) => (
          <input id={id} className="input" value={e.label} onChange={(x) => setE({ ...e, label: x.target.value })} />
        )}
      </Field>
      <Field label={t("wp.ref")}>
        {(id) => (
          <input id={id} className="input" value={e.ref} onChange={(x) => setE({ ...e, ref: x.target.value })} />
        )}
      </Field>
    </Panel>
  );
}

const IMPORT_FIELDS = ["date", "amount", "line", "label", "ref"] as const;

function ExpenseImportPanel({ onClose }: { onClose: () => void }) {
  const { t, number } = useI18n();
  const { setSnap, describe } = useProject();
  const [file, setFile] = useState<{ token: string; name: string } | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [map, setMap] = useState<Record<string, string>>({});
  const [check, setCheck] = useState<ExpenseImport | null>(null);
  const [done, setDone] = useState<ExpenseImport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const choose = async () => {
    const f = await pick("data-open");
    if (!f) return;
    setError(null);
    try {
      const r = await call<{ columns: string[] }>("expense.inspect", { file_token: f.token });
      setFile(f);
      setColumns(r.columns);
      const guess = (words: string[]) => r.columns.find((c) => words.some((w) => c.toLowerCase().includes(w))) ?? "";
      setMap({
        date: guess(["date"]),
        amount: guess(["montant", "amount", "débit", "debit"]),
        line: guess(["ligne", "line", "compte", "account", "code"]),
        label: guess(["libell", "label", "descr"]),
        ref: guess(["pièce", "piece", "ref", "voucher"]),
      });
      setCheck(null);
    } catch (e) {
      setError(describe(e));
    }
  };
  const preview = async (commit: boolean) => {
    if (!file) return;
    setError(null);
    try {
      const r = await call<Snapshot & { import: ExpenseImport }>("expense.import", {
        file_token: file.token,
        columns: map,
        commit,
      });
      if (commit) {
        setSnap(r);
        setDone(r.import);
      } else setCheck(r.import);
    } catch (e) {
      setError(describe(e));
    }
  };
  return (
    <Panel
      wide
      title={t("wp.importExpenses")}
      onClose={onClose}
      testId="expense-import-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.close")}
          </button>
          {file && !done && (
            <>
              <button className="btn" onClick={() => preview(false)} disabled={!map.date || !map.amount || !map.line}>
                {t("wp.check")}
              </button>
              <button
                className="btn primary"
                onClick={() => preview(true)}
                disabled={!check || !check.read}
                data-testid="expense-import-run"
              >
                {t("wp.importN", { n: check?.read ?? 0 })}
              </button>
            </>
          )}
        </>
      }
    >
      {error && <Notice kind="error">{error}</Notice>}
      <p className="muted small">{t("wp.importLead")}</p>
      <div>
        <button className="btn" onClick={choose} data-testid="expense-file">
          <Icon name="open" /> {file ? file.name : t("wp.chooseFile")}
        </button>
      </div>
      {file && !done && (
        <div className="grid-2">
          {IMPORT_FIELDS.map((k) => (
            <Field key={k} label={t(`wp.col_${k}`)}>
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={map[k] ?? ""}
                  onChange={(e) => setMap({ ...map, [k]: e.target.value })}
                >
                  <option value="" />
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          ))}
        </div>
      )}
      {check && !done && (
        <Notice kind={check.read ? "info" : "error"}>
          {t("wp.checkResult", { n: check.read, total: number(check.total, 0), rows: check.rows })}
          {check.duplicates > 0 && ` ${t("wp.checkDuplicates", { n: check.duplicates })}`}
          {check.bad > 0 && ` ${t("wp.checkBad", { n: check.bad })}`}
          {check.unknown_lines.length > 0 &&
            ` ${t("wp.checkUnknown", { lines: check.unknown_lines.map((u) => u.line || "?").join(", ") })}`}
        </Notice>
      )}
      {done && <Notice kind="ok">{t("wp.imported", { n: done.read, total: number(done.total, 0) })}</Notice>}
    </Panel>
  );
}
