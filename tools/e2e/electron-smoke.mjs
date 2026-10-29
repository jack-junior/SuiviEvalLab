// End-to-end test of the installed app (unpacked installer output).
// Starts SuiviEvalLab.exe, waits for both engines, runs the demo computation
// and checks the displayed result. Screenshots go to build/e2e.
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
  await page.waitForSelector("text=Moteur statistique R", { timeout: 60_000 });
  // Both engines must reach "Prêt" (R takes a few seconds to start).
  await page.waitForFunction(() => document.querySelectorAll(".st-ok").length >= 3, null, { timeout: 120_000 });
  const engines = await page.locator(".row .s").allInnerTexts();
  notice("E2E engines", engines.join(" | "));

  await page.getByRole("button", { name: "Lancer le calcul" }).click();
  await page.waitForSelector(".figure", { timeout: 120_000 });
  const figure = await page.locator(".figure").innerText();
  const ic = await page.locator(".result .muted").first().innerText();
  notice("E2E computation", `${figure}, ${ic}`);
  await page.screenshot({ path: "build/e2e/start-light.png" });

  if (!/62,0\s?%/.test(figure)) throw new Error(`Unexpected result: ${figure}`);

  await page.getByRole("button", { name: "Changer de thème" }).click();
  await page.screenshot({ path: "build/e2e/start-dark.png" });
  notice("E2E", "Installed app: start, engines and computation verified");
} finally {
  await app.close();
}
