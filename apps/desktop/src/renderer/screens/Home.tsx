// Home: create, open or try the example project, and "My projects", the list of
// projects known to this computer with their progress.

import { useEffect, useState } from "react";
import {
  call,
  FrameworkModel,
  forgetProject,
  pick,
  Recent,
  recents,
  recentToken,
  revealProject,
  Snapshot,
} from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Confirm, Field, Icon, IconButton, Notice, Panel } from "../ui";
import { customValid, ModelPicker, useModels } from "./ModelPicker";
import { SampleSizePanel } from "./SampleSize";

const REOPEN_KEY = "sme.reopenLast";
let reopenTried = false; // once per app session

function readReopen(): boolean {
  try {
    return localStorage.getItem(REOPEN_KEY) === "1";
  } catch {
    return false;
  }
}

export function Home({ enginesReady }: { enginesReady: boolean }) {
  const { t, tn, lang, date } = useI18n();
  const { run, busy, error, go } = useProject();
  const [name, setName] = useState("");
  const [list, setList] = useState<Recent[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  const [reopen, setReopen] = useState(readReopen);
  const [history, setHistory] = useState<Recent | null>(null);
  const [sampling, setSampling] = useState(false);
  const models = useModels();
  const [model, setModel] = useState<FrameworkModel | null>(null);
  const chosen = model ?? models?.[0] ?? null;

  const opened = (s: Snapshot | null) => {
    if (s) go(s.indicators.length ? "overview" : "framework");
  };

  const openRecent = async (r: Recent) => {
    const token = await recentToken(r.path);
    if (token) opened(await run("project.open", { file_token: token }));
  };

  useEffect(() => {
    recents()
      .then((l) => {
        setList(l);
        if (!reopenTried && readReopen() && l[0]?.exists) {
          reopenTried = true;
          void recentToken(l[0].path).then(async (token) => {
            if (!token) return;
            const s = await run<Snapshot>("project.open", { file_token: token });
            if (s) go(s.indicators.length ? "overview" : "framework");
          });
        }
        reopenTried = true;
      })
      .catch(() => setList([]));
  }, [run, go]);

  const toggleReopen = (v: boolean) => {
    setReopen(v);
    try {
      localStorage.setItem(REOPEN_KEY, v ? "1" : "0");
    } catch {
      /* preference not kept */
    }
  };

  const create = async () => {
    const file = await pick("project-save", `${name.trim() || t("home.defaultName")}.sme`);
    if (!file) return;
    opened(
      await run("project.create", {
        file_token: file.token,
        name: name.trim() || t("home.defaultName"),
        model: chosen,
      }),
    );
  };

  const open = async () => {
    const file = await pick("project-open");
    if (file) opened(await run("project.open", { file_token: file.token }));
  };

  const example = async () => {
    const file = await pick("project-save", `${t("home.exampleFile")}.sme`);
    if (!file) return;
    opened(
      await run("project.create", { file_token: file.token, name: "x", example: true, lang }, t("home.exampleBusy")),
    );
  };

  const shown = (list ?? []).filter((r) => {
    const q = query.trim().toLowerCase();
    return !q || r.name.toLowerCase().includes(q) || r.path.toLowerCase().includes(q);
  });

  return (
    <div className="inner wide">
      <div>
        <h1>{t("home.title")}</h1>
        <p className="lead">{t("home.lead")}</p>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      <section className="choice-row">
        <div className="choice">
          <Icon name="plus" size={22} />
          <h2>{t("home.newTitle")}</h2>
          <p className="muted">{t("home.newText")}</p>
          <button className="btn primary" onClick={() => setCreating(true)} data-testid="new-project">
            {t("home.newAction")}
          </button>
        </div>

        <div className="choice">
          <Icon name="folder" size={22} />
          <h2>{t("home.openTitle")}</h2>
          <p className="muted">{t("home.openText")}</p>
          <button className="btn" onClick={open} disabled={!!busy} data-testid="open-project">
            {t("home.openAction")}
          </button>
        </div>
      </section>

      <p className="muted small home-links">
        <button
          className="link"
          onClick={example}
          disabled={!!busy || !enginesReady}
          data-testid="open-example"
          title={enginesReady ? undefined : t("home.enginesStarting")}
        >
          <Icon name="chart" /> {busy === t("home.exampleBusy") ? t("home.exampleBusy") : t("home.exampleLink")}
        </button>{" "}
        {t("home.exampleHint")}
        <br />
        <button className="link" onClick={() => setSampling(true)} disabled={!enginesReady} data-testid="open-sample">
          <Icon name="calc" /> {t("sample.open")}
        </button>{" "}
        {t("sample.openHint")}
      </p>

      <section className="stack" data-testid="my-projects">
        <div className="section-head">
          <h2>{t("home.myProjects")}</h2>
          {(list?.length ?? 0) > 4 && (
            <input
              className="input search"
              placeholder={t("home.search")}
              aria-label={t("home.search")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          )}
        </div>
        {list && list.length === 0 && <p className="muted">{t("home.noProjects")}</p>}
        {shown.length > 0 && (
          <div className="projects">
            {shown.map((r) => (
              <div key={r.path} className={`project-row${r.exists ? "" : " missing"}`}>
                <button
                  className="project-open"
                  onClick={() => openRecent(r)}
                  disabled={!r.exists || !!busy}
                  data-testid="project-row"
                  title={r.path}
                >
                  <span className="project-title">{r.name}</span>
                  <span className="project-path">{r.exists ? r.path : t("home.missingFile")}</span>
                  <span className="project-meta">
                    {r.modified ? t("home.modified", { date: date(r.modified) }) : ""}
                    {r.summary && r.summary.indicators > 0 && (
                      <span className="project-status">
                        {tn("home.indicators", r.summary.indicators)}
                        {r.summary.achieved > 0 && (
                          <span className="st-ok">{tn("home.achieved", r.summary.achieved)}</span>
                        )}
                        {r.summary.on_track > 0 && (
                          <span className="st-mid">{tn("home.onTrack", r.summary.on_track)}</span>
                        )}
                        {r.summary.late > 0 && <span className="st-late">{tn("home.late", r.summary.late)}</span>}
                      </span>
                    )}
                  </span>
                </button>
                <div className="row-tools">
                  {r.exists && (
                    <IconButton
                      icon="history"
                      label={t("backups.open")}
                      onClick={() => setHistory(r)}
                      testId="project-backups"
                    />
                  )}
                  {r.exists && (
                    <IconButton icon="folder" label={t("home.reveal")} onClick={() => void revealProject(r.path)} />
                  )}
                  <IconButton
                    icon="close"
                    label={t("home.forget")}
                    onClick={() => forgetProject(r.path).then(setList)}
                    testId="project-forget"
                  />
                </div>
              </div>
            ))}
          </div>
        )}
        {(list?.length ?? 0) > 0 && (
          <label className="check inline-check">
            <input type="checkbox" checked={reopen} onChange={(e) => toggleReopen(e.target.checked)} />
            <span className="check-text">{t("home.reopenLast")}</span>
          </label>
        )}
      </section>
      {sampling && <SampleSizePanel onClose={() => setSampling(false)} />}
      {creating && (
        <Panel
          title={t("home.newTitle")}
          onClose={() => setCreating(false)}
          testId="new-panel"
          footer={
            <>
              <button className="btn" onClick={() => setCreating(false)}>
                {t("common.cancel")}
              </button>
              <button
                className="btn primary"
                onClick={create}
                disabled={!!busy || !chosen || !customValid(chosen)}
                data-testid="new-create"
              >
                {t("home.chooseLocation")}
              </button>
            </>
          }
        >
          <Field label={t("home.projectName")}>
            {(id) => (
              <input
                id={id}
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("home.namePlaceholder")}
                data-testid="new-name"
              />
            )}
          </Field>
          <div className="field">
            <span className="label">{t("models.title")}</span>
            <p className="muted small">{t("models.createHint")}</p>
            {chosen && <ModelPicker value={chosen} onChange={setModel} />}
          </div>
        </Panel>
      )}
      {history && <BackupsPanel project={history} onClose={() => setHistory(null)} onOpened={opened} />}
    </div>
  );
}

interface Backup {
  id: string;
  taken_at: string;
  updated_at: string | null;
  indicators: number;
  datasets: number;
}

function BackupsPanel({
  project,
  onClose,
  onOpened,
}: {
  project: Recent;
  onClose: () => void;
  onOpened: (s: Snapshot | null) => void;
}) {
  const { t, tn, date } = useI18n();
  const { run, describe } = useProject();
  const [list, setList] = useState<Backup[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [restoring, setRestoring] = useState<Backup | null>(null);

  useEffect(() => {
    let live = true;
    void recentToken(project.path).then((token) =>
      call<{ backups: Backup[] }>("project.backups", { file_token: token })
        .then((r) => live && setList(r.backups))
        .catch((e) => live && setErr(describe(e))),
    );
    return () => {
      live = false;
    };
  }, [project.path, describe]);

  const restore = async (b: Backup) => {
    const token = await recentToken(project.path);
    if (!token) return;
    const s = await run<Snapshot>("project.restore", { file_token: token, backup: b.id });
    setRestoring(null);
    if (s) {
      onClose();
      onOpened(s);
    }
  };

  return (
    <Panel title={t("backups.title", { name: project.name })} onClose={onClose} testId="backups-panel">
      <p className="muted">{t("backups.lead")}</p>
      {err && <Notice kind="error">{err}</Notice>}
      {list && list.length === 0 && <p className="muted">{t("backups.none")}</p>}
      {list && list.length > 0 && (
        <ul className="backup-list">
          {list.map((b) => (
            <li key={b.id} className="backup-row">
              <div>
                <div>{t("backups.taken", { date: date(b.taken_at) })}</div>
                <div className="muted small">
                  {tn("backups.indicators", b.indicators)}, {tn("backups.datasets", b.datasets)}
                </div>
              </div>
              <button className="btn" onClick={() => setRestoring(b)} data-testid="backup-restore">
                {t("backups.restore")}
              </button>
            </li>
          ))}
        </ul>
      )}
      {restoring && (
        <Confirm
          text={t("backups.confirm", { date: date(restoring.taken_at) })}
          confirmLabel={t("backups.restore")}
          onCancel={() => setRestoring(null)}
          onConfirm={() => restore(restoring)}
        />
      )}
    </Panel>
  );
}
