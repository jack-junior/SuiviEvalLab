// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// End-to-end test of the app: the whole path on real data, in the installed app.
//
//   node tools/e2e/electron-smoke.mjs apps/desktop/release/win-unpacked/SuiviEvalLab.exe
//   E2E_LOCAL=1 node tools/e2e/electron-smoke.mjs apps/desktop   (development build, Linux)
//
// 1. Manual path: new project, framework, import of the two real datasets, a
//    cleaning rule, an indicator, analysis with comparison, Word report, an SPSS
//    file with its labels, a merge of containers with their households, and the
//    read-only HTML dashboard.
// 2. Example project: overview with the three indicators, a statistical test.
// 3. Language switch.
// File dialogs are answered through SME_E2E_DIALOGS. Selectors use data-testid
// only, so the test does not depend on the interface language. Screenshots go
// to build/e2e.

import { _electron as electron } from "playwright";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
} from "node:fs";
import { createServer } from "node:http";
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
  : path.join(
      path.dirname(target),
      "resources",
      "engine",
      "python",
      "sme_engine",
      "examples",
    );
const file2019 = path.join(examples, "mcna_irak_2019.xlsx");
const file2020 = path.join(examples, "mcna_irak_2020.xlsx");
if (!existsSync(file2019))
  throw new Error(`Example data not found: ${file2019}`);
// Test files from the repository (the test runs from the repository root).
const fixtures = path.resolve("engine/python/tests/fixtures");
const fileSav = path.join(fixtures, "wash_bgd_2018.sav");
const fileMerge = path.join(fixtures, "wash_bgd_containers.xlsx");

const dialogs = [
  path.join(work, "manuel.sme"),
  file2019,
  file2020,
  path.join(work, "rapport-manuel.docx"),
  fileSav,
  fileMerge,
  fileMerge,
  path.join(work, "nettoyage.R"),
  path.join(work, "tableau.html"),
  path.join(work, "plan.xlsx"),
  path.join(work, "exemple.sme"),
];

// A local server answering like KoboToolbox, for the server synchronisation.
const KOBO_TOKEN = "e2e-token";
const kobo = createServer((req, res) => {
  const send = (code, body) => {
    res.writeHead(code, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
  };
  if (req.headers.authorization !== `Token ${KOBO_TOKEN}`)
    return send(401, { detail: "bad token" });
  const url = new URL(req.url, "http://127.0.0.1");
  if (url.pathname === "/api/v2/assets/")
    return send(200, {
      next: null,
      results: [
        {
          uid: "aE2E",
          name: "Suivi des ménages",
          asset_type: "survey",
          has_deployment: true,
          deployment__submission_count: 3,
        },
      ],
    });
  if (url.pathname === "/api/v2/assets/aE2E/")
    return send(200, {
      content: {
        translations: [null],
        survey: [
          { type: "integer", name: "taille", label: ["Taille du ménage"] },
          {
            type: "select_one",
            select_from_list_name: "yn",
            name: "ecole",
            label: ["École à 2 km"],
          },
        ],
        choices: [
          { list_name: "yn", name: "oui", label: ["Oui"] },
          { list_name: "yn", name: "non", label: ["Non"] },
        ],
      },
    });
  if (url.pathname === "/api/v2/assets/aE2E/data/")
    return send(200, {
      next: null,
      results: [
        { _id: 1, taille: "5", ecole: "oui", _submission_time: "2026-02-01" },
        { _id: 2, taille: "3", ecole: "non", _submission_time: "2026-02-02" },
        { _id: 3, taille: "8", ecole: "oui", _submission_time: "2026-02-03" },
      ],
    });
  send(404, {});
});
await new Promise((ok) => kobo.listen(0, "127.0.0.1", ok));
const koboUrl = `http://127.0.0.1:${kobo.address().port}`;
const env = {
  ...process.env,
  SME_E2E_DIALOGS: dialogs.join("|"),
  NO_PROXY: "127.0.0.1,localhost",
  no_proxy: "127.0.0.1,localhost",
};

const app = await electron.launch(
  local
    ? {
        executablePath: path.join(
          target,
          "node_modules/electron/dist/electron",
        ),
        args: ["--no-sandbox", target],
        env,
        timeout: 60_000,
      }
    : {
        executablePath: target,
        env,
        timeout: 60_000,
      },
);

try {
  const page = await app.firstWindow();
  await page
    .setViewportSize({ width: 1320, height: 840 })
    .catch(() => undefined);
  const id = (x) => page.locator(`[data-testid="${x}"]`);
  const shot = (name) =>
    page.screenshot({ path: path.join(shots, `${name}.png`) });

  await id("lang-fr").click();
  await id("engine-ready").first().waitFor({ timeout: 150_000 });
  notice("E2E", "Engines ready");

  // 1. Manual path (from the Projects screen, whatever the workspace opened on)
  await id("nav-overview").click();
  await id("new-project").click();
  await id("new-name").fill("Projet test");
  await id("new-create").click();
  // A new project opens on its sheet: dates, then the calendar is made from them.
  await id("profile-form").waitFor({ timeout: 60_000 });
  await id("profile-start").fill("2026-01-01");
  await id("profile-end").fill("2027-12-31");
  await id("profile-save").click();
  await id("setup-tab-calendar").click();
  await id("period-T1-2026").waitFor({ timeout: 60_000 });
  const periods = await page.locator('[data-testid^="period-T"]').count();
  if (periods !== 8) throw new Error(`Expected 8 quarters, got ${periods}`);
  await id("setup-tab-disaggregations").click();
  await id("preset-sex").click();
  await id("dis-sex").waitFor({ timeout: 60_000 });
  await shot("project-sheet");
  await id("nav-framework").click();
  await id("add-impact").click();
  await id("node-title").fill("Les enfants accèdent à l'éducation");
  await id("node-save").click();
  await page.locator(".tree-row").first().hover();
  await id("node-add-child").first().click();
  await id("node-title").fill("L'accès aux écoles s'améliore");
  // Typed key by key in a second field: the cursor must stay there (it used to go
  // back to the first field of the panel at every key).
  await id("node-assumptions").click();
  await id("node-assumptions").pressSequentially("Pas de conflit", {
    delay: 30,
  });
  const typed = await id("node-assumptions").inputValue();
  const title = await id("node-title").inputValue();
  if (typed !== "Pas de conflit" || title !== "L'accès aux écoles s'améliore")
    throw new Error(`Typing in a second field failed: "${title}" / "${typed}"`);
  await id("node-save").click();
  await page.locator(".tree-row").nth(1).waitFor();

  for (const round of ["baseline", "endline"]) {
    await id("nav-data").click();
    if (round === "endline")
      await id("data-back")
        .click()
        .catch(() => undefined);
    await id("import-data").first().click();
    await id("choose-file").click();
    await page
      .locator('[data-testid="import-confirm"]:not([disabled])')
      .waitFor({ timeout: 60_000 });
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

  // Free cleaning: a formula, then a cell corrected in the data table.
  await id("add-rule").click();
  await id("kind-formula").click();
  await id("rule-target").fill("ecole_proche");
  await id("formula-text").fill(
    'si(primary_school_place = "within_2km"; 1; 0)',
  );
  await id("formula-preview").waitFor({ timeout: 60_000 });
  await id("rule-save").click();
  await page.locator(".journal-row").nth(1).waitFor();
  await id("tab-preview").click();
  await id("data-grid").waitFor({ timeout: 60_000 });
  const cell = page
    .locator('[data-testid^="cell-"][data-testid$="-ecole_proche"]')
    .first();
  const cellId = await cell.getAttribute("data-testid");
  await cell.dblclick();
  await id("cell-input").fill("0");
  await id("cell-input").press("Enter");
  await page
    .locator(`[data-testid="${cellId}"].edited`)
    .waitFor({ timeout: 60_000 });
  notice("E2E data table", `${cellId} corrected and added to the journal`);
  await id("tab-cleaning").click();
  await page.locator(".journal-row").nth(2).waitFor();

  await id("nav-indicators").click();
  await id("add-indicator").click();
  await id("indicator-name").fill(
    "Ménages avec une école primaire à moins de 2 km",
  );
  await id("indicator-column").selectOption("primary_school_place");
  await id("value-within_2km").check({ timeout: 30_000 });
  await id("indicator-target").click();
  await id("indicator-target").pressSequentially("90", { delay: 30 });
  if ((await id("indicator-target").inputValue()) !== "90")
    throw new Error("Typing in the indicator target failed");
  await id("indicator-save").click();
  await page.locator(".ind-row").first().waitFor();

  // Monitoring plan: a target per quarter; changing it asks for a reason.
  await id("nav-plan").click();
  const q1 = page.locator('[data-testid$="-T1-2026"][data-testid^="target-"]');
  await q1.fill("40");
  await q1.press("Enter");
  await page.waitForTimeout(500);
  await q1.fill("35");
  await q1.press("Enter");
  await id("reason-panel").waitFor({ timeout: 30_000 });
  await id("reason-text").fill("Rentrée scolaire décalée");
  await id("reason-save").click();
  await page
    .locator('[data-testid$="-T1-2026"].revised')
    .waitFor({ timeout: 30_000 });
  if ((await q1.inputValue()) !== "35")
    throw new Error("Revised target not shown");
  await shot("monitoring-plan");

  // An indicator with periodic entry, broken down by sex.
  await id("nav-indicators").click();
  await id("add-indicator").click();
  await id("source-routine").click();
  await id("unit-count").click();
  await id("indicator-name").fill("Enseignants formés");
  await id("breakdown-sex").check();
  await id("indicator-target").fill("100");
  await id("indicator-save").click();
  await page.locator(".ind-row", { hasText: "Enseignants formés" }).waitFor();

  // Reception: the values of the first quarter, entered by sex, then validated.
  await id("nav-reception").click();
  await id("rec-period-T1-2026").click();
  await page
    .locator('[data-testid="rec-row-Le projet"] [data-testid="rec-open"]')
    .click();
  await id("entry-panel").waitFor();
  await id("cell-Enseignants formés-sex=f").fill("12");
  await id("cell-Enseignants formés-sex=m").fill("8");
  await id("entry-save").click();
  await page.waitForTimeout(300);
  await id("entry-validate").click();
  await page
    .locator('[data-testid="entry-panel"] [data-testid="sub-status"]', {
      hasText: "Validé",
    })
    .waitFor({ timeout: 30_000 });
  await shot("reception-entry");
  await page.keyboard.press("Escape");
  await page
    .locator('[data-testid="rec-row-Le projet"] [data-testid="sub-status"]', {
      hasText: "Validé",
    })
    .waitFor({ timeout: 30_000 });

  // Tracking: 20 teachers trained to date in the first quarter.
  await id("nav-tracking").click();
  await id("trk-period").selectOption("T1-2026");
  const toDate = page.locator(
    '[data-testid="trk-row-Enseignants formés"] [data-testid="trk-to-date"]',
  );
  await toDate.filter({ hasText: "20" }).waitFor({ timeout: 30_000 });
  await id("trk-gap-Enseignants formés").click();
  await id("gap-text").fill("Formateurs disponibles à partir de mars");
  await id("gap-save").click();
  await shot("tracking");
  await id("trk-crosstab").click();
  await id("xt-rows").selectOption("period");
  await id("xt-cols").selectOption("sex");
  await page
    .locator('[data-testid="xt-table"] td', { hasText: "12" })
    .first()
    .waitFor({ timeout: 30_000 });
  await shot("crosstab");
  await page.keyboard.press("Escape");

  // Today and agenda of the project.
  await id("nav-today").click();
  await id("project-today").waitFor();
  await page
    .locator('[data-testid^="todo-"]')
    .first()
    .waitFor({ timeout: 30_000 });
  notice(
    "E2E today",
    (await id("today-tasks").innerText()).replace(/\s+/g, " ").slice(0, 200),
  );
  await shot("project-today");
  await id("nav-agenda").click();
  await id("calendar").waitFor();
  await id("agenda-add-event").click();
  await id("event-title").fill("Mission de suivi à Kara");
  await id("event-save").click();
  await page
    .locator(".cal-item", { hasText: "Mission de suivi" })
    .first()
    .waitFor({ timeout: 30_000 });
  await shot("agenda");
  await id("agenda-mode-board").click();
  await id("board-todo").waitFor();
  await shot("task-board");

  // Activities and budget: an activity already late, the M&E activities of the
  // plan, a budget line and an expense.
  await id("nav-workplan").click();
  await id("wp-add").click();
  await id("activity-title").fill("Former les relais communautaires");
  await id("activity-start").fill("2026-01-05");
  await id("activity-end").fill("2026-02-27");
  await id("activity-save").click();
  await id("act-Former les relais communautaires").waitFor();
  await id("wp-generate").click();
  await page.locator(".notice", { hasText: "S&E" }).first().waitFor();
  await id("wp-tab-timeline").click();
  await page.locator(".gantt-bar").first().waitFor();
  await shot("workplan-timeline");
  await id("wp-tab-budget").click();
  await id("line-add").click();
  await id("line-name").fill("Formations");
  await page.locator('[data-testid^="line-amount-"]').first().fill("1000");
  await id("line-save").click();
  await id("line-Formations").waitFor();
  await id("expense-add").click();
  await id("expense-amount").fill("250");
  await id("expense-save").click();
  await page
    .locator('[data-testid="budget-spent"]', { hasText: "250" })
    .waitFor();
  notice(
    "E2E work plan",
    (await id("wp-kpis").innerText()).replace(/\s+/g, " ").slice(0, 200),
  );
  await shot("workplan-budget");

  // Accountability: a complaint, a recommendation with its action, a risk, a
  // meeting whose decision becomes a task.
  await id("nav-accountability").click();
  await id("fb-add").click();
  await id("fb-summary").fill("Distribution en retard au site de Kara");
  await id("fb-save").click();
  await id("fb-row").first().waitFor();
  await id("acc-tab-recommendations").click();
  await id("rec-add").click();
  await id("rec-text").fill("Renforcer la supervision des relais");
  await id("rec-resp-accepted").click();
  await id("rec-action-add").click();
  await id("rec-action-text").fill("Recruter un superviseur");
  await id("rec-action-due").fill("2026-03-31");
  await id("rec-save").click();
  await id("rec-row").first().waitFor();
  await id("acc-tab-risks").click();
  await id("risk-from-logframe").click();
  await id("risk-row").first().waitFor();
  await id("risk-add").click();
  await id("risk-title").fill("Saison des pluies");
  await id("risk-save").click();
  await page
    .locator('[data-testid="risk-row"]', { hasText: "Saison" })
    .waitFor();
  await shot("risks");
  await id("acc-tab-learning").click();
  await id("meeting-add").click();
  await id("meeting-title").fill("Revue trimestrielle");
  await id("decision-add").click();
  await id("decision-text").fill("Relancer le partenaire");
  await id("meeting-save").click();
  await page.locator(".link", { hasText: "Revue trimestrielle" }).waitFor();

  // Evaluation: sheet, a question, a note coded by theme.
  await id("nav-evaluations").click();
  await id("ev-add").click();
  await id("ev-title").fill("Évaluation à mi-parcours");
  await id("ev-date-draft").fill("2026-12-15");
  await id("ev-save").click();
  await id("ev-view").waitFor();
  await id("ev-tab-questions").click();
  await id("evq-add").click();
  await id("evq-text").fill("Les relais ont-ils amélioré la fréquentation ?");
  await id("evq-save").click();
  await id("evq-row").waitFor();
  await id("ev-tab-qualitative").click();
  await id("themes-open").click();
  await id("theme-name").fill("Accès");
  await id("theme-add").click();
  await page
    .locator('[data-testid="themes-panel"] li', { hasText: "Accès" })
    .waitFor();
  await page.keyboard.press("Escape");
  await id("note-add").click();
  await id("note-title").fill("Groupe de femmes, Kara");
  await id("note-text").fill(
    "Le centre est loin. Les femmes viennent moins pendant les pluies.",
  );
  await id("note-save").click();
  await id("note-Groupe de femmes, Kara").click();
  await id("coding-text").waitFor();
  await page.evaluate(() => {
    const box = document.querySelector('[data-testid="coding-text"]');
    const node = box.firstChild.firstChild;
    const range = document.createRange();
    range.setStart(node, 20);
    range.setEnd(node, node.textContent.length);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    box.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await id("code-theme-Accès").check();
  await id("code-save").click();
  await page.locator('[data-testid="coding-text"] mark').first().waitFor();
  await shot("coding");
  await page.keyboard.press("Escape");
  await id("theme-summary").waitFor();

  // The project's today lists the late activity and the late action.
  await id("nav-today").click();
  const followUp = await id("today-registers").innerText();
  notice("E2E today follow-up", followUp.replace(/\s+/g, " ").slice(0, 240));
  if (!/Former les relais/.test(followUp) || !/supervision/.test(followUp))
    throw new Error(`Today misses the follow-up: ${followUp}`);

  await id("nav-analysis").click();
  await id("comparison").waitFor({ timeout: 120_000 });
  const current = await id("current-value").innerText();
  const comparison = await id("comparison").innerText();
  notice(
    "E2E analysis",
    `${current} | ${comparison.replace(/\s+/g, " ").slice(0, 300)}`,
  );
  // Unweighted (no design was set): 2020 share of within_2km among valid answers.
  if (!/\d+,\d\s?%/.test(current))
    throw new Error(`Unexpected current value: ${current}`);
  await shot("manual-analysis");

  // Custom analyses: a crosstab with its test and reading.
  await id("nav-workshop").click();
  await id("atype-crosstab").click();
  await id("analysis-dataset").selectOption({ index: 1 }); // the endline file, where ecole_proche was created
  await id("a-row").selectOption("population_group");
  await id("a-column").selectOption("ecole_proche");
  await id("analysis-reading").waitFor({ timeout: 180_000 });
  await id("analysis-chart").waitFor({ timeout: 60_000 });
  const reading = await id("analysis-reading").innerText();
  notice("E2E custom analysis", reading.replace(/\s+/g, " ").slice(0, 300));
  if (!/khi-deux|chi-square/.test(reading))
    throw new Error(`Unexpected reading: ${reading}`);
  await shot("manual-workshop");

  await id("nav-report").click();
  await id("report-content").waitFor();
  await id("generate-report").click();
  await id("report-done").waitFor({ timeout: 180_000 });
  const report = path.join(work, "rapport-manuel.docx");
  if (!existsSync(report) || statSync(report).size < 20_000)
    throw new Error("Word report missing or too small");
  notice(
    "E2E report",
    `Word report written, ${Math.round(statSync(report).size / 1024)} KB`,
  );

  // SPSS file: its variable labels come with it.
  const importFile = async (sheet, name) => {
    await id("nav-data").click();
    await id("data-back")
      .click()
      .catch(() => undefined);
    await id("import-data").first().click();
    await id("choose-file").click();
    await page
      .locator('[data-testid="import-confirm"]:not([disabled])')
      .waitFor({ timeout: 60_000 });
    if (sheet) {
      await id("import-sheet").selectOption(sheet);
      await page
        .locator('[data-testid="import-confirm"]:not([disabled])')
        .waitFor({ timeout: 60_000 });
    }
    if (name) await id("dataset-name").fill(name);
    await id("round-monitoring").click();
    await id("import-confirm").click();
    await id("tab-cleaning").waitFor({ timeout: 120_000 });
  };
  await importFile(null);
  await id("tab-columns").click();
  await page.getByText("How old are you?").first().waitFor({ timeout: 30_000 });
  notice("E2E SPSS", "SPSS file imported with its variable labels");
  await id("tab-quality").click();
  await id("quality").waitFor({ timeout: 60_000 });
  notice(
    "E2E quality",
    (await id("quality").innerText()).replace(/\s+/g, " ").slice(0, 200),
  );

  // Merge: water containers (a Kobo repeat) with their household.
  await importFile("Menages", "Menages");
  await importFile("Contenants", "Contenants");
  await id("data-back").click();
  await id("merge-data").click();
  await id("merge-left").selectOption({ label: "Contenants" });
  await id("merge-right").selectOption({ label: "Menages" });
  await id("merge-check").waitFor({ timeout: 60_000 });
  notice(
    "E2E merge check",
    (await id("merge-check").innerText()).replace(/\s+/g, " "),
  );
  await shot("merge-panel");
  await id("merge-confirm").click();
  await id("merge-line").waitFor({ timeout: 60_000 });

  // Advanced cleaning on the merged file: volume classes, then a consistency check
  // on the created column, then the journal as an R script.
  const volume = "water_collection/containers_group/volume";
  await id("add-rule").click();
  await id("kind-classes").click();
  await id("rule-column").selectOption(volume);
  await id("class-to-0").fill("10");
  await id("class-label-0").fill("Petit");
  await id("class-from-1").fill("10");
  await id("class-label-1").fill("Grand");
  await id("rule-target").fill("taille_contenant");
  await shot("advanced-rule");
  await id("rule-save").click();
  await page.locator(".journal-row").first().waitFor();
  await id("add-rule").click();
  await id("kind-check").click();
  await id("cond-column-0").selectOption(volume);
  await id("cond-op-0").selectOption("gt");
  await id("cond-value-0").fill("100");
  await id("rule-target").fill("volume_suspect");
  await id("rule-save").click();
  await page.locator(".journal-row").nth(1).waitFor();
  const journal = (await id("journal").innerText()).replace(/\s+/g, " ");
  if (!journal.includes("Nouvelle variable « taille_contenant »"))
    throw new Error(`Advanced rule not described: ${journal}`);
  notice("E2E advanced cleaning", journal.slice(0, 240));
  await id("tab-columns").click();
  await page.getByText("taille_contenant").first().waitFor({ timeout: 30_000 });
  await id("tab-cleaning").click();
  await id("export-r").click();
  await page
    .locator(".notice")
    .filter({ hasText: "Script R" })
    .waitFor({ timeout: 60_000 });
  const script = readFileSync(path.join(work, "nettoyage.R"), "utf-8");
  if (
    !script.includes("taille_contenant") ||
    !existsSync(path.join(work, "nettoyage_brut.csv"))
  )
    throw new Error("R script incomplete");
  notice("E2E R script", `${script.split("\n").length} lines`);

  // Stacking two files.
  await id("data-back").click();
  await id("stack-data").click();
  await id("stack-file-Menages").check();
  await id("stack-file-Contenants").check();
  await id("stack-check").waitFor({ timeout: 60_000 });
  notice(
    "E2E stack check",
    (await id("stack-check").innerText()).replace(/\s+/g, " "),
  );
  await shot("stack-panel");
  await id("stack-confirm").click();
  await id("stack-line").waitFor({ timeout: 60_000 });

  // Read-only dashboard.
  await id("nav-report").click();
  await id("share-dashboard").click();
  await id("share-done").waitFor({ timeout: 180_000 });
  const board = readFileSync(path.join(work, "tableau.html"), "utf-8");
  if (!board.includes("Lecture seule") || !board.includes("<svg"))
    throw new Error("Dashboard incomplete");
  notice(
    "E2E share",
    `Dashboard written, ${Math.round(board.length / 1024)} KB`,
  );

  // Checks before the report.
  await id("report-checks").waitFor({ timeout: 120_000 });
  notice(
    "E2E checks",
    (await id("report-checks").innerText()).replace(/\s+/g, " ").slice(0, 200),
  );
  await shot("report-checks");

  // The monitoring plan in Excel, from its own screen.
  await id("nav-plan").click();
  await id("plan-export").click();
  await id("plan-done").waitFor({ timeout: 120_000 });
  if (statSync(path.join(work, "plan.xlsx")).size < 5_000)
    throw new Error("Monitoring plan too small");

  // 2. Example project
  await id("close-project").click();

  // Workspace today: the tasks of every project.
  await id("nav-ws_today").click();
  await id("workspace-today").waitFor();
  await page
    .locator('[data-testid^="todo-"]')
    .first()
    .waitFor({ timeout: 60_000 });
  await shot("workspace-today");
  await id("nav-overview").click();

  // Workspace: the project card shows its calendar, and the next deadline is listed.
  await id("ws-card").first().waitFor({ timeout: 60_000 });
  await id("ws-deadlines").waitFor({ timeout: 60_000 });
  notice(
    "E2E workspace",
    (await id("ws-card").first().innerText())
      .replace(/\s+/g, " ")
      .slice(0, 200),
  );
  await shot("workspace");

  // Sample size, from the home screen without a project.
  await id("open-sample").click();
  await id("ss-goal-compare_prop").click();
  await id("sample-result").waitFor({ timeout: 60_000 });
  const sample = await id("sample-result").innerText();
  notice("E2E sample size", sample.split("\n")[0]);
  if (!/\d/.test(sample)) throw new Error(`Unexpected sample size: ${sample}`);
  await shot("sample-size");
  await page.keyboard.press("Escape");
  await id("open-example").click();
  // The example opens on its day of work; its survey results are in the overview.
  await id("project-today").waitFor({ timeout: 180_000 });
  await shot("example-today");
  await id("nav-overview").click();
  await id("overview-table").waitFor({ timeout: 180_000 });
  await page
    .locator('[data-testid^="status-"]')
    .nth(3)
    .waitFor({ timeout: 180_000 });
  // Three survey indicators and one routine indicator.
  const statuses = await page
    .locator('[data-testid="overview-table"] [data-testid^="status-"]')
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  notice("E2E example", statuses.join(", "));
  if (statuses.length !== 4 || statuses.includes("status-unknown"))
    throw new Error(`Unexpected statuses: ${statuses}`);
  await shot("example-overview-fr");

  // Test assistant: primary school within 2 km, by population group.
  await id("nav-tests").click();
  await id("question-groups").click();
  await id("test-variable").selectOption("primary_school_place");
  await id("tvalue-within_2km").check({ timeout: 30_000 });
  await id("test-group").selectOption("population_group");
  await id("run-test").click();
  await id("test-result").waitFor({ timeout: 120_000 });
  notice(
    "E2E test",
    (await id("test-result").innerText()).replace(/\s+/g, " ").slice(0, 200),
  );
  await shot("example-test-fr");

  // Logframe matrix: the assumptions are edited in place.
  await id("nav-framework").click();
  await id("framework-tab-matrix").click();
  await id("logframe-matrix").waitFor();
  const ass = page.locator('[data-testid^="matrix-assumptions-"]').first();
  await ass.click();
  await ass.fill("Sécurité suffisante pour accéder aux écoles");
  await id("framework-tab-chain").click();
  await page
    .locator(".tree-assumptions", { hasText: "Sécurité suffisante" })
    .first()
    .waitFor({ timeout: 30_000 });
  await id("framework-tab-matrix").click();
  await shot("logframe-matrix");

  // Server: a KoboToolbox form becomes a dataset of the example.
  await id("nav-data").click();
  const cards = await id("dataset-card").count();
  await id("open-servers").click();
  await id("cx-add").click();
  await id("cx-kind-kobo").click();
  await id("cx-name").fill("Kobo test");
  await id("cx-url").fill(koboUrl);
  await id("cx-secret").fill(KOBO_TOKEN);
  await id("cx-save").click();
  await id("cx-Kobo test").waitFor({ timeout: 30_000 });
  await id("cx-form").click();
  await id("cx-form-item").first().click({ timeout: 60_000 });
  await id("cx-sync").click();
  await id("cx-sync-run").click();
  await page
    .locator('[data-testid="cx-sync-panel"] .notice')
    .first()
    .waitFor({ timeout: 120_000 });
  const synced = await id("cx-sync-panel").innerText();
  notice("E2E Kobo", synced.replace(/\s+/g, " ").slice(0, 160));
  if (!/3/.test(synced)) throw new Error(`Unexpected sync: ${synced}`);
  await shot("servers");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  if ((await id("dataset-card").count()) !== cards + 1)
    throw new Error("Kobo dataset not created");

  // 3. Language
  await id("lang-en").click();
  const label = await id("nav-overview").innerText();
  if (!label.includes("Overview"))
    throw new Error(`English label expected, got: ${label}`);
  const htmlLang = await page.evaluate(() => document.documentElement.lang);
  if (htmlLang !== "en")
    throw new Error(`html lang should be "en", got: ${htmlLang}`);
  await id("theme").click();
  await id("nav-analysis").click();
  await id("rounds-table").waitFor({ timeout: 120_000 });
  await shot("example-analysis-en-dark");

  // Indicator library: search, then add a sheet to a result.
  await id("nav-indicators").click();
  const before = await page.locator(".ind-row").count();
  await id("open-library").click();
  await id("library-search").fill("gross enrolment primary");
  await id("adopt-education.ger_primary").click();
  await page
    .locator('[data-testid="adopt-education.ger_primary"]:disabled')
    .waitFor({ timeout: 30_000 });
  await shot("library");
  await page.keyboard.press("Escape");
  if ((await page.locator(".ind-row").count()) !== before + 1)
    throw new Error("Library indicator not added");

  // Updates section (in this test build, checks are off: the update test does them).
  await id("engines-link").click();
  await id("updates-section").waitFor({ timeout: 30_000 });
  notice("E2E updates", await id("update-status").innerText());
  notice(
    "E2E",
    "Full path verified: project sheet, framework, import, cleaning, indicator, monitoring plan, periodic entry, reception and validation, tracking, gap comment, project today, agenda, work plan and budget, feedback, recommendations, risks, meetings, evaluation with coded notes, analysis, report, SPSS, quality, merge, dashboard, checks, plan export, workspace today, workspace, sample size, example, test, logframe matrix, Kobo server sync, languages, indicator library",
  );
} catch (e) {
  // The screen at the moment of failure, kept with the other screenshots.
  const win = await app.firstWindow().catch(() => null);
  await win
    ?.screenshot({ path: path.join(shots, "failure.png") })
    .catch(() => undefined);
  throw e;
} finally {
  await app.close();
  kobo.close();
  if (!process.env.E2E_KEEP) rmSync(work, { recursive: true, force: true });
}
