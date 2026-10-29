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
  if (!snap) return null;
  const ready = snap.indicators.length > 0;

  const generate = async () => {
    setDone(null);
    const file = await pick("report-save", `${snap.project.name.slice(0, 60)}.docx`);
    if (!file) return;
    const r = await run("report.generate", { file_token: file.token, lang: reportLang }, "report");
    if (r) setDone(file);
  };

  const sections = ["summary", "results", "framework", "data", "methods", "sources"];
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
    </div>
  );
}
