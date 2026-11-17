// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Servers the project reads data from: KoboToolbox and ODK Central forms become
// datasets, DHIS2 values become submissions of the periods.

import { useEffect, useState } from "react";
import { call, Connection, Round, Snapshot } from "../api";
import { useI18n } from "../i18n";
import { periodLabel } from "../monitoring";
import { useProject } from "../state";
import { Empty, Field, Icon, IconButton, Notice, Panel } from "../ui";

type Kind = Connection["kind"];
const KINDS: Kind[] = ["kobo", "odk", "dhis2"];
const ROUNDS: Round[] = ["monitoring", "baseline", "midline", "endline"];

export function ConnectionsPanel({ onClose }: { onClose: () => void }) {
  const { t, date } = useI18n();
  const { snap, go } = useProject();
  const [editing, setEditing] = useState<Connection | "new" | null>(null);
  const [acting, setActing] = useState<{ c: Connection; what: "form" | "sync" | "dhis2" } | null>(null);
  if (!snap) return null;
  return (
    <Panel wide title={t("cx.title")} onClose={onClose} testId="connections-panel">
      <p className="muted small">{t("cx.lead")}</p>
      <div>
        <button className="btn primary" onClick={() => setEditing("new")} data-testid="cx-add">
          <Icon name="plus" /> {t("cx.add")}
        </button>
      </div>
      {snap.connections.length === 0 ? (
        <Empty icon="open" title={t("cx.none")} text={t("cx.noneText")} />
      ) : (
        <ul className="plain">
          {snap.connections.map((c) => {
            const last = c.syncs[c.syncs.length - 1];
            const ds = snap.datasets.find((d) => d.id === c.dataset_id);
            return (
              <li key={c.id} className="box stack" data-testid={`cx-${c.name}`}>
                <div className="row-between">
                  <div>
                    <strong>{c.name}</strong> <span className="tag">{t(`cx.kind_${c.kind}`)}</span>
                    <div className="muted small">
                      {c.url}
                      {c.form.name ? `, ${c.form.name}` : ""}
                    </div>
                    <div className="small">
                      {!c.has_secret && <span className="st-missing sub-status">{t("cx.noSecret")}</span>}{" "}
                      {last
                        ? t(c.kind === "dhis2" ? "cx.lastImport" : "cx.lastSync", {
                            date: date(last.at),
                            n: last.rows,
                          })
                        : t("cx.never")}
                      {ds && (
                        <>
                          {" "}
                          <button className="link" onClick={() => go("data", ds.id)}>
                            {t("cx.openDataset", { name: ds.name })}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="row-actions">
                    {c.kind !== "dhis2" && (
                      <button
                        className="btn small"
                        onClick={() => setActing({ c, what: "form" })}
                        data-testid="cx-form"
                      >
                        {t("cx.chooseForm")}
                      </button>
                    )}
                    {c.kind !== "dhis2" ? (
                      <button
                        className="btn small primary"
                        disabled={!c.form.uid && !c.form.form_id}
                        onClick={() => setActing({ c, what: "sync" })}
                        data-testid="cx-sync"
                      >
                        {t("cx.sync")}
                      </button>
                    ) : (
                      <button
                        className="btn small primary"
                        onClick={() => setActing({ c, what: "dhis2" })}
                        data-testid="cx-dhis2"
                      >
                        {t("cx.importDhis2")}
                      </button>
                    )}
                    <IconButton icon="edit" label={t("common.edit")} onClick={() => setEditing(c)} />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {editing && <ConnectionForm c={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {acting?.what === "form" && <FormChooser c={acting.c} onClose={() => setActing(null)} />}
      {acting?.what === "sync" && <SyncDialog c={acting.c} onClose={() => setActing(null)} />}
      {acting?.what === "dhis2" && <Dhis2Dialog c={acting.c} onClose={() => setActing(null)} />}
    </Panel>
  );
}

function ConnectionForm({ c, onClose }: { c: Connection | null; onClose: () => void }) {
  const { t } = useI18n();
  const { setSnap, describe } = useProject();
  const [x, setX] = useState({
    kind: c?.kind ?? ("kobo" as Kind),
    name: c?.name ?? "",
    url: c?.url ?? "https://kf.kobotoolbox.org",
    username: c?.username ?? "",
    form: c?.form ?? {},
  });
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = async (remove = false) => {
    try {
      const s = remove
        ? await call<Snapshot>("connection.delete", { id: c!.id })
        : await call<Snapshot>("connection.save", {
            id: c?.id,
            connection: x,
            ...(secret ? { secret } : {}),
          });
      setSnap(s);
      onClose();
    } catch (e) {
      setError(describe(e));
    }
  };
  const defaults: Record<Kind, string> = {
    kobo: "https://kf.kobotoolbox.org",
    odk: "https://",
    dhis2: "https://",
  };
  return (
    <Panel
      title={c ? c.name : t("cx.add")}
      onClose={onClose}
      testId="cx-form-panel"
      footer={
        <>
          {c && (
            <button className="btn" onClick={() => save(true)}>
              {t("common.delete")}
            </button>
          )}
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={() => save()} disabled={!x.url.trim()} data-testid="cx-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      {error && <Notice kind="error">{error}</Notice>}
      <div className="chips">
        {KINDS.map((k) => (
          <button
            key={k}
            className="chip"
            aria-pressed={x.kind === k}
            disabled={!!c}
            onClick={() => setX({ ...x, kind: k, url: x.url && x.url !== defaults[x.kind] ? x.url : defaults[k] })}
            data-testid={`cx-kind-${k}`}
          >
            {t(`cx.kind_${k}`)}
          </button>
        ))}
      </div>
      <Field label={t("cx.name")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={x.name}
            onChange={(e) => setX({ ...x, name: e.target.value })}
            data-testid="cx-name"
          />
        )}
      </Field>
      <Field label={t("cx.url")} hint={t(`cx.urlHint_${x.kind}`)}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={x.url}
            onChange={(e) => setX({ ...x, url: e.target.value })}
            data-testid="cx-url"
          />
        )}
      </Field>
      {x.kind !== "kobo" && (
        <Field
          label={t(x.kind === "odk" ? "cx.email" : "cx.username")}
          hint={x.kind === "dhis2" ? t("cx.usernameHint") : undefined}
        >
          {(id) => (
            <input
              id={id}
              className="input"
              value={x.username}
              onChange={(e) => setX({ ...x, username: e.target.value })}
            />
          )}
        </Field>
      )}
      <Field label={t(`cx.secret_${x.kind}`)} hint={t(c?.has_secret ? "cx.secretKeep" : "cx.secretHint")}>
        {(id) => (
          <input
            id={id}
            className="input"
            type="password"
            autoComplete="off"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            data-testid="cx-secret"
          />
        )}
      </Field>
    </Panel>
  );
}

function FormChooser({ c, onClose }: { c: Connection; onClose: () => void }) {
  const { t } = useI18n();
  const { setSnap, describe } = useProject();
  const [items, setItems] = useState<Record<string, string | number | boolean | null>[] | null>(null);
  const [project, setProject] = useState<string | null>(c.kind === "odk" ? null : "");
  const [error, setError] = useState<string | null>(null);
  const load = async (pid: string | null) => {
    try {
      const r = await call<{ forms: Record<string, string | number | boolean | null>[] }>("connection.forms", {
        connection_id: c.id,
        ...(pid ? { project_id: pid } : {}),
      });
      setItems(r.forms);
    } catch (e) {
      setError(describe(e));
    }
  };
  useEffect(() => {
    let live = true;
    call<{ forms: Record<string, string | number | boolean | null>[] }>("connection.forms", { connection_id: c.id })
      .then((r) => live && setItems(r.forms))
      .catch((e) => live && setError(describe(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const choose = async (f: Record<string, string | number | boolean | null>) => {
    if (c.kind === "odk" && !project) {
      setProject(String(f.project_id));
      setItems(null);
      setError(null);
      void load(String(f.project_id));
      return;
    }
    const form =
      c.kind === "kobo"
        ? { uid: String(f.uid), name: String(f.name) }
        : { project_id: project!, form_id: String(f.form_id), name: String(f.name) };
    try {
      setSnap(await call<Snapshot>("connection.save", { id: c.id, connection: { ...c, form } }));
      onClose();
    } catch (e) {
      setError(describe(e));
    }
  };
  return (
    <Panel
      title={t(c.kind === "odk" && !project ? "cx.chooseProject" : "cx.chooseForm")}
      onClose={onClose}
      testId="cx-forms"
    >
      {error && <Notice kind="error">{error}</Notice>}
      {items === null && !error && <p className="muted">{t("cx.loading")}</p>}
      <ul className="plain">
        {(items ?? []).map((f, i) => (
          <li key={i}>
            <button className="link" onClick={() => choose(f)} data-testid="cx-form-item">
              {String(f.name)}
            </button>
            {f.submissions !== undefined && f.submissions !== null && (
              <span className="muted small"> {t("cx.submissions", { n: Number(f.submissions) })}</span>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function SyncDialog({ c, onClose }: { c: Connection; onClose: () => void }) {
  const { t } = useI18n();
  const { setSnap, describe } = useProject();
  const [round, setRound] = useState<Round>("monitoring");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await call<Snapshot & { rows: number }>("connection.sync", { connection_id: c.id, round });
      setSnap(r);
      setDone(r.rows);
    } catch (e) {
      setError(describe(e));
    }
    setBusy(false);
  };
  return (
    <Panel
      title={t("cx.sync")}
      onClose={onClose}
      testId="cx-sync-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.close")}
          </button>
          {done === null && (
            <button className="btn primary" disabled={busy} onClick={run} data-testid="cx-sync-run">
              {busy ? t("cx.loading") : t("cx.sync")}
            </button>
          )}
        </>
      }
    >
      {error && <Notice kind="error">{error}</Notice>}
      {done !== null ? (
        <Notice kind="ok">{t("cx.synced", { n: done })}</Notice>
      ) : (
        <>
          <p className="muted small">{t("cx.syncHint")}</p>
          {!c.dataset_id && (
            <Field label={t("cx.round")}>
              {(id) => (
                <select id={id} className="input" value={round} onChange={(e) => setRound(e.target.value as Round)}>
                  {ROUNDS.map((r) => (
                    <option key={r} value={r}>
                      {t(`rounds.${r}`)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          )}
        </>
      )}
    </Panel>
  );
}

function Dhis2Dialog({ c, onClose }: { c: Connection; onClose: () => void }) {
  const { t, lang } = useI18n();
  const { snap, setSnap, describe } = useProject();
  const today = new Date().toISOString().slice(0, 10);
  const open = (snap?.periods ?? []).filter((p) => p.state !== "locked");
  const [chosen, setChosen] = useState<string[]>(open.filter((p) => p.end < today).map((p) => p.code));
  const [ou, setOu] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ written: number; skipped: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!snap) return null;
  const linked = snap.indicators.filter((i) => i.dhis2_id);
  const coded = snap.places.filter((p) => p.code);
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await call<Snapshot & { written: number; skipped: number }>("dhis2.import", {
        connection_id: c.id,
        periods: chosen,
        org_unit: ou,
      });
      setSnap(r);
      setDone({ written: r.written, skipped: r.skipped });
    } catch (e) {
      setError(describe(e));
    }
    setBusy(false);
  };
  return (
    <Panel
      title={t("cx.importDhis2")}
      onClose={onClose}
      testId="cx-dhis2-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.close")}
          </button>
          {!done && (
            <button
              className="btn primary"
              disabled={busy || !chosen.length || !linked.length || (!coded.length && !ou.trim())}
              onClick={run}
              data-testid="cx-dhis2-run"
            >
              {busy ? t("cx.loading") : t("cx.importDhis2")}
            </button>
          )}
        </>
      }
    >
      {error && <Notice kind="error">{error}</Notice>}
      {done ? (
        <Notice kind="ok">{t("cx.dhis2Done", { n: done.written, skipped: done.skipped })}</Notice>
      ) : (
        <>
          <p className="muted small">
            {linked.length ? t("cx.dhis2Linked", { n: linked.length }) : t("cx.dhis2NoneLinked")}{" "}
            {coded.length ? t("cx.dhis2Places", { n: coded.length }) : t("cx.dhis2NoPlaces")}
          </p>
          {!coded.length && (
            <Field label={t("cx.orgUnit")} hint={t("cx.orgUnitHint")}>
              {(id) => <input id={id} className="input" value={ou} onChange={(e) => setOu(e.target.value)} />}
            </Field>
          )}
          <fieldset className="check-list">
            <legend>{t("cx.periods")}</legend>
            {open.map((p) => (
              <label key={p.id}>
                <input
                  type="checkbox"
                  checked={chosen.includes(p.code)}
                  onChange={() =>
                    setChosen(chosen.includes(p.code) ? chosen.filter((x) => x !== p.code) : [...chosen, p.code])
                  }
                />{" "}
                {periodLabel(p, lang)}
              </label>
            ))}
          </fieldset>
        </>
      )}
    </Panel>
  );
}

/** Search a DHIS2 server for a data element or an indicator to link. */
export function Dhis2Picker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { t } = useI18n();
  const { snap, describe } = useProject();
  const servers = (snap?.connections ?? []).filter((c) => c.kind === "dhis2");
  const [query, setQuery] = useState("");
  const [what, setWhat] = useState<"data" | "indicators">("data");
  const [found, setFound] = useState<{ id: string; name: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const search = async () => {
    setError(null);
    try {
      const r = await call<{ results: { id: string; name: string }[] }>("dhis2.search", {
        connection_id: servers[0].id,
        what,
        query,
      });
      setFound(r.results);
    } catch (e) {
      setError(describe(e));
    }
  };
  return (
    <div className="stack">
      <Field label={t("cx.dhis2Id")} hint={t("cx.dhis2IdHint")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={value}
            onChange={(e) => onChange(e.target.value.trim())}
            data-testid="ind-dhis2-id"
          />
        )}
      </Field>
      {servers.length > 0 && (
        <div className="row-actions">
          <select className="input" value={what} onChange={(e) => setWhat(e.target.value as "data" | "indicators")}>
            <option value="data">{t("cx.dhis2Data")}</option>
            <option value="indicators">{t("cx.dhis2Indicators")}</option>
          </select>
          <input
            className="input"
            value={query}
            placeholder={t("cx.dhis2Search")}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void search()}
          />
          <button className="btn small" onClick={() => void search()} disabled={!query.trim()}>
            {t("cx.search")}
          </button>
        </div>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {found && (
        <ul className="plain small">
          {found.length === 0 && <li className="muted">{t("cx.nothingFound")}</li>}
          {found.map((f) => (
            <li key={f.id}>
              <button className="link" onClick={() => onChange(f.id)}>
                {f.name}
              </button>{" "}
              <span className="muted">{f.id}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
