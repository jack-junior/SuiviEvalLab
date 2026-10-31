// Automatic updates: the banner shown when a new version is ready, and the
// settings section of the engines screen.

import { useEffect, useState } from "react";
import { updates, UpdateState } from "./api";
import { useI18n } from "./i18n";

export function useUpdates(): UpdateState | null {
  const [state, setState] = useState<UpdateState | null>(null);
  useEffect(() => {
    const u = updates();
    if (!u) return;
    let live = true;
    void u.get().then((s) => live && setState(s));
    const off = u.onState((s) => live && setState(s));
    return () => {
      live = false;
      off();
    };
  }, []);
  return state;
}

function useInstall() {
  const [installing, setInstalling] = useState(false);
  const install = () => {
    setInstalling(true);
    void updates()?.install();
  };
  return { installing, install };
}

/** Shown at the top of every screen once a new version is downloaded. */
export function UpdateBanner() {
  const { t } = useI18n();
  const state = useUpdates();
  const { installing, install } = useInstall();
  const [later, setLater] = useState<string | null>(null);
  if (!state || state.status !== "ready" || later === state.version) return null;
  return (
    <div className="update-banner" role="status" data-testid="update-ready">
      <span>{t("updates.ready", { version: state.version ?? "" })}</span>
      <span className="row-actions">
        {state.notesUrl && (
          <button className="link" onClick={() => void updates()?.openNotes(state.notesUrl!)}>
            {t("updates.notes")}
          </button>
        )}
        <button className="btn" onClick={() => setLater(state.version ?? "")}>
          {t("updates.later")}
        </button>
        <button className="btn primary" onClick={install} disabled={installing} data-testid="update-install">
          {installing ? t("updates.installing") : t("updates.install")}
        </button>
      </span>
    </div>
  );
}

/** Settings and status, on the engines screen. */
export function UpdatesSection() {
  const { t, date, number } = useI18n();
  const state = useUpdates();
  const { installing, install } = useInstall();
  if (!state) return null;
  const u = updates();
  const mb = (bytes?: number) => number((bytes ?? 0) / 1024 / 1024, 1);
  const status = (() => {
    switch (state.status) {
      case "unsupported":
        return t("updates.unsupported");
      case "locked":
        return t("updates.locked");
      case "off":
        return t("updates.off");
      case "checking":
        return t("updates.checking");
      case "none":
        return t("updates.none", { date: date(state.checkedAt) });
      case "downloading":
        return t("updates.downloading", {
          version: state.version ?? "",
          percent: number(state.percent ?? 0, 0),
          done: mb(state.transferred),
          total: mb(state.total),
        });
      case "ready":
        return t("updates.ready", { version: state.version ?? "" });
      case "error":
        return t("updates.error", { detail: state.error ?? "" });
      default:
        return t("updates.idle");
    }
  })();
  const canCheck = !["unsupported", "locked", "checking", "downloading", "ready"].includes(state.status);
  return (
    <section className="stack" data-testid="updates-section">
      <h2>{t("updates.title")}</h2>
      <p className="muted">{t("updates.lead", { version: state.current })}</p>
      <p data-testid="update-status" data-status={state.status}>
        {status}
      </p>
      {state.status === "downloading" && (
        <div className="track" aria-hidden="true">
          <span className="fill" style={{ width: `${state.percent ?? 0}%` }} />
        </div>
      )}
      {state.status !== "unsupported" && (
        <label className="check inline-check">
          <input
            type="checkbox"
            checked={state.auto && !state.locked}
            disabled={state.locked}
            onChange={(e) => void u?.setAuto(e.target.checked)}
            data-testid="update-auto"
          />
          <span className="check-text">{t("updates.auto")}</span>
        </label>
      )}
      <div className="row-actions start">
        {canCheck && (
          <button className="btn" onClick={() => void u?.check()} data-testid="update-check">
            {t("updates.check")}
          </button>
        )}
        {state.status === "ready" && (
          <button className="btn primary" onClick={install} disabled={installing} data-testid="update-install">
            {installing ? t("updates.installing") : t("updates.install")}
          </button>
        )}
        {state.notesUrl && (
          <button className="link" onClick={() => void u?.openNotes(state.notesUrl!)}>
            {t("updates.notes")}
          </button>
        )}
      </div>
      <p className="small muted">{t("updates.policy")}</p>
    </section>
  );
}
