// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Engine access from the interface.
// In the app, window.sme is provided by the preload script. Opened in a plain browser
// (development preview), the interface falls back to simulated responses.

export type CallResult<T> =
  { ok: true; result: T } | { ok: false; error: string; key?: string; data?: Record<string, unknown> };

/** Error from the engines: `key` is translated by the interface, `message` is the technical detail. */
export class EngineCallError extends Error {
  constructor(
    message: string,
    public readonly key: string = "unknown",
    /** Details sent by the engine (for formulas: reason, position, column name). */
    public readonly data: Record<string, unknown> = {},
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
  workspaceAgenda?: (range: { start: string; end: string; lang: string }) => Promise<AgendaData>;
  portfolio?: () => Promise<CallResult<Dashboard>>;
  portfolioExport?: (
    kind: string,
    token: string,
    lang: string,
  ) => Promise<{ ok: boolean; error?: string; key?: string }>;
  archive?: (file: string, archived: boolean) => Promise<Recent[]>;
  duplicate?: (file: string, token: string, name: string) => Promise<CallResult<Recent[]>>;
  updates?: UpdatesBridge;
}

export type UpdateStatus =
  "unsupported" | "off" | "locked" | "idle" | "checking" | "none" | "downloading" | "ready" | "error";
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
interface UpdatesBridge {
  get: () => Promise<UpdateState>;
  check: () => Promise<UpdateState>;
  setAuto: (auto: boolean) => Promise<UpdateState>;
  install: () => Promise<void>;
  openNotes: (url: string) => Promise<void>;
  onState: (listener: (s: UpdateState) => void) => () => void;
}

export type PickKind =
  | "project-save"
  | "project-open"
  | "data-open"
  | "report-save"
  | "csv-save"
  | "html-save"
  | "xlsx-save"
  | "r-save"
  | "ics-save"
  | "ics-open"
  | "xlsx-open"
  | "pack-save"
  | "pack-open"
  | "pdf-save"
  | "folder"
  | "template-open";
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
  archived?: boolean;
  summary?: { indicators: number; achieved: number; on_track: number; late: number; unknown: number; datasets: number };
  /** What the engine reads of the file without opening it. */
  card?: ProjectCard | null;
}

export interface ProjectCard {
  path: string;
  state: "ok" | "older" | "missing" | "unreadable" | "too_new";
  name?: string;
  updated_at?: string;
  model?: string;
  profile?: Pick<
    Profile,
    "code" | "start" | "end" | "frequency" | "donors" | "countries" | "sectors" | "color" | "manager"
  >;
  time_elapsed?: number | null;
  phase?: "not_started" | "running" | "closed" | "unset";
  today?: ProjectToday | null;
  current_period?: Period | null;
  next_deadline?: {
    kind: "data" | "report";
    date: string;
    period: string;
    label_fr: string;
    label_en: string;
  } | null;
  counts?: Record<"results" | "indicators" | "datasets" | "periods" | "places" | "partners", number>;
}

// ----- Project model (mirrors engine/python/sme_engine) -----------------------------

export type Level = "impact" | "outcome" | "output" | "activity" | "detail";
export type Round = "baseline" | "midline" | "endline" | "monitoring";

export interface FrameworkNode {
  id: string;
  parent_id: string | null;
  level: Level;
  title: string;
  description: string;
  assumptions: string;
  code: string;
  depth: number;
  children: number;
}

export interface FrameworkLevel {
  fr: string;
  en: string;
  indicators: boolean;
}
export interface FrameworkModel {
  id: "standard" | "eu" | "usaid" | "un" | "worldbank" | "ifrc" | "custom";
  levels: FrameworkLevel[];
}

/** Types of indicators (specification 6.1). The last five are for values entered period by period. */
export type Unit = "percent" | "mean" | "count" | "ratio" | "rate" | "median" | "score" | "milestone" | "scale";
export const SURVEY_UNITS: Unit[] = ["percent", "mean", "count", "ratio"];
export const ENTRY_UNITS: Unit[] = [
  "count",
  "percent",
  "rate",
  "ratio",
  "mean",
  "median",
  "score",
  "milestone",
  "scale",
];
export type SourceType = "survey" | "routine" | "secondary" | "dhis2";
/** Indicators whose values are entered or imported period by period. */
export const isEntry = (i: { source_type?: SourceType }) =>
  i.source_type === "routine" || i.source_type === "secondary" || i.source_type === "dhis2";
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
  method?: string;
  frequency?: Frequency;
  responsible?: string;
  target_date?: string;
  /** survey: computed from imported data; routine: entered period by period; secondary: from another source. */
  source_type?: SourceType;
  aggregation?: "sum" | "last" | "mean" | "max";
  /** DHIS2 data element or indicator the values are read from. */
  dhis2_id?: string;
  /** For a count of people: unique people (identifiers) or contacts. */
  people?: "" | "unique" | "contacts";
  /** Plausible range of a value entered. */
  bounds?: { min?: number; max?: number };
  categories?: string[];
  /** Reference sheet of the indicator library, and its citation. */
  library_id?: string;
  library_ref?: string;
  /** Keys of the project disaggregations the indicator is reported by. */
  breakdowns?: string[];
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

export type RuleKind =
  | "duplicates"
  | "recode"
  | "range"
  | "exclude"
  | "text"
  | "compute"
  | "classes"
  | "date"
  | "check"
  | "conditional"
  | "formula"
  | "filter"
  | "edit"
  | "r_script";

export interface EditedCell {
  row: number;
  column: string;
  value: string | null;
  old?: string | null;
}

export type ComputeOp = "sum" | "mean" | "min" | "max" | "difference" | "ratio" | "count_values";
export type CondOp = "eq" | "ne" | "in" | "not_in" | "lt" | "le" | "gt" | "ge" | "missing" | "present";
export type TextOp = "trim" | "squeeze" | "lower" | "upper" | "title" | "accents";
export type DateMode = "duration" | "age" | "year" | "month";

export interface RuleCondition {
  column: string;
  op: CondOp;
  value?: string | number | null;
  values?: string[];
}

export interface RuleClass {
  from: number | null;
  to: number | null;
  label: string;
}
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
  op?: ComputeOp;
  target?: string;
  classes?: RuleClass[];
  conditions?: RuleCondition[];
  combine?: "all" | "any";
  value?: string | null;
  /** check: flag, exclude or missing; filter: keep or drop. */
  action?: "flag" | "exclude" | "missing" | "keep" | "drop";
  ops?: TextOp[];
  mode?: DateMode;
  end?: string;
  ref_date?: string;
  ref_column?: string;
  /** Formula (formula and filter kinds), keep or drop for filters. */
  expression?: string;
  cells?: EditedCell[];
  /** R code of an R script step, and whether it is accepted on this computer. */
  code?: string;
  trusted?: boolean;
  /** Plain-language description in both languages, for the advanced kinds. */
  description?: { fr: string; en: string };
  effect?: RuleEffect | null;
}

export interface RuleEffect {
  applied: boolean;
  rows_removed: number;
  cells_changed: number;
  paused?: boolean;
  error?: string;
  error_info?: Record<string, string>;
  message?: string;
  log?: string;
  columns_added?: string[];
  columns_removed?: string[];
  rows_added?: number;
}

export interface UntrustedScript {
  where: "cleaning" | "analysis";
  id: string;
  dataset?: string;
  title?: string;
  code: string;
}

export type AnalysisType = "descriptives" | "crosstab" | "means" | "correlation" | "regression" | "did" | "r_script";

export interface AnalysisSpec {
  id: string;
  type: AnalysisType;
  dataset_id: string;
  title: string;
  note: string;
  level: number;
  in_report: boolean;
  variables?: string[];
  by?: string | null;
  types?: Record<string, "numeric" | "categorical">;
  row?: string;
  column?: string;
  percent?: "row" | "column" | "total";
  outcome?: string;
  group?: string;
  predictors?: string[];
  family?: "linear" | "logistic";
  success?: string[] | null;
  factors?: string[];
  reference?: Record<string, string>;
  treated?: string[];
  period?: string;
  after?: string[];
  code?: string;
  trusted?: boolean;
}

export type CellFormat = "text" | "int" | "num" | "pct" | "p";
export interface ResultTable {
  key: string;
  title: string;
  columns: { key: string; label: string; fmt: CellFormat; data: boolean }[];
  rows: (string | number | null)[][];
}
export interface AnalysisResult {
  id: string;
  error?: string;
  message?: string;
  columns?: string[];
  paused?: boolean;
  tables?: ResultTable[];
  tests?: { key: string; label: string; statistic?: number; df?: number; df2?: number; p_value?: number }[];
  charts?: string[];
  notes?: string[];
  reading?: string[];
  script?: string;
  design?: boolean;
  n?: number;
  script_result?: { output: string; plots: string[]; table: { columns: string[]; rows: (string | null)[][] } | null };
}

export type ReportSection =
  "summary" | "results" | "analyses" | "tests" | "framework" | "annex_data" | "annex_methods" | "sources";
export interface ReportContent {
  sections: { id: ReportSection; on: boolean }[];
  indicators: Record<
    string,
    { on?: boolean; reading?: boolean; chart?: boolean; breakdown?: boolean; definition?: boolean }
  >;
  analyses: Record<string, { reading?: boolean; tables?: boolean; charts?: boolean; script?: boolean }>;
  tests: Record<string, boolean>;
  journal: boolean;
}

export interface FormulaPreview {
  type: "num" | "text" | "bool" | "date" | "col" | "null";
  columns: string[];
  rows: number;
  true?: number;
  false?: number;
  missing?: number;
  distinct?: number;
  sample?: { inputs: Record<string, string | null>; value: string | null }[];
}

export type Frequency = "" | "monthly" | "quarterly" | "semiannual" | "annual" | "rounds" | "other";

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
  /** Set for a stacked dataset: rows of several files of the same structure. */
  stack?: StackSpec;
  /** Set when a merged dataset can no longer be computed (its sources no longer join). */
  error?: string;
  columns: ColumnInfo[];
  /** Columns created by the cleaning rules. */
  derived_columns?: ColumnInfo[];
  rules: Rule[];
  /** Reporting period of the collection: its estimates enter the tracking table there. */
  period?: string;
}

export interface StackStats {
  files: number;
  rows: number;
  rows_by_file: Record<string, number>;
  columns: number;
  missing_columns: Record<string, string[]>;
  names: string[];
}

export interface StackSpec {
  sources: string[];
  source_column: string;
  stats: StackStats;
}

/** Columns of the file and those its cleaning rules create. */
export const allColumns = (ds: Dataset): ColumnInfo[] => [...ds.columns, ...(ds.derived_columns ?? [])];

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
  framework_model: FrameworkModel;
}

export interface Snapshot {
  project: ProjectInfo;
  framework: FrameworkNode[];
  indicators: Indicator[];
  datasets: Dataset[];
  tests: TestSpec[];
  analyses: AnalysisSpec[];
  untrusted_scripts: UntrustedScript[];
  report_content: ReportContent;
  profile: Profile;
  periods: Period[];
  places: Place[];
  partners: Partner[];
  disaggregations: Disaggregation[];
  targets: Record<string, Target[]>;
  submissions: Submission[];
  units: ReportingUnit[];
  gap_comments: Record<string, GapComment[]>;
  tasks: Task[];
  events: AgendaEvent[];
  quality_reviews: Record<string, QualityReview[]>;
  connections: Connection[];
  activities: Activity[];
  budget_lines: BudgetLine[];
  expenses: Expense[];
  workplan: WorkplanSummary;
  feedback: Feedback[];
  feedback_categories: FeedbackCategory[];
  recommendations: Recommendation[];
  risks: Risk[];
  learning_questions: LearningQuestion[];
  lessons: Lesson[];
  meetings: Meeting[];
  evaluations: Evaluation[];
  qual_notes: QualNote[];
  qual_themes: QualTheme[];
}

// ----- M12 report formats -----

export const SECTION_KINDS = [
  "text",
  "tracking",
  "results",
  "gaps",
  "activities",
  "next_activities",
  "budget",
  "beneficiaries",
  "feedback",
  "recommendations",
  "risks",
  "lessons",
  "surveys",
  "evaluations",
  "logframe",
  "calendar",
  "pirs",
] as const;
export type SectionKind = (typeof SECTION_KINDS)[number];
export interface FormatSection {
  key: string;
  kind: SectionKind;
  fr: string;
  en: string;
  hint_fr: string;
  hint_en: string;
}
export interface ReportFormat {
  id: string;
  donor: string;
  fr?: string;
  en?: string;
  name?: string;
  sections: FormatSection[];
  builtin: boolean;
}

// ----- M9 work plan and budget -----

export const ACTIVITY_STATES = ["not_started", "in_progress", "done", "postponed", "cancelled"] as const;
export type ActivityState = (typeof ACTIVITY_STATES)[number];
export const ME_KINDS = ["collection", "dqa", "review", "evaluation", "mission", "other"] as const;
export interface Activity {
  id: string;
  title: string;
  code: string;
  family: "project" | "me";
  me_kind: string;
  node_id: string | null;
  parent_id: string | null;
  start: string;
  end: string;
  actual_start: string;
  actual_end: string;
  status: ActivityState;
  progress: number;
  responsible: string;
  place_ids: string[];
  partner_id: string | null;
  milestone: boolean;
  comment: string;
  origin: string;
  /** Worked out by the engine. */
  expected: number | null;
  late: "" | "late_end" | "late_start";
  derived?: boolean;
}
export interface BudgetLine {
  id: string;
  code: string;
  name: string;
  activity_id: string | null;
  planned: Record<string, number>;
  note: string;
}
export interface Expense {
  id: string;
  line_id: string;
  date: string;
  amount: number;
  label: string;
  ref: string;
}
export interface BudgetSummary {
  lines: {
    line_id: string;
    planned: number;
    planned_to_date: number;
    spent: number;
    rate: number | null;
    rate_to_date: number | null;
  }[];
  planned: number;
  planned_to_date: number;
  spent: number;
  financial: number | null;
  by_period: { period: string; planned: number; spent: number }[];
}
export interface WorkplanSummary {
  day: string;
  time: number | null;
  activities: number;
  physical: number | null;
  expected: number | null;
  late: number;
  budget: BudgetSummary;
  currency: string;
  financial_ahead: number | null;
}
export interface ExpenseImport {
  rows: number;
  read: number;
  total: number;
  bad: number;
  duplicates: number;
  unknown_lines: { line: string; rows: number }[];
}

// ----- M11 accountability and learning -----

export const CHANNELS = ["box", "hotline", "meeting", "in_person", "sms", "other"] as const;
export const FEEDBACK_STATES = ["received", "forwarded", "in_progress", "answered", "closed"] as const;
export type FeedbackState = (typeof FEEDBACK_STATES)[number];
export const SENSITIVITY = ["", "sea", "fraud", "safety", "other"] as const;
export interface FeedbackCategory {
  key: string;
  name: string;
  days: number;
  sensitive: boolean;
}
export interface Feedback {
  id: string;
  received: string;
  channel: (typeof CHANNELS)[number];
  place_id: string | null;
  category: string;
  sensitive: boolean;
  sensitivity: (typeof SENSITIVITY)[number];
  person: string;
  summary: string;
  detail: string;
  response: string;
  status: FeedbackState;
  history: { status: FeedbackState; at: string; note: string }[];
  answered_at: string | null;
  closed_at: string | null;
  deadline: string;
  overdue: boolean;
}
export const REC_SOURCES = ["evaluation", "mission", "review", "audit", "other"] as const;
export const RESPONSES = ["pending", "accepted", "partial", "rejected"] as const;
export const ACTION_STATES = ["todo", "doing", "done"] as const;
export interface RecAction {
  id?: string;
  text: string;
  responsible: string;
  due: string;
  status: (typeof ACTION_STATES)[number];
  done_at?: string | null;
}
export interface Recommendation {
  id: string;
  source: (typeof REC_SOURCES)[number];
  evaluation_id: string | null;
  source_ref: string;
  date: string;
  text: string;
  response: (typeof RESPONSES)[number];
  response_reason: string;
  actions: RecAction[];
  status: "pending" | "in_progress" | "done" | "rejected";
  late_actions: string[];
}
export const REVIEW_MONTHS = [0, 1, 3, 6, 12] as const;
export interface Risk {
  id: string;
  kind: "risk" | "assumption";
  node_id: string | null;
  title: string;
  description: string;
  probability: number;
  impact: number;
  measures: string;
  responsible: string;
  review_months: number;
  status: "active" | "closed";
  reviews: { date: string; probability: number; impact: number; note: string }[];
  created_at: string;
  level: "low" | "medium" | "high";
  review_due: string;
  review_late: boolean;
}
export interface LearningQuestion {
  id: string;
  text: string;
  status: "open" | "answered";
  answer: string;
  node_id: string | null;
}
export interface Lesson {
  id: string;
  date: string;
  title: string;
  context: string;
  finding: string;
  lesson: string;
  use: string;
  question_id: string | null;
  tags: string[];
}
export const MEETING_KINDS = ["review", "quarterly", "learning", "steering", "other"] as const;
export interface Decision {
  id?: string;
  text: string;
  responsible: string;
  due: string;
  as_task: boolean;
  status: (typeof ACTION_STATES)[number];
}
export interface Meeting {
  id: string;
  date: string;
  title: string;
  kind: (typeof MEETING_KINDS)[number];
  participants: string;
  notes: string;
  decisions: Decision[];
}

// ----- M10 evaluations -----

export const EVAL_KINDS = ["midterm", "final", "thematic", "ex_post", "other"] as const;
export const EVAL_STEPS = ["tor", "recruitment", "collection", "draft", "final"] as const;
export const CRITERIA = ["relevance", "coherence", "effectiveness", "efficiency", "impact", "sustainability"] as const;
export interface EvalQuestion {
  id?: string;
  criterion: (typeof CRITERIA)[number];
  text: string;
  indicator_ids: string[];
  sources: string;
  methods: string;
  analysis_ids: string[];
  findings: string;
  conclusion: string;
}
export interface Evaluation {
  id: string;
  title: string;
  kind: (typeof EVAL_KINDS)[number];
  start: string;
  end: string;
  evaluator: string;
  budget: number | null;
  tor: string;
  steps: Record<(typeof EVAL_STEPS)[number], { date: string; done: boolean }>;
  questions: EvalQuestion[];
  conclusions: string;
}
export const NOTE_KINDS = ["interview", "fgd", "observation", "other"] as const;
export interface Excerpt {
  id?: string;
  start: number;
  end: number;
  text?: string;
  theme_ids: string[];
  question_id: string | null;
  memo: string;
}
export interface QualNote {
  id: string;
  title: string;
  kind: (typeof NOTE_KINDS)[number];
  evaluation_id: string | null;
  date: string;
  place: string;
  participants: string;
  text: string;
  excerpts: Excerpt[];
}
export interface QualTheme {
  id: string;
  name: string;
  description: string;
}

export interface Connection {
  id: string;
  kind: "kobo" | "odk" | "dhis2";
  name: string;
  url: string;
  username: string;
  form: { uid?: string; project_id?: string; form_id?: string; name?: string };
  dataset_id: string;
  syncs: { at: string; rows: number }[];
  /** Added by the application: whether the token or password is stored on this computer. */
  has_secret?: boolean;
}

export type QualityScore = "met" | "partly" | "not_met" | "";
export const QUALITY_CRITERIA = ["validity", "reliability", "timeliness", "precision", "integrity"] as const;
export interface QualityReview {
  id: string;
  indicator_id: string;
  date: string;
  scores: Record<(typeof QUALITY_CRITERIA)[number], QualityScore>;
  reviewer: string;
  conclusions: string;
  actions: string;
}
export interface Crosstab {
  rows: { key: string; label: string; values: (number | null)[]; total: number | null }[];
  cols: { key: string; label: string }[];
  col_totals: (number | null)[];
  total: number | null;
  period: string | null;
}
export interface Change {
  submission_id: string;
  period: string;
  label: string;
  unit_name: string;
  action: string;
  at: string;
  channel: string;
}

// ----- monitoring (1.0, milestone J2) -----

export type SubmissionStatus = "draft" | "submitted" | "review" | "returned" | "validated" | "locked";
export interface Submission {
  id: string;
  period: string;
  place_id: string;
  partner_id: string;
  channel: "entry" | "excel" | "import" | "secondary" | "migrated";
  status: SubmissionStatus;
  created_at: string;
  submitted_at: string | null;
  validated_at: string | null;
  comment: string;
  source_ref: string;
  history: { at: string; action: string; status: string; comment?: string }[];
}
export interface ReportingUnit {
  place_id: string;
  partner_id: string;
}
export interface GapComment {
  id: string;
  period: string;
  text: string;
  at: string;
}
export interface Alert {
  key: string;
  check: string;
  severity: "blocking" | "review" | "info";
  indicator_id: string;
  cats: string;
  info: Record<string, number | string | null>;
  justification?: string | null;
}
/** value, numerator, denominator */
export type Cell = [number | null, number | null, number | null];
export interface SubmissionDetail {
  submission: Submission;
  cells: Record<string, Record<string, Cell>>;
  alerts: Alert[];
}
export type TrackStatus = "achieved" | "on_track" | "late" | "not_started" | "no_data" | "unknown";
export interface TrackPoint {
  period: string;
  value: number | null;
  numerator: number | null;
  denominator: number | null;
  reason: string | null;
  provisional: boolean;
  target: number | null;
  to_date: number | null;
  target_to_date: number | null;
  interpolated: boolean;
  rate_to_date: number | null;
  status: TrackStatus;
  trend: "up" | "down" | "flat" | null;
  ci?: [number | null, number | null] | null;
  round?: string | null;
}
export interface TrackRow {
  indicator_id: string;
  kind: "count" | "fraction" | "mean" | "level" | "milestone" | "survey";
  mode: "sum" | "last" | "mean" | "max";
  baseline: number | null;
  target: number | null;
  period: string | null;
  value_period: number | null;
  target_period: number | null;
  rate_period: number | null;
  to_date: number | null;
  target_to_date: number | null;
  interpolated: boolean;
  rate_to_date: number | null;
  status: TrackStatus;
  trend: "up" | "down" | "flat" | null;
  provisional: boolean;
  reason: string | null;
  series: TrackPoint[];
  duplicates_possible?: boolean;
}
export interface Task {
  id: string;
  title: string;
  due: string;
  priority: "low" | "normal" | "high";
  status: "todo" | "doing" | "waiting" | "done";
  note: string;
  assignee: string;
  recurrence: "" | "monthly" | "quarterly";
  link: { kind: string; id: string } | null;
  created_at: string;
  done_at: string | null;
}
export type EventKind = "meeting" | "mission" | "training" | "workshop" | "absence" | "collection" | "other";
export interface AgendaEvent {
  id: string;
  title: string;
  kind: EventKind;
  start: string;
  end: string;
  place: string;
  note: string;
}
/** A deadline or a task worked out from the project, or one typed by the user. */
export interface AgendaItem {
  id: string;
  auto: boolean;
  kind: string;
  title?: string;
  start?: string;
  end?: string;
  due?: string;
  period?: string;
  label?: string;
  priority?: "low" | "normal" | "high";
  status?: string;
  done?: boolean;
  unit_name?: string;
  submission_id?: string | null;
  indicator_id?: string;
  indicator?: string;
  missing?: string[];
  comment?: string;
  place?: string;
  note?: string;
  days?: number;
  project?: string;
  path?: string;
  color?: string;
  personal?: boolean;
  name?: string;
  step?: string;
  category?: string;
  assignee?: string;
  activity_id?: string;
  evaluation_id?: string;
  feedback_id?: string;
  recommendation_id?: string;
  risk_id?: string;
  meeting_id?: string;
}
export interface AgendaData {
  events: AgendaItem[];
  tasks: AgendaItem[];
}
export interface ProjectToday {
  day: string;
  deadlines: AgendaItem[];
  events: AgendaItem[];
  tasks: AgendaItem[];
  alerts: number;
  late: { indicator_id: string; indicator: string; period: string; rate: number | null }[];
  since: string;
  changes: Change[];
  late_activities: { id: string; title: string; late: string; end: string; progress: number }[];
  overdue_feedback: { id: string; summary: string; category: string; deadline: string }[];
  overdue_recommendations: { id: string; text: string; late: number }[];
}

export type PeriodFrequency = "monthly" | "quarterly" | "semiannual" | "annual";
export interface Donor {
  name: string;
  agreement: string;
  frequency: PeriodFrequency | "";
}
export interface Profile {
  code: string;
  summary: string;
  start: string;
  end: string;
  frequency: PeriodFrequency;
  fiscal_start_month: number;
  data_due_days: number;
  report_due_days: number;
  donors: Donor[];
  implementer: string;
  countries: string[];
  sectors: string[];
  currency: string;
  budget: number;
  manager: string;
  color: string;
  place_levels: string[];
  reporting_by: "project" | "partner" | "place" | "partner_place";
  reporting_level: number;
  on_track: number;
}
export interface Period {
  id: string;
  code: string;
  label_fr: string;
  label_en: string;
  start: string;
  end: string;
  data_due: string;
  report_due: string;
  state: "open" | "locked";
  reported_at?: string | null;
  history?: { at: string; action: string; comment?: string }[];
}
export interface Place {
  id: string;
  name: string;
  code: string;
  level: number;
  parent_id: string;
}
export type PartnerRole = "implementing" | "funding" | "technical" | "government" | "community" | "research" | "other";
export interface Partner {
  id: string;
  name: string;
  acronym: string;
  role: PartnerRole;
  contact: string;
  place_ids: string[];
  start: string;
  end: string;
  note: string;
}
export interface Category {
  code: string;
  fr: string;
  en: string;
}
export interface Disaggregation {
  id: string;
  key: string;
  name_fr: string;
  name_en: string;
  categories: Category[];
}
export interface Target {
  id: string;
  indicator_id: string;
  period: string;
  value: number;
  history: { value: number; at: string; reason: string }[];
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
  /** "weights_scale": the two surveys' weights are not on the same scale (counts only). */
  warning?: string;
  mean_weights?: [number, number];
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
  if (!res.ok) throw new EngineCallError(res.error, res.key, res.data ?? {});
  return res.result;
}

export const appInfo = () => bridge.info();
export const pick = (kind: PickKind, defaultName?: string) => bridge.pick?.(kind, defaultName) ?? Promise.resolve(null);
export const recents = () => bridge.recents?.() ?? Promise.resolve([]);
export const recentToken = (file: string) => bridge.recentToken?.(file) ?? Promise.resolve(null);
export const archiveProject = (file: string, archived: boolean) =>
  bridge.archive?.(file, archived) ?? Promise.resolve([] as Recent[]);
export async function duplicateProject(file: string, token: string, name: string): Promise<Recent[]> {
  const res = (await bridge.duplicate?.(file, token, name)) as CallResult<Recent[]> | undefined;
  if (!res) return [];
  if (!res.ok) throw new EngineCallError(res.error, res.key, {});
  return res.result;
}
export async function portfolioDashboard(): Promise<Dashboard> {
  const res = (await bridge.portfolio?.()) as CallResult<Dashboard> | undefined;
  if (!res) throw new EngineCallError("Not available", "not_available", {});
  if (!res.ok) throw new EngineCallError(res.error, res.key, {});
  return res.result;
}
export async function portfolioExport(kind: "note" | "html" | "pdf", token: string, lang: string): Promise<void> {
  const res = await bridge.portfolioExport?.(kind, token, lang);
  if (res && !res.ok) throw new EngineCallError(res.error ?? "", res.key ?? "unknown", {});
}

export type PortfolioStatus = "on_track" | "watch" | "difficulty" | "unknown";
export interface PortfolioCard {
  source: "file" | "pack";
  path: string;
  uid: string;
  name: string;
  profile: {
    code?: string;
    start?: string;
    end?: string;
    donors?: { name: string }[];
    countries?: string[];
    sectors?: string[];
    currency?: string;
    manager?: string;
    color?: string;
  };
  exported_at: string | null;
  time: number | null;
  indicators: number;
  indicators_judged: number;
  indicators_on_track: number | null;
  late_indicators: string[];
  physical: number | null;
  expected: number | null;
  financial: number | null;
  planned: number | null;
  spent: number | null;
  activities: number;
  late_activities: number;
  feedback_overdue: number;
  next_deadline: { kind: "data" | "report"; date: string; label_fr: string; label_en: string } | null;
  deadlines_30: number;
  status: PortfolioStatus;
  reasons: string[];
}
export interface CommonIndicator {
  library_id: string;
  name: string;
  unit: string;
  projects: { name: string; to_date: number | null; target: number | null }[];
  total: number | null;
  target: number | null;
  double_count_possible: boolean;
  not_additive: boolean;
}
export interface PortfolioSettings {
  indicators_on_track: number;
  indicators_difficulty: number;
  financial_margin: number;
  late_activities: number;
}
export interface Dashboard {
  day: string;
  settings: PortfolioSettings;
  cards: PortfolioCard[];
  overview: {
    projects: number;
    by_status: Partial<Record<PortfolioStatus, number>>;
    late_activities: number;
    late_indicators: number;
    feedback_overdue: number;
    deadlines_30: number;
    planned: number;
    spent: number;
  };
  distribution: { donor: Record<string, number>; country: Record<string, number>; sector: Record<string, number> };
  common: CommonIndicator[];
}
export const forgetProject = (file: string) => bridge.forget?.(file) ?? Promise.resolve([]);
export const revealProject = (file: string) => bridge.reveal?.(file) ?? Promise.resolve();
export const saveSummary = (file: string, summary: Record<string, number>) =>
  bridge.saveSummary?.(file, summary) ?? Promise.resolve();
export const openFile = (token: string) => bridge.openFile?.(token) ?? Promise.resolve(false);
export const workspaceAgenda = (start: string, end: string, lang: string) =>
  bridge.workspaceAgenda?.({ start, end, lang }) ?? Promise.resolve({ events: [], tasks: [] } as AgendaData);

/** Automatic updates; absent in the browser preview. */
export const updates = (): UpdatesBridge | null => bridge.updates ?? null;
