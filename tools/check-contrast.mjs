// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Checks the contrast of the colour tokens of the interface, light and dark
// (WCAG 2.1, level AA: 4.5 for text, 3 for large text and outlines).
//   node tools/check-contrast.mjs

import { readFileSync } from "node:fs";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const css = readFileSync(path.join(root, "apps/desktop/src/renderer/styles.css"), "utf8");

function tokens(block) {
  const out = {};
  for (const m of block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/g)) out[m[1]] = m[2];
  return out;
}
const light = tokens(css.slice(css.indexOf(":root {"), css.indexOf("}", css.indexOf(":root {"))));
const darkStart = css.indexOf(':root[data-theme="dark"] {');
const dark = tokens(css.slice(darkStart, css.indexOf("}", darkStart)));

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function ratio(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

const grounds = ["fond", "surface", "surface-haute", "barre-laterale", "survol"];
const text = ["encre", "encre-2", "encre-3", "action", "laterite", "atteint", "en-cours", "retard"];
const pairs = [
  ...text.flatMap((t) => grounds.map((g) => [t, g, 4.5])),
  ["encre", "action-teinte", 4.5],
  ["action", "action-teinte", 4.5],
  ["en-cours", "en-cours-fond", 4.5],
  ["retard", "retard-fond", 4.5],
  ["sur-action", "action", 4.5],
  ["sur-action", "action-survol", 4.5],
  ["action", "fond", 3],
];

const failures = [];
for (const [name, theme] of [
  ["light", light],
  ["dark", dark],
]) {
  for (const [fg, bg, min] of pairs) {
    if (!theme[fg] || !theme[bg]) {
      failures.push(`${name}: token --${!theme[fg] ? fg : bg} not found`);
      continue;
    }
    const r = ratio(theme[fg], theme[bg]);
    if (r < min) failures.push(`${name}: --${fg} on --${bg} is ${r.toFixed(2)}, needs ${min}`);
  }
}
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`contrast: ${pairs.length * 2} colour pairs meet WCAG AA`);
