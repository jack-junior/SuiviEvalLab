// Word report: what it contains, the language, generation and opening.

import { useState } from "react";
import { openFile, pick } from "../api";
import { Lang, useI18n } from "../i18n";
import { useProject } from "../state";
import { Icon, Notice } from "../ui";

export function Report() {
  const { t, lang } = useI18n();
  const { snap, run, error, busy, go } = useProject();
  const [reportLang, setReportLang] = useState<Lang>(lang);
  const [done, setDone] = useState<{ token: string; name: string } | null>(null);
  const [shared, setShared] = useState<{ token: string; name: string } | null>(null);
  const [templateNote, setTemplateNote] = useState<{ kind: "ok" | "info"; text: string } | null>(null);
  if (!snap) return null;
  const ready = snap.indicators.length > 0;

  const chooseTemplate = async () => {
    const f = await pick("template-open");
    if (!f) return;
    const r = await run<{ has_anchor: boolean }>("report.set_template", { file_token: f.token });
    if (r)
      setTemplateNote(
        r.has_anchor
          ? { kind: "ok", text: t("report.templateOk", { name: f.name }) }
          : { kind: "info", text: t("report.templateNoAnchor", { name: f.name }) },
      );
  };

  const generate = async () => {
    setDone(null);
    const file = await pick("report-save", `${snap.project.name.slice(0, 60)}.docx`);
    if (!file) return;
    const r = await run("report.generate", { file_token: file.token, lang: reportLang }, "report");
    if (r) setDone(file);
  };

  const share = async () => {
    setShared(null);
    const file = await pick("html-save", `${snap.project.name.slice(0, 60)}.html`);
    if (!file) return;
    const r = await run("report.share", { file_token: file.token, lang: reportLang }, "share");
    if (r) setShared(file);
  };

  const sections = ["summary", "results", "tests", "framework", "data", "methods", "sources"];
  return (
    <div className="inner">
      <div>
        <h1>{t("nav.report")}</h1>
        <p className="lead">{t("report.lead")}</p>
      </div>
      {error && <Notice kind="error">{error}</Notice>}

      <section className="stack">
        <h2>{t("report.contents")}</h2>
        <ol className="outline">
          {sections.map((s) => (
            <li key={s}>
              <span className="outline-title">{t(`report.s_${s}`)}</span>
              <span className="muted small">{t(`report.d_${s}`)}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="stack" data-testid="template-section">
        <h2>{t("report.template")}</h2>
        <p className="muted" style={{ margin: 0 }}>
          {snap.project.report_template
            ? t("report.templateCurrent", { name: snap.project.report_template })
            : t("report.templateBuiltIn")}
        </p>
        {templateNote && <Notice kind={templateNote.kind}>{templateNote.text}</Notice>}
        <div className="row-actions start">
          <button className="btn" onClick={chooseTemplate} data-testid="choose-template">
            <Icon name="file" />{" "}
            {snap.project.report_template ? t("report.templateChange") : t("report.templateChoose")}
          </button>
          {snap.project.report_template && (
            <button className="btn" onClick={() => run("report.clear_template")}>
              {t("report.templateRemove")}
            </button>
          )}
        </div>
        <details className="help">
          <summary>{t("report.templateHow")}</summary>
          <p>{t("report.templateHelp1")}</p>
          <ul>
            <li>
              <code>{"{{contenu}}"}</code> {t("report.field_content")}
            </li>
            <li>
              <code>{"{{projet}}"}</code> {t("report.field_project")}
            </li>
            <li>
              <code>{"{{date}}"}</code> {t("report.field_date")}
            </li>
            <li>
              <code>{"{{titre_rapport}}"}</code> {t("report.field_title")}
            </li>
          </ul>
          <p>{t("report.templateHelp2")}</p>
        </details>
      </section>

      <section className="stack">
        <h2>{t("report.language")}</h2>
        <div className="chips">
          {(["fr", "en"] as Lang[]).map((l) => (
            <button key={l} className="chip" aria-pressed={reportLang === l} onClick={() => setReportLang(l)}>
              {t(`report.lang_${l}`)}
            </button>
          ))}
        </div>
      </section>

      {!ready && (
        <Notice>
          {t("report.notReady")}{" "}
          <button className="link" onClick={() => go("indicators")}>
            {t("indicators.add")}
          </button>
        </Notice>
      )}

      <div className="row-actions start">
        <button
          className="btn primary big"
          onClick={generate}
          disabled={!ready || busy === "report"}
          data-testid="generate-report"
        >
          <Icon name="doc" /> {busy === "report" ? t("report.generating") : t("report.generate")}
        </button>
      </div>

      {done && (
        <Notice kind="ok">
          <span data-testid="report-done">{t("report.done", { name: done.name })}</span>{" "}
          <button className="link" onClick={() => openFile(done.token)}>
            {t("report.open")}
          </button>
        </Notice>
      )}

      <section className="stack" data-testid="share-section">
        <h2>{t("report.shareTitle")}</h2>
        <p className="muted">{t("report.shareText")}</p>
        <div className="row-actions start">
          <button className="btn" onClick={share} disabled={!ready || busy === "share"} data-testid="share-dashboard">
            <Icon name="download" /> {busy === "share" ? t("report.sharing") : t("report.shareAction")}
          </button>
        </div>
        {shared && (
          <Notice kind="ok">
            <span data-testid="share-done">{t("report.shareDone", { name: shared.name })}</span>{" "}
            <button className="link" onClick={() => openFile(shared.token)}>
              {t("report.shareOpen")}
            </button>
          </Notice>
        )}
      </section>
    </div>
  );
}
