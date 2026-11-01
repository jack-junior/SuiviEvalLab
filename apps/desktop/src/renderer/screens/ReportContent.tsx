// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Report content: which sections, in which order, which indicators and what is
// shown for each, which analyses and saved tests, and the cleaning journal in the
// annex. Saved in the project; new indicators and analyses are included by default.

import { ReactNode } from "react";
import { ReportContent as Content, ReportSection } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { IconButton } from "../ui";
import { defaultTitle } from "./Workshop";

const MESSAGE: Record<ReportSection, string> = {
  summary: "summary",
  results: "results",
  analyses: "analyses",
  tests: "tests",
  framework: "framework",
  annex_data: "data",
  annex_methods: "methods",
  sources: "sources",
};

const IND_PARTS = ["reading", "chart", "breakdown", "definition"] as const;
const AN_PARTS = ["reading", "tables", "charts", "script"] as const;

function Toggle({
  checked,
  onChange,
  children,
  testId,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <label className="check inline-check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} data-testid={testId} />
      <span className="check-text">{children}</span>
    </label>
  );
}

export function ReportContent() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  if (!snap) return null;
  const content = snap.report_content;
  const save = (c: Content) => run("report.set_content", { content: c }, "content");

  const move = (i: number, d: number) => {
    const s = [...content.sections];
    const j = i + d;
    if (j < 0 || j >= s.length) return;
    [s[i], s[j]] = [s[j], s[i]];
    save({ ...content, sections: s });
  };

  const detail = (id: ReportSection) => {
    if (id === "results")
      return snap.indicators.length === 0 ? null : (
        <ul className="content-items">
          {snap.indicators.map((ind) => {
            const o = content.indicators[ind.id] ?? {};
            const on = o.on !== false;
            const set = (p: Record<string, boolean>) =>
              save({ ...content, indicators: { ...content.indicators, [ind.id]: { ...o, ...p } } });
            return (
              <li key={ind.id}>
                <Toggle checked={on} onChange={(v) => set({ on: v })} testId={`content-ind-${ind.id}`}>
                  {ind.name}
                </Toggle>
                {on && (
                  <span className="content-parts">
                    {IND_PARTS.map((p) => (
                      <Toggle key={p} checked={o[p] !== false} onChange={(v) => set({ [p]: v })}>
                        {t(`content.ind_${p}`)}
                      </Toggle>
                    ))}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      );
    if (id === "analyses")
      return snap.analyses.length === 0 ? (
        <p className="muted small">{t("content.noAnalyses")}</p>
      ) : (
        <ul className="content-items">
          {snap.analyses.map((a) => {
            const o = content.analyses[a.id] ?? {};
            const set = (p: Record<string, boolean>) =>
              save({ ...content, analyses: { ...content.analyses, [a.id]: { ...o, ...p } } });
            const defaults: Record<string, boolean> = { reading: true, tables: true, charts: true, script: false };
            return (
              <li key={a.id}>
                <Toggle
                  checked={a.in_report}
                  onChange={(v) => run("analysis.save", { id: a.id, analysis: { in_report: v } }, "content")}
                  testId={`content-an-${a.id}`}
                >
                  {a.title || defaultTitle(a, t)}
                </Toggle>
                {a.in_report && (
                  <span className="content-parts">
                    {AN_PARTS.map((p) => (
                      <Toggle key={p} checked={o[p] ?? defaults[p]} onChange={(v) => set({ [p]: v })}>
                        {t(`content.an_${p}`)}
                      </Toggle>
                    ))}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      );
    if (id === "tests" && snap.tests.length > 0)
      return (
        <ul className="content-items">
          {snap.tests.map((s) => (
            <li key={s.id}>
              <Toggle
                checked={content.tests[s.id!] !== false}
                onChange={(v) => save({ ...content, tests: { ...content.tests, [s.id!]: v } })}
              >
                {s.title || s.outcome.column}
              </Toggle>
            </li>
          ))}
        </ul>
      );
    if (id === "annex_data")
      return (
        <Toggle checked={content.journal} onChange={(v) => save({ ...content, journal: v })} testId="content-journal">
          {t("content.journal")}
        </Toggle>
      );
    return null;
  };

  return (
    <ol className="outline content-outline" data-testid="report-content">
      {content.sections.map((s, i) => (
        <li key={s.id} className={s.on ? undefined : "off"}>
          <div className="content-head">
            <Toggle
              checked={s.on}
              onChange={(v) =>
                save({ ...content, sections: content.sections.map((x) => (x.id === s.id ? { ...x, on: v } : x)) })
              }
              testId={`content-section-${s.id}`}
            >
              <span className="outline-title">{t(`report.s_${MESSAGE[s.id]}`)}</span>
            </Toggle>
            <span className="row-tools">
              <IconButton icon="up" label={t("common.moveUp")} onClick={() => move(i, -1)} disabled={i === 0} />
              <IconButton
                icon="down"
                label={t("common.moveDown")}
                onClick={() => move(i, 1)}
                disabled={i === content.sections.length - 1}
              />
            </span>
          </div>
          <span className="muted small">{t(`report.d_${MESSAGE[s.id]}`)}</span>
          {s.on && detail(s.id)}
        </li>
      ))}
    </ol>
  );
}
