// Project state shared by the screens: the snapshot returned by the engine, and a
// `run` helper that calls the engine, replaces the snapshot when the answer
// contains one, and reports errors in the user's language.

import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";
import { call, EngineCallError, Snapshot } from "./api";
import { useI18n } from "./i18n";

export type View = "overview" | "framework" | "indicators" | "data" | "analysis" | "report" | "engines";

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
        const res = await call<T>(method, params);
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
    [describe],
  );

  const go = useCallback((v: View, f: string | null = null) => {
    setView(v);
    setFocus(f);
  }, []);

  const value = useMemo<ProjectState>(
    () => ({ snap, setSnap, view, go, focus, busy, error, clearError: () => setError(null), run, describe }),
    [snap, view, go, focus, busy, error, run, describe],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useProject(): ProjectState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useProject must be used inside ProjectProvider");
  return ctx;
}
