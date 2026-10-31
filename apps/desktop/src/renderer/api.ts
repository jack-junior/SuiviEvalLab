// Engine access from the interface.
// In the app, window.sme is provided by the preload script. Opened in a plain browser
// (development preview), the interface falls back to simulated responses.

export type CallResult<T> = { ok: true; result: T } | { ok: false; error: string; key?: string };

/** Error from the engines: `key` is translated by the interface, `message` is the technical detail. */
export class EngineCallError extends Error {
  constructor(
    message: string,
    public readonly key: string = "unknown",
  ) {
    super(message);
  }
}

interface SmeBridge {
  call: (method: string, params?: Record<string, unknown>) => Promise<CallResult<unknown>>;
  info: () => Promise<AppInfo>;
  pick?: (kind: PickKind, defaultName?: string) => Promise<Picked | null>;
  recents?: () => Promise<Recent[]>;
  recentToken?: (file: string) => Promise<string | null>;
  forget?: (file: string) => Promise<Recent[]>;
  reveal?: (file: string) => Promise<void>;
  saveSummary?: (file: string, summary: Record<string, number>) => Promise<void>;
  openFile?: (token: string) => Promise<boolean>;
}

export type PickKind = "project-save" | "project-open" | "data-open" | "report-save" | "csv-save" | "template-open";
export interface Picked {
  token: string;
  name: string;
}
export interface Recent {
  path: string;
  name: string;
  opened_at: string;
  modified: string | null;
  exists: boolean;
  summary?: { indicators: number; achieved: number; on_track: number; late: number; unknown: number; datasets: number };
}

// ----- Project model (mirrors engine/python/sme_engine) -----------------------------

export type Level = "impact" | "outcome" | "output" | "activity";
export type Round = "baseline" | "midline" | "endline" | "monitoring";

export interface FrameworkNode {
  id: string;
  parent_id: string | null;
  level: Level;
  title: string;
  description: string;
  code: string;
  depth: number;
  children: number;
}

export type Unit = "percent" | "mean" | "count" | "ratio";
export interface Condition {
  column: string;
  values: string[];
}

export interface Indicator {
  id: string;
  node_id: string;
  name: string;
  definition: string;
  unit: Unit;
  direction: "increase" | "decrease";
  column: string | null;
  success_values: string[];
  conditions: Condition[];
  combine: "all" | "any";
  count_mode: "rows" | "sum";
  numerator: string | null;
  denominator: string | null;
  multiplier: number;
  disaggregation: string | null;
  disaggregation2: string | null;
  baseline_manual: number | null;
  target: number | null;
  unit_label: string;
  source: string;
}

export interface ColumnInfo {
  name: string;
  type: "number" | "text";
  missing: number;
  distinct: number;
  rows: number;
  min?: number;
  max?: number;
}

export interface Design {
  weights: string | null;
  strata: string[];
  cluster: string | null;
}

export type RuleKind = "duplicates" | "recode" | "range" | "exclude";
export interface Rule {
  id: string;
  dataset_id: string;
  kind: RuleKind;
  note: string;
  enabled: boolean;
  columns?: string[];
  column?: string;
  from?: string[];
  to?: string | null;
  min?: number | null;
  max?: number | null;
  values?: (string | null)[];
  effect?: { applied: boolean; rows_removed: number; cells_changed: number } | null;
}

export interface Dataset {
  id: string;
  name: string;
  round: Round;
  source_name: string;
  sheet: string | null;
  imported_at: string;
  rows: number;
  clean_rows: number;
  na_values: string[];
  id_column: string | null;
  design: Design;
  attribution?: string;
  labels?: Labels;
  form_source?: { file: string; survey: string; choices: string | null };
  /** Set for a merged dataset: rows computed from two other datasets. */
  merge?: MergeSpec;
  /** Set when a merged dataset can no longer be computed (its sources no longer join). */
  error?: string;
  columns: ColumnInfo[];
  rules: Rule[];
}

export interface MergeStats {
  left_rows: number;
  right_rows: number;
  rows: number;
  matched: number;
  left_unmatched: number;
  right_unmatched: number;
}

export interface MergeSpec {
  left: string;
  right: string;
  left_key: string;
  right_key: string;
  how: "left" | "inner";
  stats: MergeStats;
}

/** Labels by language code ("fr", "en", "default", or a questionnaire language). */
export type LangLabels = Record<string, string>;
export interface Labels {
  columns: Record<string, LangLabels>;
  values: Record<string, Record<string, LangLabels>>;
}

export interface ProjectInfo {
  path: string;
  name: string;
  created_at: string;
  updated_at: string;
  counts: Record<Level, number>;
  report_template: string | null;
}

export interface Snapshot {
  project: ProjectInfo;
  framework: FrameworkNode[];
  indicators: Indicator[];
  datasets: Dataset[];
  tests: TestSpec[];
}

export type TestQuestion = "groups" | "target" | "paired";
export interface TestSpec {
  id?: string;
  question: TestQuestion;
  kind: "proportion" | "mean";
  dataset_id: string;
  outcome: { column: string; values: string[] };
  title: string;
  group?: string;
  target?: number;
  mode?: "columns" | "datasets";
  column_b?: string;
  dataset_b_id?: string;
}

export interface TestResult {
  question: TestQuestion;
  kind: "proportion" | "mean";
  test_key: string;
  statistic: number | null;
  df: number | null;
  df2?: number | null;
  p_value: number | null;
  effect_size: number | null;
  effect_key: string;
  n: number;
  groups?: (Estimate & { group: string })[];
  estimate?: Estimate;
  before?: number;
  after?: number;
  difference?: number;
  notes: string[];
  alternative: { test_key: string; statistic: number | null; p_value: number } | null;
  design: boolean;
  script: string;
}

export interface Inspection {
  file_name: string;
  sheets: string[];
  sheet: string;
  columns: string[];
  sample: (string | null)[][];
  design: Design;
  id_column: string | null;
  form: { survey: string; choices: string | null } | null;
}

export interface Estimate {
  estimate: number | null;
  ci_low: number | null;
  ci_high: number | null;
  se?: number | null;
  n: number;
  successes?: number;
  level?: number;
  method_key?: string;
  script?: string;
  by?: (Estimate & { group: string; error?: string })[];
  error_key?: string;
  detail?: string;
}

export interface Comparison {
  a: Estimate;
  b: Estimate;
  a_id: string;
  b_id: string;
  difference: number;
  ci_low: number | null;
  ci_high: number | null;
  p_value: number | null;
  test_key: string;
  effect_size: number | null;
  effect_key: string;
  error_key?: string;
}

export type Status = "achieved" | "on_track" | "late" | "unknown";

export interface Summary {
  baseline: number | null;
  baseline_source: "data" | "manual" | null;
  current: number | null;
  current_round: Round | null;
  target: number | null;
  achievement: number | null;
  status: Status;
}

export interface IndicatorAnalysis extends Summary {
  indicator: Indicator;
  rounds: { dataset_id: string; round: Round; name: string; result: Estimate }[];
  comparison: Comparison | null;
}

export interface OverviewRow extends Summary {
  indicator_id: string;
  node_id: string;
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
  method_key: "wilson" | "survey_logit";
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
          engine: "0.1.0",
          python: "3.12",
          polars: "2.0.0",
          platform: "Aperçu navigateur",
          r: { r: "4.4.3", packages: { survey: "4.5", jsonlite: "2.0.0", nanoarrow: "0.8.0" } },
        },
      };
    }
    if (method === "demo.proportion") {
      return {
        ok: true,
        result: {
          estimate: 0.6204,
          ci_low: 0.5821,
          ci_high: 0.6574,
          level: 0.95,
          n: 612,
          successes: 381,
          method: "survey::svyciprop (logit)",
          method_key: "survey_logit",
          script:
            'library(survey)\nplan <- svydesign(ids = ~village, strata = ~zone, weights = ~poids, data = donnees, nest = TRUE)\nsvyciprop(~succes, plan, method = "logit", level = 0.95)',
        },
      };
    }
    return { ok: true, result: { pong: true } };
  },
  async info() {
    return { version: "0.1.0", electron: "preview", packaged: false, logs: "" };
  },
};

export const isSimulated = typeof window !== "undefined" && !window.sme;
const bridge: SmeBridge = (typeof window !== "undefined" && window.sme) || simulated;

export async function call<T>(method: string, params?: Record<string, unknown>): Promise<T> {
  const res = (await bridge.call(method, params)) as CallResult<T>;
  if (!res.ok) throw new EngineCallError(res.error, res.key);
  return res.result;
}

export const appInfo = () => bridge.info();
export const pick = (kind: PickKind, defaultName?: string) => bridge.pick?.(kind, defaultName) ?? Promise.resolve(null);
export const recents = () => bridge.recents?.() ?? Promise.resolve([]);
export const recentToken = (file: string) => bridge.recentToken?.(file) ?? Promise.resolve(null);
export const forgetProject = (file: string) => bridge.forget?.(file) ?? Promise.resolve([]);
export const revealProject = (file: string) => bridge.reveal?.(file) ?? Promise.resolve();
export const saveSummary = (file: string, summary: Record<string, number>) =>
  bridge.saveSummary?.(file, summary) ?? Promise.resolve();
export const openFile = (token: string) => bridge.openFile?.(token) ?? Promise.resolve(false);
