// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Helpers shared by the reception, tracking, agenda and today screens.

import { Disaggregation, Indicator, Period, ReportingUnit, Snapshot } from "./api";

export const todayIso = () => new Date().toISOString().slice(0, 10);

export const periodLabel = (p: Period | undefined, lang: string) =>
  p ? (lang === "en" ? p.label_en : p.label_fr) : "";

/** The period to work on by default: the last one ended, else the current one. */
export function defaultPeriod(periods: Period[], today = todayIso()): string | null {
  if (!periods.length) return null;
  const ended = periods.filter((p) => p.end < today);
  if (ended.length) return ended[ended.length - 1].code;
  const current = periods.find((p) => p.start <= today && today <= p.end);
  return (current ?? periods[0]).code;
}

export function unitName(snap: Snapshot, u: ReportingUnit, whole: string): string {
  const partner = snap.partners.find((p) => p.id === u.partner_id);
  const place = snap.places.find((p) => p.id === u.place_id);
  const parts = [partner?.acronym || partner?.name, place?.name].filter(Boolean);
  return parts.length ? parts.join(", ") : whole;
}

export const unitKey = (u: ReportingUnit) => `${u.partner_id}|${u.place_id}`;

export const catsKey = (cats: Record<string, string>) =>
  Object.keys(cats)
    .sort()
    .map((k) => `${k}=${cats[k]}`)
    .join(";");

export interface CellDef {
  key: string;
  cats: Record<string, string>;
  label: string;
}

/** The cells of an indicator: every combination of its disaggregations, at the finest level. */
export function cellsOf(ind: Indicator, dis: Disaggregation[], lang: string, unspecified: string): CellDef[] {
  const keys = (ind.breakdowns ?? []).filter((k) => dis.some((d) => d.key === k));
  if (!keys.length) return [];
  let combos: Record<string, string>[] = [{}];
  for (const k of keys) {
    const d = dis.find((x) => x.key === k)!;
    const codes = [...d.categories.map((c) => c.code), "_na"];
    combos = combos.flatMap((c) => codes.map((code) => ({ ...c, [k]: code })));
  }
  return combos.map((cats) => ({
    key: catsKey(cats),
    cats,
    label: keys
      .map((k) => {
        const d = dis.find((x) => x.key === k)!;
        const c = d.categories.find((x) => x.code === cats[k]);
        return c ? (lang === "en" ? c.en : c.fr) : unspecified;
      })
      .join(", "),
  }));
}

/** Kind of entry of an indicator type. */
export function entryKind(unit: string): "fraction" | "count" | "mean" | "level" | "milestone" {
  if (unit === "percent" || unit === "rate" || unit === "ratio") return "fraction";
  if (unit === "count") return "count";
  if (unit === "mean") return "mean";
  if (unit === "milestone") return "milestone";
  return "level";
}

export const toNumber = (s: string): number | null => {
  const v = Number(
    s
      .replace(/[\s\u00a0\u202f]/g, "")
      .replace(",", ".")
      .replace(/%$/, ""),
  );
  return s.trim() === "" || Number.isNaN(v) ? null : v;
};
