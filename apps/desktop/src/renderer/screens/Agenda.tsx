// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Agenda: a month of deadlines, events and dated tasks, of one project or of all
// of them, with the events and tasks typed by the user.

import { useCallback, useEffect, useState } from "react";
import { AgendaData, AgendaItem, call, EventKind, pick, Snapshot, Task, workspaceAgenda } from "../api";
import { useI18n } from "../i18n";
import { todayIso } from "../monitoring";
import { useProject } from "../state";
import { Field, Icon, IconButton, Notice, Panel } from "../ui";

const KINDS: EventKind[] = ["meeting", "mission", "training", "workshop", "collection", "absence", "other"];

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Weeks of the month, from Monday. */
function weeks(year: number, month: number): Date[][] {
  const first = new Date(year, month, 1);
  const start = new Date(first);
  start.setDate(1 - ((first.getDay() + 6) % 7));
  const out: Date[][] = [];
  const d = new Date(start);
  do {
    const week: Date[] = [];
    for (let i = 0; i < 7; i++) {
      week.push(new Date(d));
      d.setDate(d.getDate() + 1);
    }
    out.push(week);
  } while (d.getMonth() === month);
  return out;
}

export function useItemTitle() {
  const { t } = useI18n();
  return (x: AgendaItem): string => {
    if (!x.auto) return x.title ?? "";
    const vars = {
      period: x.label ?? "",
      unit: x.unit_name ?? "",
      indicator: x.indicator ?? "",
      missing: (x.missing ?? []).map((m) => t(`today.missing_${m}`)).join(", "),
      name:
        x.name || (x.category ? (x.category.startsWith("c_") ? t("fb.sensitiveCase") : t(`fb.cat_${x.category}`)) : ""),
      step: x.step ? t(`ev.step_${x.step}`) : "",
    };
    // Data of the whole project: collected by the team, not chased from a partner.
    const kind =
      (x.kind === "chase" || x.kind === "verify" || x.kind === "returned") && !x.unit_name ? `${x.kind}_own` : x.kind;
    return t(`today.kind_${kind}`, vars);
  };
}

export function Agenda({ scope }: { scope: "project" | "workspace" }) {
  const { t, lang, day } = useI18n();
  const { snap, setSnap, describe } = useProject();
  const title = useItemTitle();
  const now = new Date();
  const [cursor, setCursor] = useState({ y: now.getFullYear(), m: now.getMonth() });
  const [data, setData] = useState<AgendaData | null>(null);
  const [selected, setSelected] = useState(todayIso());
  const [editing, setEditing] = useState<{ kind: "event" | "task"; item: AgendaItem | null } | null>(null);
  const [note, setNote] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [mode, setMode] = useState<"month" | "board">("month");

  const grid = weeks(cursor.y, cursor.m);
  const start = iso(grid[0][0]);
  const end = iso(grid[grid.length - 1][6]);

  const load = useCallback(() => {
    const p =
      scope === "project" ? call<AgendaData>("agenda.list", { start, end, lang }) : workspaceAgenda(start, end, lang);
    p.then(setData).catch((e) => setNote({ kind: "error", text: describe(e) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, start, end, lang]);
  const stamp = snap ? `${snap.events.length}|${snap.tasks.length}|${snap.submissions.length}` : "";
  useEffect(load, [load, stamp]);

  const onDay = (d: string) => [
    ...(data?.events ?? []).filter(
      (e) => (e.start ?? "").slice(0, 10) <= d && d <= (e.end ?? e.start ?? "").slice(0, 10),
    ),
    ...(data?.tasks ?? []).filter((x) => (x.due ?? "").slice(0, 10) === d),
  ];

  const exportIcs = async () => {
    const file = await pick("ics-save", `${t("agenda.file")} ${(snap?.project.name ?? "").slice(0, 40)}.ics`);
    if (!file) return;
    try {
      const r = await call<{ events: number }>("agenda.export_ics", { file_token: file.token, lang });
      setNote({ kind: "ok", text: t("agenda.exported", { n: r.events, name: file.name }) });
    } catch (e) {
      setNote({ kind: "error", text: describe(e) });
    }
  };
  const importIcs = async () => {
    const file = await pick("ics-open");
    if (!file) return;
    try {
      const r = await call<Snapshot & { imported: number }>("agenda.import_ics", { file_token: file.token });
      setSnap(r);
      setNote({ kind: "ok", text: t("agenda.imported", { n: r.imported }) });
    } catch (e) {
      setNote({ kind: "error", text: describe(e) });
    }
  };

  const monthName = new Intl.DateTimeFormat(lang === "en" ? "en-GB" : "fr-FR", {
    month: "long",
    year: "numeric",
  }).format(new Date(cursor.y, cursor.m, 1));
  const dayNames = Array.from({ length: 7 }, (_, i) =>
    new Intl.DateTimeFormat(lang === "en" ? "en-GB" : "fr-FR", { weekday: "short" }).format(new Date(2024, 0, 1 + i)),
  );
  const move = (n: number) => {
    const d = new Date(cursor.y, cursor.m + n, 1);
    setCursor({ y: d.getFullYear(), m: d.getMonth() });
  };
  const today = todayIso();
  const list = onDay(selected);

  return (
    <div className="inner wide" data-testid={`agenda-${scope}`}>
      <div className="page-head">
        <div>
          <h1>{t("nav.agenda")}</h1>
          <p className="lead">{t(scope === "project" ? "agenda.leadProject" : "agenda.leadWorkspace")}</p>
        </div>
        <div className="row-actions">
          <button
            className="btn"
            onClick={() => setEditing({ kind: "event", item: null })}
            data-testid="agenda-add-event"
          >
            <Icon name="plus" /> {t("agenda.addEvent")}
          </button>
          <button
            className="btn"
            onClick={() => setEditing({ kind: "task", item: null })}
            data-testid="agenda-add-task"
          >
            <Icon name="plus" /> {t("agenda.addTask")}
          </button>
          {scope === "project" && (
            <>
              <button className="btn" onClick={exportIcs} data-testid="agenda-export">
                {t("agenda.export")}
              </button>
              <button className="btn" onClick={importIcs}>
                {t("agenda.import")}
              </button>
            </>
          )}
        </div>
      </div>
      {note && <Notice kind={note.kind}>{note.text}</Notice>}

      {scope === "project" && (
        <div className="tabs" role="tablist">
          {(["month", "board"] as const).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={mode === k}
              className="tab"
              onClick={() => setMode(k)}
              data-testid={`agenda-mode-${k}`}
            >
              {t(`agenda.mode_${k}`)}
            </button>
          ))}
        </div>
      )}
      {mode === "board" ? (
        <TaskBoard onEdit={(task) => setEditing({ kind: "task", item: task as unknown as AgendaItem })} />
      ) : (
        <>
          <div className="cal-head">
            <IconButton icon="up" label={t("agenda.previous")} onClick={() => move(-1)} />
            <h2 className="cal-title">{monthName}</h2>
            <IconButton icon="down" label={t("agenda.next")} onClick={() => move(1)} />
            <button
              className="btn small"
              onClick={() => {
                setCursor({ y: now.getFullYear(), m: now.getMonth() });
                setSelected(today);
              }}
            >
              {t("ws.today")}
            </button>
          </div>
          <div className="cal-layout">
            <table className="calendar" data-testid="calendar">
              <thead>
                <tr>
                  {dayNames.map((d) => (
                    <th key={d}>{d}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grid.map((week, i) => (
                  <tr key={i}>
                    {week.map((d) => {
                      const key = iso(d);
                      const items = onDay(key);
                      return (
                        <td
                          key={key}
                          className={[
                            d.getMonth() !== cursor.m ? "out" : "",
                            key === today ? "today" : "",
                            key === selected ? "selected" : "",
                          ].join(" ")}
                        >
                          <button className="cal-day" onClick={() => setSelected(key)} data-testid={`day-${key}`}>
                            <span className="cal-num">{d.getDate()}</span>
                            {items.slice(0, 3).map((x) => (
                              <span
                                key={`${x.id}${x.path ?? ""}`}
                                className={`cal-item k-${x.kind}${x.done ? " done" : ""}`}
                                style={x.color ? { borderLeftColor: x.color } : undefined}
                              >
                                {title(x)}
                              </span>
                            ))}
                            {items.length > 3 && <span className="cal-more">+{items.length - 3}</span>}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <aside className="cal-side">
              <h3>{day(selected)}</h3>
              {list.length === 0 && <p className="muted small">{t("agenda.nothing")}</p>}
              <ul className="plain">
                {list.map((x) => (
                  <li key={`${x.id}${x.path ?? ""}`} className="cal-entry">
                    <span className={`cal-dot k-${x.kind}`} style={x.color ? { background: x.color } : undefined} />
                    <div>
                      <div>{title(x)}</div>
                      <div className="muted small">
                        {[x.project, x.start && x.start.includes("T") ? x.start.slice(11, 16) : "", x.place]
                          .filter(Boolean)
                          .join(", ")}
                      </div>
                    </div>
                    {!x.auto && (scope === "project" ? !x.project : x.personal) && (
                      <IconButton
                        icon="edit"
                        label={t("common.edit")}
                        onClick={() =>
                          setEditing({ kind: x.due !== undefined && !x.start ? "task" : "event", item: x })
                        }
                      />
                    )}
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </>
      )}

      {editing?.kind === "event" && (
        <EventPanel scope={scope} item={editing.item} day={selected} onClose={() => setEditing(null)} onSaved={load} />
      )}
      {editing?.kind === "task" && (
        <TaskPanel
          scope={scope}
          task={editing.item as unknown as Task | null}
          day={selected}
          onClose={() => setEditing(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}

export function EventPanel({
  scope,
  item,
  day,
  onClose,
  onSaved,
}: {
  scope: "project" | "workspace";
  item: AgendaItem | null;
  day: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const { setSnap, describe } = useProject();
  const [e, setE] = useState({
    title: item?.title ?? "",
    kind: (item?.kind as EventKind) ?? "meeting",
    start: item?.start ?? day,
    end: item?.end ?? item?.start ?? day,
    place: item?.place ?? "",
    note: item?.note ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<typeof e>) => setE({ ...e, ...patch });
  const timed = e.start.includes("T");
  const save = async (remove = false) => {
    try {
      if (scope === "project") {
        const s = remove
          ? await call<Snapshot>("event.delete", { id: item!.id })
          : await call<Snapshot>("event.save", { id: item?.id, event: e });
        setSnap(s);
      } else {
        await call("personal.event_save", { id: item?.id, event: e, delete: remove });
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(describe(err));
    }
  };
  return (
    <Panel
      title={item ? t("agenda.editEvent") : t("agenda.addEvent")}
      onClose={onClose}
      testId="event-panel"
      footer={
        <>
          {item && (
            <button className="btn" onClick={() => save(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" disabled={!e.title.trim()} onClick={() => save()} data-testid="event-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      {error && <Notice kind="error">{error}</Notice>}
      <Field label={t("agenda.title")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={e.title}
            onChange={(x) => set({ title: x.target.value })}
            data-testid="event-title"
          />
        )}
      </Field>
      <div className="chips">
        {KINDS.map((k) => (
          <button key={k} className="chip small" aria-pressed={e.kind === k} onClick={() => set({ kind: k })}>
            {t(`agenda.kind_${k}`)}
          </button>
        ))}
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={timed}
          onChange={(x) =>
            set(
              x.target.checked
                ? { start: `${e.start.slice(0, 10)}T09:00`, end: `${e.end.slice(0, 10)}T10:00` }
                : { start: e.start.slice(0, 10), end: e.end.slice(0, 10) },
            )
          }
        />{" "}
        {t("agenda.timed")}
      </label>
      <div className="field-row">
        <Field label={t("setup.from")}>
          {(id) => (
            <input
              id={id}
              className="input"
              type={timed ? "datetime-local" : "date"}
              value={e.start}
              onChange={(x) => set({ start: x.target.value, end: x.target.value > e.end ? x.target.value : e.end })}
              data-testid="event-start"
            />
          )}
        </Field>
        <Field label={t("setup.to")}>
          {(id) => (
            <input
              id={id}
              className="input"
              type={timed ? "datetime-local" : "date"}
              value={e.end}
              onChange={(x) => set({ end: x.target.value })}
            />
          )}
        </Field>
      </div>
      <Field label={t("agenda.place")}>
        {(id) => <input id={id} className="input" value={e.place} onChange={(x) => set({ place: x.target.value })} />}
      </Field>
      <Field label={t("setup.note")}>
        {(id) => (
          <textarea id={id} className="input" rows={3} value={e.note} onChange={(x) => set({ note: x.target.value })} />
        )}
      </Field>
    </Panel>
  );
}

export function TaskPanel({
  scope,
  task,
  day,
  onClose,
  onSaved,
}: {
  scope: "project" | "workspace";
  task: Task | null;
  day: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const { setSnap, describe } = useProject();
  const [x, setX] = useState<Omit<Task, "id" | "created_at" | "done_at" | "link">>({
    title: task?.title ?? "",
    due: task?.due ?? day,
    priority: task?.priority ?? "normal",
    status: task?.status ?? "todo",
    note: task?.note ?? "",
    assignee: task?.assignee ?? "",
    recurrence: task?.recurrence ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<typeof x>) => setX({ ...x, ...patch });
  const save = async (remove = false) => {
    try {
      if (scope === "project") {
        const s = remove
          ? await call<Snapshot>("task.delete", { id: task!.id })
          : await call<Snapshot>("task.save", { id: task?.id, task: x });
        setSnap(s);
      } else {
        await call("personal.task_save", { id: task?.id, task: x, delete: remove });
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(describe(err));
    }
  };
  return (
    <Panel
      title={task ? t("agenda.editTask") : t("agenda.addTask")}
      onClose={onClose}
      testId="task-panel"
      footer={
        <>
          {task && (
            <button className="btn" onClick={() => save(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" disabled={!x.title.trim()} onClick={() => save()} data-testid="task-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      {error && <Notice kind="error">{error}</Notice>}
      <Field label={t("agenda.title")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={x.title}
            onChange={(e) => set({ title: e.target.value })}
            data-testid="task-title"
          />
        )}
      </Field>
      <div className="field-row">
        <Field label={t("agenda.due")}>
          {(id) => (
            <input
              id={id}
              className="input"
              type="date"
              value={x.due}
              onChange={(e) => set({ due: e.target.value })}
              data-testid="task-due"
            />
          )}
        </Field>
        <Field label={t("agenda.assignee")}>
          {(id) => (
            <input id={id} className="input" value={x.assignee} onChange={(e) => set({ assignee: e.target.value })} />
          )}
        </Field>
      </div>
      <div className="field">
        <span className="label">{t("agenda.priority")}</span>
        <div className="chips">
          {(["low", "normal", "high"] as const).map((p) => (
            <button key={p} className="chip small" aria-pressed={x.priority === p} onClick={() => set({ priority: p })}>
              {t(`agenda.priority_${p}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <span className="label">{t("setup.state")}</span>
        <div className="chips">
          {(["todo", "doing", "waiting", "done"] as const).map((p) => (
            <button key={p} className="chip small" aria-pressed={x.status === p} onClick={() => set({ status: p })}>
              {t(`agenda.status_${p}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <span className="label">{t("agenda.recurrence")}</span>
        <div className="chips">
          {(["", "monthly", "quarterly"] as const).map((p) => (
            <button
              key={p || "none"}
              className="chip small"
              aria-pressed={x.recurrence === p}
              onClick={() => set({ recurrence: p })}
            >
              {t(`agenda.recur_${p || "none"}`)}
            </button>
          ))}
        </div>
      </div>
      <Field label={t("setup.note")}>
        {(id) => (
          <textarea id={id} className="input" rows={3} value={x.note} onChange={(e) => set({ note: e.target.value })} />
        )}
      </Field>
    </Panel>
  );
}

/** Tasks of the project in columns by status, the generated ones with what is to do. */
function TaskBoard({ onEdit }: { onEdit: (t: Task) => void }) {
  const { t, lang, day } = useI18n();
  const { snap, setSnap, describe } = useProject();
  const title = useItemTitle();
  const [auto, setAuto] = useState<AgendaItem[]>([]);
  const [byPerson, setByPerson] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stamp = snap ? `${snap.submissions.map((s) => s.status).join()}|${snap.tasks.length}` : "";
  useEffect(() => {
    call<{ tasks: AgendaItem[] }>("today.project", { lang })
      .then((r) => setAuto(r.tasks.filter((x) => x.auto)))
      .catch((e) => setError(describe(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stamp, lang]);
  if (!snap) return null;
  const move = async (task: Task, status: Task["status"]) => {
    try {
      setSnap(await call<Snapshot>("task.save", { id: task.id, task: { ...task, status } }));
    } catch (e) {
      setError(describe(e));
    }
  };
  const columns = (["todo", "doing", "waiting", "done"] as const).map((st) => ({
    key: st,
    items: snap.tasks.filter((x) => x.status === st),
  }));
  const people = [...new Set(snap.tasks.filter((x) => x.status !== "done").map((x) => x.assignee || ""))].sort();
  return (
    <div className="stack" data-testid="task-board">
      {error && <Notice kind="error">{error}</Notice>}
      <label className="check">
        <input type="checkbox" checked={byPerson} onChange={(e) => setByPerson(e.target.checked)} />{" "}
        {t("agenda.byAssignee")}
      </label>
      {byPerson ? (
        <div className="board">
          {people.map((who) => (
            <div key={who || "none"} className="board-col">
              <h3>{who || t("agenda.noAssignee")}</h3>
              {snap.tasks
                .filter((x) => x.status !== "done" && (x.assignee || "") === who)
                .map((x) => (
                  <button key={x.id} className="board-card" onClick={() => onEdit(x)}>
                    {x.title}
                    <span className="muted small">{x.due ? day(x.due) : ""}</span>
                  </button>
                ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="board">
          {columns.map((c) => (
            <div key={c.key} className="board-col" data-testid={`board-${c.key}`}>
              <h3>{t(`agenda.status_${c.key}`)}</h3>
              {c.key === "todo" &&
                auto.map((x) => (
                  <div key={x.id} className="board-card auto">
                    {title(x)}
                    <span className="muted small">{x.due ? day(x.due) : t("agenda.suggested")}</span>
                  </div>
                ))}
              {c.items.map((x) => (
                <div key={x.id} className="board-card">
                  <button className="link" onClick={() => onEdit(x)}>
                    {x.title}
                  </button>
                  <span className="muted small">
                    {[x.due ? day(x.due) : "", x.assignee].filter(Boolean).join(", ")}
                  </span>
                  <select
                    className="input small"
                    value={x.status}
                    aria-label={t("setup.state")}
                    onChange={(e) => move(x, e.target.value as Task["status"])}
                  >
                    {(["todo", "doing", "waiting", "done"] as const).map((st) => (
                      <option key={st} value={st}>
                        {t(`agenda.status_${st}`)}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
