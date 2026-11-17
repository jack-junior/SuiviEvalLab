// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Working together and security (sections 7 and 8): this computer's identity,
// the protection of the project by a password, the members and their roles, the
// three ways of exchanging changes, conflicts to review, personal data and the
// audit trail.

import { useEffect, useState } from "react";
import { call, Member, pick, Role, ROLES, Snapshot, SyncResult } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Field, Icon, IconButton, Notice, Panel } from "../ui";

export function Team() {
  const { t } = useI18n();
  const { snap } = useProject();
  if (!snap) return null;
  const team = snap.team;
  const admin = team.roles.includes("admin");
  return (
    <div className="stack-lg" data-testid="team">
      <Protection />
      {/* Keyed on the name: setting up the team can set it. */}
      <Identity key={snap.team.me.name} />
      {!team.on ? <StartTeam /> : <Members />}
      {team.on && <Exchanges />}
      {team.on && team.conflicts.length > 0 && <Conflicts />}
      {admin && <PersonalData />}
      {admin && <AuditTrail />}
      {!admin && team.on && <p className="muted small">{t("team.notAdmin")}</p>}
    </div>
  );
}

function Protection() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [mode, setMode] = useState<"set" | "change" | "remove" | null>(null);
  const [old, setOld] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [note, setNote] = useState<string | null>(null);
  if (!snap) return null;
  const team = snap.team;
  const go = async () => {
    const ok =
      mode === "set"
        ? await run("project.encrypt", { password: pw })
        : mode === "change"
          ? await run("project.change_password", { old, password: pw })
          : await run("project.decrypt", { password: old });
    if (ok) {
      setNote(t(`sec.done_${mode}`));
      setMode(null);
      setOld("");
      setPw("");
      setPw2("");
    }
  };
  const valid = mode === "remove" ? !!old : pw.length >= 8 && pw === pw2 && (mode !== "change" || !!old);
  return (
    <section className="box stack-sm" data-testid="protection">
      <h2>{t("sec.title")}</h2>
      {team.encrypted ? (
        <p className="small">
          <Icon name="lock" size={14} /> {t("sec.on")}
        </p>
      ) : (
        <p className="small">{t("sec.off")}</p>
      )}
      {!team.encrypted && team.sensitive && <Notice kind="error">{t("sec.required")}</Notice>}
      {note && <Notice kind="ok">{note}</Notice>}
      {mode ? (
        <div className="stack-sm">
          {(mode === "change" || mode === "remove") && (
            <Field label={t("sec.current")}>
              {(id) => (
                <input id={id} className="input" type="password" value={old} onChange={(e) => setOld(e.target.value)} />
              )}
            </Field>
          )}
          {mode !== "remove" && (
            <div className="grid-2">
              <Field label={t("sec.new")} hint={t("sec.newHint")}>
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    type="password"
                    autoComplete="new-password"
                    value={pw}
                    onChange={(e) => setPw(e.target.value)}
                    data-testid="sec-password"
                  />
                )}
              </Field>
              <Field label={t("sec.repeat")}>
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    type="password"
                    autoComplete="new-password"
                    value={pw2}
                    onChange={(e) => setPw2(e.target.value)}
                    data-testid="sec-password2"
                  />
                )}
              </Field>
            </div>
          )}
          {mode !== "remove" && <p className="muted small">{t("sec.warning")}</p>}
          <div className="row-actions start">
            <button className="btn primary" disabled={!valid} onClick={go} data-testid="sec-confirm">
              {t(`sec.action_${mode}`)}
            </button>
            <button className="btn" onClick={() => setMode(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : (
        <div className="row-actions start">
          {!team.encrypted ? (
            <button className="btn primary" onClick={() => setMode("set")} data-testid="sec-set">
              {t("sec.action_set")}
            </button>
          ) : (
            <>
              <button className="btn" onClick={() => setMode("change")}>
                {t("sec.action_change")}
              </button>
              {!team.sensitive && (
                <button className="btn" onClick={() => setMode("remove")}>
                  {t("sec.action_remove")}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

function Identity() {
  const { t } = useI18n();
  const { snap, describe } = useProject();
  const [name, setName] = useState(snap?.team.me.name ?? "");
  const [note, setNote] = useState<string | null>(null);
  if (!snap) return null;
  const me = snap.team.me;
  const save = async () => {
    try {
      await call("identity.set_name", { name });
      setNote(t("team.nameSaved"));
    } catch (e) {
      setNote(describe(e));
    }
  };
  const exportId = async () => {
    const file = await pick("smeid-save", `${name || "identite"}.smeid`);
    if (!file) return;
    await call("identity.export", { file_token: file.token });
    setNote(t("team.identitySaved", { name: file.name }));
  };
  return (
    <section className="box stack-sm" data-testid="identity">
      <h2>{t("team.identity")}</h2>
      <p className="muted small">{t("team.identityLead")}</p>
      <div className="row-actions start wrap">
        <input
          className="input"
          style={{ maxWidth: 260 }}
          value={name}
          placeholder={t("team.yourName")}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="btn" onClick={save} disabled={!name.trim()}>
          {t("common.save")}
        </button>
        <button className="btn" onClick={exportId} disabled={!name.trim()} data-testid="identity-export">
          <Icon name="download" /> {t("team.exportIdentity")}
        </button>
      </div>
      <p className="small">
        {t("team.fingerprint")} <code>{me.fingerprint}</code>
      </p>
      {note && <p className="small muted">{note}</p>}
    </section>
  );
}

function StartTeam() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [name, setName] = useState(snap?.team.me.name ?? "");
  return (
    <section className="box stack-sm" data-testid="start-team">
      <h2>{t("team.title")}</h2>
      <p className="muted small">{t("team.startLead")}</p>
      <div className="row-actions start">
        <input
          className="input"
          style={{ maxWidth: 260 }}
          value={name}
          placeholder={t("team.yourName")}
          onChange={(e) => setName(e.target.value)}
          data-testid="team-name"
        />
        <button
          className="btn primary"
          disabled={!name.trim()}
          onClick={() => run("team.start", { name })}
          data-testid="team-start"
        >
          {t("team.start")}
        </button>
      </div>
    </section>
  );
}

function Members() {
  const { t } = useI18n();
  const { snap } = useProject();
  const [editing, setEditing] = useState<Member | "new" | null>(null);
  const [joining, setJoining] = useState<Member | null>(null);
  if (!snap) return null;
  const team = snap.team;
  const admin = team.roles.includes("admin");
  const partner = new Map(snap.partners.map((p) => [p.id, p.acronym || p.name]));
  return (
    <section className="stack-sm" data-testid="members">
      <div className="row-between">
        <h2>{t("team.members")}</h2>
        {admin && (
          <button className="btn primary" onClick={() => setEditing("new")} data-testid="member-add">
            <Icon name="plus" /> {t("team.addMember")}
          </button>
        )}
      </div>
      {!team.trusted && <Notice kind="error">{t("team.untrusted")}</Notice>}
      <table className="table">
        <thead>
          <tr>
            <th>{t("team.member")}</th>
            <th>{t("team.roles")}</th>
            <th>{t("team.fingerprintCol")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {team.members.map((m) => (
            <tr key={m.id} className={m.active ? "" : "muted"}>
              <td>
                <strong>{m.name}</strong> {m.me && <span className="tag">{t("team.you")}</span>}
                {m.id === team.owner && <span className="tag">{t("team.owner")}</span>}
                {!m.active && <span className="tag">{t("team.inactive")}</span>}
              </td>
              <td className="small">
                {m.roles.map((r) => t(`team.role_${r}`)).join(", ")}
                {m.partner_ids.length > 0 && ` (${m.partner_ids.map((p) => partner.get(p)).join(", ")})`}
              </td>
              <td className="small">
                <code>{m.fingerprint}</code>
              </td>
              <td className="row-actions">
                {admin && !m.me && (
                  <button className="btn small" onClick={() => setJoining(m)} data-testid="member-join-file">
                    {t("team.joinFile")}
                  </button>
                )}
                {admin && <IconButton icon="edit" label={t("common.edit")} onClick={() => setEditing(m)} />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">{t("team.joinHow")}</p>
      {editing && <MemberPanel member={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {joining && <JoinFilePanel member={joining} onClose={() => setJoining(null)} />}
    </section>
  );
}

function MemberPanel({ member, onClose }: { member: Member | null; onClose: () => void }) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [file, setFile] = useState<{ token: string; name: string } | null>(null);
  const [roles, setRoles] = useState<Role[]>(member?.roles ?? ["officer"]);
  const [partners, setPartners] = useState<string[]>(member?.partner_ids ?? []);
  const [active, setActive] = useState(member?.active ?? true);
  if (!snap) return null;
  const toggle = (r: Role) => setRoles(roles.includes(r) ? roles.filter((x) => x !== r) : [...roles, r]);
  const save = async () => {
    const ok = member
      ? await run("member.update", { id: member.id, roles, partner_ids: partners, active })
      : await run("member.add", { file_token: file!.token, roles, partner_ids: partners });
    if (ok) onClose();
  };
  return (
    <Panel
      title={member ? member.name : t("team.addMember")}
      onClose={onClose}
      testId="member-panel"
      footer={
        <>
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button
            className="btn primary"
            onClick={save}
            disabled={(!member && !file) || !roles.length || (roles.includes("partner") && !partners.length)}
            data-testid="member-save"
          >
            {t("common.save")}
          </button>
        </>
      }
    >
      {!member && (
        <>
          <p className="muted small">{t("team.addLead")}</p>
          <div>
            <button
              className="btn"
              onClick={async () => setFile(await pick("smeid-open"))}
              data-testid="member-identity"
            >
              <Icon name="open" /> {file ? file.name : t("team.chooseIdentity")}
            </button>
          </div>
        </>
      )}
      <h3>{t("team.roles")}</h3>
      <div className="stack-sm">
        {ROLES.map((r) => (
          <label key={r} className="check">
            <input type="checkbox" checked={roles.includes(r)} onChange={() => toggle(r)} data-testid={`role-${r}`} />{" "}
            <strong>{t(`team.role_${r}`)}</strong> <span className="muted small">{t(`team.roleText_${r}`)}</span>
          </label>
        ))}
      </div>
      {roles.includes("partner") && (
        <Field label={t("team.partnerScope")}>
          {(id) => (
            <select
              id={id}
              className="input"
              multiple
              size={Math.min(6, Math.max(2, snap.partners.length))}
              value={partners}
              onChange={(e) => setPartners(Array.from(e.target.selectedOptions).map((o) => o.value))}
            >
              {snap.partners.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.acronym || p.name}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}
      {member && !member.me && (
        <label className="check">
          <input type="checkbox" checked={!active} onChange={(e) => setActive(!e.target.checked)} />{" "}
          {t("team.deactivate")}
        </label>
      )}
    </Panel>
  );
}

function JoinFilePanel({ member, onClose }: { member: Member; onClose: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [pw, setPw] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const make = async () => {
    const file = await pick("join-save", `${member.name}.smejoin`);
    if (!file) return;
    if (await run("team.join_file", { member_id: member.id, file_token: file.token, password: pw })) setDone(file.name);
  };
  return (
    <Panel title={t("team.joinFile")} onClose={onClose} testId="join-file-panel">
      <p className="muted small">{t("team.joinFileLead", { name: member.name })}</p>
      <Field label={t("team.joinPassword")} hint={t("sec.newHint")}>
        {(id) => (
          <input id={id} className="input" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="off" />
        )}
      </Field>
      <div>
        <button className="btn primary" disabled={pw.length < 8} onClick={make}>
          {t("team.makeJoinFile")}
        </button>
      </div>
      {done && <Notice kind="ok">{t("team.joinFileDone", { name: done })}</Notice>}
    </Panel>
  );
}

function Exchanges() {
  const { t, date } = useI18n();
  const { snap, run } = useProject();
  const [url, setUrl] = useState(snap?.team.server ?? "");
  const [key, setKey] = useState("");
  const [result, setResult] = useState<SyncResult | null>(null);
  const [member, setMember] = useState("");
  if (!snap) return null;
  const team = snap.team;
  const partnerOnly = team.roles.length === 1 && team.roles[0] === "partner";
  const show = (r: (Snapshot & { sync: SyncResult }) | null) => r && setResult(r.sync);
  const chooseFolder = async () => {
    const f = await pick("folder");
    if (f) show(await run<Snapshot & { sync: SyncResult }>("sync.folder", { file_token: f.token }, "sync"));
  };
  const others = team.members.filter((m) => !m.me && m.active);
  return (
    <section className="box stack" data-testid="exchanges">
      <h2>{t("sync.title")}</h2>
      <p className="muted small">{t("sync.lead")}</p>
      {team.last_run && <p className="small">{t("sync.lastRun", { date: date(team.last_run) })}</p>}
      {result && (
        <Notice kind={result.errors?.length ? "error" : "ok"}>
          {t("sync.result", {
            applied: result.applied,
            conflicts: result.conflicts,
            requests: result.requests,
            refused: result.refused,
          })}
          {result.errors?.length ? ` ${t("sync.errors", { n: result.errors.length })}` : ""}
        </Notice>
      )}
      <div className="stack-sm">
        <h3>{t("sync.packages")}</h3>
        <p className="muted small">{t("sync.packagesLead")}</p>
        <div className="row-actions start wrap">
          <select
            className="input"
            style={{ maxWidth: 240 }}
            value={member}
            onChange={(e) => setMember(e.target.value)}
            aria-label={t("team.member")}
          >
            <option value="">{t("sync.forWhom")}</option>
            {others.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          <button
            className="btn"
            disabled={!member}
            onClick={async () => {
              const f = await pick("sync-save", `${snap.project.name.slice(0, 30)}.smesync`);
              if (f) await run("sync.package", { member_id: member, file_token: f.token });
            }}
            data-testid="sync-package"
          >
            <Icon name="download" /> {t("sync.makePackage")}
          </button>
          <button
            className="btn"
            onClick={async () => {
              const f = await pick("sync-open");
              if (f) show(await run<Snapshot & { sync: SyncResult }>("sync.receive", { file_token: f.token }, "sync"));
            }}
            data-testid="sync-receive"
          >
            <Icon name="open" /> {t("sync.receive")}
          </button>
        </div>
      </div>
      {!partnerOnly && (
        <div className="stack-sm">
          <h3>{t("sync.folder")}</h3>
          <p className="muted small">{t("sync.folderLead")}</p>
          <div className="row-actions start wrap">
            {team.folder && <code className="small">{team.folder}</code>}
            <button className="btn" onClick={chooseFolder}>
              {team.folder ? t("sync.changeFolder") : t("sync.chooseFolder")}
            </button>
            {team.folder && (
              <button className="btn primary" onClick={async () => show(await run("sync.folder", {}, "sync"))}>
                {t("sync.now")}
              </button>
            )}
          </div>
        </div>
      )}
      {!partnerOnly && (
        <div className="stack-sm">
          <h3>{t("sync.server")}</h3>
          <p className="muted small">{t("sync.serverLead")}</p>
          <div className="row-actions start wrap">
            <input
              className="input"
              style={{ maxWidth: 320 }}
              placeholder="https://"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <input
              className="input"
              style={{ maxWidth: 220 }}
              type="password"
              placeholder={t("sync.accessKey")}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              autoComplete="off"
            />
            <button
              className="btn primary"
              disabled={!url.trim()}
              onClick={async () =>
                show(
                  await run(
                    "sync.server",
                    { url, connection_id: `sync-${snap.project.uid}`, ...(key ? { secret: key } : {}) },
                    "sync",
                  ),
                )
              }
            >
              {t("sync.now")}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function Conflicts() {
  const { t, date, hasKey } = useI18n();
  const { snap, run } = useProject();
  if (!snap) return null;
  const admin = snap.team.roles.includes("admin");
  return (
    <section className="stack-sm" data-testid="conflicts">
      <h2>{t("sync.conflicts", { n: snap.team.conflicts.length })}</h2>
      <p className="muted small">{t("sync.conflictsLead")}</p>
      <table className="table compact">
        <thead>
          <tr>
            <th>{t("sync.kind")}</th>
            <th>{t("sync.object")}</th>
            <th>{t("sync.author")}</th>
            <th>{t("sync.when")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {snap.team.conflicts.map((c) => (
            <tr key={c.id}>
              <td>{t(`sync.kind_${c.kind}`)}</td>
              <td className="small">
                {hasKey(`sync.table_${c.table}`) ? t(`sync.table_${c.table}`) : c.table} {preview(c.row)}
              </td>
              <td className="small">{c.author}</td>
              <td className="small">{date(c.at)}</td>
              <td className="row-actions">
                {admin && (
                  <>
                    <button className="btn small" onClick={() => run("conflict.resolve", { id: c.id, accept: true })}>
                      {t("sync.accept")}
                    </button>
                    <button className="btn small" onClick={() => run("conflict.resolve", { id: c.id, accept: false })}>
                      {t("sync.drop")}
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function preview(row: Record<string, unknown> | null): string {
  if (!row) return "";
  try {
    const spec = typeof row.spec === "string" ? (JSON.parse(row.spec) as Record<string, unknown>) : row;
    const name = spec.name ?? spec.title ?? spec.text ?? spec.summary ?? row.value;
    return name === undefined || name === null ? "" : `: ${String(name).slice(0, 80)}`;
  } catch {
    return "";
  }
}

function PersonalData() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [months, setMonths] = useState(String(snap?.team.retention_months ?? 0));
  const [note, setNote] = useState<string | null>(null);
  if (!snap) return null;
  return (
    <section className="box stack-sm" data-testid="personal-data">
      <h2>{t("priv.title")}</h2>
      <p className="muted small">{t("priv.lead")}</p>
      <div className="row-actions start">
        <Field label={t("priv.months")} hint={t("priv.monthsHint")}>
          {(id) => (
            <input
              id={id}
              className="input num"
              style={{ maxWidth: 100 }}
              inputMode="numeric"
              value={months}
              onChange={(e) => setMonths(e.target.value.replace(/\D/g, ""))}
            />
          )}
        </Field>
        <button className="btn" onClick={() => run("privacy.settings", { retention_months: Number(months || 0) })}>
          {t("common.save")}
        </button>
        <button
          className="btn"
          disabled={!snap.team.retention_months}
          onClick={async () => {
            const r = await run<Snapshot & { purged: number }>("privacy.purge", {});
            if (r) setNote(t("priv.purged", { n: r.purged }));
          }}
        >
          {t("priv.purge")}
        </button>
      </div>
      {note && <Notice kind="ok">{note}</Notice>}
    </section>
  );
}

interface AuditEntry {
  seq: number;
  at: string;
  name: string;
  member: string;
  action: string;
  object: string;
  detail: string;
}

function AuditTrail() {
  const { t, date, hasKey } = useI18n();
  const { snap } = useProject();
  const [data, setData] = useState<{ entries: AuditEntry[]; intact: boolean; count: number } | null>(null);
  const stamp = snap?.project.updated_at;
  useEffect(() => {
    call<{ entries: AuditEntry[]; intact: boolean; count: number }>("audit.list")
      .then(setData)
      .catch(() => undefined);
  }, [stamp]);
  if (!data) return null;
  return (
    <details className="box" data-testid="audit">
      <summary>
        <strong>{t("audit.title")}</strong> <span className="muted small">{t("audit.count", { n: data.count })}</span>{" "}
        {data.intact ? (
          <span className="tag ok">{t("audit.intact")}</span>
        ) : (
          <span className="tag warn">{t("audit.broken")}</span>
        )}
      </summary>
      <p className="muted small">{t("audit.lead")}</p>
      <table className="table compact">
        <tbody>
          {data.entries.slice(0, 200).map((e) => (
            <tr key={e.seq}>
              <td className="small">{date(e.at)}</td>
              <td className="small">{e.name || e.member.slice(0, 8)}</td>
              <td className="small">{hasKey(`audit.a_${e.action}`) ? t(`audit.a_${e.action}`) : e.action}</td>
              <td className="small muted">{e.object}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** Open the invitation file an administrator sent: the copy becomes this member's project. */
export function JoinPanel({ onClose, onJoined }: { onClose: () => void; onJoined: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [file, setFile] = useState<{ token: string; name: string } | null>(null);
  const [pw, setPw] = useState("");
  const [own, setOwn] = useState("");
  const [identity, setIdentity] = useState<{ fingerprint: string; name: string } | null>(null);
  useEffect(() => {
    call<{ fingerprint: string; name: string }>("identity.get")
      .then(setIdentity)
      .catch(() => undefined);
  }, []);
  const join = async () => {
    const target = await pick("project-save", (file?.name ?? "projet").replace(/\.smejoin$/i, ".sme"));
    if (!target || !file) return;
    const ok = await run("team.join", {
      file_token: file.token,
      target_token: target.token,
      password: pw,
      ...(own ? { new_password: own } : {}),
    });
    if (ok) onJoined();
  };
  const exportId = async () => {
    const f = await pick("smeid-save", `${identity?.name || "identite"}.smeid`);
    if (f) await call("identity.export", { file_token: f.token });
  };
  return (
    <Panel
      title={t("team.joinTitle")}
      onClose={onClose}
      testId="join-panel"
      footer={
        <>
          <span className="spacer" />
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button
            className="btn primary"
            disabled={!file || !pw || (!!own && own.length < 8)}
            onClick={join}
            data-testid="join-run"
          >
            {t("team.join")}
          </button>
        </>
      }
    >
      <ol className="small stack-sm">
        <li>
          {t("team.joinStep1")}{" "}
          <button className="link" onClick={exportId}>
            {t("team.exportIdentity")}
          </button>
          {identity && (
            <div className="muted">
              {t("team.fingerprint")} <code>{identity.fingerprint}</code>
            </div>
          )}
        </li>
        <li>{t("team.joinStep2")}</li>
        <li>{t("team.joinStep3")}</li>
      </ol>
      <div>
        <button className="btn" onClick={async () => setFile(await pick("join-open"))}>
          <Icon name="open" /> {file ? file.name : t("team.chooseJoin")}
        </button>
      </div>
      <Field label={t("team.joinPassword")}>
        {(id) => <input id={id} className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} />}
      </Field>
      <Field label={t("team.ownPassword")} hint={t("team.ownPasswordHint")}>
        {(id) => (
          <input
            id={id}
            className="input"
            type="password"
            autoComplete="new-password"
            value={own}
            onChange={(e) => setOwn(e.target.value)}
          />
        )}
      </Field>
    </Panel>
  );
}
