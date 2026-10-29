// Home: create, open or try the example project; recent projects.

import { useEffect, useState } from "react";
import { pick, Recent, recents, recentToken, Snapshot } from "../api";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Field, Icon, Notice } from "../ui";

export function Home({ enginesReady }: { enginesReady: boolean }) {
  const { t, lang } = useI18n();
  const { run, busy, error, go } = useProject();
  const [name, setName] = useState("");
  const [list, setList] = useState<Recent[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    recents()
      .then(setList)
      .catch(() => setList([]));
  }, []);

  const opened = (s: Snapshot | null) => {
    if (s) go(s.indicators.length ? "overview" : "framework");
  };

  const create = async () => {
    const file = await pick("project-save", `${name.trim() || t("home.defaultName")}.sme`);
    if (!file) return;
    opened(await run("project.create", { file_token: file.token, name: name.trim() || t("home.defaultName") }));
  };

  const open = async () => {
    const file = await pick("project-open");
    if (file) opened(await run("project.open", { file_token: file.token }));
  };

  const openRecent = async (r: Recent) => {
    const token = await recentToken(r.path);
    if (token) opened(await run("project.open", { file_token: token }));
  };

  const example = async () => {
    const file = await pick("project-save", `${t("home.exampleFile")}.sme`);
    if (!file) return;
    opened(
      await run("project.create", { file_token: file.token, name: "x", example: true, lang }, t("home.exampleBusy")),
    );
  };

  return (
    <div className="inner">
      <div>
        <h1>{t("home.title")}</h1>
        <p className="lead">{t("home.lead")}</p>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      <section className="choice-grid">
        <div className="choice">
          <Icon name="plus" size={22} />
          <h2>{t("home.newTitle")}</h2>
          <p className="muted">{t("home.newText")}</p>
          {creating ? (
            <div className="stack">
              <Field label={t("home.projectName")}>
                {(id) => (
                  <input
                    id={id}
                    className="input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && create()}
                    placeholder={t("home.namePlaceholder")}
                    data-testid="new-name"
                  />
                )}
              </Field>
              <div className="row-actions">
                <button className="btn" onClick={() => setCreating(false)}>
                  {t("common.cancel")}
                </button>
                <button className="btn primary" onClick={create} disabled={!!busy} data-testid="new-create">
                  {t("home.chooseLocation")}
                </button>
              </div>
            </div>
          ) : (
            <button className="btn primary" onClick={() => setCreating(true)} data-testid="new-project">
              {t("home.newAction")}
            </button>
          )}
        </div>

        <div className="choice">
          <Icon name="folder" size={22} />
          <h2>{t("home.openTitle")}</h2>
          <p className="muted">{t("home.openText")}</p>
          <button className="btn" onClick={open} disabled={!!busy} data-testid="open-project">
            {t("home.openAction")}
          </button>
        </div>

        <div className="choice choice-wide">
          <Icon name="chart" size={22} />
          <div className="choice-text">
            <h2>{t("home.exampleTitle")}</h2>
            <p className="muted">{t("home.exampleText")}</p>
          </div>
          <button
            className="btn"
            onClick={example}
            disabled={!!busy || !enginesReady}
            data-testid="open-example"
            title={enginesReady ? undefined : t("home.enginesStarting")}
          >
            {busy === t("home.exampleBusy") ? t("home.exampleBusy") : t("home.exampleAction")}
          </button>
        </div>
      </section>

      {list.length > 0 && (
        <section>
          <h2 className="section-title">{t("home.recent")}</h2>
          <div className="list">
            {list.map((r) => (
              <button
                key={r.path}
                className="row row-button"
                onClick={() => openRecent(r)}
                disabled={!r.exists || !!busy}
                title={r.path}
              >
                <span className="t">{r.name}</span>
                <span className="s">{r.exists ? r.path : t("home.missingFile")}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
