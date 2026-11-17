// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Display preferences kept on this computer: theme and text size.

import { setZoom } from "./api";

export const TEXT_SIZES = [0.9, 1, 1.1, 1.25, 1.4, 1.6] as const;

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // not kept: the preference lasts until the application is closed
  }
}

export function textSize(): number {
  const v = Number(read("sme.textSize"));
  return (TEXT_SIZES as readonly number[]).includes(v) ? v : 1;
}

/** Step the text size up (1), down (-1) or back to normal (0); returns the new size. */
export function stepTextSize(step: -1 | 0 | 1): number {
  const sizes = TEXT_SIZES as readonly number[];
  const i = sizes.indexOf(textSize());
  const next = step === 0 ? 1 : sizes[Math.min(sizes.length - 1, Math.max(0, i + step))];
  write("sme.textSize", String(next));
  setZoom(next);
  return next;
}

export function toggleTheme(): void {
  const r = document.documentElement;
  const dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  r.dataset.theme = dark ? "light" : "dark";
  write("sme.theme", r.dataset.theme);
}

/** Applied once at start. */
export function applyDisplay(): void {
  const theme = read("sme.theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  setZoom(textSize());
}
