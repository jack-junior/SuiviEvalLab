// Results framework: impact, outcomes, outputs and activities as an editable tree.

import { useState } from "react";
import { FrameworkModel, FrameworkNode, Level } from "../api";
import { useLevels } from "../frameworks";
import { useI18n } from "../i18n";
import { useProject } from "../state";
import { Confirm, Empty, Field, IconButton, Notice, Panel } from "../ui";
import { customValid, ModelPicker } from "./ModelPicker";

// Hints describe the levels of the standard chains; other models use their own words.
const HINTED = ["standard", "eu", "un"];

type Editing = { mode: "add"; parent: FrameworkNode | null } | { mode: "edit"; node: FrameworkNode };

export function Framework() {
  const { t, tn } = useI18n();
  const { snap, run, error, go } = useProject();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assumptions, setAssumptions] = useState("");
  const [choosing, setChoosing] = useState<FrameworkModel | null>(null);
  const levels = useLevels();
  const [deleting, setDeleting] = useState<FrameworkNode | null>(null);
  if (!snap) return null;
  const nodes = snap.framework;

  const open = (e: Editing) => {
    setEditing(e);
    setTitle(e.mode === "edit" ? e.node.title : "");
    setDescription(e.mode === "edit" ? e.node.description : "");
    setAssumptions(e.mode === "edit" ? (e.node.assumptions ?? "") : "");
  };
  const NEXT = (level: Level) => levels.next(level);

  const save = async () => {
    if (!editing || !title.trim()) return;
    const ok =
      editing.mode === "add"
        ? await run("framework.add", { parent_id: editing.parent?.id ?? null, title, description, assumptions })
        : await run("framework.update", { id: editing.node.id, title, description, assumptions });
    if (ok) setEditing(null);
  };

  const levelOfNew = editing?.mode === "add" ? (editing.parent ? NEXT(editing.parent.level)! : "impact") : null;
  const hintLevel = levelOfNew ?? (editing?.mode === "edit" ? editing.node.level : "impact");
  const indicatorCount = (id: string) => snap.indicators.filter((i) => i.node_id === id).length;

  return (
    <div className="inner wide">
      <div className="page-head">
        <div>
          <h1>{t("nav.framework")}</h1>
          <p className="lead">{t("framework.lead")}</p>
          <p className="muted small" data-testid="framework-model">
            {t("models.current", { name: t(`models.${levels.model.id}`), chain: levels.names.join("  >  ") })}{" "}
            <button className="link" onClick={() => setChoosing(levels.model)} data-testid="change-model">
              {t("models.change")}
            </button>
          </p>
        </div>
        {nodes.length > 0 && (
          <button className="btn" onClick={() => open({ mode: "add", parent: null })}>
            {t("framework.addTop", { level: levels.names[0] })}
          </button>
        )}
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      {nodes.length === 0 ? (
        <Empty
          icon="tree"
          title={t("framework.emptyTitle")}
          text={t("framework.emptyText")}
          action={
            <button
              className="btn primary"
              onClick={() => open({ mode: "add", parent: null })}
              data-testid="add-impact"
            >
              {t("framework.startWith", { level: levels.names[0] })}
            </button>
          }
        />
      ) : (
        <ul className="tree" data-testid="framework-tree">
          {nodes.map((n) => {
            const count = indicatorCount(n.id);
            return (
              <li key={n.id} className={`tree-row level-${n.level}`} style={{ paddingLeft: 12 + n.depth * 28 }}>
                <div className="tree-main" onDoubleClick={() => open({ mode: "edit", node: n })}>
                  <span className="tree-level">
                    {levels.name(n.level)} {n.code}
                  </span>
                  <span className="tree-title">
                    {n.title}
                    {n.assumptions && (
                      <span className="tree-assumptions">
                        {t("framework.assumptionsShort", { text: n.assumptions })}
                      </span>
                    )}
                  </span>
                  {count > 0 && (
                    <button className="tag" onClick={() => go("indicators", n.id)}>
                      {tn("framework.indicatorCount", count)}
                    </button>
                  )}
                </div>
                <div className="tree-actions">
                  {NEXT(n.level) && (
                    <IconButton
                      icon="plus"
                      label={t("framework.addChild", { level: levels.name(NEXT(n.level)!).toLowerCase() })}
                      onClick={() => open({ mode: "add", parent: n })}
                      testId="node-add-child"
                    />
                  )}
                  <IconButton icon="edit" label={t("common.edit")} onClick={() => open({ mode: "edit", node: n })} />
                  <IconButton
                    icon="up"
                    label={t("common.moveUp")}
                    onClick={() => run("framework.move", { id: n.id, direction: -1 })}
                  />
                  <IconButton
                    icon="down"
                    label={t("common.moveDown")}
                    onClick={() => run("framework.move", { id: n.id, direction: 1 })}
                  />
                  <IconButton icon="trash" label={t("common.delete")} onClick={() => setDeleting(n)} />
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {editing && (
        <Panel
          title={
            editing.mode === "edit"
              ? t("framework.editTitle", { level: levels.name(editing.node.level).toLowerCase() })
              : t("framework.addTitle", { level: levels.name(levelOfNew!).toLowerCase() })
          }
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn" onClick={() => setEditing(null)}>
                {t("common.cancel")}
              </button>
              <button className="btn primary" onClick={save} disabled={!title.trim()} data-testid="node-save">
                {t("common.save")}
              </button>
            </>
          }
        >
          {editing.mode === "add" && editing.parent && (
            <p className="muted small">{t("framework.under", { title: editing.parent.title })}</p>
          )}
          <Field
            label={t("framework.fieldTitle")}
            hint={HINTED.includes(levels.model.id) ? t(`framework.hint_${hintLevel}`) : undefined}
          >
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={3}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                data-testid="node-title"
              />
            )}
          </Field>
          <Field label={t("framework.fieldDescription")}>
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            )}
          </Field>
          <Field label={t("framework.fieldAssumptions")} hint={t("framework.assumptionsHint")}>
            {(id) => (
              <textarea
                id={id}
                className="input"
                rows={3}
                value={assumptions}
                onChange={(e) => setAssumptions(e.target.value)}
                data-testid="node-assumptions"
              />
            )}
          </Field>
        </Panel>
      )}

      {choosing && (
        <Panel
          title={t("models.title")}
          onClose={() => setChoosing(null)}
          testId="model-panel"
          footer={
            <>
              <button className="btn" onClick={() => setChoosing(null)}>
                {t("common.cancel")}
              </button>
              <button
                className="btn primary"
                disabled={!customValid(choosing)}
                onClick={async () => {
                  if (await run("framework.set_model", { model: choosing })) setChoosing(null);
                }}
                data-testid="model-save"
              >
                {t("models.apply")}
              </button>
            </>
          }
        >
          <p className="muted">{t("models.lead")}</p>
          <ModelPicker value={choosing} onChange={setChoosing} />
        </Panel>
      )}

      {deleting && (
        <Confirm
          text={
            deleting.children > 0 || indicatorCount(deleting.id) > 0
              ? t("framework.deleteWithChildren", { title: deleting.title })
              : t("framework.deleteOne", { title: deleting.title })
          }
          confirmLabel={t("common.delete")}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            await run("framework.delete", { id: deleting.id });
            setDeleting(null);
          }}
        />
      )}
    </div>
  );
}
