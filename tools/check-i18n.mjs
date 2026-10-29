// Checks that every interface text key used in the code exists in the catalogues.
//   node tools/check-i18n.mjs
// Literal keys t("a.b") must exist; keys built at run time t(`a.${x}`) must match
// at least one key with that prefix. The English catalogue is typed against the
// French one, so both always have the same keys.

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const dir = path.join(root, "apps/desktop/src/renderer");
const catalogue = readFileSync(path.join(dir, "i18n/messages.ts"), "utf8");
const frBlock = catalogue.slice(catalogue.indexOf("export const fr"), catalogue.indexOf("export type MessageKey"));
const keys = new Set([...frBlock.matchAll(/^\s+"([^"]+)":/gm)].map((m) => m[1]));

const files = [];
const walk = (d) => {
  for (const f of readdirSync(d)) {
    const p = path.join(d, f);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.tsx?$/.test(f) && !p.includes(`${path.sep}i18n${path.sep}`)) files.push(p);
  }
};
walk(dir);

const problems = [];
for (const file of files) {
  const src = readFileSync(file, "utf8");
  for (const m of src.matchAll(/\bt\("([a-zA-Z_.]+)"/g)) {
    if (!keys.has(m[1])) problems.push(`${path.relative(root, file)}: unknown key ${m[1]}`);
  }
  for (const m of src.matchAll(/\btn\("([a-zA-Z_.]+)"/g)) {
    for (const form of ["one", "other"])
      if (!keys.has(`${m[1]}_${form}`)) problems.push(`${path.relative(root, file)}: unknown key ${m[1]}_${form}`);
  }
  for (const m of src.matchAll(/\bt\(`([a-zA-Z_.]+)\$\{/g)) {
    if (![...keys].some((k) => k.startsWith(m[1]))) problems.push(`${path.relative(root, file)}: no key starts with ${m[1]}`);
  }
}
if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log(`i18n: ${keys.size} keys, ${files.length} files checked`);
