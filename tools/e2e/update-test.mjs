// Automatic update test, on Windows: the real installer, the real updater.
//
//   node tools/e2e/update-test.mjs <folder of version A> <folder of version B>
//
// Each folder holds what electron-builder wrote: the installer, its block map
// and latest.yml. Version B is one patch above A. The test
// 1. installs A silently, as a user would (per-user install, no admin rights);
// 2. serves B on a local web server, as GitHub releases would (with A's block
//    map next to it, so the download is differential);
// 3. starts the installed A with SME_UPDATE_FEED pointing to that server, checks
//    for updates from the engines screen, waits for the download;
// 4. clicks "Restart and install" and waits until the installed program is B.

import { _electron as electron } from "playwright";
import { execFileSync, spawnSync } from "node:child_process";
import {
  copyFileSync,
  createReadStream,
  existsSync,
  mkdirSync,
  readdirSync,
  statSync,
} from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";

const notice = (title, msg) => console.log(`::notice title=${title}::${msg}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const [dirA, dirB] = process.argv.slice(2).map((p) => path.resolve(p));
const installer = (dir) =>
  readdirSync(dir).find((f) => /-installation\.exe$/.test(f));
const exeA = installer(dirA);
const exeB = installer(dirB);
const version = (name) => name.match(/SuiviEvalLab-(.+)-installation\.exe/)[1];
const [vA, vB] = [version(exeA), version(exeB)];
notice("Update test", `from ${vA} to ${vB}`);

// The feed: B's files, plus A's block map (the updater compares the two).
const feed = path.join(tmpdir(), "sme-update-feed");
mkdirSync(feed, { recursive: true });
for (const f of ["latest.yml", exeB, `${exeB}.blockmap`])
  copyFileSync(path.join(dirB, f), path.join(feed, f));
copyFileSync(
  path.join(dirA, `${exeA}.blockmap`),
  path.join(feed, `${exeA}.blockmap`),
);

let served = 0;
const server = createServer((req, res) => {
  const file = path.join(
    feed,
    decodeURIComponent(new URL(req.url, "http://x").pathname).replace(
      /^\/+/,
      "",
    ),
  );
  if (!file.startsWith(feed) || !existsSync(file)) {
    res.writeHead(404).end();
    return;
  }
  const size = statSync(file).size;
  const range = req.headers.range;
  if (range && file.endsWith(".exe")) {
    // The differential download asks for several ranges at once; answer them one part each.
    const parts = range
      .replace(/^bytes=/, "")
      .split(",")
      .map((r) => r.trim().split("-").map(Number));
    if (parts.length === 1) {
      const [start, end] = parts[0];
      res.writeHead(206, {
        "Content-Range": `bytes ${start}-${end}/${size}`,
        "Content-Length": end - start + 1,
        "Accept-Ranges": "bytes",
      });
      served += end - start + 1;
      createReadStream(file, { start, end }).pipe(res);
      return;
    }
    const boundary = "smeboundary";
    res.writeHead(206, {
      "Content-Type": `multipart/byteranges; boundary=${boundary}`,
    });
    const next = (i) => {
      if (i === parts.length) {
        res.end(`\r\n--${boundary}--\r\n`);
        return;
      }
      const [start, end] = parts[i];
      res.write(
        `\r\n--${boundary}\r\nContent-Range: bytes ${start}-${end}/${size}\r\n\r\n`,
      );
      served += end - start + 1;
      const s = createReadStream(file, { start, end });
      s.on("end", () => next(i + 1));
      s.pipe(res, { end: false });
    };
    next(0);
    return;
  }
  if (file.endsWith(".exe")) served += size;
  res.writeHead(200, { "Content-Length": size, "Accept-Ranges": "bytes" });
  createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const url = `http://127.0.0.1:${server.address().port}/`;

// 1. Install A.
const run = spawnSync(path.join(dirA, exeA), ["/S"], { stdio: "inherit" });
if (run.status !== 0)
  throw new Error(`Installer of ${vA} failed (${run.status})`);
const programs = path.join(process.env.LOCALAPPDATA, "Programs");
const folder = readdirSync(programs)
  .map((d) => path.join(programs, d))
  .find((d) => existsSync(path.join(d, "SuiviEvalLab.exe")));
if (!folder) throw new Error(`SuiviEvalLab.exe not found under ${programs}`);
const installed = path.join(folder, "SuiviEvalLab.exe");
const productVersion = () =>
  execFileSync("powershell", [
    "-NoProfile",
    "-Command",
    `(Get-Item '${installed}').VersionInfo.ProductVersion`,
  ])
    .toString()
    .trim();
notice("Update test", `installed ${productVersion()} in ${folder}`);

// An organisation's policy (registry, current user) turns updates off.
const key = "HKCU\\Software\\Policies\\SuiviEvalLab";
spawnSync("reg", [
  "add",
  key,
  "/v",
  "Updates",
  "/t",
  "REG_SZ",
  "/d",
  "off",
  "/f",
]);
{
  const locked = await electron.launch({
    executablePath: installed,
    env: { ...process.env, SME_UPDATE_FEED: url, SME_E2E_DIALOGS: "" },
    timeout: 60_000,
  });
  const p = await locked.firstWindow();
  await p.locator('[data-testid="engines-link"]').click();
  await p
    .locator('[data-testid="update-status"][data-status="locked"]')
    .waitFor({ timeout: 60_000 });
  await locked.close();
}
spawnSync("reg", ["delete", key, "/f"]);
notice("Update test", "Registry policy Updates=off respected");

// 2-3. Start A, check, download.
const app = await electron.launch({
  executablePath: installed,
  env: { ...process.env, SME_UPDATE_FEED: url, SME_E2E_DIALOGS: "" },
  timeout: 60_000,
});
const page = await app.firstWindow();
const id = (x) => page.locator(`[data-testid="${x}"]`);
await id("engines-link").click();
await id("updates-section").waitFor({ timeout: 60_000 });
await id("update-check")
  .click({ timeout: 10_000 })
  .catch(() => undefined); // the first automatic check may already be running
await page
  .locator('[data-testid="update-status"][data-status="ready"]')
  .waitFor({ timeout: 600_000 });
const sizeB = statSync(path.join(feed, exeB)).size;
notice(
  "Update test",
  `${vB} downloaded: ${Math.round(served / 1048576)} MB fetched for a ${Math.round(sizeB / 1048576)} MB installer`,
);
await page
  .screenshot({ path: path.resolve("build/e2e/update-ready.png") })
  .catch(() => undefined);
if (!(await id("update-ready").isVisible()))
  throw new Error("The update banner is not shown");

// 4. Install and wait for B.
await id("update-install").first().click();
await app.waitForEvent("close", { timeout: 60_000 }).catch(() => undefined);
let now = "";
for (let i = 0; i < 90; i++) {
  await sleep(2000);
  try {
    now = productVersion();
  } catch {
    continue; // the file is being replaced
  }
  if (now.startsWith(vB)) break;
}
server.close();
spawnSync("taskkill", ["/IM", "SuiviEvalLab.exe", "/F", "/T"]); // the app restarted after installing
if (!now.startsWith(vB))
  throw new Error(`Installed version is ${now}, expected ${vB}`);
notice("Update test", `Updated from ${vA} to ${vB} by the app itself`);
process.exit(0);
