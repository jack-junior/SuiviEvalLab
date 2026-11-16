// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Today: what is to do now, on the open project, or on all projects at once.

import { useEffect, useState } from "react";
import { AgendaItem, call, ProjectToday, Recent, recents, recentToken, Snapshot, Task } from "../api";
import { useI18n } from "../i18n";
import { todayIso } from "../monitoring";
import { useProject } from "../state";
import { Empty, Icon, Notice } from "../ui";
import { TaskPanel, useItemTitle } from "./Agenda";

function useWhen() {
  const { t, day } = useI18n();
  return (iso: string | undefined) => {
    if (!iso) return "";
    const n = Math.round(
      (Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) - Date.parse(`${todayIso()}T00:00:00Z`)) / 86_400_000,
    );
    const rel =
      n === 0
        ? t("ws.today")
        : n === 1
          ? t("ws.tomorrow")
          : n > 0
            ? t("ws.inDays", { n })
            : t("today.daysLate", { n: -n });
    return `${day(iso)} (${rel})`;
  };
}

function TaskList({
  tasks,
  onOpen,
  onDone,
}: {
  tasks: AgendaItem[];
  onOpen: (x: AgendaItem) => void;
  onDone?: (x: AgendaItem) => void;
}) {
  const { t } = useI18n();
  const title = useItemTitle();
  const when = useWhen();
  return (
    <ul className="todo-list" data-testid="today-tasks">
      {tasks.map((x) => (
        <li
          key={`${x.id}${x.path ?? ""}`}
          className={`todo prio-${x.priority ?? "normal"}`}
          data-testid={`todo-${x.kind}`}
        >
          {onDone && !x.auto ? (
            <input type="checkbox" aria-label={t("today.markDone")} onChange={() => onDone(x)} />
          ) : (
            <span className={`cal-dot k-${x.kind}`} style={x.color ? { background: x.color } : undefined} />
          )}
          <button className="link todo-title" onClick={() => onOpen(x)}>
            {title(x)}
          </button>
          <span className="muted small">{[x.project, x.due ? when(x.due) : ""].filter(Boolean).join(", ")}</span>
        </li>
      ))}
    </ul>
  );
}

/** Where a task leads in the project. */
function useOpenItem() {
  const { go } = useProject();
  return (x: AgendaItem) => {
    if (x.kind === "chase" || x.kind === "verify" || x.kind === "returned") go("reception", x.submission_id ?? null);
    else if (x.kind === "gap" || x.kind === "report") go("tracking");
    else if (x.kind === "sheet") go("indicators", null);
    else if (x.kind === "data_due") go("reception");
    else if (x.kind === "report_due") go("tracking");
    else go("agenda");
  };
}

export function ProjectTodayScreen() {
  const { t } = useI18n();
  const { snap, setSnap, go, describe } = useProject();
  const [data, setData] = useState<ProjectToday | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const open = useOpenItem();
  const title = useItemTitle();
  const when = useWhen();
  const { lang } = useI18n();
  const stamp = snap
    ? `${snap.submissions.map((s) => s.status).join()}|${snap.tasks.map((x) => x.status).join()}|${snap.periods.map((p) => p.reported_at ?? "").join()}|${Object.keys(snap.gap_comments).length}`
    : "";
  useEffect(() => {
    call<ProjectToday>("today.project", { lang })
      .then(setData)
      .catch((e) => setError(describe(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stamp, lang]);
  if (!snap) return null;

  const done = async (x: AgendaItem) => {
    const task = snap.tasks.find((k) => k.id === x.id);
    if (!task) return;
    try {
      setSnap(await call<Snapshot>("task.save", { id: task.id, task: { ...task, status: "done" } }));
    } catch (e) {
      setError(describe(e));
    }
  };
  const nothing =
    data &&
    !data.tasks.length &&
    !data.deadlines.length &&
    !data.alerts &&
    !data.late.length &&
    !data.events.length &&
    !data.changes.length;

  return (
    <div className="inner wide" data-testid="project-today">
      <div className="page-head">
        <div>
          <h1>{t("nav.today")}</h1>
          <p className="lead">{t("today.lead")}</p>
        </div>
        <div className="row-actions">
          <button className="btn" onClick={() => go("reception")}>
            <Icon name="table" /> {t("today.enter")}
          </button>
          <button className="btn" onClick={() => setAdding(true)} data-testid="today-add-task">
            <Icon name="plus" /> {t("agenda.addTask")}
          </button>
        </div>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!snap.periods.length && (
        <Notice>
          {t("ws.noSheet")}{" "}
          <button className="link" onClick={() => go("setup")}>
            {t("mplan.openSetup")}
          </button>
        </Notice>
      )}
      {nothing && <Empty icon="check" title={t("today.nothing")} text={t("today.nothingText")} />}
      {data && (
        <div className="today-grid">
          {data.tasks.length > 0 && (
            <section className="box stack">
              <h2>{t("today.tasks", { n: data.tasks.length })}</h2>
              <TaskList tasks={data.tasks} onOpen={open} onDone={done} />
            </section>
          )}
          <div className="stack">
            {data.deadlines.length > 0 && (
              <section className="box stack">
                <h2>{t("ws.deadlines")}</h2>
                <ul className="plain small" data-testid="today-deadlines">
                  {data.deadlines.map((d) => (
                    <li key={d.id}>
                      <button className="link" onClick={() => open(d)}>
                        {title(d)}
                      </button>{" "}
                      <span className="muted">{when(d.start)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {(data.alerts > 0 || data.late.length > 0) && (
              <section className="box stack">
                <h2>{t("today.watch")}</h2>
                {data.alerts > 0 && (
                  <button className="link" onClick={() => go("reception")} data-testid="today-alerts">
                    {t("today.alerts", { n: data.alerts })}
                  </button>
                )}
                {data.late.length > 0 && (
                  <ul className="plain small">
                    {data.late.map((l) => (
                      <li key={l.indicator_id}>
                        <button className="link" onClick={() => go("tracking")}>
                          {t("today.late", { name: l.indicator })}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
            {data.changes.length > 0 && (
              <section className="box stack" data-testid="today-changes">
                <h2>{t("today.changes")}</h2>
                <ul className="plain small">
                  {data.changes.slice(0, 10).map((c) => (
                    <li key={`${c.submission_id}${c.at}`}>
                      <button className="link" onClick={() => go("reception", c.submission_id)}>
                        {t(`today.change_${c.action}`, {
                          unit: c.unit_name || t("rec.wholeProject"),
                          period: c.label,
                        })}
                      </button>{" "}
                      <span className="muted">{when(c.at)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {data.events.length > 0 && (
              <section className="box stack">
                <h2>{t("today.week")}</h2>
                <ul className="plain small">
                  {data.events.map((e) => (
                    <li key={e.id}>
                      {e.title} <span className="muted">{when(e.start)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </div>
      )}
      {adding && (
        <TaskPanel
          scope="project"
          task={null}
          day={todayIso()}
          onClose={() => setAdding(false)}
          onSaved={() => undefined}
        />
      )}
    </div>
  );
}

// ----- all projects --------------------------------------------------------------------------------

export function WorkspaceToday() {
  const { t, lang } = useI18n();
  const { run, go } = useProject();
  const [list, setList] = useState<Recent[] | null>(null);
  const [mine, setMine] = useState<{ tasks: Task[] } | null>(null);
  const [adding, setAdding] = useState(false);
  const when = useWhen();
  const title = useItemTitle();

  const reload = () => {
    recents()
      .then(setList)
      .catch(() => setList([]));
    call<{ tasks: Task[] }>("personal.get")
      .then(setMine)
      .catch(() => setMine({ tasks: [] }));
  };
  useEffect(reload, [lang]);

  const openProject = async (r: Recent, view: "today" | "reception" | "tracking" = "today") => {
    const token = await recentToken(r.path);
    if (!token) return;
    if (await run("project.open", { file_token: token })) go(view);
  };

  const today = todayIso();
  const projects = (list ?? []).filter((r) => r.exists && r.card?.today);
  const tasks: (AgendaItem & { recent?: Recent })[] = [
    ...projects.flatMap((r) =>
      (r.card!.today!.tasks ?? []).map((x) => ({
        ...x,
        project: r.card?.name ?? r.name,
        color: r.card?.profile?.color,
        recent: r,
      })),
    ),
    ...(mine?.tasks ?? [])
      .filter((x) => x.status !== "done")
      .map((x) => ({ ...x, auto: false, kind: "personal", personal: true }) as AgendaItem),
  ];
  const due = tasks.filter((x) => x.due && x.due <= today).sort((a, b) => (a.due ?? "").localeCompare(b.due ?? ""));
  const later = tasks
    .filter((x) => !x.due || x.due > today)
    .sort((a, b) => (a.due || "9999").localeCompare(b.due || "9999"));
  const deadlines = projects
    .flatMap((r) => r.card!.today!.deadlines.map((d) => ({ ...d, project: r.card?.name ?? r.name, recent: r })))
    .sort((a, b) => (a.start ?? "").localeCompare(b.start ?? ""))
    .slice(0, 10);
  const watch = projects.filter((r) => r.card!.today!.alerts > 0 || r.card!.today!.late.length > 0);

  const doneMine = async (x: AgendaItem) => {
    const task = mine?.tasks.find((k) => k.id === x.id);
    if (!task) return;
    setMine(await call<{ tasks: Task[] }>("personal.task_save", { id: task.id, task: { ...task, status: "done" } }));
  };
  const openItem = (x: AgendaItem & { recent?: Recent }) => {
    if (x.recent) void openProject(x.recent, x.kind === "chase" || x.kind === "verify" ? "reception" : "today");
  };

  return (
    <div className="inner wide" data-testid="workspace-today">
      <div className="page-head">
        <div>
          <h1>{t("nav.today")}</h1>
          <p className="lead">{t("today.leadWorkspace")}</p>
        </div>
        <button className="btn" onClick={() => setAdding(true)} data-testid="ws-add-task">
          <Icon name="plus" /> {t("agenda.addTask")}
        </button>
      </div>
      {list && !list.length && <Empty icon="home" title={t("today.noProjects")} text={t("today.noProjectsText")} />}
      <div className="today-grid">
        <section className="box stack">
          <h2>{t("today.dueNow", { n: due.length })}</h2>
          {due.length ? (
            <TaskList tasks={due} onOpen={openItem} onDone={doneMine} />
          ) : (
            <p className="muted small">{t("today.nothingDue")}</p>
          )}
          {later.length > 0 && (
            <>
              <h3 className="panel-section">{t("today.later")}</h3>
              <TaskList tasks={later.slice(0, 12)} onOpen={openItem} onDone={doneMine} />
            </>
          )}
        </section>
        <div className="stack">
          {deadlines.length > 0 && (
            <section className="box stack">
              <h2>{t("ws.deadlines")}</h2>
              <ul className="plain small">
                {deadlines.map((d) => (
                  <li key={`${d.id}${d.recent.path}`}>
                    <button className="link" onClick={() => openItem(d)}>
                      {title(d)}
                    </button>{" "}
                    <span className="muted">
                      {d.project}, {when(d.start)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {watch.length > 0 && (
            <section className="box stack">
              <h2>{t("today.watch")}</h2>
              <ul className="plain small">
                {watch.map((r) => (
                  <li key={r.path}>
                    <button className="link" onClick={() => void openProject(r, "reception")}>
                      {r.card?.name ?? r.name}
                    </button>
                    {": "}
                    {[
                      r.card!.today!.alerts ? t("today.alerts", { n: r.card!.today!.alerts }) : "",
                      r.card!.today!.late.length ? t("today.lateCount", { n: r.card!.today!.late.length }) : "",
                    ]
                      .filter(Boolean)
                      .join(", ")}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
      {adding && (
        <TaskPanel scope="workspace" task={null} day={today} onClose={() => setAdding(false)} onSaved={reload} />
      )}
    </div>
  );
}
