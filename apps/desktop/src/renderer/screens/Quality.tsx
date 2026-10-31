// Data quality diagnosis of a dataset, after its cleaning journal. Each issue can
// become a cleaning rule in one click; the rule then shows in the journal and the report.

import { useEffect, useState } from "react";
import { call, Dataset } from "../api";
import { useI18n } from "../i18n";
import { useLabels } from "../labels";
import { useProject } from "../state";
import { Notice } from "../ui";

export interface QualityIssue {
  key: string;
  severity: "warning" | "info";
  column: string | null;
  count: number;
  share: number;
  samples: string[];
  fix: Record<string, unknown> | null;
  low?: number;
  high?: number;
  median?: number;
}
interface Diagnosis {
  rows: number;
  columns: number;
  issues: QualityIssue[];
}

export function Quality({ ds }: { ds: Dataset }) {
  const { t, number, percent } = useI18n();
  const { run, describe } = useProject();
  const labels = useLabels();
  const [state, setState] = useState<{ for: string; d?: Diagnosis; err?: string } | null>(null);
  // Recomputed whenever the journal changes.
  const signature = `${ds.id}|${ds.clean_rows}|${JSON.stringify(ds.rules.map((r) => [r.id, r.enabled]))}`;

  useEffect(() => {
    let live = true;
    call<Diagnosis>("dataset.quality", { id: ds.id })
      .then((d) => live && setState({ for: signature, d }))
      .catch((e) => live && setState({ for: signature, err: describe(e) }));
    return () => {
      live = false;
    };
  }, [signature, ds.id, describe]);

  const current = state?.for === signature ? state : null;
  if (!current) return <p className="muted">{t("quality.running")}</p>;
  if (current.err) return <Notice kind="error">{current.err}</Notice>;
  const d = current.d!;
  const warnings = d.issues.filter((i) => i.severity === "warning");
  const infos = d.issues.filter((i) => i.severity === "info");

  const apply = async (i: QualityIssue) => {
    if (!i.fix) return;
    await run("cleaning.add", { dataset_id: ds.id, rule: { ...i.fix, note: t(`quality.note_${i.key}`) } });
  };

  const text = (i: QualityIssue) =>
    t(`quality.${i.key}`, {
      n: number(i.count, 0),
      share: percent(i.share),
      col: i.column ? labels.colText(i.column, ds) : "",
      low: i.low !== undefined ? number(i.low, 1) : "",
      high: i.high !== undefined ? number(i.high, 1) : "",
      median: i.median !== undefined ? number(i.median, 1) : "",
    });

  return (
    <div className="stack" data-testid="quality">
      <p className="muted">{t("quality.lead", { rows: number(d.rows, 0), columns: number(d.columns, 0) })}</p>
      {warnings.length === 0 ? (
        <Notice kind="ok">{t("quality.none")}</Notice>
      ) : (
        <ol className="journal" data-testid="quality-warnings">
          {warnings.map((i, k) => (
            <li key={`${i.key}-${i.column}-${k}`} className="quality-row" data-testid={`issue-${i.key}`}>
              <div>
                <div>{text(i)}</div>
                {i.samples.length > 0 && (
                  <div className="muted small">
                    {t("quality.samples")}{" "}
                    {i.samples
                      .map((v) =>
                        i.column && i.key === "unknown_codes" ? v : (labels.val(i.column ?? "", v, ds) ?? v),
                      )
                      .join(", ")}
                  </div>
                )}
              </div>
              {i.fix ? (
                <button className="btn" onClick={() => apply(i)} data-testid={`fix-${i.key}`}>
                  {t(`quality.fix_${i.key}`)}
                </button>
              ) : (
                <span />
              )}
            </li>
          ))}
        </ol>
      )}
      {infos.length > 0 && (
        <details className="quality-infos">
          <summary>{t("quality.infos", { n: number(infos.length, 0) })}</summary>
          <ul>
            {infos.map((i, k) => (
              <li key={`${i.key}-${i.column}-${k}`}>{text(i)}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
