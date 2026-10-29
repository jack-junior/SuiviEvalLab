// End-to-end test of the installed app (unpacked installer output).
// Starts SuiviEvalLab.exe, waits for both engines, runs the demo computation,
// checks the displayed result in both interface languages, and takes
// screenshots in build/e2e. Selectors use data-testid, never displayed text,
// so the test does not depend on the interface language.
//
//   node tools/e2e/electron-smoke.mjs apps/desktop/release/win-unpacked/SuiviEvalLab.exe

import { _electron as electron } from "playwright";
import { mkdirSync } from "node:fs";

const exe = process.argv[2];
const notice = (title, msg) => console.log(`::notice title=${title}::${msg}`);
mkdirSync("build/e2e", { recursive: true });

const app = await electron.launch({ executablePath: exe, timeout: 60_000 });
try {
  const page = await app.firstWindow();
  const byId = (id) => page.locator(`[data-testid="${id}"]`);

  // Interface, Python and R must all reach "ready" (R takes a few seconds to start).
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="status-ready"]').length >= 3, null, {
    timeout: 120_000,
  });
  const engines = await page.locator(".row .s").allInnerTexts();
  notice("E2E engines", engines.join(" | "));

  // French first.
  await byId("lang-fr").click();
  const runFr = await byId("run-demo").innerText();
  if (runFr !== "Lancer le calcul") throw new Error(`French label expected, got: ${runFr}`);

  await byId("run-demo").click();
  await byId("figure").waitFor({ timeout: 120_000 });
  const figureFr = await byId("figure").innerText();
  const ciFr = await byId("ci").innerText();
  notice("E2E computation (fr)", `${figureFr}, ${ciFr}`);
  if (!/^62,0\s?%$/.test(figureFr.trim())) throw new Error(`Unexpected French result: ${figureFr}`);
  await page.screenshot({ path: "build/e2e/start-fr-light.png" });

  // Then English: the same result must be reformatted, without a new calculation.
  await byId("lang-en").click();
  const runEn = await byId("run-demo").innerText();
  if (runEn !== "Run the calculation") throw new Error(`English label expected, got: ${runEn}`);
  const figureEn = await byId("figure").innerText();
  const ciEn = await byId("ci").innerText();
  notice("E2E computation (en)", `${figureEn}, ${ciEn}`);
  if (!/^62\.0\s?%$/.test(figureEn.trim())) throw new Error(`Unexpected English result: ${figureEn}`);
  const htmlLang = await page.evaluate(() => document.documentElement.lang);
  if (htmlLang !== "en") throw new Error(`html lang should be "en", got: ${htmlLang}`);

  await byId("theme").click();
  await page.screenshot({ path: "build/e2e/start-en-dark.png" });
  notice("E2E", "Installed app: start, engines, computation and both languages verified");
} finally {
  await app.close();
}
