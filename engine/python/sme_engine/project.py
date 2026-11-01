"""Project file (.sme): a SQLite database owned by the Python engine.

One project is open at a time. Every change is written immediately, so there is
no separate "save" step and nothing is lost if the app closes.

The schema holds the project metadata (with the framework model), the results
framework, the indicators and the values of routine indicators, the imported
datasets (raw data kept unchanged as Parquet), the cleaning journal of each
dataset and the saved tests. Version 2 added saved tests, version 3 the
assumptions of the framework and routine values.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import frameworks
from .rpc import INVALID_PARAMS, RpcError

APPLICATION_ID = 0x534D4531  # "SME1": marks a file as a SuiviEvalLab project
SCHEMA_VERSION = 3
EXTENSION = ".sme"

# Framework levels, from the top. The interface translates them; projects store keys.
LEVELS = ("impact", "outcome", "output", "activity")

_SCHEMA = """
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE framework_node (
    id          TEXT PRIMARY KEY,
    parent_id   TEXT REFERENCES framework_node(id) ON DELETE CASCADE,
    level       TEXT NOT NULL CHECK (level IN ('impact', 'outcome', 'output', 'activity')),
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    assumptions TEXT NOT NULL DEFAULT '',  -- logframe column: assumptions and risks
    position    INTEGER NOT NULL
);
CREATE INDEX framework_node_parent ON framework_node(parent_id, position);

CREATE TABLE indicator (
    id          TEXT PRIMARY KEY,
    node_id     TEXT NOT NULL REFERENCES framework_node(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    spec        TEXT NOT NULL            -- JSON, see indicators.py
);

CREATE TABLE dataset (
    id          TEXT PRIMARY KEY,
    position    INTEGER NOT NULL,
    spec        TEXT NOT NULL,           -- JSON: name, round, source file, sheet, survey design
    raw         BLOB NOT NULL            -- Parquet, never modified after import
);

CREATE TABLE saved_test (
    id          TEXT PRIMARY KEY,
    position    INTEGER NOT NULL,
    spec        TEXT NOT NULL            -- JSON, see stattests.py
);

CREATE TABLE routine_value (
    id           TEXT PRIMARY KEY,
    indicator_id TEXT NOT NULL REFERENCES indicator(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    spec         TEXT NOT NULL           -- JSON, see routine.py
);

CREATE TABLE cleaning_rule (
    id          TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    spec        TEXT NOT NULL            -- JSON, see cleaning.py
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _err(message: str, key: str, code: int = INVALID_PARAMS) -> RpcError:
    return RpcError(message, code, data={"key": key})


def _text(params: dict[str, Any], name: str, *, required: bool = True, max_len: int = 2000) -> str:
    value = params.get(name, "")
    if not isinstance(value, str):
        raise _err(f"{name} must be a string", "invalid_params")
    value = value.strip()
    if required and not value:
        raise _err(f"{name} is required", "field_required")
    if len(value) > max_len:
        raise _err(f"{name} is longer than {max_len} characters", "field_too_long")
    return value


class Project:
    """An open .sme file."""

    def __init__(self, path: Path, conn: sqlite3.Connection):
        self.path = path
        self.conn = conn

    # ----- opening and creating -------------------------------------------------

    @classmethod
    def create(cls, path: str | Path, name: str, model: dict[str, Any] | None = None) -> Project:
        path = Path(path)
        if path.suffix.lower() != EXTENSION:
            path = path.with_suffix(EXTENSION)
        if path.exists():
            # The save dialog already asked the user to confirm the overwrite.
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = cls._connect(path)
        with conn:
            conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.executescript(_SCHEMA)
            now = _now()
            conn.executemany(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                [("name", name), ("created_at", now), ("updated_at", now), ("app_schema", str(SCHEMA_VERSION))],
            )
            if model:
                conn.execute("INSERT INTO meta(key, value) VALUES ('framework_model', ?)", (json.dumps(model),))
        return cls(path, conn)

    @classmethod
    def open(cls, path: str | Path) -> Project:
        path = Path(path)
        if not path.is_file():
            raise _err(f"File not found: {path}", "project_not_found")
        try:
            conn = cls._connect(path)
            app_id = conn.execute("PRAGMA application_id").fetchone()[0]
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        except sqlite3.DatabaseError:
            raise _err(f"Not a SuiviEvalLab project: {path}", "project_invalid") from None
        if app_id != APPLICATION_ID:
            conn.close()
            raise _err(f"Not a SuiviEvalLab project: {path}", "project_invalid")
        if version > SCHEMA_VERSION:
            conn.close()
            raise _err(f"Project made with a newer version (schema {version})", "project_too_new")
        try:
            from . import backups

            backups.snapshot(conn, path)  # before any migration, so the old version is kept too
        except (OSError, sqlite3.Error):
            pass  # a copy that cannot be written must not stop the user from working
        cls._migrate(conn, version)
        return cls(path, conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection, version: int) -> None:
        """Bring a project made with an older version up to the current schema."""
        with conn:
            if version < 2:
                # 0.3: tests saved from the test assistant.
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS saved_test "
                    "(id TEXT PRIMARY KEY, position INTEGER NOT NULL, spec TEXT NOT NULL)"
                )
            if version < 3:
                # 0.4: assumptions in the framework, values of routine monitoring indicators.
                cols = [r[1] for r in conn.execute("PRAGMA table_info(framework_node)")]
                if "assumptions" not in cols:
                    conn.execute("ALTER TABLE framework_node ADD COLUMN assumptions TEXT NOT NULL DEFAULT ''")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS routine_value (id TEXT PRIMARY KEY, indicator_id TEXT NOT NULL "
                    "REFERENCES indicator(id) ON DELETE CASCADE, position INTEGER NOT NULL, spec TEXT NOT NULL)"
                )
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(path, isolation_level="DEFERRED")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = DELETE")  # a single file the user can copy or email
        return conn

    def close(self) -> None:
        self.conn.close()

    # ----- metadata -------------------------------------------------------------

    def meta(self) -> dict[str, str]:
        return {row["key"]: row["value"] for row in self.conn.execute("SELECT key, value FROM meta")}

    def info(self) -> dict[str, Any]:
        meta = self.meta()
        counts = {
            level: n
            for level, n in self.conn.execute("SELECT level, COUNT(*) FROM framework_node GROUP BY level").fetchall()
        }
        return {
            "path": str(self.path),
            "name": meta.get("name", self.path.stem),
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
            "counts": {level: counts.get(level, 0) for level in LEVELS},
            "report_template": meta.get("report_template_name") or None,
            "framework_model": frameworks.from_meta(meta),
        }

    def model(self) -> dict[str, Any]:
        return frameworks.from_meta(self.meta())

    def set_meta(self, key: str, value: str | None) -> None:
        with self.conn:
            if value is None:
                self.conn.execute("DELETE FROM meta WHERE key = ?", (key,))
            else:
                self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))
            self._touch()

    def rename(self, name: str) -> dict[str, Any]:
        with self.conn:
            self.conn.execute("UPDATE meta SET value = ? WHERE key = 'name'", (name,))
            self._touch()
        return self.info()

    def _touch(self) -> None:
        self.conn.execute("UPDATE meta SET value = ? WHERE key = 'updated_at'", (_now(),))

    # ----- results framework ----------------------------------------------------

    def framework(self) -> list[dict[str, Any]]:
        """All nodes in display order, with their computed code (1, 1.2, 1.2.3)."""
        rows = self.conn.execute(
            "SELECT id, parent_id, level, title, description, assumptions, position "
            "FROM framework_node ORDER BY position"
        ).fetchall()
        children: dict[str | None, list[sqlite3.Row]] = {}
        for row in rows:
            children.setdefault(row["parent_id"], []).append(row)

        out: list[dict[str, Any]] = []

        def walk(parent: str | None, prefix: str, depth: int) -> None:
            for i, row in enumerate(children.get(parent, []), start=1):
                # The top level (impact) is not numbered; numbering starts below it.
                code = "" if depth == 0 else (f"{prefix}.{i}" if prefix else str(i))
                kids = children.get(row["id"], [])
                out.append(
                    {
                        "id": row["id"],
                        "parent_id": row["parent_id"],
                        "level": row["level"],
                        "title": row["title"],
                        "description": row["description"],
                        "assumptions": row["assumptions"],
                        "code": code,
                        "depth": depth,
                        "children": len(kids),
                    }
                )
                walk(row["id"], code, depth + 1)

        walk(None, "", 0)
        return out

    def _node(self, node_id: Any) -> sqlite3.Row:
        if not isinstance(node_id, str):
            raise _err("id must be a string", "invalid_params")
        row = self.conn.execute("SELECT * FROM framework_node WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            raise _err(f"Unknown framework node: {node_id}", "node_not_found")
        return row

    def add_node(
        self, parent_id: str | None, title: str, description: str = "", assumptions: str = ""
    ) -> dict[str, Any]:
        depth = len(self.model()["levels"])
        if parent_id is None:
            level = LEVELS[0]
        else:
            parent = self._node(parent_id)
            index = LEVELS.index(parent["level"])
            if index >= depth - 1:
                raise _err("The last level of the framework cannot have children", "node_no_children")
            level = LEVELS[index + 1]
        position = self.conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM framework_node WHERE parent_id IS ?", (parent_id,)
        ).fetchone()[0]
        node_id = uuid.uuid4().hex
        with self.conn:
            self.conn.execute(
                "INSERT INTO framework_node(id, parent_id, level, title, description, assumptions, position) "
                "VALUES (?,?,?,?,?,?,?)",
                (node_id, parent_id, level, title, description, assumptions, position),
            )
            self._touch()
        return {"id": node_id}

    def update_node(self, node_id: str, title: str, description: str, assumptions: str | None = None) -> None:
        node = self._node(node_id)
        if assumptions is None:
            assumptions = node["assumptions"]
        with self.conn:
            self.conn.execute(
                "UPDATE framework_node SET title = ?, description = ?, assumptions = ? WHERE id = ?",
                (title, description, assumptions, node_id),
            )
            self._touch()

    def delete_node(self, node_id: str) -> int:
        """Delete a node and everything below it. Returns the number of nodes removed."""
        self._node(node_id)
        removed = self.conn.execute(
            """WITH RECURSIVE sub(id) AS (
                   SELECT ? UNION ALL SELECT f.id FROM framework_node f JOIN sub ON f.parent_id = sub.id)
               SELECT COUNT(*) FROM sub""",
            (node_id,),
        ).fetchone()[0]
        with self.conn:
            self.conn.execute("DELETE FROM framework_node WHERE id = ?", (node_id,))
            self._touch()
        return removed

    def move_node(self, node_id: str, direction: int) -> None:
        """Swap a node with its previous (-1) or next (+1) sibling."""
        if direction not in (-1, 1):
            raise _err("direction must be -1 or 1", "invalid_params")
        node = self._node(node_id)
        siblings = [
            r["id"]
            for r in self.conn.execute(
                "SELECT id FROM framework_node WHERE parent_id IS ? ORDER BY position", (node["parent_id"],)
            )
        ]
        i = siblings.index(node_id)
        j = i + direction
        if j < 0 or j >= len(siblings):
            return
        siblings[i], siblings[j] = siblings[j], siblings[i]
        with self.conn:
            self.conn.executemany(
                "UPDATE framework_node SET position = ? WHERE id = ?",
                [(pos, sid) for pos, sid in enumerate(siblings, start=1)],
            )
            self._touch()

    # ----- positioned JSON records (indicators, datasets, cleaning rules) --------

    _SCOPES = {
        "indicator": "node_id",
        "dataset": None,
        "cleaning_rule": "dataset_id",
        "saved_test": None,
        "routine_value": "indicator_id",
    }

    def records(self, table: str, scope: str | None = None) -> list[dict[str, Any]]:
        col = self._SCOPES[table]
        sql = f"SELECT id, {col + ', ' if col else ''}spec FROM {table}"
        args: tuple[Any, ...] = ()
        if col and scope is not None:
            sql += f" WHERE {col} = ?"
            args = (scope,)
        sql += " ORDER BY position"
        out = []
        for row in self.conn.execute(sql, args):
            rec = json.loads(row["spec"])
            rec["id"] = row["id"]
            if col:
                rec[col] = row[col]
            out.append(rec)
        return out

    def record(self, table: str, record_id: Any) -> dict[str, Any]:
        if not isinstance(record_id, str):
            raise _err("id must be a string", "invalid_params")
        col = self._SCOPES[table]
        row = self.conn.execute(
            f"SELECT id, {col + ', ' if col else ''}spec FROM {table} WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            raise _err(f"Unknown {table}: {record_id}", f"{table}_not_found")
        rec = json.loads(row["spec"])
        rec["id"] = row["id"]
        if col:
            rec[col] = row[col]
        return rec

    def insert_record(self, table: str, spec: dict[str, Any], scope: str | None = None, **blobs: bytes) -> str:
        col = self._SCOPES[table]
        where = f"WHERE {col} = ?" if col else ""
        position = self.conn.execute(
            f"SELECT COALESCE(MAX(position), 0) + 1 FROM {table} {where}", (scope,) if col else ()
        ).fetchone()[0]
        record_id = uuid.uuid4().hex
        names = ["id", "position", "spec", *([col] if col else []), *blobs.keys()]
        values = [record_id, position, json.dumps(spec, ensure_ascii=False), *([scope] if col else []), *blobs.values()]
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {table}({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})", values
            )
            self._touch()
        return record_id

    def update_record(self, table: str, record_id: str, spec: dict[str, Any]) -> None:
        self.record(table, record_id)
        clean = {k: v for k, v in spec.items() if k not in ("id", self._SCOPES[table])}
        with self.conn:
            self.conn.execute(
                f"UPDATE {table} SET spec = ? WHERE id = ?", (json.dumps(clean, ensure_ascii=False), record_id)
            )
            self._touch()

    def delete_record(self, table: str, record_id: str) -> None:
        self.record(table, record_id)
        with self.conn:
            self.conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
            self._touch()

    def move_record(self, table: str, record_id: str, direction: int) -> None:
        if direction not in (-1, 1):
            raise _err("direction must be -1 or 1", "invalid_params")
        rec = self.record(table, record_id)
        col = self._SCOPES[table]
        ids = [r["id"] for r in self.records(table, rec.get(col) if col else None)]
        i = ids.index(record_id)
        j = i + direction
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            with self.conn:
                self.conn.executemany(
                    f"UPDATE {table} SET position = ? WHERE id = ?", [(p, rid) for p, rid in enumerate(ids, start=1)]
                )
                self._touch()

    def blob(self, table: str, column: str, record_id: str) -> bytes:
        row = self.conn.execute(f"SELECT {column} FROM {table} WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise _err(f"Unknown {table}: {record_id}", f"{table}_not_found")
        return bytes(row[0])


class Workspace:
    """Holds the project currently open in the engine."""

    def __init__(self) -> None:
        self.project: Project | None = None

    def require(self) -> Project:
        if self.project is None:
            raise RpcError("No project is open", INVALID_PARAMS, data={"key": "no_project"})
        return self.project

    def set(self, project: Project) -> None:
        self.close()
        self.project = project

    def close(self) -> None:
        if self.project is not None:
            self.project.close()
            self.project = None
