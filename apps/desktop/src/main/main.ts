// Electron main process: window, engines, secure exchanges with the interface.

import { app, BrowserWindow, ipcMain, Menu, shell } from "electron";
import path from "node:path";
import { EngineClient, EngineError, EngineLaunch } from "./engine";

// Engine methods the interface is allowed to call (allowlist).
const ALLOWED = new Set(["system.ping", "system.versions", "r.ping", "demo.proportion"]);

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
      return { ok: false, error: "Action non autorisée." };
    }
    try {
      const result = await engine!.call(method, (params as Record<string, unknown>) ?? {});
      return { ok: true, result };
    } catch (err) {
      const message = err instanceof EngineError || err instanceof Error ? err.message : String(err);
      return { ok: false, error: message };
    }
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
