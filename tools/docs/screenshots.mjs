// Screenshots of the documentation, taken in the real application.
//
//   xvfb-run -a node tools/docs/screenshots.mjs apps/desktop <data folder>
//
// <data folder> holds the files of the test kit (tools/test-kit). The script
// opens the example project, adds the Bangladesh survey with its Kobo
// questionnaire, and photographs each screen and panel in French, light theme,
// at 1440 x 900. Images go to docs/guide/img; the guide and the Word document
// use the same files, so running this again refreshes both.

import { _electron as electron } from "playwright";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const target = path.resolve(process.argv[2] ?? "apps/desktop");
const data = path.resolve(process.argv[3] ?? "build/test-kit/donnees");
const out = path.resolve("docs/guide/img");
mkdirSync(out, { recursive: true });
const work = mkdtempSync(path.join(tmpdir(), "sme-docs-"));
// A fresh profile: "My projects" shows only the projects of this run.
const profile = mkdtempSync(path.join(tmpdir(), "sme-docs-profile-"));
const bgd = path.join(data, "03_bangladesh_wash_2018_reference.xlsx");

const dialogs = [
  path.join(work, "Acces-education-Irak.sme"), // example project
  bgd, // Kobo households
  path.join(work, "nettoyage.R"), // cleaning journal as an R script
  bgd, // Kobo containers
  path.join(work, "rapport.docx"),
  path.join(work, "plan-de-suivi.xlsx"),
  path.join(work, "tableau-de-bord.html"),
];

const app = await electron.launch({
  executablePath: path.join(target, "node_modules/electron/dist/electron"),
  args: ["--no-sandbox", target],
  env: {
    ...process.env,
    SME_E2E_DIALOGS: dialogs.join("|"),
    XDG_CONFIG_HOME: profile,
    SME_BACKUP_DIR: path.join(profile, "backups"),
  },
  timeout: 60_000,
});
const page = await app.firstWindow();
await app.evaluate(({ BrowserWindow }) =>
  BrowserWindow.getAllWindows()[0].setSize(1440, 900),
);
await page.setViewportSize({ width: 1440, height: 900 }).catch(() => undefined);
const id = (x) => page.locator(`[data-testid="${x}"]`);
const pause = (ms = 400) => page.waitForTimeout(ms);
const shot = async (name, locator) => {
  await pause();
  const file = path.join(out, `${name}.png`);
  if (locator) await locator.screenshot({ path: file });
  else await page.screenshot({ path: file });
  console.log(name);
};
const panel = () => page.locator(".panel").last();
const closePanel = async () => {
  await page.keyboard.press("Escape");
  await pause(300);
};

try {
  await id("lang-fr").click();
  await page.evaluate(() => (document.documentElement.dataset.theme = "light"));
  await id("engine-ready").first().waitFor({ timeout: 150_000 });

  // Sample size, engines (the home screen is taken at the end, with a project in its list)
  await id("open-sample").click();
  await panel().waitFor();
  await id("sample-result").waitFor({ timeout: 60_000 });
  await shot("02-taille-echantillon");
  await closePanel();
  await id("engines-link").click();
  await id("updates-section").waitFor();
  await shot("03-moteurs");
  await page.locator('a[href="#home"]').click();

  // New project: choice of the framework model
  await id("new-project").click();
  await panel().waitFor();
  await id("new-name").fill("Projet eau et assainissement");
  await id("model-eu").click();
  await shot("04-nouveau-projet");
  await closePanel();

  // Example project
  await id("open-example").click();
  await id("overview-table").waitFor({ timeout: 180_000 });
  await page
    .locator('[data-testid^="status-"]')
    .nth(2)
    .waitFor({ timeout: 180_000 });
  await shot("10-vue-ensemble");

  await id("nav-framework").click();
  await id("framework-tree").waitFor();
  await shot("11-cadre-resultats");
  await page.locator(".tree-row").first().hover();
  await shot("12-cadre-actions", page.locator(".tree-row").first());
  await id("change-model").click();
  await id("model-panel").waitFor();
  await shot("13-modele-cadre");
  await closePanel();

  await id("nav-indicators").click();
  await page.locator(".ind-row").first().waitFor();
  await shot("20-indicateurs");
  await page.getByRole("button", { name: "Modifier" }).first().click();
  await panel().waitFor();
  await shot("21-indicateur-fiche");
  await panel()
    .locator(".panel-body")
    .evaluate((el) => (el.scrollTop = el.scrollHeight));
  await shot("22-indicateur-plan-de-suivi");
  await closePanel();

  // Routine monitoring indicator
  await id("nav-analysis").click();
  await page
    .locator('[data-testid="analysis-item"]', { hasText: "Salles de classe" })
    .click();
  await id("routine").waitFor({ timeout: 60_000 });
  await shot("23-indicateur-routine");

  // Data
  await id("nav-data").click();
  await id("dataset-card").first().waitFor();
  await shot("30-donnees");
  await id("dataset-card").first().click();
  await id("journal").waitFor();
  await shot("31-journal-nettoyage");
  await id("add-rule").click();
  await panel().waitFor();
  await id("rule-column").selectOption("primary_school_place");
  await id("rule-values").waitFor({ timeout: 30_000 });
  await shot("32-regle-nettoyage");
  await closePanel();
  await id("tab-quality").click();
  await id("quality").waitFor({ timeout: 60_000 });
  await shot("33-qualite");
  await id("tab-preview").click();
  await id("preview-grid").waitFor();
  await shot("34-apercu");

  // Kobo survey with its questionnaire
  await id("data-back").click();
  await id("import-data").first().click();
  await id("choose-file").click();
  await page
    .locator('[data-testid="import-confirm"]:not([disabled])')
    .waitFor({ timeout: 120_000 });
  await id("import-sheet").selectOption("Dataset");
  await page
    .locator('[data-testid="import-confirm"]:not([disabled])')
    .waitFor({ timeout: 120_000 });
  await id("dataset-name").fill("WASH Bangladesh, ménages");
  await id("round-monitoring").click();
  await shot("35-import");
  await id("import-confirm").click();
  await id("tab-cleaning").waitFor({ timeout: 180_000 });
  await id("tab-quality").click();
  await id("quality-warnings").waitFor({ timeout: 60_000 });
  await shot("36-qualite-kobo");
  await id("tab-preview").click();
  await id("preview-grid").waitFor();
  await id("show-labels")
    .check()
    .catch(() => id("show-labels").click());
  await shot("37-apercu-libelles");
  // Advanced cleaning on the Kobo file: interview duration, then too short interviews.
  await id("tab-cleaning").click();
  await id("add-rule").click();
  await id("kind-date").click();
  await id("rule-target").fill("duree_entretien");
  await shot("41-regle-duree");
  await id("rule-save").click();
  await page.locator(".journal-row").first().waitFor();
  await id("add-rule").click();
  await id("kind-check").click();
  await id("cond-column-0").selectOption("duree_entretien");
  await id("cond-op-0").selectOption("lt");
  await id("cond-value-0").fill("15");
  await id("rule-target").fill("entretien_court");
  await shot("42-controle-coherence");
  await id("rule-save").click();
  await page.locator(".journal-row").nth(1).waitFor();
  await shot("43-journal-avance");
  await id("export-r").click();
  await page
    .locator(".notice")
    .filter({ hasText: "Script R" })
    .waitFor({ timeout: 60_000 });
  await id("tab-columns").click();
  await pause(600);
  await shot("38-colonnes");
  const labelled = id("label-household_water/What_is_the_main_source_DRINK");
  await labelled.scrollIntoViewIfNeeded();
  await labelled.click();
  await panel().waitFor();
  await shot("39-libelles");
  await closePanel();

  // Merge: water containers with their household
  await id("data-back").click();
  await id("import-data").first().click();
  await id("choose-file").click();
  await page
    .locator('[data-testid="import-confirm"]:not([disabled])')
    .waitFor({ timeout: 120_000 });
  await id("import-sheet").selectOption("Dataset_containergroup");
  await page
    .locator('[data-testid="import-confirm"]:not([disabled])')
    .waitFor({ timeout: 120_000 });
  await id("dataset-name").fill("WASH Bangladesh, contenants");
  await id("round-monitoring").click();
  await id("import-confirm").click();
  await id("tab-cleaning").waitFor({ timeout: 180_000 });
  await id("data-back").click();
  await id("merge-data").click();
  await id("merge-left").selectOption({ label: "WASH Bangladesh, contenants" });
  await id("merge-right").selectOption({ label: "WASH Bangladesh, ménages" });
  await id("merge-check").waitFor({ timeout: 60_000 });
  await shot("40-fusion");
  await closePanel();
  await id("stack-data").click();
  await page.locator('[data-testid^="stack-file-"]').nth(0).check();
  await page.locator('[data-testid^="stack-file-"]').nth(1).check();
  await id("stack-check").waitFor({ timeout: 60_000 });
  await shot("44-empiler");
  await closePanel();

  // Analysis and tests
  await id("nav-analysis").click();
  await id("analysis-item").first().click();
  await id("comparison").waitFor({ timeout: 120_000 });
  await shot("50-analyse");
  await page.getByRole("tab", { name: "Désagrégation" }).click();
  await id("breakdown-table").waitFor({ timeout: 60_000 });
  await shot("51-analyse-desagregation");
  await page.getByRole("tab", { name: "Méthode et script R" }).click();
  await id("r-script").waitFor({ timeout: 30_000 });
  await shot("52-analyse-script-r");

  await id("nav-tests").click();
  await id("question-groups").click();
  await id("test-variable").selectOption("primary_school_place");
  await id("tvalue-within_2km").check({ timeout: 30_000 });
  await id("test-group").selectOption("population_group");
  await id("run-test").click();
  await id("test-result").waitFor({ timeout: 120_000 });
  await shot("60-test-groupes");

  // Report
  await id("nav-report").click();
  await id("report-checks").waitFor({ timeout: 120_000 });
  await shot("70-rapport");
  await id("generate-report").click();
  await id("report-done").waitFor({ timeout: 180_000 });
  await id("export-plan").click();
  await id("plan-done").waitFor({ timeout: 120_000 });
  await id("share-dashboard").click();
  await id("share-done").waitFor({ timeout: 180_000 });
  await id("share-section").scrollIntoViewIfNeeded();
  await shot("71-rapport-partage");

  // My projects and automatic copies
  await id("close-project").click();
  await id("my-projects").waitFor();
  // Reopen once: the first automatic copy is taken at opening.
  await id("project-row").first().click();
  await id("overview-table").waitFor({ timeout: 180_000 });
  await id("close-project").click();
  await id("my-projects").waitFor();
  await shot("01-accueil");
  await shot("80-mes-projets", id("my-projects"));
  await id("project-backups").first().click();
  await panel().waitFor();
  await shot("81-copies");
  await closePanel();

  // The dashboard as a partner sees it
  const { chromium } = await import("playwright");
  const browser = await chromium.launch();
  const view = await browser.newPage({
    viewport: { width: 1280, height: 900 },
  });
  await view.goto(`file://${path.join(work, "tableau-de-bord.html")}`);
  await view.screenshot({ path: path.join(out, "72-tableau-de-bord.png") });
  console.log("72-tableau-de-bord");
  await browser.close();
  console.log(`Files written in ${work}: rapport.docx, plan-de-suivi.xlsx`);
} finally {
  await app.close();
  rmSync(profile, { recursive: true, force: true });
  if (!process.env.KEEP) rmSync(work, { recursive: true, force: true });
}
