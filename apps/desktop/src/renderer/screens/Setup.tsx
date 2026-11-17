// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Project sheet: what the project is, its reporting calendar, where it works,
// with whom, and how its results are broken down.

import { useEffect, useMemo, useState } from "react";
import {
  call,
  Category,
  Disaggregation,
  Donor,
  PeriodFrequency as Frequency,
  Partner,
  PartnerRole,
  Period,
  Place,
  Profile,
} from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Confirm, Empty, Field, Icon, IconButton, Notice, Panel } from "../ui";
import { Team } from "./Team";

type Tab = "profile" | "calendar" | "places" | "partners" | "disaggregations" | "team";
const TABS: Tab[] = ["profile", "calendar", "places", "partners", "disaggregations", "team"];
const FREQUENCIES: Frequency[] = ["monthly", "quarterly", "semiannual", "annual"];
const ROLES: PartnerRole[] = ["implementing", "funding", "technical", "government", "community", "research", "other"];

export function Setup() {
  const { t } = useI18n();
  const { snap, focus } = useProject();
  const [tab, setTab] = useState<Tab>(focus === "team" ? "team" : "profile");
  if (!snap) return null;
  const counts: Partial<Record<Tab, number>> = {
    calendar: snap.periods.length,
    places: snap.places.length,
    partners: snap.partners.length,
    disaggregations: snap.disaggregations.length,
  };
  return (
    <div className="inner wide">
      <div>
        <h1>{t("setup.title")}</h1>
        <p className="lead">{t("setup.lead")}</p>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map((k) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            className="tab"
            onClick={() => setTab(k)}
            data-testid={`setup-tab-${k}`}
          >
            {t(`setup.tab_${k}`)}
            {!!counts[k] && <span className="tab-count">{counts[k]}</span>}
          </button>
        ))}
      </div>
      {tab === "profile" && <ProfileForm onCalendar={() => setTab("calendar")} />}
      {tab === "calendar" && <Calendar />}
      {tab === "places" && <Places />}
      {tab === "partners" && <Partners />}
      {tab === "disaggregations" && <Disaggregations />}
      {tab === "team" && <Team />}
    </div>
  );
}

// ----- profile ---------------------------------------------------------------------

const list = (s: string) =>
  s
    .split(/[,;\n]/)
    .map((x) => x.trim())
    .filter(Boolean);

function ProfileForm({ onCalendar }: { onCalendar: () => void }) {
  const { t, lang } = useI18n();
  const { snap, run } = useProject();
  const saved = snap!.profile;
  const [p, setP] = useState<Profile>(saved);
  const [countries, setCountries] = useState(saved.countries.join(", "));
  const [sectors, setSectors] = useState(saved.sectors.join(", "));
  const [levels, setLevels] = useState(saved.place_levels.join(", "));
  const [note, setNote] = useState<string | null>(null);
  const set = (patch: Partial<Profile>) => setP({ ...p, ...patch });
  const setDonor = (i: number, patch: Partial<Donor>) =>
    set({ donors: p.donors.map((d, k) => (k === i ? { ...d, ...patch } : d)) });

  const calendarChanged =
    p.start !== saved.start ||
    p.end !== saved.end ||
    p.frequency !== saved.frequency ||
    p.fiscal_start_month !== saved.fiscal_start_month ||
    p.data_due_days !== saved.data_due_days ||
    p.report_due_days !== saved.report_due_days;

  const save = async () => {
    const first = snap!.periods.length === 0 && !!p.start && !!p.end;
    const s = await run("profile.set", {
      profile: {
        ...p,
        countries: list(countries),
        sectors: list(sectors),
        place_levels: list(levels),
        donors: p.donors.filter((d) => d.name.trim()),
      },
      generate_periods: first,
    });
    if (!s) return;
    setP(s.profile);
    if (first) setNote(t("setup.calendarMade", { n: s.periods.length }));
    else if (calendarChanged && snap!.periods.length) setNote(t("setup.calendarStale"));
    else setNote(t("setup.saved"));
  };

  const months = Array.from({ length: 12 }, (_, i) =>
    new Intl.DateTimeFormat(lang === "en" ? "en-GB" : "fr-FR", { month: "long" }).format(new Date(2026, i, 1)),
  );

  return (
    <div className="stack" data-testid="profile-form">
      {note && (
        <Notice kind="ok">
          {note}{" "}
          {note === t("setup.calendarStale") && (
            <button className="link" onClick={onCalendar}>
              {t("setup.openCalendar")}
            </button>
          )}
        </Notice>
      )}
      <section className="box stack">
        <h2>{t("setup.identity")}</h2>
        <div className="form-grid">
          <Field label={t("setup.code")}>
            {(id) => <input id={id} className="input" value={p.code} onChange={(e) => set({ code: e.target.value })} />}
          </Field>
          <Field label={t("setup.manager")}>
            {(id) => (
              <input id={id} className="input" value={p.manager} onChange={(e) => set({ manager: e.target.value })} />
            )}
          </Field>
          <Field label={t("setup.implementer")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={p.implementer}
                onChange={(e) => set({ implementer: e.target.value })}
              />
            )}
          </Field>
          <Field label={t("setup.countries")} hint={t("setup.listHint")}>
            {(id) => (
              <input id={id} className="input" value={countries} onChange={(e) => setCountries(e.target.value)} />
            )}
          </Field>
          <Field label={t("setup.sectors")} hint={t("setup.listHint")}>
            {(id) => <input id={id} className="input" value={sectors} onChange={(e) => setSectors(e.target.value)} />}
          </Field>
          <Field label={t("setup.color")}>
            {(id) => (
              <input
                id={id}
                type="color"
                className="input color"
                value={p.color}
                onChange={(e) => set({ color: e.target.value })}
              />
            )}
          </Field>
          <Field label={t("setup.summary")} wide>
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={3}
                value={p.summary}
                onChange={(e) => set({ summary: e.target.value })}
              />
            )}
          </Field>
        </div>
      </section>

      <section className="box stack">
        <h2>{t("setup.funding")}</h2>
        <div className="form-grid">
          <Field label={t("setup.currency")}>
            {(id) => (
              <input
                id={id}
                className="input"
                maxLength={8}
                value={p.currency}
                onChange={(e) => set({ currency: e.target.value.toUpperCase() })}
              />
            )}
          </Field>
          <Field label={t("setup.budget")}>
            {(id) => (
              <input
                id={id}
                className="input"
                inputMode="decimal"
                value={p.budget || ""}
                onChange={(e) => set({ budget: Number(e.target.value.replace(/\s/g, "").replace(",", ".")) || 0 })}
              />
            )}
          </Field>
        </div>
        <table className="table compact">
          <thead>
            <tr>
              <th>{t("setup.donor")}</th>
              <th>{t("setup.agreement")}</th>
              <th>{t("setup.donorFrequency")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {p.donors.map((d, i) => (
              <tr key={i}>
                <td>
                  <input
                    className="input"
                    aria-label={t("setup.donor")}
                    value={d.name}
                    onChange={(e) => setDonor(i, { name: e.target.value })}
                    data-testid={`donor-name-${i}`}
                  />
                </td>
                <td>
                  <input
                    className="input"
                    aria-label={t("setup.agreement")}
                    value={d.agreement}
                    onChange={(e) => setDonor(i, { agreement: e.target.value })}
                  />
                </td>
                <td>
                  <select
                    className="input"
                    aria-label={t("setup.donorFrequency")}
                    value={d.frequency}
                    onChange={(e) => setDonor(i, { frequency: e.target.value as Frequency | "" })}
                  >
                    <option value="">{t("setup.sameFrequency")}</option>
                    {FREQUENCIES.map((f) => (
                      <option key={f} value={f}>
                        {t(`setup.freq_${f}`)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <IconButton
                    icon="trash"
                    label={t("common.remove")}
                    onClick={() => set({ donors: p.donors.filter((_, k) => k !== i) })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div>
          <button
            className="btn"
            onClick={() => set({ donors: [...p.donors, { name: "", agreement: "", frequency: "" }] })}
            data-testid="add-donor"
          >
            <Icon name="plus" /> {t("setup.addDonor")}
          </button>
        </div>
      </section>

      <section className="box stack">
        <h2>{t("setup.dates")}</h2>
        <div className="form-grid">
          <Field label={t("setup.start")}>
            {(id) => (
              <input
                id={id}
                type="date"
                className="input"
                value={p.start}
                onChange={(e) => set({ start: e.target.value })}
                data-testid="profile-start"
              />
            )}
          </Field>
          <Field label={t("setup.end")}>
            {(id) => (
              <input
                id={id}
                type="date"
                className="input"
                value={p.end}
                onChange={(e) => set({ end: e.target.value })}
                data-testid="profile-end"
              />
            )}
          </Field>
          <Field label={t("setup.frequency")} hint={t("setup.frequencyHint")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={p.frequency}
                onChange={(e) => set({ frequency: e.target.value as Frequency })}
                data-testid="profile-frequency"
              >
                {FREQUENCIES.map((f) => (
                  <option key={f} value={f}>
                    {t(`setup.freq_${f}`)}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t("setup.fiscal")} hint={t("setup.fiscalHint")}>
            {(id) => (
              <select
                id={id}
                className="input"
                value={p.fiscal_start_month}
                onChange={(e) => set({ fiscal_start_month: Number(e.target.value) })}
              >
                {months.map((m, i) => (
                  <option key={i} value={i + 1}>
                    {m}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t("setup.dataDue")} hint={t("setup.daysHint")}>
            {(id) => (
              <input
                id={id}
                type="number"
                min={0}
                max={180}
                className="input"
                value={p.data_due_days}
                onChange={(e) => set({ data_due_days: Number(e.target.value) })}
              />
            )}
          </Field>
          <Field label={t("setup.reportDue")} hint={t("setup.daysHint")}>
            {(id) => (
              <input
                id={id}
                type="number"
                min={0}
                max={365}
                className="input"
                value={p.report_due_days}
                onChange={(e) => set({ report_due_days: Number(e.target.value) })}
              />
            )}
          </Field>
        </div>
      </section>

      <section className="box stack">
        <h2>{t("setup.placeLevels")}</h2>
        <Field label={t("setup.placeLevelsLabel")} hint={t("setup.placeLevelsHint")} wide>
          {(id) => <input id={id} className="input" value={levels} onChange={(e) => setLevels(e.target.value)} />}
        </Field>
      </section>

      <div className="row-actions">
        <button className="btn primary" onClick={save} data-testid="profile-save">
          {t("common.save")}
        </button>
      </div>
    </div>
  );
}

// ----- calendar --------------------------------------------------------------------

function Calendar() {
  const { t, lang, day } = useI18n();
  const { snap, run } = useProject();
  const [editing, setEditing] = useState<Period | "new" | null>(null);
  const [confirm, setConfirm] = useState(false);
  const periods = snap!.periods;
  const used = useMemo(() => new Set(Object.values(snap!.targets).flatMap((l) => l.map((x) => x.period))), [snap]);
  const today = new Date().toISOString().slice(0, 10);
  const hasDates = !!snap!.profile.start && !!snap!.profile.end;

  const generate = async () => {
    setConfirm(false);
    await run("period.generate");
  };

  return (
    <div className="stack" data-testid="calendar">
      <div className="row-actions start">
        <button
          className="btn primary"
          disabled={!hasDates}
          onClick={() => (periods.length ? setConfirm(true) : void generate())}
          data-testid="generate-periods"
        >
          {t(periods.length ? "setup.regenerate" : "setup.generate")}
        </button>
        <button className="btn" onClick={() => setEditing("new")} data-testid="add-period">
          <Icon name="plus" /> {t("setup.addPeriod")}
        </button>
      </div>
      {!hasDates && <Notice>{t("setup.needDates")}</Notice>}
      {periods.length === 0 ? (
        <Empty icon="calendar" title={t("setup.noPeriods")} text={t("setup.noPeriodsText")} />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("setup.period")}</th>
              <th>{t("setup.from")}</th>
              <th>{t("setup.to")}</th>
              <th>{t("setup.dataDueCol")}</th>
              <th>{t("setup.reportDueCol")}</th>
              <th>{t("setup.state")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {periods.map((x) => {
              const current = x.start <= today && today <= x.end;
              return (
                <tr key={x.id} className={current ? "current" : undefined} data-testid={`period-${x.code}`}>
                  <td>
                    <strong>{lang === "en" ? x.label_en : x.label_fr}</strong>
                    {current && <span className="tag">{t("setup.current")}</span>}
                  </td>
                  <td>{day(x.start)}</td>
                  <td>{day(x.end)}</td>
                  <td>{day(x.data_due)}</td>
                  <td>{day(x.report_due)}</td>
                  <td>
                    <button
                      className="chip small"
                      aria-pressed={x.state === "locked"}
                      onClick={() =>
                        run("period.set_state", { id: x.id, state: x.state === "locked" ? "open" : "locked" })
                      }
                      title={t(x.state === "locked" ? "setup.unlock" : "setup.lock")}
                      data-testid={`lock-${x.code}`}
                    >
                      {x.state === "locked" && <Icon name="lock" size={14} />}
                      {t(`setup.state_${x.state}`)}
                    </button>
                  </td>
                  <td className="row-actions">
                    <IconButton icon="edit" label={t("common.edit")} onClick={() => setEditing(x)} />
                    <IconButton
                      icon="trash"
                      label={t("common.delete")}
                      disabled={used.has(x.code) || x.state === "locked"}
                      onClick={() => run("period.delete", { id: x.id })}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {editing && <PeriodPanel period={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {confirm && (
        <Confirm
          text={t("setup.regenerateConfirm")}
          confirmLabel={t("setup.regenerate")}
          onConfirm={generate}
          onCancel={() => setConfirm(false)}
        />
      )}
    </div>
  );
}

function PeriodPanel({ period, onClose }: { period: Period | null; onClose: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [p, setP] = useState(
    period ?? { code: "", label_fr: "", label_en: "", start: "", end: "", data_due: "", report_due: "" },
  );
  const set = (patch: Partial<typeof p>) => setP({ ...p, ...patch });
  const save = async () => {
    const s = await run("period.save", { id: period?.id, period: p });
    if (s) onClose();
  };
  const fields: [keyof typeof p, string, string][] = [
    ["code", "setup.periodCode", "text"],
    ["label_fr", "setup.labelFr", "text"],
    ["label_en", "setup.labelEn", "text"],
    ["start", "setup.from", "date"],
    ["end", "setup.to", "date"],
    ["data_due", "setup.dataDueCol", "date"],
    ["report_due", "setup.reportDueCol", "date"],
  ];
  return (
    <Panel
      title={t(period ? "setup.editPeriod" : "setup.addPeriod")}
      onClose={onClose}
      testId="period-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" onClick={save} disabled={!p.start || !p.end} data-testid="period-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      {fields.map(([k, label, type]) => (
        <Field key={k} label={t(label)}>
          {(id) => (
            <input
              id={id}
              type={type}
              className="input"
              value={String(p[k] ?? "")}
              onChange={(e) => set({ [k]: e.target.value })}
              data-testid={`period-${k}`}
            />
          )}
        </Field>
      ))}
    </Panel>
  );
}

// ----- places ----------------------------------------------------------------------

function Places() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const levels = snap!.profile.place_levels;
  const places = snap!.places;
  const [editing, setEditing] = useState<{ place: Place | null; parent: Place | null } | null>(null);
  const [pasting, setPasting] = useState(false);
  const [deleting, setDeleting] = useState<Place | null>(null);

  // Depth-first order, so each place shows under its parent.
  const ordered = useMemo(() => {
    const out: Place[] = [];
    const walk = (parent: string) => {
      for (const p of places.filter((x) => (x.parent_id || "") === parent)) {
        out.push(p);
        walk(p.id);
      }
    };
    walk("");
    return out;
  }, [places]);

  return (
    <div className="stack" data-testid="places">
      <p className="muted">{t("setup.placesLead", { levels: levels.join(" > ") })}</p>
      <div className="row-actions start">
        <button
          className="btn primary"
          onClick={() => setEditing({ place: null, parent: null })}
          data-testid="add-place"
        >
          <Icon name="plus" /> {t("setup.addPlace", { level: levels[0] ?? "" })}
        </button>
        <button className="btn" onClick={() => setPasting(true)} data-testid="paste-places">
          {t("setup.pastePlaces")}
        </button>
      </div>
      {ordered.length === 0 ? (
        <Empty icon="pin" title={t("setup.noPlaces")} text={t("setup.noPlacesText")} />
      ) : (
        <ul className="tree-list">
          {ordered.map((p) => (
            <li key={p.id} style={{ paddingLeft: `${p.level * 1.5}rem` }} data-testid={`place-${p.name}`}>
              <span className="muted small">{levels[p.level]}</span> <strong>{p.name}</strong>
              {p.code && <span className="muted small"> {p.code}</span>}
              <span className="row-actions">
                {p.level + 1 < levels.length && (
                  <IconButton
                    icon="plus"
                    label={t("setup.addPlace", { level: levels[p.level + 1] })}
                    onClick={() => setEditing({ place: null, parent: p })}
                  />
                )}
                <IconButton
                  icon="edit"
                  label={t("common.edit")}
                  onClick={() => setEditing({ place: p, parent: places.find((x) => x.id === p.parent_id) ?? null })}
                />
                <IconButton
                  icon="trash"
                  label={t("common.delete")}
                  disabled={places.some((x) => x.parent_id === p.id)}
                  onClick={() => setDeleting(p)}
                />
              </span>
            </li>
          ))}
        </ul>
      )}
      {editing && <PlacePanel {...editing} levels={levels} onClose={() => setEditing(null)} />}
      {pasting && <PastePlaces levels={levels} onClose={() => setPasting(false)} />}
      {deleting && (
        <Confirm
          text={t("setup.deletePlace", { name: deleting.name })}
          confirmLabel={t("common.delete")}
          onConfirm={() => {
            void run("place.delete", { id: deleting.id });
            setDeleting(null);
          }}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}

function PlacePanel({
  place,
  parent,
  levels,
  onClose,
}: {
  place: Place | null;
  parent: Place | null;
  levels: string[];
  onClose: () => void;
}) {
  const { t } = useI18n();
  const { run } = useProject();
  const [name, setName] = useState(place?.name ?? "");
  const [code, setCode] = useState(place?.code ?? "");
  const level = parent ? parent.level + 1 : 0;
  const save = async () => {
    const s = await run("place.save", { id: place?.id, place: { name, code, parent_id: parent?.id ?? "" } });
    if (s) onClose();
  };
  return (
    <Panel
      title={place ? place.name : t("setup.addPlace", { level: levels[level] ?? "" })}
      onClose={onClose}
      testId="place-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" disabled={!name.trim()} onClick={save} data-testid="place-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      {parent && <p className="muted">{t("setup.inside", { name: parent.name })}</p>}
      <Field label={t("setup.placeName")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            data-testid="place-name"
          />
        )}
      </Field>
      <Field label={t("setup.placeCode")} hint={t("setup.placeCodeHint")}>
        {(id) => <input id={id} className="input" value={code} onChange={(e) => setCode(e.target.value)} />}
      </Field>
    </Panel>
  );
}

function PastePlaces({ levels, onClose }: { levels: string[]; onClose: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [text, setText] = useState("");
  const rows = text
    .split(/\r?\n/)
    .map((l) => l.split("\t").map((c) => c.trim()))
    .filter((r) => r.some(Boolean));
  const save = async () => {
    const s = await run("place.import", { rows });
    if (s) onClose();
  };
  return (
    <Panel
      title={t("setup.pastePlaces")}
      onClose={onClose}
      testId="paste-places-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" disabled={!rows.length} onClick={save} data-testid="paste-places-save">
            {t("setup.importRows", { n: rows.length })}
          </button>
        </>
      }
    >
      <p className="muted">{t("setup.pastePlacesHint", { levels: levels.join(" | ") })}</p>
      <textarea
        className="input mono"
        rows={14}
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-label={t("setup.pastePlaces")}
        data-testid="paste-places-text"
      />
    </Panel>
  );
}

// ----- partners --------------------------------------------------------------------

function Partners() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [editing, setEditing] = useState<Partner | "new" | null>(null);
  const names = new Map(snap!.places.map((p) => [p.id, p.name]));
  return (
    <div className="stack" data-testid="partners">
      <div className="row-actions start">
        <button className="btn primary" onClick={() => setEditing("new")} data-testid="add-partner">
          <Icon name="plus" /> {t("setup.addPartner")}
        </button>
      </div>
      {snap!.partners.length === 0 ? (
        <Empty icon="people" title={t("setup.noPartners")} text={t("setup.noPartnersText")} />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("setup.partnerName")}</th>
              <th>{t("setup.role")}</th>
              <th>{t("setup.partnerPlaces")}</th>
              <th>{t("setup.agreementDates")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {snap!.partners.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{p.name}</strong>
                  {p.acronym && <span className="muted"> ({p.acronym})</span>}
                </td>
                <td>{t(`setup.role_${p.role}`)}</td>
                <td>{p.place_ids.map((id) => names.get(id)).join(", ")}</td>
                <td>{[p.start, p.end].filter(Boolean).join(" / ")}</td>
                <td className="row-actions">
                  <IconButton icon="edit" label={t("common.edit")} onClick={() => setEditing(p)} />
                  <IconButton
                    icon="trash"
                    label={t("common.delete")}
                    onClick={() => run("partner.delete", { id: p.id })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && <PartnerPanel partner={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function PartnerPanel({ partner, onClose }: { partner: Partner | null; onClose: () => void }) {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [p, setP] = useState<Omit<Partner, "id">>(
    partner ?? {
      name: "",
      acronym: "",
      role: "implementing",
      contact: "",
      place_ids: [],
      start: "",
      end: "",
      note: "",
    },
  );
  const set = (patch: Partial<Partner>) => setP({ ...p, ...patch });
  const toggle = (id: string) =>
    set({ place_ids: p.place_ids.includes(id) ? p.place_ids.filter((x) => x !== id) : [...p.place_ids, id] });
  const save = async () => {
    const s = await run("partner.save", { id: partner?.id, partner: p });
    if (s) onClose();
  };
  const levels = snap!.profile.place_levels;
  return (
    <Panel
      title={partner ? partner.name : t("setup.addPartner")}
      onClose={onClose}
      testId="partner-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn primary" disabled={!p.name.trim()} onClick={save} data-testid="partner-save">
            {t("common.save")}
          </button>
        </>
      }
    >
      <Field label={t("setup.partnerName")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={p.name}
            onChange={(e) => set({ name: e.target.value })}
            data-testid="partner-name"
          />
        )}
      </Field>
      <Field label={t("setup.acronym")}>
        {(id) => (
          <input id={id} className="input" value={p.acronym} onChange={(e) => set({ acronym: e.target.value })} />
        )}
      </Field>
      <Field label={t("setup.role")}>
        {(id) => (
          <select
            id={id}
            className="input"
            value={p.role}
            onChange={(e) => set({ role: e.target.value as PartnerRole })}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`setup.role_${r}`)}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label={t("setup.contact")}>
        {(id) => (
          <input id={id} className="input" value={p.contact} onChange={(e) => set({ contact: e.target.value })} />
        )}
      </Field>
      <div className="form-grid">
        <Field label={t("setup.from")}>
          {(id) => (
            <input
              id={id}
              type="date"
              className="input"
              value={p.start}
              onChange={(e) => set({ start: e.target.value })}
            />
          )}
        </Field>
        <Field label={t("setup.to")}>
          {(id) => (
            <input id={id} type="date" className="input" value={p.end} onChange={(e) => set({ end: e.target.value })} />
          )}
        </Field>
      </div>
      <fieldset className="check-list">
        <legend>{t("setup.partnerPlaces")}</legend>
        {snap!.places.length === 0 && <p className="muted small">{t("setup.noPlacesYet")}</p>}
        {snap!.places
          .filter((x) => x.level < 2)
          .map((x) => (
            <label key={x.id} style={{ paddingLeft: `${x.level * 1.2}rem` }}>
              <input type="checkbox" checked={p.place_ids.includes(x.id)} onChange={() => toggle(x.id)} /> {x.name}{" "}
              <span className="muted small">{levels[x.level]}</span>
            </label>
          ))}
      </fieldset>
      <Field label={t("setup.note")}>
        {(id) => (
          <textarea id={id} className="input" rows={3} value={p.note} onChange={(e) => set({ note: e.target.value })} />
        )}
      </Field>
    </Panel>
  );
}

// ----- disaggregations ---------------------------------------------------------------

interface Preset {
  key: string;
  name_fr: string;
  name_en: string;
  categories: Category[];
}

let presetCache: Preset[] | null = null;

function Disaggregations() {
  const { t, lang } = useI18n();
  const { snap, run } = useProject();
  const [presets, setPresets] = useState<Preset[] | null>(presetCache);
  const [editing, setEditing] = useState<Disaggregation | "new" | null>(null);
  useEffect(() => {
    if (presetCache) return;
    let live = true;
    call<{ presets: Preset[] }>("disaggregation.presets")
      .then((r) => {
        presetCache = r.presets;
        if (live) setPresets(r.presets);
      })
      .catch(() => live && setPresets([]));
    return () => {
      live = false;
    };
  }, []);
  const have = new Set(snap!.disaggregations.map((d) => d.key));
  const name = (d: { name_fr: string; name_en: string }) => (lang === "en" ? d.name_en : d.name_fr);
  return (
    <div className="stack" data-testid="disaggregations">
      <p className="muted">{t("setup.disLead")}</p>
      <div className="row-actions start wrap">
        {(presets ?? [])
          .filter((p) => !have.has(p.key))
          .map((p) => (
            <button
              key={p.key}
              className="btn"
              onClick={() => run("disaggregation.save", { disaggregation: { preset: p.key } })}
              data-testid={`preset-${p.key}`}
            >
              <Icon name="plus" /> {name(p)}
            </button>
          ))}
        <button className="btn" onClick={() => setEditing("new")} data-testid="add-disaggregation">
          <Icon name="plus" /> {t("setup.customDis")}
        </button>
      </div>
      {snap!.disaggregations.length === 0 ? (
        <Empty icon="table" title={t("setup.noDis")} text={t("setup.noDisText")} />
      ) : (
        <div className="box-list">
          {snap!.disaggregations.map((d, i) => (
            <div key={d.id} className="box row-between" data-testid={`dis-${d.key}`}>
              <div>
                <strong>{name(d)}</strong>
                <div className="muted small">
                  {[...d.categories.map((c) => (lang === "en" ? c.en : c.fr)), t("setup.unspecified")].join(", ")}
                </div>
              </div>
              <div className="row-actions">
                <IconButton
                  icon="up"
                  label={t("common.moveUp")}
                  disabled={i === 0}
                  onClick={() => run("disaggregation.move", { id: d.id, direction: -1 })}
                />
                <IconButton icon="edit" label={t("common.edit")} onClick={() => setEditing(d)} />
                <IconButton
                  icon="trash"
                  label={t("common.delete")}
                  onClick={() => run("disaggregation.delete", { id: d.id })}
                />
              </div>
            </div>
          ))}
        </div>
      )}
      {editing && <DisaggregationPanel dis={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function DisaggregationPanel({ dis, onClose }: { dis: Disaggregation | null; onClose: () => void }) {
  const { t } = useI18n();
  const { run } = useProject();
  const [nameFr, setNameFr] = useState(dis?.name_fr ?? "");
  const [nameEn, setNameEn] = useState(dis?.name_en ?? "");
  const [cats, setCats] = useState(
    (dis?.categories ?? []).map((c) => (c.en && c.en !== c.fr ? `${c.fr} | ${c.en}` : c.fr)).join("\n"),
  );
  const categories = cats
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l, i) => {
      const [fr, en] = l.split("|").map((x) => x.trim());
      return { code: dis?.categories[i]?.fr === fr ? dis.categories[i].code : "", fr, en: en || fr };
    });
  const save = async () => {
    const s = await run("disaggregation.save", {
      id: dis?.id,
      disaggregation: { key: dis?.key ?? "", name_fr: nameFr, name_en: nameEn, categories },
    });
    if (s) onClose();
  };
  return (
    <Panel
      title={dis ? dis.name_fr : t("setup.customDis")}
      onClose={onClose}
      testId="dis-panel"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button
            className="btn primary"
            disabled={!nameFr.trim() || categories.length < 2}
            onClick={save}
            data-testid="dis-save"
          >
            {t("common.save")}
          </button>
        </>
      }
    >
      <Field label={t("setup.disNameFr")}>
        {(id) => (
          <input
            id={id}
            className="input"
            value={nameFr}
            onChange={(e) => setNameFr(e.target.value)}
            data-testid="dis-name"
          />
        )}
      </Field>
      <Field label={t("setup.disNameEn")}>
        {(id) => <input id={id} className="input" value={nameEn} onChange={(e) => setNameEn(e.target.value)} />}
      </Field>
      <Field label={t("setup.categories")} hint={t("setup.categoriesHint")}>
        {(id) => (
          <textarea
            id={id}
            className="input"
            rows={8}
            value={cats}
            onChange={(e) => setCats(e.target.value)}
            data-testid="dis-categories"
          />
        )}
      </Field>
    </Panel>
  );
}
