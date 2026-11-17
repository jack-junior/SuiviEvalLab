// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Project state shared by the screens: the snapshot returned by the engine, and a
// `run` helper that calls the engine, replaces the snapshot when the answer
// contains one, and reports errors in the user's language.

import { createContext, ReactNode, useCallback, useContext, useMemo, useRef, useState } from "react";
import { call, EngineCallError, Snapshot } from "./api";
import { useI18n } from "./i18n";

export type View =
  | "today"
  | "reception"
  | "tracking"
  | "agenda"
  | "workplan"
  | "accountability"
  | "evaluations"
  | "ws_today"
  | "ws_agenda"
  | "ws_dashboard"
  | "overview"
  | "setup"
  | "framework"
  | "indicators"
  | "plan"
  | "data"
  | "analysis"
  | "tests"
  | "workshop"
  | "report"
  | "engines";

interface ProjectState {
  snap: Snapshot | null;
  setSnap: (s: Snapshot | null) => void;
  view: View;
  go: (v: View, focus?: string | null) => void;
  focus: string | null;
  busy: string | null;
  error: string | null;
  clearError: () => void;
  run: <T = Snapshot>(method: string, params?: Record<string, unknown>, busyLabel?: string) => Promise<T | null>;
  describe: (e: unknown) => string;
}

const Ctx = createContext<ProjectState | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { t, hasKey } = useI18n();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [view, setView] = useState<View>("overview");
  const [focus, setFocus] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState<{ error: string | null; resolve: (p: string | null) => void } | null>(null);
  const askPassword = useRef<((error: string | null) => Promise<string | null>) | null>(null);
  askPassword.current = (err) => new Promise((resolve) => setAsking({ error: err, resolve }));

  const describe = useCallback(
    (e: unknown) => {
      if (e instanceof EngineCallError) {
        const key = `errors.${e.key}`;
        return hasKey(key) ? t(key, { detail: e.message }) : t("errors.unknown", { detail: e.message });
      }
      return t("errors.unknown", { detail: String(e) });
    },
    [t, hasKey],
  );

  const run = useCallback(
    async <T,>(method: string, params?: Record<string, unknown>, busyLabel?: string): Promise<T | null> => {
      setBusy(busyLabel ?? method);
      setError(null);
      try {
        let res: T;
        try {
          res = await call<T>(method, params);
        } catch (e) {
          // A protected project: ask its password, then open it again with it.
          if (!(e instanceof EngineCallError) || e.key !== "password_required" || !askPassword.current) throw e;
          let lastError: string | null = null;
          for (;;) {
            const password = await askPassword.current(lastError);
            if (password === null) return null;
            try {
              res = await call<T>(method, { ...params, password });
              break;
            } catch (again) {
              if (!(again instanceof EngineCallError) || again.key !== "password_wrong") throw again;
              lastError = t("errors.password_wrong");
            }
          }
        }
        const maybe = res as unknown as Partial<Snapshot>;
        if (maybe && typeof maybe === "object" && maybe.project && maybe.framework) setSnap(maybe as Snapshot);
        return res;
      } catch (e) {
        setError(describe(e));
        return null;
      } finally {
        setBusy(null);
      }
    },
    [describe, t],
  );

  const go = useCallback((v: View, f: string | null = null) => {
    setView(v);
    setFocus(f);
  }, []);

  const value = useMemo<ProjectState>(
    () => ({ snap, setSnap, view, go, focus, busy, error, clearError: () => setError(null), run, describe }),
    [snap, view, go, focus, busy, error, run, describe],
  );
  return (
    <Ctx.Provider value={value}>
      {children}
      {asking && (
        <PasswordDialog
          error={asking.error}
          onDone={(p) => {
            asking.resolve(p);
            setAsking(null);
          }}
        />
      )}
    </Ctx.Provider>
  );
}

export function useProject(): ProjectState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useProject must be used inside ProjectProvider");
  return ctx;
}

function PasswordDialog({ error, onDone }: { error: string | null; onDone: (password: string | null) => void }) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  return (
    <div className="panel-layer center">
      <form
        className="confirm"
        role="dialog"
        aria-modal="true"
        aria-label={t("sec.passwordTitle")}
        onSubmit={(e) => {
          e.preventDefault();
          if (value) onDone(value);
        }}
      >
        <p>
          <strong>{t("sec.passwordTitle")}</strong>
        </p>
        <p className="muted small">{t("sec.passwordLead")}</p>
        {error && <p className="small warn-text">{error}</p>}
        <input
          className="input"
          type="password"
          autoFocus
          autoComplete="current-password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          data-testid="open-password"
        />
        <div className="row-actions">
          <button type="button" className="btn" onClick={() => onDone(null)}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="btn primary" disabled={!value} data-testid="open-password-ok">
            {t("sec.open")}
          </button>
        </div>
      </form>
    </div>
  );
}
