// Merge two datasets by a key: individuals (or another Kobo repeat) with their household.
// The merged dataset keeps no data of its own; it follows the cleaning of its sources.

import { useEffect, useState } from "react";
import { call, Dataset, MergeStats, Round } from "../api";
import { useI18n } from "../i18n";
import { useLabels } from "../labels";
import { useProject } from "../state";
import { Field, Notice, Panel } from "../ui";

type How = "left" | "inner";
interface Check {
  stats: MergeStats;
  added: number;
  renamed: string[];
}

/** Kobo repeats link `_parent_index` to `_index`; otherwise a column both files share, ids first. */
export function guessKeys(left: Dataset, right: Dataset): [string, string] {
  const l = left.columns.map((c) => c.name);
  const r = right.columns.map((c) => c.name);
  if (l.includes("_parent_index") && r.includes("_index")) return ["_parent_index", "_index"];
  const common = l.filter((c) => r.includes(c) && !c.startsWith("_"));
  const id = common.find((c) => /(^|_)(id|code|key)$|^id_|_id_/i.test(c)) ?? common[0];
  if (id) return [id, id];
  return [left.id_column ?? l[0] ?? "", right.id_column ?? r[0] ?? ""];
}

export function MergePanel({ onClose }: { onClose: () => void }) {
  const { t, number, percent } = useI18n();
  const { run, describe, go, snap } = useProject();
  const list = (snap?.datasets ?? []).filter((d) => !d.error);
  const [leftId, setLeftId] = useState(list[0]?.id ?? "");
  const [rightId, setRightId] = useState(list[1]?.id ?? "");
  const left = list.find((d) => d.id === leftId);
  const right = list.find((d) => d.id === rightId);
  const [keys, setKeys] = useState<Record<string, [string, string]>>({});
  const pair = `${leftId}|${rightId}`;
  const [leftKey, rightKey] = keys[pair] ?? (left && right ? guessKeys(left, right) : ["", ""]);
  const setKey = (side: 0 | 1, v: string) => setKeys({ ...keys, [pair]: side === 0 ? [v, rightKey] : [leftKey, v] });
  const [how, setHow] = useState<How>("left");
  const [name, setName] = useState("");
  const [round, setRound] = useState<Round | null>(null);
  const [check, setCheck] = useState<{ for: string; ok?: Check; err?: string } | null>(null);
  const labels = useLabels();

  const query = `${pair}|${leftKey}|${rightKey}|${how}`;
  const same = leftId === rightId;
  useEffect(() => {
    if (!leftKey || !rightKey || same) return;
    let live = true;
    call<Check>("dataset.merge", {
      left: leftId,
      right: rightId,
      left_key: leftKey,
      right_key: rightKey,
      how,
      dry_run: true,
    })
      .then((ok) => live && setCheck({ for: query, ok }))
      .catch((e) => live && setCheck({ for: query, err: describe(e) }));
    return () => {
      live = false;
    };
  }, [query, leftId, rightId, leftKey, rightKey, how, same, describe]);
  const current = check?.for === query ? check : null;

  const create = async () => {
    if (!left || !right) return;
    const res = await run<{ created: string }>("dataset.merge", {
      left: leftId,
      right: rightId,
      left_key: leftKey,
      right_key: rightKey,
      how,
      name: name.trim() || t("merge.defaultName", { left: left.name, right: right.name }),
      round: round ?? left.round,
    });
    if (res) {
      onClose();
      go("data", res.created);
    }
  };

  const columnSelect = (ds: Dataset | undefined, value: string, side: 0 | 1, testId: string) => {
    return (
      <Field label={side === 0 ? t("merge.leftKey") : t("merge.rightKey")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={value}
            onChange={(e) => setKey(side, e.target.value)}
            data-testid={testId}
          >
            {(ds?.columns ?? []).map((c) => (
              <option key={c.name} value={c.name}>
                {labels.colText(c.name, ds)}
              </option>
            ))}
          </select>
        )}
      </Field>
    );
  };

  const s = current?.ok?.stats;
  return (
    <Panel
      title={t("merge.title")}
      onClose={onClose}
      testId="merge-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={create} disabled={!current?.ok} data-testid="merge-confirm">
            {t("merge.action")}
          </button>
        </>
      }
    >
      <p className="muted">{t("merge.lead")}</p>
      <Field label={t("merge.left")} hint={t("merge.leftHint")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={leftId}
            onChange={(e) => setLeftId(e.target.value)}
            data-testid="merge-left"
          >
            {list.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label={t("merge.right")} hint={t("merge.rightHint")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={rightId}
            onChange={(e) => setRightId(e.target.value)}
            data-testid="merge-right"
          >
            {list.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      {same ? (
        <Notice kind="info">{t("merge.same")}</Notice>
      ) : (
        <>
          <div className="field-row">
            {columnSelect(left, leftKey, 0, "merge-left-key")}
            {columnSelect(right, rightKey, 1, "merge-right-key")}
          </div>
          <div className="field">
            <span className="label">{t("merge.how")}</span>
            <div className="chips">
              {(["left", "inner"] as How[]).map((h) => (
                <button
                  key={h}
                  className="chip"
                  aria-pressed={how === h}
                  onClick={() => setHow(h)}
                  data-testid={`merge-how-${h}`}
                >
                  {t(`merge.how_${h}`)}
                </button>
              ))}
            </div>
          </div>
          {current?.err && <Notice kind="error">{current.err}</Notice>}
          {s && left && right && (
            <div className="merge-check" data-testid="merge-check">
              <p>
                {t("merge.matched", {
                  matched: number(s.matched, 0),
                  rows: number(s.left_rows, 0),
                  share: percent(s.left_rows ? s.matched / s.left_rows : 0),
                  left: left.name,
                })}
              </p>
              {s.left_unmatched > 0 && (
                <p className="muted small">
                  {how === "left"
                    ? t("merge.unmatchedKept", { n: number(s.left_unmatched, 0) })
                    : t("merge.unmatchedDropped", { n: number(s.left_unmatched, 0) })}
                </p>
              )}
              {s.right_unmatched > 0 && (
                <p className="muted small">
                  {t("merge.rightUnused", { n: number(s.right_unmatched, 0), right: right.name })}
                </p>
              )}
              <p className="muted small">
                {t("merge.result", { rows: number(s.rows, 0), added: number(current.ok!.added, 0) })}
                {current.ok!.renamed.length > 0 &&
                  " " + t("merge.renamed", { cols: current.ok!.renamed.slice(0, 4).join(", ") })}
              </p>
            </div>
          )}
          <Field label={t("data.name")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={name}
                placeholder={left && right ? t("merge.defaultName", { left: left.name, right: right.name }) : ""}
                onChange={(e) => setName(e.target.value)}
                data-testid="merge-name"
              />
            )}
          </Field>
          <div className="field">
            <span className="label">{t("data.round")}</span>
            <div className="chips">
              {(["baseline", "midline", "endline", "monitoring"] as Round[]).map((r) => (
                <button
                  key={r}
                  className="chip"
                  aria-pressed={(round ?? left?.round) === r}
                  onClick={() => setRound(r)}
                >
                  {t(`rounds.${r}`)}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </Panel>
  );
}
