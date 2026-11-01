// The cleaned data as an editable table: sort by a column, filter with a formula,
// correct a cell by double-clicking it. Each correction becomes a step of the
// cleaning journal (identified by the row number in the file), so nothing is
// changed in the raw data and every correction can be reviewed or undone.

import { useEffect, useState } from "react";
import { call, Dataset, EngineCallError } from "../api";
import { useI18n } from "../i18n";
import { useLabels } from "../labels";
import { useProject } from "../state";
import { IconButton, Notice } from "../ui";
import { FormulaError, useFormulaErrorText } from "./FreeRule";

interface Page {
  total: number;
  filtered: number | null;
  columns: string[];
  row_numbers: number[];
  rows: (string | null)[][];
  edited: string[];
}

const LIMIT = 100;

export function DataTable({ ds, showLabels }: { ds: Dataset; showLabels: boolean }) {
  const { t, number } = useI18n();
  const { run, describe } = useProject();
  const { col, val } = useLabels();
  const errorText = useFormulaErrorText();
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filterText, setFilterText] = useState("");
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<{ column: string; descending: boolean } | null>(null);
  const [editing, setEditing] = useState<{ row: number; column: string; value: string } | null>(null);
  const stamp = `${ds.id}-${ds.clean_rows}-${ds.rules.length}-${JSON.stringify(ds.rules.map((r) => r.effect?.cells_changed))}`;

  useEffect(() => {
    call<Page>("dataset.rows", { id: ds.id, offset, limit: LIMIT, filter, sort })
      .then((p) => {
        setPage(p);
        setErr(null);
      })
      .catch((e: unknown) => {
        if (e instanceof EngineCallError && e.key === "formula_invalid") {
          const { reason, pos, ...info } = e.data as { reason: string; pos: number } & Record<string, unknown>;
          const fe: FormulaError = {
            reason,
            pos,
            info: Object.fromEntries(Object.entries(info).map(([k, v]) => [k, String(v)])),
          };
          setErr(errorText(fe));
        } else setErr(describe(e));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ds.id, offset, filter, sort, stamp, describe]);

  const save = async () => {
    if (!editing) return;
    const done = await run("cleaning.edit_cells", {
      dataset_id: ds.id,
      cells: [{ row: editing.row, column: editing.column, value: editing.value }],
    });
    if (done) setEditing(null);
  };

  const toggleSort = (c: string) => {
    setOffset(0);
    setSort(
      !sort || sort.column !== c
        ? { column: c, descending: false }
        : sort.descending
          ? null
          : { column: c, descending: true },
    );
  };

  const edited = new Set(page?.edited ?? []);

  return (
    <section className="stack">
      <div className="section-head">
        <form
          className="grid-filter"
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            setFilter(filterText.trim());
          }}
        >
          <input
            className="input mono"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder={t("grid.filterPlaceholder")}
            aria-label={t("grid.filter")}
            data-testid="grid-filter"
          />
          <button className="btn" type="submit" data-testid="grid-filter-apply">
            {t("grid.apply")}
          </button>
          {filter && (
            <button
              className="link"
              type="button"
              onClick={() => {
                setFilter("");
                setFilterText("");
              }}
            >
              {t("grid.clearFilter")}
            </button>
          )}
        </form>
        {page && (
          <div className="pager">
            <span className="muted small" data-testid="grid-info">
              {page.filtered !== null
                ? t("grid.filtered", { n: number(page.filtered, 0), total: number(ds.clean_rows, 0) })
                : t("data.pageInfo", {
                    from: number(page.total ? offset + 1 : 0, 0),
                    to: number(Math.min(offset + LIMIT, page.total), 0),
                    total: number(page.total, 0),
                  })}
            </span>
            <IconButton
              icon="up"
              label={t("data.previous")}
              onClick={() => setOffset(Math.max(0, offset - LIMIT))}
              disabled={offset === 0}
            />
            <IconButton
              icon="down"
              label={t("data.next")}
              onClick={() => setOffset(offset + LIMIT)}
              disabled={offset + LIMIT >= page.total}
            />
          </div>
        )}
      </div>
      <p className="muted small">{t("grid.help")}</p>
      {err && <Notice kind="error">{err}</Notice>}
      {page && (
        <div className="grid-wrap" data-testid="data-grid">
          <table className="table compact grid editable">
            <thead>
              <tr>
                <th className="rownum" title={t("grid.rowNumber")}>
                  #
                </th>
                {page.columns.map((c) => (
                  <th key={c} title={col(c, ds) ? `${col(c, ds)} (${c})` : c}>
                    <button className="th-sort" onClick={() => toggleSort(c)} data-testid={`sort-${c}`}>
                      {showLabels ? (col(c, ds) ?? c) : c}
                      {sort?.column === c && <span aria-hidden="true">{sort.descending ? " ▼" : " ▲"}</span>}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.rows.map((r, i) => {
                const rowNo = page.row_numbers[i];
                return (
                  <tr key={rowNo}>
                    <td className="rownum">{rowNo}</td>
                    {r.map((v, j) => {
                      const c = page.columns[j];
                      const isEditing = editing?.row === rowNo && editing.column === c;
                      const mark = edited.has(`${rowNo}|${c}`);
                      if (isEditing)
                        return (
                          <td key={j} className="cell-edit">
                            <input
                              className="input cell-input"
                              autoFocus
                              value={editing.value}
                              onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") save();
                                if (e.key === "Escape") setEditing(null);
                              }}
                              onBlur={() => setEditing(null)}
                              aria-label={t("grid.editCell", { row: rowNo, column: c })}
                              data-testid="cell-input"
                            />
                          </td>
                        );
                      return (
                        <td
                          key={j}
                          className={[v === null ? "na" : "", mark ? "edited" : ""].join(" ").trim() || undefined}
                          title={mark ? t("grid.editedCell") : undefined}
                          onDoubleClick={() => setEditing({ row: rowNo, column: c, value: v ?? "" })}
                          data-testid={`cell-${rowNo}-${c}`}
                        >
                          {v === null ? t("data.na") : showLabels ? (val(c, v, ds) ?? v) : v}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
