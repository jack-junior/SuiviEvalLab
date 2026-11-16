// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Monitoring plan: the targets of every indicator for every reporting period, and
// the indicator reference sheet (source, method, frequency, who, breakdowns).

import { useMemo, useState } from "react";
import { call, EngineCallError, Frequency, Indicator, openFile, pick, Snapshot, Target } from "../api";
import { useLevels } from "../frameworks";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Empty, Field, Icon, Notice, Panel, useValueFormat } from "../ui";

const FREQUENCIES: Frequency[] = ["", "monthly", "quarterly", "semiannual", "annual", "rounds", "other"];
const TOTAL = "total";

/** Value typed by the user: percentages in %, stored as shares. */
const shown = (v: number | null | undefined, percent: boolean) =>
  v === null || v === undefined ? "" : String(+(percent ? v * 100 : v).toFixed(4));
const parsed = (s: string, percent: boolean): number | null => {
  const v = Number(s.replace(/\s/g, "").replace(",", "."));
  if (s.trim() === "" || Number.isNaN(v)) return null;
  return percent ? v / 100 : v;
};

interface Pending {
  indicator: Indicator;
  period: string;
  value: number;
}

export function Plan() {
  const { t, lang } = useI18n();
  const { snap, setSnap, go, describe, busy, run } = useProject();
  const levels = useLevels();
  const [sheet, setSheet] = useState<Indicator | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exported, setExported] = useState<{ token: string; name: string } | null>(null);

  const groups = useMemo(() => {
    if (!snap) return [];
    return snap.framework
      .filter((n) => levels.carries(n.level))
      .map((node) => ({ node, list: snap.indicators.filter((i) => i.node_id === node.id) }))
      .filter((g) => g.list.length);
  }, [snap, levels]);

  if (!snap) return null;
  const periods = snap.periods;

  const save = async (indicator: Indicator, period: string, value: number | null, reason = "") => {
    setError(null);
    try {
      const s =
        value === null
          ? await call<Snapshot>("target.clear", { indicator_id: indicator.id, period })
          : await call<Snapshot>("target.set", { indicator_id: indicator.id, period, value, reason });
      setSnap(s);
      return true;
    } catch (e) {
      if (e instanceof EngineCallError && e.key === "target_reason_required" && value !== null) {
        setPending({ indicator, period, value });
      } else {
        setError(describe(e));
      }
      return false;
    }
  };

  const exportPlan = async () => {
    const file = await pick("xlsx-save", `${t("plan.file")} ${snap.project.name.slice(0, 50)}.xlsx`);
    if (!file) return;
    setExported(null);
    if (await run("report.plan", { file_token: file.token, lang }, "plan")) setExported(file);
  };

  return (
    <div className="inner wide">
      <div className="page-head">
        <div>
          <h1>{t("nav.plan")}</h1>
          <p className="lead">{t("mplan.lead")}</p>
        </div>
        <button className="btn" onClick={exportPlan} disabled={!snap.indicators.length} data-testid="plan-export">
          <Icon name="table" /> {busy === "plan" ? t("plan.exporting") : t("plan.action")}
        </button>
      </div>
      {exported && (
        <Notice kind="ok">
          <span data-testid="plan-done">{t("plan.done", { name: exported.name })}</span>{" "}
          <button className="link" onClick={() => openFile(exported.token)}>
            {t("report.shareOpen")}
          </button>
        </Notice>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {periods.length === 0 && (
        <Notice>
          {t("mplan.noCalendar")}{" "}
          <button className="link" onClick={() => go("setup")}>
            {t("mplan.openSetup")}
          </button>
        </Notice>
      )}
      {groups.length === 0 ? (
        <Empty
          icon="target"
          title={t("mplan.noIndicators")}
          text={t("mplan.noIndicatorsText")}
          action={
            <button className="btn" onClick={() => go("indicators")}>
              {t("nav.indicators")}
            </button>
          }
        />
      ) : (
        <div className="grid-scroll">
          <table className="table plan-grid" data-testid="plan-grid">
            <thead>
              <tr>
                <th className="sticky">{t("mplan.indicator")}</th>
                <th>{t("mplan.baseline")}</th>
                {periods.map((p) => (
                  <th key={p.id} title={`${p.start} / ${p.end}`}>
                    {lang === "en" ? p.label_en : p.label_fr}
                    {p.state === "locked" && <Icon name="lock" size={12} />}
                  </th>
                ))}
                <th>{t("mplan.total")}</th>
              </tr>
            </thead>
            <tbody>
              {groups.map(({ node, list }) => (
                <GroupRows
                  key={node.id}
                  title={t("common.labelled", {
                    a: [levels.name(node.level), node.code].filter(Boolean).join(" "),
                    b: node.title,
                  })}
                  span={periods.length + 3}
                  list={list}
                  onSheet={setSheet}
                  onSave={save}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {sheet && (
        <SheetPanel
          indicator={snap.indicators.find((i) => i.id === sheet.id) ?? sheet}
          onClose={() => setSheet(null)}
        />
      )}
      {pending && (
        <ReasonPanel
          pending={pending}
          onCancel={() => setPending(null)}
          onConfirm={async (reason) => {
            if (await save(pending.indicator, pending.period, pending.value, reason)) setPending(null);
          }}
        />
      )}
    </div>
  );
}

function GroupRows({
  title,
  span,
  list,
  onSheet,
  onSave,
}: {
  title: string;
  span: number;
  list: Indicator[];
  onSheet: (i: Indicator) => void;
  onSave: (i: Indicator, period: string, value: number | null) => Promise<boolean>;
}) {
  const { t } = useI18n();
  const { snap } = useProject();
  const format = useValueFormat();
  return (
    <>
      <tr className="group-row">
        <td colSpan={span}>{title}</td>
      </tr>
      {list.map((ind) => {
        const pct = ind.unit === "percent";
        const targets = new Map((snap!.targets[ind.id] ?? []).map((x) => [x.period, x]));
        return (
          <tr key={ind.id} data-testid={`plan-row-${ind.name}`}>
            <td className="sticky">
              <button className="link" onClick={() => onSheet(ind)} title={t("mplan.sheet")}>
                {ind.name}
              </button>
              <div className="muted small">{t(`indicators.unit_${ind.unit}`)}</div>
            </td>
            <td className="num muted">{ind.baseline_manual !== null ? format(ind.baseline_manual, ind.unit) : ""}</td>
            {snap!.periods.map((p) => (
              <td key={p.id}>
                <TargetCell
                  target={targets.get(p.code)}
                  percent={pct}
                  locked={p.state === "locked"}
                  label={`${ind.name}, ${p.label_fr}`}
                  testId={`target-${ind.name}-${p.code}`}
                  onCommit={(v) => onSave(ind, p.code, v)}
                />
              </td>
            ))}
            <td>
              <TargetCell
                target={targets.get(TOTAL) ?? (ind.target !== null ? ({ value: ind.target } as Target) : undefined)}
                percent={pct}
                locked={false}
                label={`${ind.name}, ${t("mplan.total")}`}
                testId={`target-${ind.name}-total`}
                onCommit={(v) => onSave(ind, TOTAL, v)}
              />
            </td>
          </tr>
        );
      })}
    </>
  );
}

function TargetCell({
  target,
  percent,
  locked,
  label,
  testId,
  onCommit,
}: {
  target: Target | undefined;
  percent: boolean;
  locked: boolean;
  label: string;
  testId: string;
  onCommit: (v: number | null) => Promise<boolean>;
}) {
  const { t } = useI18n();
  const saved = shown(target?.value, percent);
  // What is being typed; null when the cell shows the saved value.
  const [text, setText] = useState<string | null>(null);
  const revised = (target?.history?.length ?? 0) > 0;
  const commit = async () => {
    if (text === null) return;
    const typed = text.trim();
    const v = parsed(typed, percent);
    if (typed === saved || (typed !== "" && v === null)) {
      setText(null);
      return;
    }
    await onCommit(v);
    setText(null);
  };
  return (
    <input
      className={`input cell${revised ? " revised" : ""}`}
      inputMode="decimal"
      value={text ?? saved}
      disabled={locked && !!target}
      aria-label={label}
      title={revised ? t("mplan.revised", { n: target!.history.length }) : undefined}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") setText(null);
      }}
      data-testid={testId}
    />
  );
}

function ReasonPanel({
  pending,
  onCancel,
  onConfirm,
}: {
  pending: Pending;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const { t } = useI18n();
  const format = useValueFormat();
  const [reason, setReason] = useState("");
  return (
    <Panel
      title={t("mplan.reasonTitle")}
      onClose={onCancel}
      testId="reason-panel"
      footer={
        <>
          <button className="btn" onClick={onCancel}>
            {t("common.cancel")}
          </button>
          <button
            className="btn primary"
            disabled={!reason.trim()}
            onClick={() => onConfirm(reason)}
            data-testid="reason-save"
          >
            {t("mplan.revise")}
          </button>
        </>
      }
    >
      <p>
        {t("mplan.reasonText", {
          name: pending.indicator.name,
          value: format(pending.value, pending.indicator.unit),
        })}
      </p>
      <Field label={t("mplan.reason")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="reason-text"
          />
        )}
      </Field>
    </Panel>
  );
}

function SheetPanel({ indicator, onClose }: { indicator: Indicator; onClose: () => void }) {
  const { t, lang, date } = useI18n();
  const { snap, run } = useProject();
  const format = useValueFormat();
  const [d, setD] = useState<Indicator>({ ...indicator, breakdowns: indicator.breakdowns ?? [] });
  const set = (patch: Partial<Indicator>) => setD({ ...d, ...patch });
  const toggle = (key: string) => {
    const list = d.breakdowns ?? [];
    set({ breakdowns: list.includes(key) ? list.filter((k) => k !== key) : [...list, key] });
  };
  const save = async () => {
    const { id, node_id, ...spec } = d;
    void node_id;
    const s = await run("indicator.save", { id, indicator: spec });
    if (s) onClose();
  };
  const history = (snap!.targets[indicator.id] ?? []).flatMap((x) =>
    x.history.map((h) => ({ ...h, period: x.period, now: x.value })),
  );
  const periodName = (code: string) => {
    if (code === TOTAL) return t("mplan.total");
    const p = snap!.periods.find((x) => x.code === code);
    return p ? (lang === "en" ? p.label_en : p.label_fr) : code;
  };
  return (
    <Panel
      title={indicator.name}
      onClose={onClose}
      testId="sheet-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} data-testid="sheet-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <p className="muted small">{t("mplan.sheetHint")}</p>
      <Field label={t("indicators.source")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={d.source}
            onChange={(e) => set({ source: e.target.value })}
            data-testid="sheet-source"
          />
        )}
      </Field>
      <Field label={t("indicators.method")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={d.method ?? ""}
            onChange={(e) => set({ method: e.target.value })}
            data-testid="sheet-method"
          />
        )}
      </Field>
      <div className="field-row">
        <Field label={t("indicators.frequency")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={d.frequency ?? ""}
              onChange={(e) => set({ frequency: e.target.value as Frequency })}
              data-testid="sheet-frequency"
            >
              {FREQUENCIES.map((f) => (
                <option key={f} value={f}>
                  {f ? t(`indicators.freq_${f}`) : t("indicators.freq_none")}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("indicators.responsible")}>
          {(id) => (
            <input
              id={id}
              className="input"
              value={d.responsible ?? ""}
              onChange={(e) => set({ responsible: e.target.value })}
              data-testid="sheet-responsible"
            />
          )}
        </Field>
      </div>
      <fieldset className="check-list">
        <legend>{t("mplan.breakdowns")}</legend>
        {snap!.disaggregations.length === 0 && <p className="muted small">{t("mplan.noBreakdowns")}</p>}
        {snap!.disaggregations.map((x) => (
          <label key={x.key}>
            <input
              type="checkbox"
              checked={(d.breakdowns ?? []).includes(x.key)}
              onChange={() => toggle(x.key)}
              data-testid={`sheet-breakdown-${x.key}`}
            />{" "}
            {lang === "en" ? x.name_en : x.name_fr}
          </label>
        ))}
      </fieldset>
      {history.length > 0 && (
        <>
          <h3 className="panel-section">{t("mplan.history")}</h3>
          <ul className="plain small" data-testid="sheet-history">
            {history.map((h, i) => (
              <li key={i}>
                {t("mplan.historyLine", {
                  period: periodName(h.period),
                  before: format(h.value, indicator.unit),
                  date: date(h.at),
                  reason: h.reason,
                })}
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
