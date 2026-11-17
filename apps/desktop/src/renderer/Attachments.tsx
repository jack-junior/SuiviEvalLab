// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Supporting documents of an object (submission, activity, feedback...): added
// from a file, kept inside the project with their fingerprint, saved out again.

import { useEffect, useState } from "react";
import { Attachment, call, openFile, pick } from "./api";
import { useI18n } from "./i18n";
import { useProject } from "./state";
import { Icon, IconButton, Notice } from "./ui";

export function Attachments({ kind, id }: { kind: string; id: string | null | undefined }) {
  const { t, number, date } = useI18n();
  const { snap, setSnap, describe } = useProject();
  const [list, setList] = useState<Attachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const count = id ? (snap?.attachments[`${kind}:${id}`] ?? 0) : 0;

  useEffect(() => {
    if (!id) return;
    let live = true;
    call<{ attachments: Attachment[] }>("attachment.list", { owner_kind: kind, owner_id: id })
      .then((r) => live && setList(r.attachments))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [kind, id, count]);

  if (!id) return null;
  const add = async () => {
    const file = await pick("any-open");
    if (!file) return;
    setError(null);
    try {
      setSnap(await call("attachment.add", { owner_kind: kind, owner_id: id, file_token: file.token }));
    } catch (e) {
      setError(describe(e));
    }
  };
  const saveAs = async (a: Attachment) => {
    const file = await pick("any-save", a.name);
    if (!file) return;
    try {
      await call("attachment.save_as", { id: a.id, file_token: file.token });
      await openFile(file.token);
    } catch (e) {
      setError(describe(e));
    }
  };
  const size = (n: number) =>
    n > 1_000_000 ? `${number(n / 1_000_000, 1)} Mo` : `${number(Math.max(1, n / 1000), 0)} ko`;
  return (
    <div className="stack-sm" data-testid={`attachments-${kind}`}>
      <div className="row-between">
        <h3>{t("att.title", { n: list.length })}</h3>
        <button className="btn small" onClick={add} data-testid="attachment-add">
          <Icon name="plus" /> {t("att.add")}
        </button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {list.length === 0 ? (
        <p className="muted small">{t("att.none")}</p>
      ) : (
        <ul className="plain small">
          {list.map((a) => (
            <li key={a.id} className="row-between">
              <span>
                <button className="link" onClick={() => saveAs(a)} title={`SHA-256 ${a.sha256}`}>
                  {a.name}
                </button>{" "}
                <span className="muted">
                  {size(a.size)}, {date(a.added_at)}
                  {a.added_by ? `, ${a.added_by}` : ""}
                </span>
              </span>
              <IconButton
                icon="trash"
                label={t("common.delete")}
                onClick={async () => setSnap(await call("attachment.delete", { id: a.id }))}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
