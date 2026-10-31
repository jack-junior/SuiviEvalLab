// Word report: what it contains, the language, generation and opening.

import { useEffect, useState } from "react";
import { call, openFile, pick } from "../api";
import { Lang, useI18n } from "../i18n";
import { useProject } from "../state";
import { Icon, Notice } from "../ui";

interface CheckItem {
  key: string;
  severity: "warning" | "info";
  view: "indicators" | "analysis" | "data";
  id: string | null;
  name: string;
  detail?: string;
  n?: number;
  round?: string;
  code?: string;
}

function Checks() {
  const { t, number } = useI18n();
  const { snap, go, describe } = useProject();
  const [state, setState] = useState<{ for: unknown; items?: CheckItem[]; err?: string } | null>(null);
  useEffect(() => {
    let live = true;
    call<{ items: CheckItem[] }>("report.checks")
      .then((r) => live && setState({ for: snap, items: r.items }))
      .catch((e) => live && setState({ for: snap, err: describe(e) }));
    return () => {
      live = false;
    };
  }, [snap, describe]);
  const current = state?.for === snap ? state : null;
  if (!current) return <p className="muted">{t("checks.running")}</p>;
  if (current.err) return <Notice kind="error">{current.err}</Notice>;
  const items = current.items ?? [];
  const warnings = items.filter((i) => i.severity === "warning");
  const remarks = items.filter((i) => i.severity === "info");
  const line = (i: CheckItem, k: number) => (
    <li key={`${i.key}-${i.id}-${k}`}>
      {t(`checks.${i.key}`, {
        name: i.name,
        n: number(i.n ?? 0, 0),
        round: i.round ? t(`rounds.${i.round}`) : "",
        detail: i.detail ?? "",
        code: i.code ?? "",
      })}{" "}
      <button className="link" onClick={() => go(i.view, i.id)}>
        {t("checks.fix")}
      </button>
    </li>
  );
  return (
    <section className="stack" data-testid="report-checks">
      <h2>{t("checks.title")}</h2>
      {warnings.length === 0 ? (
        <Notice kind="ok">{t("checks.ok")}</Notice>
      ) : (
        <div className="checks warn">
          <p>{t("checks.warnings", { n: number(warnings.length, 0) })}</p>
          <ul data-testid="check-warnings">{warnings.map(line)}</ul>
        </div>
      )}
      {remarks.length > 0 && (
        <details className="quality-infos">
          <summary>{t("checks.remarks", { n: number(remarks.length, 0) })}</summary>
          <ul>{remarks.map(line)}</ul>
        </details>
      )}
    </section>
  );
}

export function Report() {
  const { t, lang } = useI18n();
  const { snap, run, error, busy, go } = useProject();
  const [reportLang, setReportLang] = useState<Lang>(lang);
  const [done, setDone] = useState<{ token: string; name: string } | null>(null);
  const [shared, setShared] = useState<{ token: string; name: string } | null>(null);
  const [planned, setPlanned] = useState<{ token: string; name: string } | null>(null);
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

  const exportPlan = async () => {
    setPlanned(null);
    const file = await pick("xlsx-save", `${t("plan.file")} ${snap.project.name.slice(0, 50)}.xlsx`);
    if (!file) return;
    const r = await run("report.plan", { file_token: file.token, lang: reportLang }, "plan");
    if (r) setPlanned(file);
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

      {ready && <Checks />}

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

      <section className="stack" data-testid="plan-section">
        <h2>{t("plan.title")}</h2>
        <p className="muted">{t("plan.text")}</p>
        <div className="row-actions start">
          <button className="btn" onClick={exportPlan} disabled={!ready || busy === "plan"} data-testid="export-plan">
            <Icon name="table" /> {busy === "plan" ? t("plan.exporting") : t("plan.action")}
          </button>
        </div>
        {planned && (
          <Notice kind="ok">
            <span data-testid="plan-done">{t("plan.done", { name: planned.name })}</span>{" "}
            <button className="link" onClick={() => openFile(planned.token)}>
              {t("report.shareOpen")}
            </button>
          </Notice>
        )}
      </section>

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
