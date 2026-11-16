// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Workspace: every project known to this computer as a card (calendar, next
// deadline, size), and the next deadlines of all projects together.

import { ReactNode } from "react";
import { Recent } from "../api";
import { useI18n } from "../i18n";
import { Progress } from "../ui";

const DAY = 86_400_000;

function daysFrom(today: string, iso: string): number {
  return Math.round((Date.parse(`${iso}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY);
}

export function useWhen() {
  const { t, day } = useI18n();
  const today = new Date().toISOString().slice(0, 10);
  return (iso: string) => {
    const n = daysFrom(today, iso);
    const rel = n === 0 ? t("ws.today") : n === 1 ? t("ws.tomorrow") : t("ws.inDays", { n });
    return `${day(iso)} (${rel})`;
  };
}

/** The next deadlines of all projects, soonest first. */
export function Deadlines({ list, onOpen }: { list: Recent[]; onOpen: (r: Recent) => void }) {
  const { t, lang } = useI18n();
  const when = useWhen();
  const items = list
    .filter((r) => r.exists && r.card?.next_deadline)
    .map((r) => ({ r, d: r.card!.next_deadline! }))
    .sort((a, b) => a.d.date.localeCompare(b.d.date))
    .slice(0, 6);
  if (!items.length) return null;
  return (
    <section className="stack" data-testid="ws-deadlines">
      <h2>{t("ws.deadlines")}</h2>
      <ul className="deadlines">
        {items.map(({ r, d }) => (
          <li key={r.path}>
            <span className="dl-date">{when(d.date)}</span>
            <span className="dl-what">
              {t(d.kind === "data" ? "ws.dueData" : "ws.dueReport", {
                period: lang === "en" ? d.label_en : d.label_fr,
              })}
            </span>
            <button className="link" onClick={() => onOpen(r)}>
              {r.card?.name ?? r.name}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ProjectCard({
  r,
  busy,
  onOpen,
  tools,
  status,
}: {
  r: Recent;
  busy: boolean;
  onOpen: () => void;
  tools: ReactNode;
  status: ReactNode;
}) {
  const { t, tn, lang, day, date } = useI18n();
  const when = useWhen();
  const c = r.card;
  const p = c?.profile;
  const facts = [p?.code, p?.donors.map((d) => d.name).join(", "), p?.countries.join(", ")].filter(Boolean);
  return (
    <div
      className={`ws-card${r.exists ? "" : " missing"}`}
      style={{ borderLeftColor: p?.color ?? "var(--ligne)" }}
      data-testid="ws-card"
    >
      <button
        className="ws-open"
        onClick={onOpen}
        disabled={!r.exists || busy}
        title={r.path}
        data-testid="project-row"
      >
        <span className="project-title">{c?.name ?? r.name}</span>
        {facts.length > 0 && (
          <span className="project-meta">
            {facts.map((f) => (
              <span key={f}>{f}</span>
            ))}
          </span>
        )}
        {!r.exists && <span className="muted small">{t("home.missingFile")}</span>}
        {c?.state === "older" && <span className="muted small">{t("ws.older")}</span>}
        {c?.state === "too_new" && <span className="muted small">{t("ws.tooNew")}</span>}
        {p?.start && p.end && (
          <span className="ws-time">
            <span className="small">
              {t("ws.dates", { start: day(p.start), end: day(p.end) })}
              {c?.phase && c.phase !== "running" && c.phase !== "unset" && ` (${t(`ws.phase_${c.phase}`)})`}
            </span>
            {c?.phase === "running" && <Progress value={c.time_elapsed ?? null} />}
          </span>
        )}
        {c?.current_period && (
          <span className="small">
            {t("ws.current", {
              period: lang === "en" ? c.current_period.label_en : c.current_period.label_fr,
            })}
          </span>
        )}
        {c?.next_deadline && (
          <span className="small ws-next">
            {t(c.next_deadline.kind === "data" ? "ws.nextData" : "ws.nextReport", {
              period: lang === "en" ? c.next_deadline.label_en : c.next_deadline.label_fr,
              when: when(c.next_deadline.date),
            })}
          </span>
        )}
        {r.exists && c?.state === "ok" && p && !p.start && <span className="small muted">{t("ws.noSheet")}</span>}
        <span className="project-meta">
          {c?.counts && (
            <span>
              {[
                tn("ws.indicators", c.counts.indicators),
                c.counts.places ? tn("ws.places", c.counts.places) : "",
                c.counts.partners ? tn("ws.partners", c.counts.partners) : "",
              ]
                .filter(Boolean)
                .join(", ")}
            </span>
          )}
          {status}
          {r.modified && <span>{t("home.modified", { date: date(r.modified) })}</span>}
        </span>
      </button>
      <div className="row-tools">{tools}</div>
    </div>
  );
}
