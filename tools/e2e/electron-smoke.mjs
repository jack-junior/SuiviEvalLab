// Test de bout en bout de l'application installée (version décompressée de l'installateur).
// Lance SuiviEvalLab.exe, attend que les deux moteurs soient prêts, lance le calcul
// de démonstration et vérifie le résultat affiché. Capture d'écran dans build/e2e.
//
//   node tools/e2e/electron-smoke.mjs apps/desktop/release/win-unpacked/SuiviEvalLab.exe

import { _electron as electron } from "playwright";
import { mkdirSync } from "node:fs";

const exe = process.argv[2];
const notice = (titre, msg) => console.log(`::notice title=${titre}::${msg}`);
mkdirSync("build/e2e", { recursive: true });

const app = await electron.launch({ executablePath: exe, timeout: 60_000 });
try {
  const page = await app.firstWindow();
  await page.waitForSelector("text=Moteur statistique R", { timeout: 60_000 });
  // Les deux moteurs doivent passer à « Prêt » (R démarre en quelques secondes).
  await page.waitForFunction(() => document.querySelectorAll(".st-ok").length >= 3, null, { timeout: 120_000 });
  const moteurs = await page.locator(".row .s").allInnerTexts();
  notice("E2E moteurs", moteurs.join(" | "));

  await page.getByRole("button", { name: "Lancer le calcul" }).click();
  await page.waitForSelector(".figure", { timeout: 120_000 });
  const chiffre = await page.locator(".figure").innerText();
  const ic = await page.locator(".result .muted").first().innerText();
  notice("E2E calcul", `${chiffre}, ${ic}`);
  await page.screenshot({ path: "build/e2e/demarrage-clair.png" });

  if (!/62,0\s?%/.test(chiffre)) throw new Error(`Résultat inattendu : ${chiffre}`);

  await page.getByRole("button", { name: "Changer de thème" }).click();
  await page.screenshot({ path: "build/e2e/demarrage-sombre.png" });
  notice("E2E", "Application installée : démarrage, moteurs et calcul vérifiés");
} finally {
  await app.close();
}
