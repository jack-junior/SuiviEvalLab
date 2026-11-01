// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Checks that every source file starts with the licence and copyright notice.
//   node tools/check-headers.mjs

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const dirs = ["apps/desktop/src", "engine/python/sme_engine", "engine/python/tests", "engine/r", "tools"];
const skip = new Set(["node_modules", "dist", "release", "__pycache__", "fixtures"]);
const exts = /\.(py|R|ts|tsx|mjs|css)$/;
const missing = [];
const walk = (d) => {
  for (const f of readdirSync(d)) {
    if (skip.has(f)) continue;
    const p = path.join(d, f);
    if (statSync(p).isDirectory()) walk(p);
    else if (exts.test(f)) {
      const head = readFileSync(p, "utf8").slice(0, 400);
      if (!head.includes("SPDX-License-Identifier: GPL-3.0-or-later") || !head.includes("Copyright (C)"))
        missing.push(path.relative(root, p));
    }
  }
};
for (const d of dirs) walk(path.join(root, d));
if (missing.length) {
  console.error(`Licence header missing (see CONTRIBUTING.md):\n${missing.join("\n")}`);
  process.exit(1);
}
console.log("headers: every source file carries the licence notice");
