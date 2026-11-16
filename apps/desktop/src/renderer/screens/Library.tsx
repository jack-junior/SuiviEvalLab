// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Indicator library: reference sheets by sector, searched and added to a result.

import { useEffect, useState } from "react";
import { call } from "../api";
import { useLevels } from "../frameworks";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Field, Panel } from "../ui";

type Text = { fr: string; en: string };
interface Sector {
  key: string;
  name: Text;
  count: number;
}
interface Sheet {
  id: string;
  sector: string;
  name: Text;
  definition: Text;
  type: "percent" | "count" | "mean" | "ratio";
  level: "impact" | "outcome" | "output";
  collection: "routine" | "survey";
  numerator?: Text;
  denominator?: Text;
  benchmark?: Text;
  ref?: string;
  citation: string;
}

export function LibraryPanel({ nodeId, onClose }: { nodeId: string | null; onClose: () => void }) {
  const { t, lang } = useI18n();
  const { snap, run } = useProject();
  const levels = useLevels();
  const results = (snap?.framework ?? []).filter((n) => levels.carries(n.level));
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [sector, setSector] = useState<string>("");
  const [query, setQuery] = useState("");
  const [sheets, setSheets] = useState<Sheet[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [target, setTarget] = useState(nodeId ?? results[0]?.id ?? "");
  const [added, setAdded] = useState<string[]>([]);
  const pick = (x: Text | undefined) => (x ? (lang === "en" ? x.en : x.fr) : "");

  useEffect(() => {
    call<{ sectors: Sector[] }>("library.sectors")
      .then((r) => setSectors(r.sectors))
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      call<{ results: Sheet[] }>("library.search", { query, sector: sector || null })
        .then((r) => live && setSheets(r.results))
        .catch(() => undefined);
    }, 150);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [query, sector]);

  const adopt = async (s: Sheet) => {
    const r = await run("library.adopt", { id: s.id, node_id: target, lang });
    if (r) setAdded([...added, s.id]);
  };
  const inProject = new Set(snap?.indicators.map((i) => i.library_id).filter(Boolean));

  return (
    <Panel title={t("library.title")} onClose={onClose} testId="library-panel">
      <p className="muted small">{t("library.lead")}</p>
      <Field label={t("library.target")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            data-testid="library-node"
          >
            {results.map((n) => (
              <option key={n.id} value={n.id}>
                {levels.name(n.level)} {n.code} {n.title}
              </option>
            ))}
          </select>
        )}
      </Field>
      <input
        className="input"
        type="search"
        placeholder={t("library.search")}
        aria-label={t("library.search")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        data-testid="library-search"
      />
      <div className="chips">
        <button className="chip small" aria-pressed={sector === ""} onClick={() => setSector("")}>
          {t("library.all")}
        </button>
        {sectors.map((s) => (
          <button
            key={s.key}
            className="chip small"
            aria-pressed={sector === s.key}
            onClick={() => setSector(s.key)}
            data-testid={`library-sector-${s.key}`}
          >
            {pick(s.name)} <span className="muted">{s.count}</span>
          </button>
        ))}
      </div>
      {sheets.length === 0 && <p className="muted">{t("library.none")}</p>}
      <ul className="lib-list">
        {sheets.map((s) => {
          const done = added.includes(s.id) || inProject.has(s.id);
          return (
            <li key={s.id} data-testid={`lib-${s.id}`}>
              <div className="row-between">
                <button className="link lib-name" onClick={() => setOpen(open === s.id ? null : s.id)}>
                  {pick(s.name)}
                </button>
                <button
                  className="btn small"
                  disabled={!target || done}
                  onClick={() => adopt(s)}
                  data-testid={`adopt-${s.id}`}
                >
                  {done ? t("library.added") : t("library.add")}
                </button>
              </div>
              <div className="muted small">
                {[t(`indicators.unit_${s.type}`), t(`library.collection_${s.collection}`), s.ref]
                  .filter(Boolean)
                  .join(", ")}
              </div>
              {open === s.id && (
                <div className="lib-detail small">
                  <p>{pick(s.definition)}</p>
                  {s.numerator && (
                    <p>
                      <strong>{t("library.numerator")}</strong> {pick(s.numerator)}
                      <br />
                      <strong>{t("library.denominator")}</strong> {pick(s.denominator)}
                    </p>
                  )}
                  {s.benchmark && <p className="lib-benchmark">{pick(s.benchmark)}</p>}
                  <p className="muted">
                    {s.citation ? t("library.source", { source: s.citation }) : t("library.noSource")}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
