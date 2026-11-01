// Stack files of the same structure (one per region, per month or per team) into
// one. Like a merged file, the stacked file keeps no data of its own: it follows
// the cleaning of its sources.

import { useEffect, useState } from "react";
import { call, Round, StackStats } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Field, Notice, Panel } from "../ui";

export function StackPanel({ onClose }: { onClose: () => void }) {
  const { t, number } = useI18n();
  const { run, describe, go, snap } = useProject();
  const list = (snap?.datasets ?? []).filter((d) => !d.error);
  const [ids, setIds] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [round, setRound] = useState<Round | null>(null);
  const [check, setCheck] = useState<{ for: string; ok?: StackStats; err?: string } | null>(null);
  const key = ids.join("|");
  const first = list.find((d) => d.id === ids[0]);

  useEffect(() => {
    if (ids.length < 2) return;
    let live = true;
    call<{ stats: StackStats }>("dataset.stack", { sources: key.split("|"), dry_run: true })
      .then((r) => live && setCheck({ for: key, ok: r.stats }))
      .catch((e) => live && setCheck({ for: key, err: describe(e) }));
    return () => {
      live = false;
    };
  }, [key, ids.length, describe]);
  const current = check?.for === key ? check : null;
  const s = current?.ok;

  const create = async () => {
    const res = await run<{ created: string }>("dataset.stack", {
      sources: ids,
      name: name.trim() || t("stack.defaultName", { n: ids.length }),
      round: round ?? first?.round,
    });
    if (res) {
      onClose();
      go("data", res.created);
    }
  };

  return (
    <Panel
      title={t("stack.title")}
      onClose={onClose}
      testId="stack-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={create} disabled={!s} data-testid="stack-confirm">
            {t("stack.action")}
          </button>
        </>
      }
    >
      <p className="muted">{t("stack.lead")}</p>
      <div className="field">
        <span className="label">{t("stack.files")}</span>
        <div className="value-list">
          {list.map((d) => (
            <label key={d.id} className="check">
              <input
                type="checkbox"
                checked={ids.includes(d.id)}
                onChange={(e) => setIds(e.target.checked ? [...ids, d.id] : ids.filter((x) => x !== d.id))}
                data-testid={`stack-file-${d.name}`}
              />
              <span className="check-text">{d.name}</span>
              <span className="muted small">{number(d.clean_rows, 0)}</span>
            </label>
          ))}
        </div>
      </div>
      {ids.length < 2 && <p className="muted small">{t("stack.chooseTwo")}</p>}
      {current?.err && <Notice kind="error">{current.err}</Notice>}
      {s && (
        <div className="merge-check" data-testid="stack-check">
          <p>
            {t("stack.result", { rows: number(s.rows, 0), files: number(s.files, 0), columns: number(s.columns, 0) })}
          </p>
          {Object.entries(s.missing_columns).map(([file, cols]) => (
            <p key={file} className="muted small">
              {t("stack.missing", {
                file,
                n: number(cols.length, 0),
                cols: cols.slice(0, 5).join(", ") + (cols.length > 5 ? ", ..." : ""),
              })}
            </p>
          ))}
          {Object.keys(s.missing_columns).length === 0 && <p className="muted small">{t("stack.sameColumns")}</p>}
        </div>
      )}
      <Field label={t("data.name")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={name}
            placeholder={t("stack.defaultName", { n: Math.max(ids.length, 2) })}
            onChange={(e) => setName(e.target.value)}
            data-testid="stack-name"
          />
        )}
      </Field>
      <div className="field">
        <span className="label">{t("data.round")}</span>
        <div className="chips">
          {(["baseline", "midline", "endline", "monitoring"] as Round[]).map((r) => (
            <button key={r} className="chip" aria-pressed={(round ?? first?.round) === r} onClick={() => setRound(r)}>
              {t(`rounds.${r}`)}
            </button>
          ))}
        </div>
      </div>
    </Panel>
  );
}
