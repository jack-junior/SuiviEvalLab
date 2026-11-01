// Shown when a project contains R code that was not written or accepted on this
// computer (a project received from someone else). The code is shown in full;
// until the user accepts it, those steps stay paused and the rest of the project
// works normally.

import { useState } from "react";
import { useI18n } from "./i18n";
import { useProject } from "./state";
import { Panel } from "./ui";

export function TrustDialog() {
  const { t } = useI18n();
  const { snap, run } = useProject();
  const [dismissed, setDismissed] = useState<string | null>(null);
  const scripts = snap?.untrusted_scripts ?? [];
  const key = `${snap?.project.path}|${scripts.map((s) => s.id).join(",")}`;
  if (!snap || scripts.length === 0 || dismissed === key) return null;

  const close = () => setDismissed(key);
  return (
    <Panel
      title={t("trust.title")}
      onClose={close}
      testId="trust-dialog"
      footer={
        <>
          <button className="btn" onClick={close} data-testid="trust-later">
            {t("trust.later")}
          </button>
          <button
            className="btn primary"
            onClick={async () => {
              await run("scripts.trust", { ids: scripts.map((s) => s.id) }, "trust");
              close();
            }}
            data-testid="trust-accept"
          >
            {t("trust.accept")}
          </button>
        </>
      }
    >
      <p>{t("trust.lead")}</p>
      <p className="muted small">{t("trust.why")}</p>
      {scripts.map((s) => (
        <div key={s.id} className="trust-script">
          <div className="strong">
            {s.where === "cleaning"
              ? t("trust.inCleaning", { name: s.dataset ?? "" })
              : t("trust.inAnalysis", { name: s.title || t("analyses.type_r_script") })}
          </div>
          <pre className="mono code-view">{s.code}</pre>
        </div>
      ))}
    </Panel>
  );
}
