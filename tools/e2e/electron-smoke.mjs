// End-to-end test of the app: the whole path on real data, in the installed app.
//
//   node tools/e2e/electron-smoke.mjs apps/desktop/release/win-unpacked/SuiviEvalLab.exe
//   E2E_LOCAL=1 node tools/e2e/electron-smoke.mjs apps/desktop   (development build, Linux)
//
// 1. Manual path: new project, framework, import of the two real datasets, a
//    cleaning rule, an indicator, analysis with comparison, Word report.
// 2. Example project: overview with the three indicators.
// 3. Language switch.
// File dialogs are answered through SME_E2E_DIALOGS. Selectors use data-testid
// only, so the test does not depend on the interface language. Screenshots go
// to build/e2e.

import { _electron as electron } from "playwright";
import { existsSync, mkdirSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const target = path.resolve(process.argv[2]);
const local = process.env.E2E_LOCAL === "1";
const notice = (title, msg) => console.log(`::notice title=${title}::${msg}`);
const shots = path.resolve("build/e2e");
mkdirSync(shots, { recursive: true });
const work = mkdtempSync(path.join(tmpdir(), "sme-e2e-"));

const examples = local
  ? path.resolve("engine/python/sme_engine/examples")
  : path.join(path.dirname(target), "resources", "engine", "python", "sme_engine", "examples");
const file2019 = path.join(examples, "mcna_irak_2019.xlsx");
const file2020 = path.join(examples, "mcna_irak_2020.xlsx");
if (!existsSync(file2019)) throw new Error(`Example data not found: ${file2019}`);

const dialogs = [
  path.join(work, "manuel.sme"),
  file2019,
  file2020,
  path.join(work, "rapport-manuel.docx"),
  path.join(work, "exemple.sme"),
];

const app = await electron.launch(
  local
    ? {
        executablePath: path.join(target, "node_modules/electron/dist/electron"),
        args: ["--no-sandbox", target],
        env: { ...process.env, SME_E2E_DIALOGS: dialogs.join("|") },
        timeout: 60_000,
      }
    : { executablePath: target, env: { ...process.env, SME_E2E_DIALOGS: dialogs.join("|") }, timeout: 60_000 },
);

try {
  const page = await app.firstWindow();
  await page.setViewportSize({ width: 1320, height: 840 }).catch(() => undefined);
  const id = (x) => page.locator(`[data-testid="${x}"]`);
  const shot = (name) => page.screenshot({ path: path.join(shots, `${name}.png`) });

  await id("lang-fr").click();
  await id("engine-ready").first().waitFor({ timeout: 150_000 });
  notice("E2E", "Engines ready");

  // 1. Manual path
  await id("new-project").click();
  await id("new-name").fill("Projet test");
  await id("new-create").click();
  await id("add-impact").click();
  await id("node-title").fill("Les enfants accèdent à l'éducation");
  await id("node-save").click();
  await page.locator(".tree-row").first().hover();
  await id("node-add-child").first().click();
  await id("node-title").fill("L'accès aux écoles s'améliore");
  await id("node-save").click();
  await page.locator(".tree-row").nth(1).waitFor();

  for (const round of ["baseline", "endline"]) {
    await id("nav-data").click();
    if (round === "endline") await id("data-back").click().catch(() => undefined);
    await id("import-data").first().click();
    await id("choose-file").click();
    await page.locator('[data-testid="import-confirm"]:not([disabled])').waitFor({ timeout: 60_000 });
    await id(`round-${round}`).click();
    await id("import-confirm").click();
    await id("tab-cleaning").waitFor({ timeout: 120_000 });
  }
  // A cleaning rule on the endline dataset: "do_not_know" becomes missing.
  await id("add-rule").click();
  await id("kind-recode").click();
  await id("rule-column").selectOption("primary_school_place");
  await id("rvalue-do_not_know").check();
  await id("rule-note").fill("Ne sait pas : valeur manquante");
  await id("rule-save").click();
  await page.locator(".journal-row").first().waitFor();
  const effect = await page.locator(".journal-effect").first().innerText();
  notice("E2E cleaning", effect);
  await shot("manual-journal");

  await id("nav-indicators").click();
  await id("add-indicator").click();
  await id("indicator-name").fill("Ménages avec une école primaire à moins de 2 km");
  await id("indicator-column").selectOption("primary_school_place");
  await id("value-within_2km").check({ timeout: 30_000 });
  await id("indicator-target").fill("90");
  await id("indicator-save").click();
  await page.locator(".ind-row").first().waitFor();

  await id("nav-analysis").click();
  await id("comparison").waitFor({ timeout: 120_000 });
  const current = await id("current-value").innerText();
  const comparison = await id("comparison").innerText();
  notice("E2E analysis", `${current} | ${comparison.replace(/\s+/g, " ").slice(0, 300)}`);
  // Unweighted (no design was set): 2020 share of within_2km among valid answers.
  if (!/\d+,\d\s?%/.test(current)) throw new Error(`Unexpected current value: ${current}`);
  await shot("manual-analysis");

  await id("nav-report").click();
  await id("generate-report").click();
  await id("report-done").waitFor({ timeout: 180_000 });
  const report = path.join(work, "rapport-manuel.docx");
  if (!existsSync(report) || statSync(report).size < 20_000) throw new Error("Word report missing or too small");
  notice("E2E report", `Word report written, ${Math.round(statSync(report).size / 1024)} KB`);

  // 2. Example project
  await id("close-project").click();
  await id("open-example").click();
  await id("overview-table").waitFor({ timeout: 180_000 });
  await page.locator('[data-testid^="status-"]').nth(2).waitFor({ timeout: 180_000 });
  const statuses = await page.locator('[data-testid="overview-table"] [data-testid^="status-"]').evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-testid")),
  );
  notice("E2E example", statuses.join(", "));
  if (statuses.length !== 3 || statuses.includes("status-unknown")) throw new Error(`Unexpected statuses: ${statuses}`);
  await shot("example-overview-fr");

  // 3. Language
  await id("lang-en").click();
  const label = await id("nav-overview").innerText();
  if (!label.includes("Overview")) throw new Error(`English label expected, got: ${label}`);
  const htmlLang = await page.evaluate(() => document.documentElement.lang);
  if (htmlLang !== "en") throw new Error(`html lang should be "en", got: ${htmlLang}`);
  await id("theme").click();
  await id("nav-analysis").click();
  await id("rounds-table").waitFor({ timeout: 120_000 });
  await shot("example-analysis-en-dark");
  notice("E2E", "Full path verified: framework, import, cleaning, indicator, analysis, report, example, languages");
} finally {
  await app.close();
  rmSync(work, { recursive: true, force: true });
}
