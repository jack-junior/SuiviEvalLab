# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Formula language for new variables and filters.

A formula is read by this module's own parser and translated into a Polars
expression. Nothing typed by the user is evaluated as Python or R code: the
only things a formula can do are the operators and functions listed here.

    si(age >= 18 et sexe = "F"; 1; 0)
    somme(depenses_eau; depenses_sante) / taille_menage
    jours_entre(date([start]); date([end]))
    [water/containers] > 2 ou est_manquant(revenu)

Columns are written as they are named, or between square brackets when the
name has spaces, slashes or other signs ([groupe/age]). Texts are between
quotes. Arguments are separated by ";" (or ","). Function names and words
exist in French and in English (si / if, et / and, ou / or, non / not).

Rows are computed one by one; the few *_colonne functions (col_mean, ...) use
the whole column, for instance to centre a variable. Missing values propagate:
a calculation with a missing value gives a missing value, and a condition on
a missing value is not true.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any

import polars as pl

from .cleaning_more import _as_text, datetime_expr
from .rpc import INVALID_PARAMS, RpcError

MAX_LENGTH = 4000


class FormulaError(RpcError):
    """A formula that cannot be read. `reason` says why, `pos` where (0-based)."""

    def __init__(self, reason: str, pos: int, **info: Any):
        detail = ", ".join(f"{k}={v}" for k, v in info.items())
        super().__init__(
            f"Formula error {reason} at {pos + 1}" + (f" ({detail})" if detail else ""),
            INVALID_PARAMS,
            data={"key": "formula_invalid", "reason": reason, "pos": pos, **info},
        )
        self.reason, self.pos, self.info = reason, pos, info


# ----- tokens ------------------------------------------------------------------------


@dataclass
class Tok:
    kind: str  # num, str, name, col, op, lp, rp, sep, end
    value: Any
    pos: int


_OPS = ("<=", ">=", "<>", "!=", "==", "&&", "||", "=", "<", ">", "+", "-", "*", "/", "^", "&", "!")
_NAME = re.compile(r"[^\W\d][\w.]*", re.UNICODE)
_NUM = re.compile(r"\d+(\.\d+)?([eE][+-]?\d+)?")


def tokenize(text: str) -> list[Tok]:
    out: list[Tok] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c in "\"'«“":
            close = {"«": "»", "“": "”"}.get(c, c)
            j = text.find(close, i + 1)
            if j < 0:
                raise FormulaError("unclosed_text", i)
            out.append(Tok("str", text[i + 1 : j], i))
            i = j + 1
            continue
        if c in "[`":
            close = "]" if c == "[" else "`"
            j = text.find(close, i + 1)
            if j < 0:
                raise FormulaError("unclosed_column", i)
            name = text[i + 1 : j].strip()
            if not name:
                raise FormulaError("empty_column", i)
            out.append(Tok("col", name, i))
            i = j + 1
            continue
        m = _NUM.match(text, i)
        if m:
            out.append(Tok("num", float(m.group()), i))
            i = m.end()
            continue
        m = _NAME.match(text, i)
        if m:
            out.append(Tok("name", m.group(), i))
            i = m.end()
            continue
        if c == "(":
            out.append(Tok("lp", c, i))
        elif c == ")":
            out.append(Tok("rp", c, i))
        elif c in ";,":
            out.append(Tok("sep", c, i))
        else:
            op = next((o for o in _OPS if text.startswith(o, i)), None)
            if not op:
                raise FormulaError("unexpected_sign", i, sign=c)
            out.append(Tok("op", op, i))
            i += len(op)
            continue
        i += 1
    out.append(Tok("end", None, n))
    return out


# ----- syntax tree -------------------------------------------------------------------


@dataclass
class Node:
    kind: str  # num, str, bool, null, col, call, bin, not, neg
    value: Any
    pos: int
    args: list[Node] = field(default_factory=list)


WORDS_AND = {"et", "and"}
WORDS_OR = {"ou", "or"}
WORDS_NOT = {"non", "not"}
WORDS_TRUE = {"vrai", "true"}
WORDS_FALSE = {"faux", "false"}
WORDS_NULL = {"manquant", "missing", "na", "null"}
RESERVED = WORDS_AND | WORDS_OR | WORDS_NOT | WORDS_TRUE | WORDS_FALSE | WORDS_NULL


class Parser:
    def __init__(self, toks: list[Tok]):
        self.toks, self.i = toks, 0

    @property
    def tok(self) -> Tok:
        return self.toks[self.i]

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def word(self, words: set[str]) -> bool:
        t = self.tok
        if t.kind == "name" and t.value.lower() in words and self.toks[self.i + 1].kind != "lp":
            self.i += 1
            return True
        return False

    def op(self, *ops: str) -> str | None:
        if self.tok.kind == "op" and self.tok.value in ops:
            return self.next().value
        return None

    def parse(self) -> Node:
        if self.tok.kind == "end":
            raise FormulaError("empty", 0)
        node = self.or_()
        if self.tok.kind != "end":
            raise self.unexpected()
        return node

    def unexpected(self) -> FormulaError:
        t = self.tok
        if t.kind == "end":
            return FormulaError("unexpected_end", t.pos)
        return FormulaError("unexpected", t.pos, token=str(t.value if t.kind != "num" else _fmt(t.value)))

    def or_(self) -> Node:
        left = self.and_()
        while True:
            pos = self.tok.pos
            if self.word(WORDS_OR) or self.op("||"):
                left = Node("bin", "or", pos, [left, self.and_()])
            else:
                return left

    def and_(self) -> Node:
        left = self.not_()
        while True:
            pos = self.tok.pos
            if self.word(WORDS_AND) or self.op("&&"):
                left = Node("bin", "and", pos, [left, self.not_()])
            else:
                return left

    def not_(self) -> Node:
        pos = self.tok.pos
        if self.word(WORDS_NOT) or self.op("!"):
            return Node("not", None, pos, [self.not_()])
        return self.cmp()

    def cmp(self) -> Node:
        left = self.concat()
        pos = self.tok.pos
        op = self.op("=", "==", "!=", "<>", "<", "<=", ">", ">=")
        if not op:
            return left
        op = {"==": "=", "<>": "!="}.get(op, op)
        return Node("bin", op, pos, [left, self.concat()])

    def concat(self) -> Node:
        left = self.add()
        while True:
            pos = self.tok.pos
            if self.op("&"):
                left = Node("call", "concat", pos, [left, self.add()])
            else:
                return left

    def add(self) -> Node:
        left = self.mul()
        while True:
            pos = self.tok.pos
            op = self.op("+", "-")
            if not op:
                return left
            left = Node("bin", op, pos, [left, self.mul()])

    def mul(self) -> Node:
        left = self.unary()
        while True:
            pos = self.tok.pos
            op = self.op("*", "/")
            if not op:
                return left
            left = Node("bin", op, pos, [left, self.unary()])

    def unary(self) -> Node:
        pos = self.tok.pos
        if self.op("-"):
            return Node("neg", None, pos, [self.unary()])
        if self.op("+"):
            return self.unary()
        return self.power()

    def power(self) -> Node:
        base = self.atom()
        pos = self.tok.pos
        if self.op("^"):
            return Node("bin", "^", pos, [base, self.unary()])
        return base

    def atom(self) -> Node:
        t = self.tok
        if t.kind == "num":
            self.next()
            return Node("num", t.value, t.pos)
        if t.kind == "str":
            self.next()
            return Node("str", t.value, t.pos)
        if t.kind == "col":
            self.next()
            return Node("col", t.value, t.pos)
        if t.kind == "lp":
            self.next()
            node = self.or_()
            if self.tok.kind != "rp":
                raise FormulaError("missing_parenthesis", self.tok.pos)
            self.next()
            return node
        if t.kind == "name":
            self.next()
            if self.tok.kind == "lp":
                self.next()
                args: list[Node] = []
                if self.tok.kind != "rp":
                    while True:
                        args.append(self.or_())
                        if self.tok.kind == "sep":
                            self.next()
                            continue
                        break
                if self.tok.kind != "rp":
                    raise FormulaError("missing_parenthesis", self.tok.pos)
                self.next()
                return Node("call", t.value.lower(), t.pos, args)
            low = t.value.lower()
            if low in WORDS_TRUE:
                return Node("bool", True, t.pos)
            if low in WORDS_FALSE:
                return Node("bool", False, t.pos)
            if low in WORDS_NULL:
                return Node("null", None, t.pos)
            return Node("col", t.value, t.pos)
        raise self.unexpected()


# ----- functions ---------------------------------------------------------------------

# canonical name: (aliases: French, English, then other accepted spellings; min args; max args or None)
FUNCTIONS: dict[str, tuple[tuple[str, ...], int, int | None]] = {
    "if": (("si", "if"), 2, 3),
    "is_missing": (("est_manquant", "is_missing", "manque"), 1, 1),
    "not_missing": (("non_manquant", "not_missing", "present"), 1, 1),
    "if_missing": (("si_manquant", "if_missing", "remplacer_manquant"), 2, 2),
    "in": (("dans", "in", "parmi"), 2, None),
    "abs": (("abs",), 1, 1),
    "round": (("arrondi", "round"), 1, 2),
    "floor": (("plancher", "floor", "ent"), 1, 1),
    "ceiling": (("plafond", "ceiling", "ceil"), 1, 1),
    "sqrt": (("racine", "sqrt"), 1, 1),
    "log": (("log", "log", "ln"), 1, 1),
    "log10": (("log10",), 1, 1),
    "exp": (("exp",), 1, 1),
    "sum": (("somme", "sum"), 1, None),
    "mean": (("moyenne", "mean"), 1, None),
    "min": (("min",), 1, None),
    "max": (("max",), 1, None),
    "count": (("compter", "count"), 2, None),
    "count_missing": (("nb_manquants", "count_missing"), 1, None),
    "col_mean": (("moyenne_colonne", "col_mean"), 1, 1),
    "col_sum": (("somme_colonne", "col_sum"), 1, 1),
    "col_min": (("min_colonne", "col_min"), 1, 1),
    "col_max": (("max_colonne", "col_max"), 1, 1),
    "col_sd": (("ecart_type_colonne", "col_sd"), 1, 1),
    "lower": (("minuscule", "lower"), 1, 1),
    "upper": (("majuscule", "upper"), 1, 1),
    "trim": (("nettoyer", "trim"), 1, 1),
    "length": (("longueur", "length"), 1, 1),
    "contains": (("contient", "contains"), 2, 2),
    "starts_with": (("commence_par", "starts_with"), 2, 2),
    "ends_with": (("finit_par", "ends_with"), 2, 2),
    "concat": (("concat", "concat", "concatener"), 1, None),
    "substr": (("extraire", "substr"), 2, 3),
    "replace": (("remplacer", "replace"), 3, 3),
    "number": (("nombre", "number"), 1, 1),
    "text": (("texte", "text"), 1, 1),
    "date": (("date",), 1, 1),
    "year": (("annee", "year", "année"), 1, 1),
    "month": (("mois", "month"), 1, 1),
    "day": (("jour", "day"), 1, 1),
    "days_between": (("jours_entre", "days_between"), 2, 2),
    "minutes_between": (("minutes_entre", "minutes_between"), 2, 2),
    "age": (("age", "age", "âge"), 1, 2),
    "today": (("aujourdhui", "today"), 0, 0),
}
ALIASES = {a: name for name, (aliases, _, _) in FUNCTIONS.items() for a in aliases}


def display_name(aliases: tuple[str, ...], lang: str) -> str:
    """Name shown in the formula editor: the French or the English alias."""
    return aliases[0] if lang == "fr" or len(aliases) == 1 else aliases[1]


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


# ----- typed compilation -------------------------------------------------------------

# Types: num, text, bool, date, col (a column: text that may hold numbers), null.
Typed = tuple[pl.Expr, str]


class Compiler:
    def __init__(self, columns: list[str]):
        self.columns = columns
        self.lower = {c.lower(): c for c in columns}
        self.used: list[str] = []

    # conversions
    def num(self, t: Typed, pos: int) -> pl.Expr:
        e, k = t
        if k == "num":
            return e
        if k in ("col", "text"):
            return e.cast(pl.Utf8).str.strip_chars().str.replace(",", ".", literal=True).cast(pl.Float64, strict=False)
        if k == "bool":
            return e.cast(pl.Float64)
        if k == "null":
            return pl.lit(None, dtype=pl.Float64)
        raise FormulaError("date_in_calculation", pos)

    def text(self, t: Typed) -> pl.Expr:
        e, k = t
        if k == "num":
            return _as_text(e)
        if k == "bool":
            return pl.when(e).then(pl.lit("1")).when(~e).then(pl.lit("0")).otherwise(pl.lit(None, dtype=pl.Utf8))
        if k == "date":
            return e.dt.strftime("%Y-%m-%d")
        if k == "null":
            return pl.lit(None, dtype=pl.Utf8)
        return e.cast(pl.Utf8)

    def boolean(self, t: Typed, pos: int) -> pl.Expr:
        e, k = t
        if k == "bool":
            return e
        if k == "null":
            return pl.lit(None, dtype=pl.Boolean)
        if k in ("num", "col"):
            return self.num(t, pos) != 0
        raise FormulaError("not_a_condition", pos)

    def date(self, t: Typed, pos: int) -> pl.Expr:
        e, k = t
        if k == "date":
            return e
        if k in ("col", "text"):
            return datetime_expr(e)
        if k == "null":
            return pl.lit(None, dtype=pl.Datetime("us"))
        if k == "num":  # an Excel serial number
            return datetime_expr(self.text(t))
        raise FormulaError("not_a_date", pos)

    def unify(self, items: list[Typed]) -> tuple[list[pl.Expr], str]:
        """Common type for the branches of si() and si_manquant()."""
        kinds = {k for _, k in items} - {"null"}
        if not kinds:
            return [e for e, _ in items], "null"
        if kinds <= {"num", "bool"} or (kinds <= {"num", "bool", "col"} and "num" in kinds):
            return [self.num(t, 0) for t in items], "num"
        if kinds == {"bool"}:
            return [self.boolean(t, 0) for t in items], "bool"
        if kinds == {"date"}:
            return [self.date(t, 0) for t in items], "date"
        return [self.text(t) for t in items], "text" if kinds != {"col"} else "col"

    # nodes
    def compile(self, n: Node) -> Typed:
        k = n.kind
        if k == "num":
            return pl.lit(float(n.value)), "num"
        if k == "str":
            return pl.lit(n.value, dtype=pl.Utf8), "text"
        if k == "bool":
            return pl.lit(n.value), "bool"
        if k == "null":
            return pl.lit(None), "null"
        if k == "col":
            return self.column(n)
        if k == "neg":
            return -self.num(self.compile(n.args[0]), n.pos), "num"
        if k == "not":
            return ~self.boolean(self.compile(n.args[0]), n.args[0].pos), "bool"
        if k == "bin":
            return self.binary(n)
        return self.call(n)

    def column(self, n: Node) -> Typed:
        name = n.value
        if name not in self.columns:
            low = self.lower.get(name.lower())
            if low is None:
                close = difflib.get_close_matches(name, self.columns, n=1, cutoff=0.6)
                raise FormulaError("unknown_column", n.pos, name=name, **({"suggestion": close[0]} if close else {}))
            name = low
        if name not in self.used:
            self.used.append(name)
        return pl.col(name), "col"

    def binary(self, n: Node) -> Typed:
        op = n.value
        a, b = self.compile(n.args[0]), self.compile(n.args[1])
        if op in ("and", "or"):
            x, y = self.boolean(a, n.args[0].pos), self.boolean(b, n.args[1].pos)
            return (x & y if op == "and" else x | y), "bool"
        if op in ("+", "-", "*", "/", "^"):
            if "text" in (a[1], b[1]) and op == "+":
                raise FormulaError("text_in_calculation", n.pos, hint="concat")
            for t, arg in ((a, n.args[0]), (b, n.args[1])):
                if t[1] == "text":
                    raise FormulaError("text_in_calculation", arg.pos)
            if op == "-" and a[1] == "date" and b[1] == "date":
                return (a[0] - b[0]).dt.total_seconds() / 86400, "num"
            x, y = self.num(a, n.args[0].pos), self.num(b, n.args[1].pos)
            if op == "+":
                return x + y, "num"
            if op == "-":
                return x - y, "num"
            if op == "*":
                return x * y, "num"
            if op == "/":
                return pl.when(y != 0).then(x / y), "num"
            return x.pow(y), "num"
        # comparisons
        if "null" in (a[1], b[1]):
            other = b if a[1] == "null" else a
            if op == "=":
                return other[0].is_null(), "bool"
            if op == "!=":
                return other[0].is_not_null(), "bool"
            raise FormulaError("compare_missing", n.pos)
        kinds = {a[1], b[1]}
        if kinds & {"num", "bool"}:
            x, y = self.num(a, n.args[0].pos), self.num(b, n.args[1].pos)
        elif "date" in kinds:
            x, y = self.date(a, n.args[0].pos), self.date(b, n.args[1].pos)
        elif op in ("=", "!="):
            x, y = self.text(a), self.text(b)
        elif "text" in kinds:
            raise FormulaError("compare_text", n.pos)
        else:  # two columns ordered: as numbers
            x, y = self.num(a, n.args[0].pos), self.num(b, n.args[1].pos)
        expr = {"=": x == y, "!=": x != y, "<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]
        return expr, "bool"

    def call(self, n: Node) -> Typed:
        name = ALIASES.get(n.value)
        if name is None:
            close = difflib.get_close_matches(n.value, list(ALIASES), n=1, cutoff=0.6)
            raise FormulaError("unknown_function", n.pos, name=n.value, **({"suggestion": close[0]} if close else {}))
        _, lo, hi = FUNCTIONS[name]
        if len(n.args) < lo or (hi is not None and len(n.args) > hi):
            raise FormulaError("arguments", n.pos, name=n.value, min=lo, max=hi if hi is not None else "n")
        args = [self.compile(a) for a in n.args]
        pos = [a.pos for a in n.args]

        def num(i: int) -> pl.Expr:
            return self.num(args[i], pos[i])

        def txt(i: int) -> pl.Expr:
            return self.text(args[i])

        def literal(i: int, kind: str) -> Any:
            node = n.args[i]
            if kind == "num" and node.kind == "num":
                return node.value
            if kind == "str" and node.kind == "str":
                return node.value
            raise FormulaError("literal_expected", node.pos, name=n.value, expected=kind)

        if name == "if":
            cond = self.boolean(args[0], pos[0]).fill_null(False)
            branches = args[1:] if len(args) == 3 else [args[1], (pl.lit(None), "null")]
            (yes, no), kind = self.unify(branches)
            return pl.when(cond).then(yes).otherwise(no), kind
        if name == "is_missing":
            return args[0][0].is_null(), "bool"
        if name == "not_missing":
            return args[0][0].is_not_null(), "bool"
        if name == "if_missing":
            (x, y), kind = self.unify(args)
            return pl.coalesce(x, y), kind
        if name == "in":
            values = n.args[1:]
            if any(v.kind not in ("num", "str") for v in values):
                raise FormulaError("literal_expected", values[0].pos, name=n.value, expected="values")
            if all(v.kind == "num" for v in values):
                return num(0).is_in([float(v.value) for v in values]), "bool"
            return txt(0).is_in([v.value if v.kind == "str" else _fmt(v.value) for v in values]), "bool"
        if name in ("abs", "floor", "ceiling", "sqrt", "log", "log10", "exp"):
            x = num(0)
            if name == "abs":
                return x.abs(), "num"
            if name == "floor":
                return x.floor(), "num"
            if name == "ceiling":
                return x.ceil(), "num"
            if name == "sqrt":
                return pl.when(x >= 0).then(x.sqrt()), "num"
            if name == "log":
                return pl.when(x > 0).then(x.log()), "num"
            if name == "log10":
                return pl.when(x > 0).then(x.log10()), "num"
            return x.exp(), "num"
        if name == "round":
            digits = int(literal(1, "num")) if len(args) == 2 else 0
            return num(0).round(digits), "num"
        if name in ("sum", "mean", "min", "max"):
            xs = [num(i) for i in range(len(args))]
            if name == "sum":
                return pl.when(pl.any_horizontal([x.is_not_null() for x in xs])).then(pl.sum_horizontal(xs)), "num"
            if name == "mean":
                return pl.mean_horizontal(xs), "num"
            return (pl.min_horizontal(xs) if name == "min" else pl.max_horizontal(xs)), "num"
        if name == "count":
            target = args[0]
            hits = []
            for i in range(1, len(args)):
                if target[1] == "num":
                    hits.append((num(i) == target[0]).fill_null(False).cast(pl.Int64))
                else:
                    hits.append((txt(i) == self.text(target)).fill_null(False).cast(pl.Int64))
            return pl.sum_horizontal(hits).cast(pl.Float64), "num"
        if name == "count_missing":
            return pl.sum_horizontal([a[0].is_null().cast(pl.Int64) for a in args]).cast(pl.Float64), "num"
        if name.startswith("col_"):
            x = num(0)
            agg = {"col_mean": x.mean(), "col_sum": x.sum(), "col_min": x.min(), "col_max": x.max(), "col_sd": x.std()}
            return agg[name], "num"
        if name == "lower":
            return txt(0).str.to_lowercase(), "text"
        if name == "upper":
            return txt(0).str.to_uppercase(), "text"
        if name == "trim":
            return txt(0).str.strip_chars().str.replace_all(r"\s+", " "), "text"
        if name == "length":
            return txt(0).str.len_chars().cast(pl.Float64), "num"
        if name in ("contains", "starts_with", "ends_with"):
            pattern = literal(1, "str")
            x = txt(0)
            if name == "contains":
                return x.str.contains(pattern, literal=True), "bool"
            return (x.str.starts_with(pattern) if name == "starts_with" else x.str.ends_with(pattern)), "bool"
        if name == "concat":
            return pl.concat_str([txt(i) for i in range(len(args))], ignore_nulls=True), "text"
        if name == "substr":
            start = int(literal(1, "num"))
            length = int(literal(2, "num")) if len(args) == 3 else None
            return txt(0).str.slice(max(start - 1, 0), length), "text"
        if name == "replace":
            return txt(0).str.replace_all(literal(1, "str"), literal(2, "str"), literal=True), "text"
        if name == "number":
            return num(0), "num"
        if name == "text":
            return txt(0), "text"
        if name == "date":
            return self.date(args[0], pos[0]), "date"
        if name in ("year", "month", "day"):
            d = self.date(args[0], pos[0])
            part = {"year": d.dt.year(), "month": d.dt.month(), "day": d.dt.day()}[name]
            return part.cast(pl.Float64), "num"
        if name in ("days_between", "minutes_between"):
            a, b = self.date(args[0], pos[0]), self.date(args[1], pos[1])
            seconds = (b - a).dt.total_seconds()
            return (seconds / 86400 if name == "days_between" else seconds / 60), "num"
        if name == "age":
            birth = self.date(args[0], pos[0])
            ref = self.date(args[1], pos[1]) if len(args) == 2 else pl.lit(_date.today()).cast(pl.Datetime("us"))
            years = ref.dt.year() - birth.dt.year()
            before = (ref.dt.month() < birth.dt.month()) | (
                (ref.dt.month() == birth.dt.month()) & (ref.dt.day() < birth.dt.day())
            )
            return (years - before.cast(pl.Int32)).cast(pl.Float64), "num"
        if name == "today":
            return pl.lit(_date.today()).cast(pl.Datetime("us")), "date"
        raise FormulaError("unknown_function", n.pos, name=n.value)  # pragma: no cover


# ----- public API --------------------------------------------------------------------


def parse(text: Any) -> Node:
    if not isinstance(text, str) or not text.strip():
        raise FormulaError("empty", 0)
    if len(text) > MAX_LENGTH:
        raise FormulaError("too_long", MAX_LENGTH)
    return Parser(tokenize(text)).parse()


def compile_(text: str, columns: list[str]) -> tuple[pl.Expr, str, list[str]]:
    """The expression, its type (num, text, bool, date, col, null) and the columns it reads."""
    c = Compiler(columns)
    expr, kind = c.compile(parse(text))
    return expr, kind, c.used


def value_expr(text: str, columns: list[str]) -> pl.Expr:
    """The formula as a text column, as everywhere in the cleaned table (conditions give 1 or 0)."""
    expr, kind, _ = compile_(text, columns)
    c = Compiler(columns)
    return c.text((expr, kind))


def condition_expr(text: str, columns: list[str]) -> pl.Expr:
    """The formula as a condition: true, or false when false or missing."""
    expr, kind, _ = compile_(text, columns)
    if kind not in ("bool", "num", "col"):
        raise FormulaError("not_a_condition", 0)
    c = Compiler(columns)
    return c.boolean((expr, kind), 0).fill_null(False)


def check(text: str, columns: list[str], condition: bool = False) -> dict[str, Any]:
    """Validate a formula. Returns its type and the columns it reads; raises FormulaError otherwise."""
    expr, kind, used = compile_(text, columns)
    if condition and kind not in ("bool", "num", "col"):
        raise FormulaError("not_a_condition", 0)
    # Polars checks the types of the whole expression on an empty table.
    try:
        pl.DataFrame({c: pl.Series([], dtype=pl.Utf8) for c in columns}).select(expr.alias("x"))
    except pl.exceptions.PolarsError as exc:
        raise FormulaError("invalid", 0, detail=str(exc).splitlines()[0][:200]) from None
    return {"type": kind, "columns": used}


def preview(df: pl.DataFrame, text: str, condition: bool = False, limit: int = 8) -> dict[str, Any]:
    """What the formula gives on the data: a few values, and counts."""
    info = check(text, df.columns, condition)
    if condition:
        mask = df.with_columns(condition_expr(text, df.columns).alias("__x"))["__x"]
        true = int(mask.sum())
        return {**info, "rows": df.height, "true": true, "false": df.height - true}
    values = df.with_columns(value_expr(text, df.columns).alias("__x"))["__x"]
    sample = []
    shown = info["columns"][:4]
    for i in range(min(limit, df.height)):
        sample.append({"inputs": {c: df[c][i] for c in shown}, "value": values[i]})
    return {
        **info,
        "rows": df.height,
        "missing": int(values.is_null().sum()),
        "distinct": int(values.n_unique()),
        "sample": sample,
    }
