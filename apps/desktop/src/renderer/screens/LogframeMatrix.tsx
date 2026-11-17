// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Logframe matrix: one row per result, with its indicators, baselines, targets,
// sources of verification and assumptions, editable in place as in the donor's table.

import { useState } from "react";
import { FrameworkNode, Indicator } from "../api";
import { useLevels } from "../frameworks";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { useValueFormat } from "../ui";

/** A text cell saved when it loses the focus; Escape gives the saved text back. */
function EditCell({
  value,
  label,
  placeholder,
  onSave,
  testId,
}: {
  value: string;
  label: string;
  placeholder?: string;
  onSave: (v: string) => Promise<unknown>;
  testId?: string;
}) {
  const [text, setText] = useState<string | null>(null);
  const commit = async () => {
    if (text === null) return;
    const v = text.trim();
    if (v !== value.trim()) await onSave(v);
    setText(null);
  };
  return (
    <textarea
      className="matrix-edit"
      value={text ?? value}
      rows={Math.max(2, Math.min(10, Math.ceil((text ?? value).length / 28)))}
      aria-label={label}
      placeholder={placeholder}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Escape") setText(null);
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) (e.target as HTMLTextAreaElement).blur();
      }}
      data-testid={testId}
    />
  );
}

export function LogframeMatrix() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const levels = useLevels();
  const format = useValueFormat();
  if (!snap) return null;

  const saveNode = (n: FrameworkNode, patch: Partial<FrameworkNode>) =>
    run("framework.update", {
      id: n.id,
      title: patch.title ?? n.title,
      description: n.description,
      assumptions: patch.assumptions ?? n.assumptions ?? "",
    });
  const saveSource = (ind: Indicator, source: string) => {
    const { id, node_id, ...spec } = ind;
    void node_id;
    return run("indicator.save", { id, indicator: { ...spec, source } });
  };
  const value = (v: number | null, ind: Indicator) => (v === null || v === undefined ? "" : format(v, ind.unit));

  return (
    <div className="grid-scroll matrix-scroll">
      <table className="table matrix" data-testid="logframe-matrix">
        <thead>
          <tr>
            <th className="col-logic">{t("matrix.logic")}</th>
            <th className="col-ind">{t("matrix.indicators")}</th>
            <th className="col-num">{t("matrix.baseline")}</th>
            <th className="col-num">{t("matrix.target")}</th>
            <th className="col-src">{t("matrix.sources")}</th>
            <th className="col-ass">{t("matrix.assumptions")}</th>
          </tr>
        </thead>
        <tbody>
          {snap.framework.map((n) => {
            const list = snap.indicators.filter((i) => i.node_id === n.id);
            const carries = levels.carries(n.level);
            const rows = Math.max(1, list.length);
            return Array.from({ length: rows }, (_, k) => {
              const ind: Indicator | undefined = list[k];
              return (
                <tr key={`${n.id}-${k}`} className={`level-${n.level}${k === 0 ? " first" : ""}`}>
                  {k === 0 && (
                    <td rowSpan={rows} className="col-logic">
                      <div className="matrix-level">
                        {levels.name(n.level)} {n.code}
                      </div>
                      <EditCell
                        value={n.title}
                        label={t("matrix.logic")}
                        onSave={(v) => (v ? saveNode(n, { title: v }) : Promise.resolve())}
                        testId={`matrix-title-${n.code}`}
                      />
                      {carries && list.length === 0 && (
                        <span className="tag warn" data-testid={`matrix-missing-${n.code}`}>
                          {t("matrix.noIndicator")}
                        </span>
                      )}
                    </td>
                  )}
                  <td className="col-ind">{ind ? ind.name : carries ? "" : <span className="muted">-</span>}</td>
                  <td className="col-num num">{ind ? value(ind.baseline_manual, ind) : ""}</td>
                  <td className="col-num num">{ind ? value(ind.target, ind) : ""}</td>
                  <td className="col-src">
                    {ind && (
                      <EditCell
                        value={ind.source}
                        label={t("matrix.sources")}
                        placeholder={t("matrix.sourcesHint")}
                        onSave={(v) => saveSource(ind, v)}
                      />
                    )}
                  </td>
                  {k === 0 && (
                    <td rowSpan={rows} className="col-ass">
                      <EditCell
                        value={n.assumptions ?? ""}
                        label={t("matrix.assumptions")}
                        placeholder={t("matrix.assumptionsHint")}
                        onSave={(v) => saveNode(n, { assumptions: v })}
                        testId={`matrix-assumptions-${n.code}`}
                      />
                    </td>
                  )}
                </tr>
              );
            });
          })}
        </tbody>
      </table>
    </div>
  );
}
