// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Shared interface pieces: icons, buttons, fields, side panel, confirm dialog,
// empty states, status labels, progress bar and the results chart.

import { KeyboardEvent as ReactKeyboardEvent, ReactNode, useEffect, useId, useRef } from "react";
import type { Estimate, Status } from "./api";
import { useI18n } from "./i18n";

const PATHS: Record<string, ReactNode> = {
  list: <path d="M7 4.5h8M7 9h8M7 13.5h8M3.2 4.5h.6M3.2 9h.6M3.2 13.5h.6" />,
  chat: <path d="M3 4.2h12v7.6H8.6L5.4 14.6v-2.8H3zM6 7.2h6M6 9.4h4" />,
  clipboard: <path d="M6.2 3.5H4.5v11.5h9V3.5h-1.7M6.5 2.6h5v2h-5zM6.5 8.2l1.5 1.5 3-3M6.5 12h5" />,
  plus: <path d="M9 3.5v11M3.5 9h11" />,
  edit: <path d="M11.8 3.6l2.6 2.6-7.6 7.6-3.3.7.7-3.3zM10.4 5l2.6 2.6" />,
  trash: <path d="M3.5 5h11M7.2 5V3.6h3.6V5M5 5l.7 9.4h6.6L13 5M7.6 7.6v4.6M10.4 7.6v4.6" />,
  up: <path d="M9 14V4M4.8 8.2L9 4l4.2 4.2" />,
  down: <path d="M9 4v10M4.8 9.8L9 14l4.2-4.2" />,
  close: <path d="M4.5 4.5l9 9M13.5 4.5l-9 9" />,
  file: <path d="M5 2.5h5.5L13.5 5.5V15.5H5zM10.5 2.5v3h3" />,
  folder: <path d="M2.5 5h4.6l1.4 1.6h7v7.9h-13z" />,
  check: <path d="M4 9.4l3.1 3.1L14 5.6" />,
  download: <path d="M9 3v8.5M5.2 7.8L9 11.6l3.8-3.8M3.5 14.5h11" />,
  open: <path d="M10.5 3.5h4v4M14.5 3.5L8.5 9.5M12.5 10.5v4h-9v-9h4" />,
  table: <path d="M3 4h12v10H3zM3 7.3h12M3 10.6h12M7 4v10" />,
  chart: <path d="M3.5 14.5h11M5.5 12V8M9 12V5M12.5 12V9.5" />,
  doc: <path d="M5 2.5h8v13H5zM7 6h4M7 9h4M7 12h2.5" />,
  tree: <path d="M4 3.5v11M4 6.5h4.5M4 11.5h4.5M8.5 5h6v3h-6zM8.5 10h6v3h-6z" />,
  target: <path d="M9 15A6 6 0 1 0 9 3a6 6 0 0 0 0 12zM9 11.6a2.6 2.6 0 1 0 0-5.2 2.6 2.6 0 0 0 0 5.2z" />,
  home: <path d="M3 8.2L9 3.5l6 4.7V15H3zM7.3 15v-4h3.4v4" />,
  gauge: <path d="M2.8 12.5a6.2 6.2 0 1 1 12.4 0M9 12.5l3-4" />,
  history: <path d="M3.4 9a5.6 5.6 0 1 0 1.7-4M3.2 2.8v2.6h2.6M9 6v3.2l2.2 1.4" />,
  calc: <path d="M4.5 2.5h9v13h-9zM6.5 5h5v2.5h-5zM6.5 10h.1M9 10h.1M11.5 10h.1M6.5 12.8h.1M9 12.8h.1M11.5 12.8h.1" />,
  scale: <path d="M9 3v12M5 15h8M3.5 6.5h11M3.5 6.5L2 10.5h3zM14.5 6.5L13 10.5h3" />,
  plan: <path d="M3 3.5h12v11H3zM3 7h12M7.5 3.5v11M11.2 7v7.5" />,
  calendar: <path d="M3 4.5h12v10H3zM3 7.5h12M6 2.8v3M12 2.8v3M6 10.2h.1M9 10.2h.1M12 10.2h.1M6 12.6h.1M9 12.6h.1" />,
  pin: (
    <path d="M9 15.5s4.5-4.4 4.5-8a4.5 4.5 0 0 0-9 0c0 3.6 4.5 8 4.5 8zM9 9a1.6 1.6 0 1 0 0-3.2A1.6 1.6 0 0 0 9 9z" />
  ),
  lock: <path d="M4.5 8h9v6.5h-9zM6.3 8V5.8a2.7 2.7 0 0 1 5.4 0V8" />,
  people: (
    <path d="M6.5 8.5a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6zM2.5 14.5c0-2.3 1.8-3.8 4-3.8s4 1.5 4 3.8M12 8.3a2 2 0 1 0 0-4M13 10.9c1.5.4 2.5 1.6 2.5 3.6" />
  ),
};

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS | string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

export function IconButton({
  icon,
  label,
  onClick,
  disabled,
  testId,
}: {
  icon: string;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  testId?: string;
}) {
  return (
    <button
      type="button"
      className="icon-btn"
      onClick={onClick}
      aria-label={label}
      title={label}
      disabled={disabled}
      data-testid={testId}
    >
      <Icon name={icon} />
    </button>
  );
}

export function Field({
  label,
  hint,
  children,
  wide,
}: {
  label: string;
  hint?: ReactNode;
  children: (id: string) => ReactNode;
  wide?: boolean;
}) {
  const id = useId();
  return (
    <div className={`field${wide ? " wide" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  );
}

/** Side panel for editing, closed with Escape or the close button. */
export function Panel({
  title,
  onClose,
  children,
  footer,
  testId,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  testId?: string;
  /** A wider panel, for grids of values. */
  wide?: boolean;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  // The latest onClose, without making the effects below run again: callers pass a new
  // function at each render, and focusing again at each render sent the cursor back to
  // the first field at every key typed in another one.
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close.current();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  // Focus the first field once, when the panel opens (the panel itself if it has
  // none); give the focus back to where it was when the panel closes.
  useEffect(() => {
    const before = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const first = ref.current?.querySelector<HTMLElement>("input, textarea, select");
    (first ?? ref.current)?.focus();
    return () => {
      if (before?.isConnected) before.focus();
    };
  }, []);
  // Tab stays inside the panel while it is open.
  const trap = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Tab" || !ref.current) return;
    const items = [
      ...ref.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
      ),
    ].filter((el) => el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };
  return (
    <div className="panel-layer" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className={`panel${wide ? " wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
        tabIndex={-1}
        onKeyDown={trap}
        data-testid={testId}
      >
        <div className="panel-head">
          <h2>{title}</h2>
          <IconButton icon="close" label={t("common.close")} onClick={onClose} />
        </div>
        <div className="panel-body">{children}</div>
        {footer && <div className="panel-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Confirm({
  text,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  text: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="panel-layer center" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="confirm" role="alertdialog" aria-modal="true" aria-label={text}>
        <p>{text}</p>
        <div className="row-actions">
          <button type="button" className="btn" onClick={onCancel} autoFocus>
            {t("common.cancel")}
          </button>
          <button type="button" className="btn danger" onClick={onConfirm} data-testid="confirm">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Empty({
  title,
  text,
  action,
  icon = "file",
}: {
  title: string;
  text: string;
  action?: ReactNode;
  icon?: string;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={22} />
      </span>
      <div>
        <div className="empty-title">{title}</div>
        <p className="muted">{text}</p>
        {action}
      </div>
    </div>
  );
}

export function StatusTag({ status }: { status: Status }) {
  const { t } = useI18n();
  const cls = { achieved: "st-ok", on_track: "st-mid", late: "st-late", unknown: "st-none" }[status];
  return (
    <span className={`status ${cls}`} data-testid={`status-${status}`}>
      <span className="dot-ring" aria-hidden="true" />
      {t(`status.${status}`)}
    </span>
  );
}

export function Progress({ value }: { value: number | null }) {
  const { percent } = useI18n();
  if (value === null) return <span className="muted small">{" "}</span>;
  const w = Math.max(0, Math.min(1, value));
  return (
    <span className="progress" title={percent(value, 0)}>
      <span className="progress-track">
        <span className="progress-fill" style={{ width: `${w * 100}%` }} />
      </span>
      <span className="progress-label">{percent(value, 0)}</span>
    </span>
  );
}

/** Bars with confidence intervals and the target line, drawn in SVG. */
export function ResultChart({
  bars,
  target,
  unit,
}: {
  bars: { label: string; value: Estimate }[];
  target: number | null;
  unit: string;
}) {
  const percentUnit = unit === "percent";
  const digits = unit === "count" ? 0 : 2;
  const { t, number, percent } = useI18n();
  const usable = bars.filter((b) => b.value.estimate !== null);
  if (!usable.length) return null;
  const W = 520;
  const H = 230;
  const pad = { l: 44, r: 12, t: 16, b: 34 };
  const vals = usable.flatMap((b) => [b.value.estimate ?? 0, b.value.ci_high ?? 0]).concat(target ?? 0);
  const rawMax = Math.max(...vals);
  const max = percentUnit ? Math.min(1, Math.max(0.1, Math.ceil((rawMax * 1.15) / 0.1) * 0.1)) : rawMax * 1.2 || 1;
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max);
  const slot = (W - pad.l - pad.r) / usable.length;
  const bw = Math.min(90, slot * 0.46);
  const ticks = Array.from({ length: 5 }, (_, i) => (max * i) / 4);
  const fmt = (v: number) => (percentUnit ? percent(v, 0) : number(v, unit === "count" ? 0 : 1));
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("analysis.chartLabel")}>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} className="chart-grid" />
          <text x={pad.l - 8} y={y(v) + 4} className="chart-axis" textAnchor="end">
            {fmt(v)}
          </text>
        </g>
      ))}
      {usable.map((b, i) => {
        const cx = pad.l + slot * i + slot / 2;
        const v = b.value.estimate ?? 0;
        return (
          <g key={b.label}>
            <rect x={cx - bw / 2} y={y(v)} width={bw} height={y(0) - y(v)} rx="3" className="chart-bar" />
            {b.value.ci_low !== null && b.value.ci_high !== null && (
              <g className="chart-ci">
                <line x1={cx} x2={cx} y1={y(b.value.ci_low)} y2={y(b.value.ci_high)} />
                <line x1={cx - 6} x2={cx + 6} y1={y(b.value.ci_low)} y2={y(b.value.ci_low)} />
                <line x1={cx - 6} x2={cx + 6} y1={y(b.value.ci_high)} y2={y(b.value.ci_high)} />
              </g>
            )}
            <text x={cx} y={y(b.value.ci_high ?? v) - 8} textAnchor="middle" className="chart-value">
              {percentUnit ? percent(v) : number(v, digits)}
            </text>
            <text x={cx} y={H - 12} textAnchor="middle" className="chart-label">
              {b.label}
            </text>
          </g>
        );
      })}
      {target !== null && (
        <g className="chart-target">
          <line x1={pad.l} x2={W - pad.r} y1={y(target)} y2={y(target)} />
          <text x={pad.l + 6} y={y(target) - 6} textAnchor="start">
            {t("indicators.target")} {fmt(target)}
          </text>
        </g>
      )}
    </svg>
  );
}

/** Props of a table row that opens something: reachable with Tab, opened with Enter or Space. */
export function rowOpen(open: () => void) {
  return {
    tabIndex: 0,
    onClick: open,
    onKeyDown: (e: ReactKeyboardEvent<HTMLElement>) => {
      if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) {
        e.preventDefault();
        open();
      }
    },
  };
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "ok"; children: ReactNode }) {
  return (
    <div className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

/** Format an indicator value by its unit: percentage, count (no decimals), mean or ratio. */
export function useValueFormat() {
  const { t, percent, number } = useI18n();
  return (v: number | null | undefined, unit: string, digits?: number) =>
    v === null || v === undefined
      ? t("common.none")
      : unit === "percent"
        ? percent(v, digits ?? 1)
        : number(v, digits ?? (unit === "count" ? 0 : 2));
}
