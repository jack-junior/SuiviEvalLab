// Accès aux moteurs depuis l'interface.
// Dans l'application, window.sme est fourni par le preload. Ouverte dans un simple
// navigateur (aperçu de développement), l'interface utilise des réponses simulées.

export type CallResult<T> = { ok: true; result: T } | { ok: false; error: string };

interface SmeBridge {
  call: (method: string, params?: Record<string, unknown>) => Promise<CallResult<unknown>>;
  info: () => Promise<AppInfo>;
}

export interface AppInfo {
  version: string;
  electron: string;
  packaged: boolean;
  logs: string;
}

export interface Versions {
  engine: string;
  python: string;
  polars: string;
  platform: string;
  r?: { r: string; packages: Record<string, string | null> };
  r_error?: string;
}

export interface Proportion {
  estimate: number;
  ci_low: number;
  ci_high: number;
  level: number;
  n: number;
  successes: number;
  method: string;
  script: string;
}

declare global {
  interface Window {
    sme?: SmeBridge;
  }
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const simulated: SmeBridge = {
  async call(method) {
    await wait(500);
    if (method === "system.versions") {
      return {
        ok: true,
        result: {
          engine: "0.1.0", python: "3.12", polars: "2.0.0", platform: "Aperçu navigateur",
          r: { r: "4.4.3", packages: { survey: "4.5", jsonlite: "2.0.0", nanoarrow: "0.8.0" } },
        },
      };
    }
    if (method === "demo.proportion") {
      return {
        ok: true,
        result: {
          estimate: 0.6205, ci_low: 0.5821, ci_high: 0.6574, level: 0.95, n: 612, successes: 381,
          method: "Proportion pondérée, plan d'enquête (survey::svyciprop, méthode logit)",
          script: "library(survey)\nplan <- svydesign(ids = ~village, strata = ~zone, weights = ~poids, data = donnees, nest = TRUE)\nsvyciprop(~succes, plan, method = \"logit\", level = 0.95)",
        },
      };
    }
    return { ok: true, result: { pong: true } };
  },
  async info() {
    return { version: "0.1.0", electron: "aperçu", packaged: false, logs: "" };
  },
};

export const isSimulated = typeof window !== "undefined" && !window.sme;
const bridge: SmeBridge = (typeof window !== "undefined" && window.sme) || simulated;

export async function call<T>(method: string, params?: Record<string, unknown>): Promise<T> {
  const res = (await bridge.call(method, params)) as CallResult<T>;
  if (!res.ok) throw new Error(res.error);
  return res.result;
}

export const appInfo = () => bridge.info();
