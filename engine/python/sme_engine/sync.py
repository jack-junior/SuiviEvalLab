# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Working together on a project (section 7).

Each member works on a local copy. Copies exchange operations, never whole
files. SQLite triggers write every change of a shared table into `changes`,
with a hybrid logical clock (milliseconds, counter, member) and the member it
comes from, whatever the code that made the change.

An operation carries the row as it is, the clock of the change and the clock
of the version it replaced (its base). On receipt:

- the newest clock wins, row by row;
- when the copy changed the same row since the base the sender knew, the two
  changes were concurrent: the one that loses is kept as a conflict to review;
- a change to validated data or to a locked period, from anyone but an
  administrator or a validator, is never applied: it becomes a request;
- a change outside the author's role or scope is refused.

The same files travel by hand (packages), through a shared folder, or through
a relay server. Each file is signed by its author and encrypted with the key of
the project, so a relay server can neither read nor forge them.
"""

from __future__ import annotations

import base64
import gzip
import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import security
from .rpc import INVALID_PARAMS, RpcError

SYNC_FORMAT = "suivievallab-sync"
SYNC_MAGIC = b"SMESYNC2"
JOIN_MAGIC = b"SMEJOIN1"
LOCAL_TABLES = {"changes", "conflict", "audit", "measure_cache", "sqlite_sequence", "lineage"}
ROLES = ("admin", "officer", "partner", "validator", "feedback", "reader")
# Tables a partner focal point may change, always within its own partners.
PARTNER_TABLES = {"submission", "value", "person", "attachment"}
# Meta keys that belong to one copy only. The office key and the partner keys are
# handed over in invitations, never in changes.
LOCAL_META = ("updated_at", "opened_at", "previous_open", "office_key")
DESIGN_TABLES = {
    "framework_node",
    "indicator",
    "period",
    "place",
    "partner",
    "disaggregation",
    "target",
    "member",
    "meta",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS changes (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    tbl     TEXT NOT NULL,
    pk      TEXT NOT NULL,
    op      TEXT NOT NULL,       -- 'u' upsert, 'd' delete
    hlc     TEXT NOT NULL,
    origin  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS changes_pk ON changes(tbl, pk, hlc);
CREATE INDEX IF NOT EXISTS changes_origin ON changes(origin, seq);
-- The version each received change replaced, to tell concurrent edits from later ones.
CREATE TABLE IF NOT EXISTS lineage (
    tbl     TEXT NOT NULL,
    pk      TEXT NOT NULL,
    hlc     TEXT NOT NULL,
    base    TEXT NOT NULL,
    PRIMARY KEY (tbl, pk, hlc)
);
-- Changes not applied: concurrent edits that lost, and requests on protected data.
CREATE TABLE IF NOT EXISTS conflict (
    id      TEXT PRIMARY KEY,
    kind    TEXT NOT NULL,       -- 'conflict' or 'request'
    tbl     TEXT NOT NULL,
    pk      TEXT NOT NULL,
    at      TEXT NOT NULL,
    author  TEXT NOT NULL,
    payload TEXT NOT NULL,       -- JSON: the operation not applied
    state   TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS member (
    id          TEXT PRIMARY KEY,
    position    INTEGER NOT NULL,
    spec        TEXT NOT NULL    -- JSON: name, roles, partner_ids, public_key, active
);
"""


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ----- clock and triggers ------------------------------------------------------------------------------

CLOCKS: dict[int, Any] = {}


class Clock:
    """Hybrid logical clock of one open project, ordered as text."""

    def __init__(self, origin: str, last: str = ""):
        self.origin = origin
        self.ms, self.n = 0, 0
        if last:
            self.observe(last)
        self.applying: tuple[str, str] | None = None

    def observe(self, hlc: str) -> None:
        try:
            ms, n = int(hlc[:13]), int(hlc[14:19])
        except ValueError:
            return
        if (ms, n) > (self.ms, self.n):
            self.ms, self.n = ms, n

    def tick(self) -> str:
        if self.applying:
            return self.applying[0]
        now_ms = int(time.time() * 1000)
        if now_ms > self.ms:
            self.ms, self.n = now_ms, 0
        else:
            self.n += 1
        return f"{self.ms:013d}.{self.n:05d}.{self.origin}"

    def who(self) -> str:
        return self.applying[1] if self.applying else self.origin


def attach(conn: Any) -> Clock:
    """Make the clock functions the triggers call, for this connection."""
    me = security.identity()["id"]
    try:
        row = conn.execute("SELECT MAX(hlc) FROM changes").fetchone()
        last = row[0] if row and row[0] else ""
    except Exception:  # noqa: BLE001 - a project made before 1.0 has no table yet
        last = ""
    clock = Clock(me, last)
    conn.create_function("sme_hlc", 0, clock.tick)
    conn.create_function("sme_origin", 0, clock.who)
    return clock


def _key_expr(table: str, cols: list[str], row: str) -> str | None:
    if table == "value":
        return f"{row}.submission_id || '|' || {row}.indicator_id || '|' || {row}.cats"
    if table == "person":
        return f"{row}.submission_id || '|' || {row}.indicator_id || '|' || {row}.cats || '|' || {row}.pid"
    if table == "meta":
        return f"{row}.key"
    return f"{row}.id" if "id" in cols else None


def shared_tables(conn: Any) -> dict[str, list[str]]:
    out = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        if name in LOCAL_TABLES or name.startswith("sqlite_"):
            continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()]
        if _key_expr(name, cols, "NEW"):
            out[name] = cols
    return out


def install_triggers(conn: Any) -> None:
    """Changes are logged once the team is set up (a member exists): a project used
    by one person carries no log; setting up the team logs what it holds then."""
    conn.executescript(SCHEMA)
    team = "EXISTS (SELECT 1 FROM member)"
    for table, cols in shared_tables(conn).items():
        new, old = _key_expr(table, cols, "NEW"), _key_expr(table, cols, "OLD")
        when_new = when_old = f" WHEN {team}"
        if table == "meta":
            skip = (
                " AND ".join(f"{{r}}.key <> '{k}'" for k in LOCAL_META)
                + " AND {r}.key NOT LIKE 'rev:%' AND {r}.key NOT LIKE 'partner_key:%'"
            )
            when_new = f" WHEN {team} AND " + skip.format(r="NEW")
            when_old = f" WHEN {team} AND " + skip.format(r="OLD")
        body = "INSERT INTO changes(tbl, pk, op, hlc, origin) VALUES ('{t}', {k}, '{o}', sme_hlc(), sme_origin());"
        conn.executescript(
            f"""
DROP TRIGGER IF EXISTS sync_{table}_i;
DROP TRIGGER IF EXISTS sync_{table}_u;
DROP TRIGGER IF EXISTS sync_{table}_d;
CREATE TRIGGER sync_{table}_i AFTER INSERT ON {table}{when_new}
BEGIN {body.format(t=table, k=new, o="u")} END;
CREATE TRIGGER sync_{table}_u AFTER UPDATE ON {table}{when_new}
BEGIN {body.format(t=table, k=new, o="u")} END;
CREATE TRIGGER sync_{table}_d AFTER DELETE ON {table}{when_old}
BEGIN {body.format(t=table, k=old, o="d")} END;
"""
        )


def compact(conn: Any) -> int:
    """Keep the two latest changes of each row: the latest is sent, the one before
    is its base. Returns how many were removed."""
    with conn:
        cur = conn.execute(
            "DELETE FROM changes WHERE seq IN (SELECT seq FROM (SELECT seq, ROW_NUMBER() OVER "
            "(PARTITION BY tbl, pk ORDER BY hlc DESC, seq DESC) AS n FROM changes) WHERE n > 2)"
        )
    return cur.rowcount


# ----- members and their rights ---------------------------------------------------------------------


def members(p: Any) -> list[dict[str, Any]]:
    return p.records("member")


def member_list_bytes(p: Any) -> bytes:
    return security.canonical(
        sorted(
            (
                {
                    "id": m["id"],
                    "public_key": m["public_key"],
                    "roles": sorted(m["roles"]),
                    "partner_ids": sorted(m.get("partner_ids") or []),
                    "active": bool(m.get("active", True)),
                }
                for m in members(p)
            ),
            key=lambda m: m["id"],
        )
    )


def team_on(p: Any) -> bool:
    return bool(p.meta().get("owner"))


def me_member(p: Any) -> dict[str, Any] | None:
    me = security.identity()["id"]
    return next((m for m in members(p) if m["id"] == me), None)


def my_roles(p: Any) -> set[str]:
    """Without a team, the only user has every role (section 2)."""
    if not team_on(p):
        return set(ROLES)
    m = me_member(p)
    return set(m["roles"]) if m and m.get("active", True) else set()


def start_team(p: Any, name: str) -> None:
    """The project's first member is its administrator, owner of the member list."""
    if team_on(p):
        raise _err("The team is already set up", "team_exists")
    me = security.identity(name or None)
    p.set_meta("sync_key", security.b64(security.secrets.token_bytes(32)))
    p.set_meta("office_key", security.b64(security.secrets.token_bytes(32)))
    p.conn.execute(
        "INSERT OR REPLACE INTO member(id, position, spec) VALUES (?, 1, ?)",
        (
            me["id"],
            json.dumps(
                {
                    "name": name or me["name"],
                    "roles": ["admin"],
                    "partner_ids": [],
                    "public_key": me["public"],
                    "active": True,
                    "added_at": now(),
                },
                ensure_ascii=False,
            ),
        ),
    )
    p.conn.commit()
    p.set_meta("owner", me["id"])
    p.set_meta("owner_key", me["public"])
    sign_members(p)
    security.audit(p.conn, "team_started", me["id"], {"name": name})


def sign_members(p: Any) -> None:
    p.set_meta("members_sig", security.sign(member_list_bytes(p)))


def validate_member(spec: Any, partner_ids: set[str]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise _err("The member must be an object", "invalid_params")
    name = str(spec.get("name") or "").strip()[:120]
    if not name:
        raise _err("The member needs a name", "field_required")
    roles = [r for r in spec.get("roles") or [] if r in ROLES]
    if not roles:
        raise _err("Give at least one role", "field_required")
    key = str(spec.get("public_key") or "")
    try:
        if len(security.unb64(key)) != 32:
            raise ValueError
    except ValueError:
        raise _err("The identity file is not valid", "identity_invalid") from None
    parts = [x for x in spec.get("partner_ids") or [] if x in partner_ids]
    if "partner" in roles and not parts:
        raise _err("A partner focal point needs its partner", "field_required")
    return {
        "name": name,
        "roles": roles,
        "partner_ids": parts,
        "public_key": key,
        "active": spec.get("active", True) is not False,
    }


def members_trusted(p: Any) -> bool:
    meta = p.meta()
    if not meta.get("owner_key") or not meta.get("members_sig"):
        return False
    return security.verify(meta["owner_key"], member_list_bytes(p), meta["members_sig"])


def _sub_partner(p: Any, row: dict[str, Any], table: str) -> str | None:
    if table == "submission":
        spec = json.loads(row.get("spec") or "{}")
        return spec.get("partner_id") or ""
    sub_id = row.get("submission_id") or (
        json.loads(row.get("spec") or "{}").get("owner_id") if table == "attachment" else None
    )
    if not sub_id:
        return None
    got = p.conn.execute("SELECT spec FROM submission WHERE id = ?", (sub_id,)).fetchone()
    return json.loads(got[0]).get("partner_id", "") if got else None


def allowed(p: Any, author: dict[str, Any], table: str, row: dict[str, Any] | None) -> bool:
    roles = set(author["roles"])
    if "admin" in roles:
        return True
    if table in ("member",) or (
        table == "meta" and row and row.get("key") in ("owner", "owner_key", "members_sig", "sync_key", "office_key")
    ):
        return False
    if "reader" in roles and len(roles) == 1:
        return False
    if roles == {"partner"}:
        if table not in PARTNER_TABLES or row is None:
            return False
        partner = _sub_partner(p, row, table)
        return partner is not None and partner in (author.get("partner_ids") or [])
    if "officer" in roles:
        return table not in ("target",)
    ok = set()
    if "validator" in roles:
        ok |= {"submission", "justification", "gap_comment", "value", "person"}
    if "feedback" in roles:
        ok |= {"feedback", "recommendation", "attachment"}
    return table in ok


def protected(p: Any, author: dict[str, Any], table: str, row: dict[str, Any] | None, pk: str) -> bool:
    """A change to validated data or a locked period, from someone who may not make it."""
    if {"admin", "validator"} & set(author["roles"]):
        return False
    sub_id = None
    if table == "submission":
        sub_id = pk
    elif table in ("value", "person"):
        sub_id = pk.split("|", 1)[0]
    if sub_id:
        got = p.conn.execute("SELECT spec FROM submission WHERE id = ?", (sub_id,)).fetchone()
        if got and json.loads(got[0]).get("status") in ("validated", "locked"):
            return True
    if table == "period" and row is not None:
        got = p.conn.execute("SELECT spec FROM period WHERE id = ?", (pk,)).fetchone()
        if got and json.loads(got[0]).get("state") == "locked":
            return True
    return False


# ----- operations -------------------------------------------------------------------------------------


def _row(p: Any, table: str, pk: str, cols: list[str]) -> dict[str, Any] | None:
    if table == "meta":
        got = p.conn.execute("SELECT key, value FROM meta WHERE key = ?", (pk,)).fetchone()
        return {"key": got[0], "value": got[1]} if got else None
    if table in ("value", "person"):
        parts = pk.split("|")
        names = ["submission_id", "indicator_id", "cats"] + (["pid"] if table == "person" else [])
        where = " AND ".join(f"{n} = ?" for n in names)
        got = p.conn.execute(f"SELECT * FROM {table} WHERE {where}", parts[: len(names)]).fetchone()
    else:
        got = p.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (pk,)).fetchone()
    if got is None:
        return None
    out = {}
    for c in cols:
        v = got[c]
        if c == "id" and table in ("value",):
            continue
        out[c] = {"$b": base64.b64encode(v).decode("ascii")} if isinstance(v, bytes) else v
    return out


def collect(p: Any, origin: str | None, after: int, keep=None) -> tuple[list[dict[str, Any]], int]:
    """Operations changed since `after`, the latest state of each row, with their base."""
    tables = shared_tables(p.conn)
    rows = p.conn.execute(
        "SELECT seq, tbl, pk, op, hlc, origin FROM changes WHERE seq > ? ORDER BY seq", (after,)
    ).fetchall()
    last = max((r[0] for r in rows), default=after)
    latest: dict[tuple[str, str], tuple] = {}
    for r in rows:
        latest[(r[1], r[2])] = r
    ops = []
    for (table, pk), _r in sorted(latest.items(), key=lambda kv: kv[1][4]):
        if table not in tables:
            continue
        top = p.conn.execute(
            "SELECT op, hlc, origin FROM changes WHERE tbl = ? AND pk = ? ORDER BY hlc DESC, seq DESC LIMIT 2",
            (table, pk),
        ).fetchall()
        op, hlc, who = top[0]
        if origin is not None and who != origin:
            continue
        base = top[1][1] if len(top) > 1 else ""
        row = _row(p, table, pk, tables[table]) if op == "u" else None
        if op == "u" and row is None:
            op = "d"
        if keep and not keep(table, pk, row):
            continue
        ops.append({"t": table, "k": pk, "o": op, "h": hlc, "b": base, "a": who, "r": row})
    return ops, last


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    return {k: base64.b64decode(v["$b"]) if isinstance(v, dict) and "$b" in v else v for k, v in row.items()}


def apply(p: Any, clock: Clock, ops: list[dict[str, Any]], authors: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Apply received operations; returns how many were applied, skipped, refused, held."""
    me = clock.origin
    tables = shared_tables(p.conn)
    stats = {"applied": 0, "skipped": 0, "refused": 0, "conflicts": 0, "requests": 0}
    p.conn.execute("PRAGMA defer_foreign_keys = ON")
    for op in sorted(ops, key=lambda o: o["h"]):
        table, pk, hlc, who = op["t"], op["k"], op["h"], op["a"]
        clock.observe(hlc)
        if who == me or table not in tables:
            stats["skipped"] += 1
            continue
        local = p.conn.execute(
            "SELECT hlc, origin FROM changes WHERE tbl = ? AND pk = ? ORDER BY hlc DESC, seq DESC LIMIT 1",
            (table, pk),
        ).fetchone()
        if local and local[0] >= hlc:
            if local[0] > hlc and local[1] != who and not _superseded(p, table, pk, hlc, who):
                _hold(p, "conflict", op)
                stats["conflicts"] += 1
            else:
                stats["skipped"] += 1
            continue
        author = authors.get(who)
        row = _decode(op["r"]) if op.get("r") else None
        if author is None or not allowed(p, author, table, row):
            stats["refused"] += 1
            continue
        if protected(p, author, table, row, pk):
            _hold(p, "request", op)
            stats["requests"] += 1
            continue
        if local and local[1] != who and (op.get("b") or "") < local[0]:
            # Both copies changed the row: the newer wins, the other is kept for review.
            loser = {**op, "r": _row(p, table, pk, tables[table]), "h": local[0], "a": local[1], "lost_to": hlc}
            _hold(p, "conflict", loser)
            stats["conflicts"] += 1
        clock.applying = (hlc, who)
        try:
            _write(p, table, pk, op["o"], row)
        finally:
            clock.applying = None
        p.conn.execute(
            "INSERT OR REPLACE INTO lineage(tbl, pk, hlc, base) VALUES (?, ?, ?, ?)",
            (table, pk, hlc, op.get("b") or ""),
        )
        stats["applied"] += 1
    p.conn.commit()
    p.conn.execute("DELETE FROM measure_cache")
    p.conn.commit()
    return stats


def _superseded(p: Any, table: str, pk: str, hlc: str, who: str) -> bool:
    """Whether a later version known here already builds on this change of `who`."""
    tail = f".{who}"
    for (base,) in p.conn.execute("SELECT base FROM lineage WHERE tbl = ? AND pk = ?", (table, pk)).fetchall():
        if base.endswith(tail) and base >= hlc:
            return True
    got = p.conn.execute(
        "SELECT 1 FROM changes WHERE tbl = ? AND pk = ? AND origin = ? AND hlc >= ? LIMIT 1", (table, pk, who, hlc)
    ).fetchone()
    return got is not None


def _write(p: Any, table: str, pk: str, op: str, row: dict[str, Any] | None) -> None:
    if table == "meta":
        if op == "d":
            p.conn.execute("DELETE FROM meta WHERE key = ?", (pk,))
        else:
            p.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (row["key"], row["value"]))
        return
    if table in ("value", "person"):
        names = ["submission_id", "indicator_id", "cats"] + (["pid"] if table == "person" else [])
        parts = pk.split("|")[: len(names)]
        where = " AND ".join(f"{n} = ?" for n in names)
        if op != "u" or not row:
            p.conn.execute(f"DELETE FROM {table} WHERE {where}", parts)
            return
        # Updated in place, or added: one change logged, never a deletion with the same
        # time as the new version (which one came last could not be told).
        row = {k: v for k, v in row.items() if k != "id"}
        cur = p.conn.execute(
            f"UPDATE {table} SET {', '.join(f'{k} = ?' for k in row)} WHERE {where}", [*row.values(), *parts]
        )
        if cur.rowcount == 0:
            p.conn.execute(
                f"INSERT INTO {table}({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values())
            )
        return
    if op == "d":
        p.conn.execute(f"DELETE FROM {table} WHERE id = ?", (pk,))
        return
    p.conn.execute(
        f"INSERT OR REPLACE INTO {table}({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values())
    )


def _hold(p: Any, kind: str, op: dict[str, Any]) -> None:
    p.conn.execute(
        "INSERT INTO conflict(id, kind, tbl, pk, at, author, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, kind, op["t"], op["k"], now(), op["a"], json.dumps(op, ensure_ascii=False)),
    )


def conflicts(p: Any) -> list[dict[str, Any]]:
    names = {m["id"]: m["name"] for m in members(p)}
    out = []
    for r in p.conn.execute(
        "SELECT id, kind, tbl, pk, at, author, payload, state FROM conflict WHERE state = 'open' ORDER BY at"
    ).fetchall():
        op = json.loads(r[6])
        out.append(
            {
                "id": r[0],
                "kind": r[1],
                "table": r[2],
                "pk": r[3],
                "at": r[4],
                "author": names.get(r[5], r[5]),
                "op": op["o"],
                "row": op.get("r"),
            }
        )
    return out


def resolve(p: Any, clock: Clock, conflict_id: Any, accept: bool) -> None:
    """Keep the change that was set aside (accept), or drop it."""
    got = p.conn.execute(
        "SELECT payload, kind FROM conflict WHERE id = ? AND state = 'open'", (conflict_id,)
    ).fetchone()
    if got is None:
        raise _err("Unknown conflict", "conflict_not_found")
    if "admin" not in my_roles(p):
        raise _err("Only an administrator resolves conflicts", "not_allowed")
    op = json.loads(got[0])
    if accept:
        row = _decode(op["r"]) if op.get("r") else None
        # Taken again by this copy now: a new change, made here, that others will receive.
        _write(p, op["t"], op["k"], op["o"] if row is not None or op["o"] == "d" else "d", row)
    p.conn.execute("UPDATE conflict SET state = ? WHERE id = ?", ("accepted" if accept else "dropped", conflict_id))
    p.conn.commit()
    security.audit(p.conn, "conflict_" + ("accepted" if accept else "dropped"), f"{op['t']}:{op['k']}", got[1])


# ----- signed and encrypted files -----------------------------------------------------------------------


def _sync_key(p: Any) -> bytes:
    key = p.meta().get("sync_key")
    if not key:
        raise _err("Set up the team first", "team_missing")
    return security.unb64(key)


# Who may read a file (section 7.3). Each file is encrypted for one audience:
#   "all"           the design of the project, with the key every member has;
#   "office"        everything else, with the office key, which partners do not have;
#   "partner:<id>"  the data of one partner, with a key derived from the office key and
#                   given only to that partner's focal points.
# A file in a shared folder or on the server can thus be fetched by every member, but
# read only by those it is for.


def partner_key(office_key: bytes, partner_id: str) -> bytes:
    import hashlib
    import hmac

    return hmac.new(office_key, b"partner:" + partner_id.encode(), hashlib.sha256).digest()


def audience_key(p: Any, audience: str) -> bytes | None:
    meta = p.meta()
    if audience == "all":
        return _sync_key(p)
    office = meta.get("office_key")
    if audience == "office":
        return security.unb64(office) if office else None
    if audience.startswith("partner:"):
        pid = audience.split(":", 1)[1]
        if office:
            return partner_key(security.unb64(office), pid)
        own = meta.get(f"partner_key:{pid}")
        return security.unb64(own) if own else None
    return None


def audience_of(p: Any, op: dict[str, Any]) -> str:
    table = op["t"]
    if table in DESIGN_TABLES:
        return "all"
    if table in PARTNER_TABLES:
        row = _decode(op["r"]) if op.get("r") else None
        if row is None and table in ("value", "person", "submission"):
            sub_id = op["k"] if table == "submission" else op["k"].split("|", 1)[0]
            got = p.conn.execute("SELECT spec FROM submission WHERE id = ?", (sub_id,)).fetchone()
            partner = json.loads(got[0]).get("partner_id", "") if got else ""
        else:
            partner = _sub_partner(p, row, table) if row is not None else ""
        if partner:
            return f"partner:{partner}"
    return "office"


def pack(p: Any, ops: list[dict[str, Any]], audience: str = "office") -> bytes:
    me = security.identity()
    payload = gzip.compress(
        security.canonical(
            {
                "format": SYNC_FORMAT,
                "version": 2,
                "project": p.meta().get("uid", ""),
                "author": me["id"],
                "created": now(),
                "audience": audience,
                "ops": ops,
            }
        )
    )
    key = audience_key(p, audience)
    if key is None:
        raise _err("This copy cannot write for this audience", "not_allowed")
    envelope = security.canonical({"author": me["id"], "sig": security.sign(payload), "payload": security.b64(payload)})
    head = SYNC_MAGIC + bytes([len(audience)]) + audience.encode()
    return head + security.seal(key, envelope, head)


def packs(p: Any, ops: list[dict[str, Any]]) -> list[tuple[str, bytes, int]]:
    """Operations split by audience, one file each: (audience, file, number of operations)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for op in ops:
        groups.setdefault(audience_of(p, op), []).append(op)
    return [(aud, pack(p, items, aud), len(items)) for aud, items in sorted(groups.items())]


def file_audience(blob: bytes) -> str:
    if not blob.startswith(SYNC_MAGIC) or len(blob) < len(SYNC_MAGIC) + 1:
        raise _err("This file is not a synchronisation file", "sync_invalid")
    n = blob[len(SYNC_MAGIC)]
    return blob[len(SYNC_MAGIC) + 1 : len(SYNC_MAGIC) + 1 + n].decode("ascii", "replace")


def unpack(p: Any, blob: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    audience = file_audience(blob)
    head = blob[: len(SYNC_MAGIC) + 1 + len(audience.encode())]
    key = audience_key(p, audience)
    if key is None:
        raise _err("This file is for other members of the team", "sync_not_for_me")
    try:
        envelope = json.loads(security.unseal(key, blob[len(head) :], head))
    except RpcError:
        raise _err("This file belongs to another project", "sync_other_project") from None
    if not members_trusted(p):
        raise _err("The member list of this copy is not signed by the administrator", "members_untrusted")
    author = next((m for m in members(p) if m["id"] == envelope["author"] and m.get("active", True)), None)
    if author is None:
        raise _err("The author of this file is not a member of the project", "sync_unknown_author")
    payload = security.unb64(envelope["payload"])
    if not security.verify(author["public_key"], payload, envelope["sig"]):
        raise _err("The signature of this file is not valid", "sync_bad_signature")
    data = json.loads(gzip.decompress(payload))
    if data.get("project") != p.meta().get("uid") or data.get("audience") != audience:
        raise _err("This file belongs to another project", "sync_other_project")
    return data, author


def receive(p: Any, clock: Clock, blob: bytes) -> dict[str, Any]:
    data, sender = unpack(p, blob)
    # Operations relayed in a package keep their own author; each is judged by its author's rights.
    # Only an administrator relays the operations of others: from anyone else, an operation
    # under another author's name is refused (a member cannot act in another's name).
    authors = {m["id"]: m for m in members(p) if m.get("active", True)}
    relay_ok = "admin" in (authors.get(sender["id"], {}).get("roles") or [])
    forged = [o for o in data["ops"] if o["a"] != sender["id"] and not relay_ok]
    if forged:
        data = {**data, "ops": [o for o in data["ops"] if o not in forged]}
    # Member list changes from the administrator come first, then the rest under the new list.
    first = [
        o
        for o in data["ops"]
        if o["t"] == "member" or (o["t"] == "meta" and o["k"] in ("members_sig", "owner", "owner_key"))
    ]
    rest = [o for o in data["ops"] if o not in first]
    stats = apply(p, clock, first, authors) if first else {}
    if first and not members_trusted(p):
        raise _err("The member list received is not signed by the administrator", "members_untrusted")
    authors = {m["id"]: m for m in members(p) if m.get("active", True)}
    # Submissions before their values: only the latest version of a row is sent, so a
    # submission (submitted after its values were typed) can be newer than its values,
    # and the rights on a value are read from its submission.
    more = apply(p, clock, [o for o in rest if o["t"] == "submission"], authors)
    later = apply(p, clock, [o for o in rest if o["t"] != "submission"], authors)
    for part in (stats, later):
        for k, v in part.items():
            more[k] += v
    more["refused"] += len(forged)
    security.audit(p.conn, "sync_received", sender["id"], more)
    return more


# ----- three ways of carrying the files --------------------------------------------------------------


def _config_file() -> Path:
    return security.folder() / "sync.json"


def config(uid: str) -> dict[str, Any]:
    try:
        data = json.loads(_config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return data.get(uid, {})


def save_config(uid: str, values: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(_config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[uid] = {**data.get(uid, {}), **values}
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(f)
    return data[uid]


def scope_filter(p: Any, member: dict[str, Any]):
    """What a member may receive: a partner focal point only its own data and the design."""
    if set(member["roles"]) != {"partner"}:
        return None
    design = DESIGN_TABLES
    mine = set(member.get("partner_ids") or [])

    def keep(table: str, pk: str, row: dict[str, Any] | None) -> bool:
        if table in design:
            return True
        if table in PARTNER_TABLES:
            if row is None:
                return True
            partner = _sub_partner(p, _decode(row), table)
            return partner in mine
        return False

    return keep


def _my_audience(p: Any) -> str:
    """The audience this copy writes its own files for when it has no other choice."""
    meta = p.meta()
    if meta.get("office_key"):
        return "office"
    own = sorted(k.split(":", 1)[1] for k in meta if k.startswith("partner_key:"))
    return f"partner:{own[0]}" if own else "all"


def package_for(p: Any, member_id: Any) -> tuple[bytes, int]:
    """A package for one member: all changes since the last package sent to them."""
    member = next((m for m in members(p) if m["id"] == member_id), None)
    if member is None:
        raise _err("Unknown member", "member_not_found")
    uid = p.meta().get("uid", "")
    sent = config(uid).get("sent", {}).get(member_id, 0)
    ops, last = collect(p, None, sent, scope_filter(p, member))
    ops = [o for o in ops if o["a"] != member_id]
    # Encrypted for the one who receives it: a partner's own key, or the office key.
    theirs = sorted(member.get("partner_ids") or [])
    if set(member["roles"]) == {"partner"} and theirs and p.meta().get("office_key"):
        audience = f"partner:{theirs[0]}"
    else:
        audience = _my_audience(p)
    blob = pack(p, ops, audience)
    cfg = config(uid)
    save_config(uid, {"sent": {**cfg.get("sent", {}), member_id: last}})
    security.audit(p.conn, "package_written", member_id, {"ops": len(ops)})
    return blob, len(ops)


def _own_since(p: Any, key: str) -> tuple[list[tuple[str, bytes, int]], int]:
    """Files for a shared channel: one per audience, so that each member reads only
    what is for them although every member can fetch every file."""
    uid = p.meta().get("uid", "")
    me = security.identity()["id"]
    after = config(uid).get(key, 0)
    # An administrator also passes on what it received from the others (packages from
    # partners, say), so that a team using several ways ends with the same data.
    ops, last = collect(p, None if "admin" in my_roles(p) else me, after)
    if not ops:
        return [], last
    if not p.meta().get("office_key"):
        return [(_my_audience(p), pack(p, ops, _my_audience(p)), len(ops))], last
    return packs(p, ops), last


def folder_run(p: Any, clock: Clock, folder: Path) -> dict[str, Any]:
    """Write this copy's new changes into the shared folder and read everyone else's."""
    uid = p.meta().get("uid", "")
    me = security.identity()["id"]
    if not folder.is_dir():
        raise _err("The shared folder cannot be reached", "folder_missing")
    box = folder / f"suivievallab-{uid[:12]}"
    box.mkdir(exist_ok=True)
    files_out, last = _own_since(p, "folder_sent")
    written = 0
    stamp = int(time.time() * 1000)
    for k, (_aud, blob, n) in enumerate(files_out):
        name = f"{me}-{stamp:013d}-{k}.smesync"
        tmp = box / (name + ".part")
        tmp.write_bytes(blob)
        tmp.replace(box / name)  # others never read a half-written file
        written += n
    save_config(uid, {"folder_sent": last, "folder": str(folder)})
    done = set(config(uid).get("folder_read", []))
    owner = p.meta().get("owner", "")
    files = sorted(
        (f for f in box.glob("*.smesync") if not f.name.startswith(me) and f.name not in done),
        key=lambda f: (not f.name.startswith(owner), f.name),
    )
    totals = {"applied": 0, "skipped": 0, "refused": 0, "conflicts": 0, "requests": 0}
    errors = []
    for f in files:
        try:
            got = receive(p, clock, f.read_bytes())
            for k in totals:
                totals[k] += got.get(k, 0)
            done.add(f.name)
        except RpcError as exc:
            key = (exc.data or {}).get("key")
            if key == "sync_not_for_me":
                done.add(f.name)  # for other members: not an error
                continue
            errors.append({"file": f.name, "key": key})
    save_config(uid, {"folder_read": sorted(done)[-5000:], "last_run": now()})
    return {"written": written, "read": len(files) - len(errors), "errors": errors, **totals}


def server_run(p: Any, clock: Clock, url: str, token: str) -> dict[str, Any]:
    """The same files through a relay server, which stores them without reading them."""
    from .connectors import clean_url

    uid = p.meta().get("uid", "")
    me = security.identity()["id"]
    base = clean_url(url).rstrip("/") + f"/v1/projects/{uid}"
    headers = {"Authorization": f"Bearer {token}"}

    def call(path: str, data: bytes | None = None, extra: dict[str, str] | None = None) -> bytes:
        req = urllib.request.Request(
            base + path, data=data, headers={**headers, **(extra or {})}, method="POST" if data is not None else "GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            raise _err(
                f"Server answered {exc.code}", "server_auth" if exc.code in (401, 403) else "server_error"
            ) from None
        except (urllib.error.URLError, OSError):
            raise _err("The server cannot be reached", "server_unreachable") from None

    files_out, last = _own_since(p, "server_sent")
    for _aud, blob, _n in files_out:
        call("/files", blob, {"X-Author": me, "Content-Type": "application/octet-stream"})
    save_config(uid, {"server_sent": last, "server": url})
    after = config(uid).get("server_read", 0)
    listing = json.loads(call(f"/files?after={after}"))
    owner = p.meta().get("owner", "")
    totals = {"applied": 0, "skipped": 0, "refused": 0, "conflicts": 0, "requests": 0}
    errors, top = [], after
    for item in sorted(listing.get("files", []), key=lambda x: (x["author"] != owner, x["seq"])):
        top = max(top, item["seq"])
        if item["author"] == me:
            continue
        try:
            got = receive(p, clock, call(f"/files/{item['seq']}"))
            for k in totals:
                totals[k] += got.get(k, 0)
        except RpcError as exc:
            key = (exc.data or {}).get("key")
            if key != "sync_not_for_me":  # a file for other members is not an error
                errors.append({"file": str(item["seq"]), "key": key})
    save_config(uid, {"server_read": top, "last_run": now()})
    written = sum(n for _a, _b, n in files_out)
    return {"written": written, "read": len(listing.get("files", [])), "errors": errors, **totals}
