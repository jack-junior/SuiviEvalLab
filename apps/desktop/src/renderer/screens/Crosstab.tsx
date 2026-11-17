// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Quick crosstab: one indicator by two dimensions (period, place, partner or one
// of its disaggregations), with totals, ready to paste into Excel or Word.

import { useEffect, useState } from "react";
import { call, Crosstab as Table, Indicator } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Field, Notice, Panel, useValueFormat } from "../ui";

export function CrosstabPanel({
  indicators,
  period,
  provisional,
  onClose,
}: {
  indicators: Indicator[];
  period: string | null;
  provisional: boolean;
  onClose: () => void;
}) {
  const { t, lang } = useI18n();
  const { snap, describe } = useProject();
  const format = useValueFormat();
  const [indId, setIndId] = useState(indicators[0]?.id ?? "");
  const ind = indicators.find((i) => i.id === indId);
  const dims = [
    { key: "period", label: t("setup.period") },
    ...(snap?.places.length ? [{ key: "place", label: t("trk.place") }] : []),
    ...(snap?.partners.length ? [{ key: "partner", label: t("trk.partner") }] : []),
    ...(ind?.breakdowns ?? [])
      .map((k) => snap?.disaggregations.find((d) => d.key === k))
      .filter((d) => !!d)
      .map((d) => ({ key: d!.key, label: lang === "en" ? d!.name_en : d!.name_fr })),
  ];
  const [rows, setRows] = useState(dims[1]?.key ?? "period");
  const [cols, setCols] = useState("");
  const [level, setLevel] = useState(0);
  const [data, setData] = useState<Table | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!indId) return;
    let live = true;
    call<Table>("tracking.crosstab", {
      indicator_id: indId,
      rows,
      cols,
      period,
      provisional,
      place_level: level,
      lang,
    })
      .then((r) => {
        if (live) {
          setData(r);
          setError(null);
        }
      })
      .catch((e) => live && setError(describe(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indId, rows, cols, period, provisional, level, lang]);

  const v = (x: number | null) => (x === null || !ind ? "" : format(x, ind.unit));
  const copy = async () => {
    if (!data) return;
    const head = ["", ...data.cols.map((c) => c.label), ...(data.cols.length > 1 ? [t("rec.total")] : [])];
    const body = data.rows.map((r) => [r.label, ...r.values.map(v), ...(data.cols.length > 1 ? [v(r.total)] : [])]);
    const foot = [t("rec.total"), ...data.col_totals.map(v), ...(data.cols.length > 1 ? [v(data.total)] : [])];
    await navigator.clipboard.writeText([head, ...body, foot].map((l) => l.join("\t")).join("\n"));
    setCopied(true);
  };

  return (
    <Panel wide title={t("xt.title")} onClose={onClose} testId="crosstab-panel">
      <p className="muted small">{t("xt.lead")}</p>
      <div className="filters">
        <Field label={t("mplan.indicator")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={indId}
              onChange={(e) => setIndId(e.target.value)}
              data-testid="xt-indicator"
            >
              {indicators.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("xt.rows")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={rows}
              onChange={(e) => setRows(e.target.value)}
              data-testid="xt-rows"
            >
              {dims.map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={t("xt.cols")}>
          {(id) => (
            <select
              id={id}
              className="input"
              value={cols}
              onChange={(e) => setCols(e.target.value)}
              data-testid="xt-cols"
            >
              <option value="">{t("xt.none")}</option>
              {dims
                .filter((d) => d.key !== rows)
                .map((d) => (
                  <option key={d.key} value={d.key}>
                    {d.label}
                  </option>
                ))}
            </select>
          )}
        </Field>
        {(rows === "place" || cols === "place") && snap && (
          <Field label={t("xt.level")}>
            {(id) => (
              <select id={id} className="input" value={level} onChange={(e) => setLevel(Number(e.target.value))}>
                {snap.profile.place_levels.map((l, i) => (
                  <option key={l} value={i}>
                    {l}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        <button className="btn" onClick={copy} disabled={!data} data-testid="xt-copy">
          {copied ? t("xt.copied") : t("xt.copy")}
        </button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {data && (
        <div className="grid-scroll">
          <table className="table compact" data-testid="xt-table">
            <thead>
              <tr>
                <th />
                {data.cols.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
                {data.cols.length > 1 && <th>{t("rec.total")}</th>}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.key}>
                  <td>{r.label}</td>
                  {r.values.map((x, i) => (
                    <td key={i} className="num">
                      {v(x)}
                    </td>
                  ))}
                  {data.cols.length > 1 && (
                    <td className="num">
                      <strong>{v(r.total)}</strong>
                    </td>
                  )}
                </tr>
              ))}
              <tr className="total-row">
                <td>
                  <strong>{t("rec.total")}</strong>
                </td>
                {data.col_totals.map((x, i) => (
                  <td key={i} className="num">
                    <strong>{v(x)}</strong>
                  </td>
                ))}
                {data.cols.length > 1 && (
                  <td className="num">
                    <strong>{v(data.total)}</strong>
                  </td>
                )}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
