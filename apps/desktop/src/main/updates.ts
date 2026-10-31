// Automatic updates from the GitHub releases of the project (electron-updater).
//
// - At start (after a short delay) and every six hours, when internet is
//   available, the app looks for a newer release. Offline, nothing happens.
// - A newer version is downloaded in the background; only the changed blocks
//   are fetched when the previous release published its block map.
// - The user restarts to install when it suits them. If they simply quit, the
//   update is installed silently on the way out.
// - The user can turn checks off. An organisation can turn them off for
//   everyone: environment variable SME_UPDATES=off, or a file
//   update-policy.json containing {"updates": "off"} next to SuiviEvalLab.exe.
// - SME_UPDATE_FEED=<url> points to another feed (a folder with latest.yml);
//   the update test of the CI uses it with a local server.

import { app, BrowserWindow } from "electron";
import { autoUpdater, ProgressInfo, UpdateInfo } from "electron-updater";
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

export type UpdateStatus =
  | "unsupported" // development build
  | "off" // turned off by the user
  | "locked" // turned off by the organisation
  | "idle"
  | "checking"
  | "none" // up to date
  | "downloading"
  | "ready"
  | "error";

export interface UpdateState {
  status: UpdateStatus;
  current: string;
  auto: boolean;
  locked: boolean;
  version?: string;
  percent?: number;
  transferred?: number;
  total?: number;
  checkedAt?: string;
  error?: string;
  notesUrl?: string;
}

const RELEASES = "https://github.com/jack-junior/SuiviEvalLab/releases/tag/v";
const EVERY = 6 * 60 * 60 * 1000;

interface Settings {
  updates?: { auto?: boolean };
}

export class Updates {
  private state: UpdateState;
  private timer: NodeJS.Timeout | null = null;
  private readonly settingsFile = path.join(app.getPath("userData"), "settings.json");
  private readonly logFile = path.join(app.getPath("userData"), "logs", "mises-a-jour.log");

  constructor(
    private readonly window: () => BrowserWindow | null,
    private readonly beforeInstall: () => Promise<void>,
  ) {
    const feed = process.env.SME_UPDATE_FEED;
    const supported = app.isPackaged && (!process.env.SME_E2E_DIALOGS || Boolean(feed));
    const locked = this.lockedByPolicy();
    const auto = this.readSettings().updates?.auto !== false;
    this.state = {
      status: !supported ? "unsupported" : locked ? "locked" : auto ? "idle" : "off",
      current: app.getVersion(),
      auto,
      locked,
    };
    if (!supported) return;

    autoUpdater.autoDownload = true;
    autoUpdater.autoInstallOnAppQuit = true;
    // Versions below 1.0 are published as GitHub pre-releases.
    autoUpdater.allowPrerelease = true;
    autoUpdater.logger = {
      info: (m) => this.log(m),
      warn: (m) => this.log(m),
      error: (m) => this.log(m),
      debug: () => undefined,
    };
    if (feed) autoUpdater.setFeedURL({ provider: "generic", url: feed });

    autoUpdater.on("checking-for-update", () => this.set({ status: "checking", error: undefined }));
    autoUpdater.on("update-not-available", () => this.set({ status: "none", checkedAt: new Date().toISOString() }));
    autoUpdater.on("update-available", (info: UpdateInfo) =>
      this.set({
        status: "downloading",
        version: info.version,
        percent: 0,
        notesUrl: RELEASES + info.version,
        checkedAt: new Date().toISOString(),
      }),
    );
    autoUpdater.on("download-progress", (p: ProgressInfo) =>
      this.set({ status: "downloading", percent: p.percent, transferred: p.transferred, total: p.total }),
    );
    autoUpdater.on("update-downloaded", (info: UpdateInfo) =>
      this.set({ status: "ready", version: info.version, percent: 100, notesUrl: RELEASES + info.version }),
    );
    autoUpdater.on("error", (err: Error) => {
      this.log(`Erreur : ${err.message}`);
      // Offline or GitHub unreachable: reported quietly, retried at the next check.
      this.set({ status: "error", error: err.message.split("\n")[0].slice(0, 300) });
    });
  }

  get(): UpdateState {
    return this.state;
  }

  /** First check shortly after start, then every six hours. */
  start(): void {
    if (this.state.status !== "idle") return;
    setTimeout(() => void this.check(), 15_000).unref();
    this.timer = setInterval(() => void this.check(), EVERY);
    this.timer.unref();
  }

  async check(): Promise<UpdateState> {
    const s = this.state.status;
    if (s === "unsupported" || s === "locked" || s === "checking" || s === "downloading" || s === "ready") {
      return this.state;
    }
    try {
      await autoUpdater.checkForUpdates();
    } catch (err) {
      this.set({ status: "error", error: err instanceof Error ? err.message.split("\n")[0] : String(err) });
    }
    return this.state;
  }

  setAuto(auto: boolean): UpdateState {
    if (this.state.locked || this.state.status === "unsupported") return this.state;
    this.writeSettings({ ...this.readSettings(), updates: { auto } });
    if (auto) {
      this.set({ auto, status: this.state.status === "off" ? "idle" : this.state.status });
      if (!this.timer) this.start();
    } else {
      if (this.timer) clearInterval(this.timer);
      this.timer = null;
      // A download already finished stays ready to install.
      this.set({ auto, status: this.state.status === "ready" ? "ready" : "off" });
    }
    return this.state;
  }

  /** Stop the engines (their files must not be in use), then install and restart. */
  async install(): Promise<void> {
    if (this.state.status !== "ready") return;
    this.log(`Installation de la version ${this.state.version}`);
    await this.beforeInstall();
    autoUpdater.quitAndInstall(true, true);
  }

  private set(patch: Partial<UpdateState>): void {
    this.state = { ...this.state, ...patch };
    this.window()?.webContents.send("updates:state", this.state);
  }

  private lockedByPolicy(): boolean {
    if ((process.env.SME_UPDATES ?? "").toLowerCase() === "off") return true;
    try {
      const policy = JSON.parse(
        readFileSync(path.join(path.dirname(app.getPath("exe")), "update-policy.json"), "utf8"),
      );
      return String(policy?.updates).toLowerCase() === "off";
    } catch {
      return false;
    }
  }

  private readSettings(): Settings {
    try {
      return JSON.parse(readFileSync(this.settingsFile, "utf8")) as Settings;
    } catch {
      return {};
    }
  }

  private writeSettings(s: Settings): void {
    try {
      writeFileSync(this.settingsFile, JSON.stringify(s, null, 2), "utf8");
    } catch (err) {
      this.log(`Réglage non enregistré : ${String(err)}`);
    }
  }

  private log(message: unknown): void {
    try {
      mkdirSync(path.dirname(this.logFile), { recursive: true });
      appendFileSync(this.logFile, `${new Date().toISOString()} ${String(message)}\n`, "utf8");
    } catch {
      /* logging is best effort */
    }
  }
}
