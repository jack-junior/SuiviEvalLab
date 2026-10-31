// Electron main process: window, engines, secure exchanges with the interface.

import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from "electron";
import { randomUUID } from "node:crypto";
import { readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { EngineClient, EngineError, EngineLaunch } from "./engine";

// Engine methods the interface is allowed to call (allowlist). Methods that read or
// write files never receive a path from the interface: they receive a `file_token`
// obtained from a file dialog, which the main process swaps for the real path.
const ALLOWED = new Set([
  "system.ping",
  "system.versions",
  "r.ping",
  "demo.proportion",
  "project.create",
  "project.open",
  "project.close",
  "project.get",
  "project.rename",
  "framework.add",
  "framework.update",
  "framework.delete",
  "framework.move",
  "indicator.save",
  "indicator.delete",
  "indicator.move",
  "dataset.inspect",
  "dataset.import",
  "dataset.update",
  "dataset.delete",
  "dataset.export",
  "dataset.preview",
  "dataset.column_values",
  "cleaning.add",
  "cleaning.update",
  "cleaning.delete",
  "cleaning.move",
  "analysis.indicator",
  "analysis.overview",
  "test.run",
  "test.save",
  "test.delete",
  "dataset.attach_form",
  "dataset.set_labels",
  "dataset.merge",
  "report.generate",
  "report.share",
  "report.set_template",
  "report.clear_template",
]);

// Paths chosen by the user in a dialog, by token. Tokens live for the session.
const pickedFiles = new Map<string, string>();

type DialogKind =
  "project-save" | "project-open" | "data-open" | "report-save" | "csv-save" | "html-save" | "template-open";

// End-to-end tests answer dialogs through SME_E2E_DIALOGS (paths separated by "|").
const e2eAnswers = (process.env.SME_E2E_DIALOGS ?? "").split("|").filter(Boolean);

async function pickFile(kind: DialogKind, defaultName?: string): Promise<{ token: string; name: string } | null> {
  let chosen: string | undefined;
  if (e2eAnswers.length > 0) {
    chosen = e2eAnswers.shift();
  } else if (win) {
    const docs = app.getPath("documents");
    if (kind === "project-save" || kind === "report-save" || kind === "csv-save" || kind === "html-save") {
      const filter = {
        "project-save": { name: "SuiviEvalLab", extensions: ["sme"], file: "Projet.sme" },
        "report-save": { name: "Word", extensions: ["docx"], file: "Rapport.docx" },
        "csv-save": { name: "CSV", extensions: ["csv"], file: "Donnees.csv" },
        "html-save": { name: "HTML", extensions: ["html"], file: "Tableau-de-bord.html" },
      }[kind];
      const res = await dialog.showSaveDialog(win, {
        defaultPath: path.join(docs, defaultName ?? filter.file),
        filters: [{ name: filter.name, extensions: filter.extensions }],
      });
      chosen = res.canceled ? undefined : res.filePath;
    } else {
      const filters = {
        "project-open": [{ name: "SuiviEvalLab", extensions: ["sme"] }],
        "data-open": [
          { name: "Excel, CSV, SPSS, Stata", extensions: ["xlsx", "xlsm", "xls", "csv", "sav", "zsav", "dta"] },
        ],
        "template-open": [{ name: "Word", extensions: ["docx", "dotx"] }],
      }[kind as "project-open" | "data-open" | "template-open"];
      const res = await dialog.showOpenDialog(win, { defaultPath: docs, properties: ["openFile"], filters });
      chosen = res.canceled ? undefined : res.filePaths[0];
    }
  }
  if (!chosen) return null;
  const token = randomUUID();
  pickedFiles.set(token, chosen);
  return { token, name: path.basename(chosen) };
}

// Projects known to this computer ("My projects"), kept in the user profile.
// Each entry may carry a summary of the indicators, saved when the overview is computed.
interface ProjectSummary {
  indicators: number;
  achieved: number;
  on_track: number;
  late: number;
  unknown: number;
  datasets: number;
}
interface KnownProject {
  path: string;
  name: string;
  opened_at: string;
  summary?: ProjectSummary;
}
const recentFile = () => path.join(app.getPath("userData"), "recent-projects.json");

function readRecents(): KnownProject[] {
  try {
    const list = JSON.parse(readFileSync(recentFile(), "utf8"));
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function writeRecents(list: KnownProject[]): void {
  try {
    writeFileSync(recentFile(), JSON.stringify(list.slice(0, 50), null, 2), "utf8");
  } catch {
    /* the project list is a convenience only */
  }
}

function rememberProject(file: string, name: string): void {
  const list = readRecents();
  const old = list.find((r) => r.path === file);
  writeRecents([
    { path: file, name, opened_at: new Date().toISOString(), summary: old?.summary },
    ...list.filter((r) => r.path !== file),
  ]);
}

function listProjects() {
  return readRecents().map((r) => {
    let modified: string | null = null;
    try {
      modified = statSync(r.path).mtime.toISOString();
    } catch {
      modified = null;
    }
    return { ...r, exists: modified !== null, modified };
  });
}

function tokenForRecent(file: string): string | null {
  if (!readRecents().some((r) => r.path === file)) return null;
  const token = randomUUID();
  pickedFiles.set(token, file);
  return token;
}

let engine: EngineClient | null = null;
let win: BrowserWindow | null = null;

function engineLaunch(): EngineLaunch {
  if (app.isPackaged) {
    // Installed app: Python and R are embedded in the resources.
    const res = process.resourcesPath;
    return {
      command: path.join(res, "python", "python.exe"),
      args: ["-X", "utf8", "-m", "sme_engine"],
      cwd: path.join(res, "engine", "python"),
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
        SME_R_DIR: path.join(res, "engine", "r"),
        SME_RSCRIPT: path.join(res, "R", "bin", "Rscript.exe"),
      },
    };
  }
  // Development: engines from the repository, system Python and R.
  const root = path.resolve(__dirname, "..", "..", "..", "..");
  const enginePy = path.join(root, "engine", "python");
  return {
    command: process.env.SME_PYTHON ?? (process.platform === "win32" ? "python" : "python3"),
    args: ["-X", "utf8", "-m", "sme_engine"],
    cwd: enginePy,
    env: {
      ...process.env,
      PYTHONPATH: enginePy,
      PYTHONIOENCODING: "utf-8",
      SME_R_DIR: path.join(root, "engine", "r"),
    },
  };
}

function createWindow(): void {
  win = new BrowserWindow({
    width: 1320,
    height: 840,
    minWidth: 1024,
    minHeight: 640,
    title: "SuiviEvalLab",
    backgroundColor: "#F6F5F2",
    // Installed on Windows, the window takes the icon of the .exe; in development, the PNG.
    icon: app.isPackaged ? undefined : path.join(__dirname, "..", "..", "build-resources", "icon.png"),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  win.once("ready-to-show", () => win?.show());
  // No link opens inside the app: external links go to the browser.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) void shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e) => e.preventDefault());
  void win.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  engine = new EngineClient(
    engineLaunch(),
    path.join(app.getPath("userData"), "logs", "moteur.log"),
    (method, params) => win?.webContents.send("engine:event", { method, params }),
  );
  engine.start();

  ipcMain.handle("engine:call", async (_e, method: unknown, params: unknown) => {
    if (typeof method !== "string" || !ALLOWED.has(method)) {
      return { ok: false, error: "Not allowed", key: "not_allowed" };
    }
    const args: Record<string, unknown> = { ...((params as Record<string, unknown>) ?? {}) };
    delete args.path; // paths only ever come from a dialog token
    if (typeof args.file_token === "string") {
      const file = pickedFiles.get(args.file_token);
      if (!file) return { ok: false, error: "Unknown file token", key: "file_token" };
      args.path = file;
      delete args.file_token;
    }
    try {
      const result = await engine!.call(method, args);
      if ((method === "project.create" || method === "project.open" || method === "project.rename") && result) {
        const info = (result as { project?: { path: string; name: string } }).project;
        if (info) {
          rememberProject(info.path, info.name);
          win?.setTitle(`${info.name} - SuiviEvalLab`);
        }
      }
      if (method === "project.close") win?.setTitle("SuiviEvalLab");
      return { ok: true, result };
    } catch (err) {
      if (err instanceof EngineError) return { ok: false, error: err.message, key: err.key };
      return { ok: false, error: err instanceof Error ? err.message : String(err), key: "unknown" };
    }
  });
  ipcMain.handle("dialog:pick", (_e, kind: unknown, defaultName: unknown) => {
    const kinds: DialogKind[] = [
      "project-save",
      "project-open",
      "data-open",
      "report-save",
      "csv-save",
      "html-save",
      "template-open",
    ];
    if (typeof kind !== "string" || !kinds.includes(kind as DialogKind)) return null;
    return pickFile(kind as DialogKind, typeof defaultName === "string" ? defaultName.slice(0, 120) : undefined);
  });
  ipcMain.handle("project:recents", () => listProjects());
  ipcMain.handle("project:forget", (_e, file: unknown) => {
    if (typeof file === "string") writeRecents(readRecents().filter((r) => r.path !== file));
    return listProjects();
  });
  ipcMain.handle("project:reveal", (_e, file: unknown) => {
    if (typeof file === "string" && readRecents().some((r) => r.path === file)) shell.showItemInFolder(file);
  });
  ipcMain.handle("project:summary", (_e, file: unknown, summary: unknown) => {
    if (typeof file !== "string" || !summary || typeof summary !== "object") return;
    const s = summary as Record<string, unknown>;
    const n = (k: string) => (typeof s[k] === "number" ? (s[k] as number) : 0);
    writeRecents(
      readRecents().map((r) =>
        r.path === file
          ? {
              ...r,
              summary: {
                indicators: n("indicators"),
                achieved: n("achieved"),
                on_track: n("on_track"),
                late: n("late"),
                unknown: n("unknown"),
                datasets: n("datasets"),
              },
            }
          : r,
      ),
    );
  });
  ipcMain.handle("project:recent-token", (_e, file: unknown) =>
    typeof file === "string" ? tokenForRecent(file) : null,
  );
  ipcMain.handle("file:reveal", (_e, token: unknown) => {
    const file = typeof token === "string" ? pickedFiles.get(token) : undefined;
    if (file) void shell.openPath(file);
    return Boolean(file);
  });
  ipcMain.handle("app:info", () => ({
    version: app.getVersion(),
    electron: process.versions.electron,
    packaged: app.isPackaged,
    logs: path.join(app.getPath("userData"), "logs"),
  }));

  createWindow();
});

app.on("window-all-closed", () => {
  engine?.stop();
  app.quit();
});
