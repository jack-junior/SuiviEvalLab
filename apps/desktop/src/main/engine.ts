// Python engine client: child process, line-delimited JSON-RPC 2.0.
// Error messages are user-facing (French for now, moved to i18n later).

import { ChildProcess, spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";

export interface EngineLaunch {
  command: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
}

interface Pending {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timer: NodeJS.Timeout;
}

// Errors carry a stable `key` that the interface translates; `message` is a technical fallback.
export class EngineError extends Error {
  constructor(
    message: string,
    public readonly key: string = "unknown",
    public readonly code: number = -32000,
  ) {
    super(message);
  }
}

export class EngineClient {
  private proc: ChildProcess | null = null;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private restarts = 0;
  private stopping = false;

  constructor(
    private readonly launch: EngineLaunch,
    private readonly logFile: string,
    private readonly onEvent: (method: string, params: unknown) => void,
  ) {
    mkdirSync(path.dirname(logFile), { recursive: true });
  }

  start(): void {
    this.log(`Démarrage du moteur : ${this.launch.command} ${this.launch.args.join(" ")}`);
    const proc = spawn(this.launch.command, this.launch.args, {
      cwd: this.launch.cwd,
      env: this.launch.env,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.proc = proc;
    proc.stdout!.setEncoding("utf8");
    proc.stderr!.setEncoding("utf8");
    createInterface({ input: proc.stdout! }).on("line", (line) => this.onLine(line));
    createInterface({ input: proc.stderr! }).on("line", (line) => this.log(line));
    proc.on("error", (err) => this.log(`Impossible de lancer le moteur : ${err.message}`));
    proc.on("exit", (code) => {
      this.log(`Moteur arrêté (code ${code})`);
      this.failAll(new EngineError("Engine stopped", "engine_stopped"));
      this.proc = null;
      if (!this.stopping && this.restarts < 3) {
        this.restarts += 1;
        setTimeout(() => this.start(), 1000 * this.restarts);
      }
    });
  }

  call<T = unknown>(method: string, params: Record<string, unknown> = {}, timeoutMs = 180_000): Promise<T> {
    if (!this.proc || !this.proc.stdin || this.proc.stdin.destroyed) {
      return Promise.reject(new EngineError("Engine unavailable", "engine_unavailable"));
    }
    const id = this.nextId++;
    const line = JSON.stringify({ jsonrpc: "2.0", id, method, params });
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new EngineError(`Timeout for ${method}`, "timeout"));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer });
      this.proc!.stdin!.write(line + "\n", "utf8");
    });
  }

  stop(): void {
    this.stopping = true;
    if (this.proc && this.proc.stdin && !this.proc.stdin.destroyed) this.proc.stdin.end();
    const proc = this.proc;
    setTimeout(() => proc?.kill(), 3000).unref();
  }

  /**
   * Stop the engines and wait until they have exited, so their files are free (an
   * update replaces them). The Python engine closes R when its input ends; if it
   * does not exit in time, the whole process tree is killed.
   */
  stopAndWait(timeoutMs = 8000): Promise<void> {
    const proc = this.proc;
    this.stopping = true;
    if (!proc || proc.exitCode !== null) return Promise.resolve();
    return new Promise<void>((resolve) => {
      const done = () => {
        clearTimeout(timer);
        resolve();
      };
      proc.once("exit", done);
      const timer = setTimeout(() => {
        this.log("Le moteur ne s'arrête pas : arrêt forcé");
        if (process.platform === "win32" && proc.pid) {
          spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"], { windowsHide: true }).on("exit", done);
        } else {
          proc.kill("SIGKILL");
          setTimeout(done, 500);
        }
      }, timeoutMs);
      if (proc.stdin && !proc.stdin.destroyed) proc.stdin.end();
    });
  }

  private onLine(line: string): void {
    let msg: {
      id?: number;
      result?: unknown;
      error?: { code: number; message: string; data?: { key?: string } };
      method?: string;
      params?: unknown;
    };
    try {
      msg = JSON.parse(line);
    } catch {
      this.log(`Sortie du moteur ignorée : ${line.slice(0, 200)}`);
      return;
    }
    if (msg.id === undefined || msg.id === null) {
      if (msg.method) this.onEvent(msg.method, msg.params);
      return;
    }
    const p = this.pending.get(msg.id);
    if (!p) return;
    this.pending.delete(msg.id);
    clearTimeout(p.timer);
    if (msg.error) p.reject(new EngineError(msg.error.message, msg.error.data?.key ?? "unknown", msg.error.code));
    else p.resolve(msg.result);
  }

  private failAll(err: Error): void {
    for (const [id, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(err);
      this.pending.delete(id);
    }
  }

  private log(text: string): void {
    try {
      appendFileSync(this.logFile, `${new Date().toISOString()} ${text}\n`, "utf8");
    } catch {
      /* log unavailable: keep going */
    }
  }
}
