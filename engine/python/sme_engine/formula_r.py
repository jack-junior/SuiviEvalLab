"""A formula (formula.py) written as R code, for the journal exported as an R script.

The same syntax tree is translated with the same types and the same handling of
missing values, so that the script gives the table the application gives.
"""

from __future__ import annotations

from typing import Any

from .formula import ALIASES, FormulaError, Node, parse

# Helpers the translated formulas use; added to the script when a formula is present.
HELPERS = r"""sme_bool_text <- function(b) ifelse(is.na(b), NA_character_, ifelse(b, "1", "0"))
sme_if <- function(cond, yes, no) {
  n <- max(length(cond), length(yes), length(no))
  cond <- rep_len(cond, n); yes <- rep_len(yes, n); no <- rep_len(no, n)
  out <- no
  i <- !is.na(cond) & cond
  out[i] <- yes[i]
  out
}
sme_rsum <- function(...) {
  m <- cbind(...)
  out <- rowSums(m, na.rm = TRUE)
  out[rowSums(!is.na(m)) == 0] <- NA
  out
}
sme_rmean <- function(...) { out <- rowMeans(cbind(...), na.rm = TRUE); out[is.nan(out)] <- NA; out }
sme_cat <- function(...) {
  parts <- lapply(list(...), function(x) ifelse(is.na(x), "", x))
  do.call(paste0, parts)
}
sme_in <- function(x, values) ifelse(is.na(x), NA, x %in% values)
sme_age <- function(b, r) {
  years <- as.numeric(format(r, "%Y")) - as.numeric(format(b, "%Y"))
  years - (format(r, "%m%d") < format(b, "%m%d"))
}
"""


def _q(value: Any) -> str:
    s = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'


def _num_lit(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else repr(float(x))


R = tuple[str, str]  # code, type


class RCompiler:
    def __init__(self, columns: list[str], frame: str = "d"):
        self.columns = columns
        self.lower = {c.lower(): c for c in columns}
        self.frame = frame

    def num(self, t: R) -> str:
        code, k = t
        if k == "num":
            return code
        if k in ("col", "text"):
            return f"sme_num(trimws({code}))"
        if k == "bool":
            return f"as.numeric({code})"
        if k == "null":
            return "NA_real_"
        raise FormulaError("date_in_calculation", 0)

    def text(self, t: R) -> str:
        code, k = t
        if k == "num":
            return f"sme_text({code})"
        if k == "bool":
            return f"sme_bool_text({code})"
        if k == "date":
            return f'format({code}, "%Y-%m-%d")'
        if k == "null":
            return "NA_character_"
        return code

    def boolean(self, t: R) -> str:
        code, k = t
        if k == "bool":
            return code
        if k == "null":
            return "NA"
        return f"({self.num(t)} != 0)"

    def date(self, t: R) -> str:
        code, k = t
        if k == "date":
            return code
        if k in ("col", "text"):
            return f"sme_dt({code})"
        if k == "null":
            return 'as.POSIXct(NA, tz = "UTC")'
        return f"sme_dt({self.text(t)})"

    def unify(self, items: list[R]) -> tuple[list[str], str]:
        kinds = {k for _, k in items} - {"null"}
        if not kinds:
            return ["NA" for _ in items], "null"
        if kinds <= {"num", "bool"} or (kinds <= {"num", "bool", "col"} and "num" in kinds):
            return [self.num(t) for t in items], "num"
        if kinds == {"bool"}:
            return [self.boolean(t) for t in items], "bool"
        if kinds == {"date"}:
            return [self.date(t) for t in items], "date"
        return [self.text(t) for t in items], "text" if kinds != {"col"} else "col"

    def compile(self, n: Node) -> R:
        k = n.kind
        if k == "num":
            return _num_lit(n.value), "num"
        if k == "str":
            return _q(n.value), "text"
        if k == "bool":
            return ("TRUE" if n.value else "FALSE"), "bool"
        if k == "null":
            return "NA", "null"
        if k == "col":
            name = n.value if n.value in self.columns else self.lower.get(n.value.lower(), n.value)
            return f"{self.frame}[[{_q(name)}]]", "col"
        if k == "neg":
            return f"(-{self.num(self.compile(n.args[0]))})", "num"
        if k == "not":
            return f"(!{self.boolean(self.compile(n.args[0]))})", "bool"
        if k == "bin":
            return self.binary(n)
        return self.call(n)

    def binary(self, n: Node) -> R:
        op = n.value
        a, b = self.compile(n.args[0]), self.compile(n.args[1])
        if op in ("and", "or"):
            return f"({self.boolean(a)} {'&' if op == 'and' else '|'} {self.boolean(b)})", "bool"
        if op in ("+", "-", "*", "/", "^"):
            if op == "-" and a[1] == "date" and b[1] == "date":
                return f'as.numeric(difftime({a[0]}, {b[0]}, units = "days"))', "num"
            x, y = self.num(a), self.num(b)
            if op == "/":
                return f"ifelse({y} != 0, {x} / {y}, NA_real_)", "num"
            return f"({x} {op} {y})", "num"
        if "null" in (a[1], b[1]):
            other = b if a[1] == "null" else a
            return (f"is.na({other[0]})" if op == "=" else f"!is.na({other[0]})"), "bool"
        kinds = {a[1], b[1]}
        if kinds & {"num", "bool"}:
            x, y = self.num(a), self.num(b)
        elif "date" in kinds:
            x, y = self.date(a), self.date(b)
        elif op in ("=", "!="):
            x, y = self.text(a), self.text(b)
        else:
            x, y = self.num(a), self.num(b)
        rop = {"=": "==", "!=": "!="}.get(op, op)
        return f"({x} {rop} {y})", "bool"

    def call(self, n: Node) -> R:
        name = ALIASES[n.value]
        args = [self.compile(a) for a in n.args]

        def num(i: int) -> str:
            return self.num(args[i])

        def txt(i: int) -> str:
            return self.text(args[i])

        if name == "if":
            branches = args[1:] if len(args) == 3 else [args[1], ("NA", "null")]
            (yes, no), kind = self.unify(branches)
            return f"sme_if({self.boolean(args[0])}, {yes}, {no})", kind
        if name == "is_missing":
            return f"is.na({args[0][0]})", "bool"
        if name == "not_missing":
            return f"!is.na({args[0][0]})", "bool"
        if name == "if_missing":
            (x, y), kind = self.unify(args)
            return f"ifelse(is.na({x}), {y}, {x})", kind
        if name == "in":
            values = n.args[1:]
            if all(v.kind == "num" for v in values):
                return f"sme_in({num(0)}, c({', '.join(_num_lit(v.value) for v in values)}))", "bool"
            lits = ", ".join(_q(v.value if v.kind == "str" else _num_lit(v.value)) for v in values)
            return f"sme_in({txt(0)}, c({lits}))", "bool"
        simple = {"abs": "abs", "floor": "floor", "ceiling": "ceiling", "exp": "exp"}
        if name in simple:
            return f"{simple[name]}({num(0)})", "num"
        if name == "sqrt":
            return f"ifelse({num(0)} >= 0, suppressWarnings(sqrt({num(0)})), NA_real_)", "num"
        if name in ("log", "log10"):
            return f"ifelse({num(0)} > 0, suppressWarnings({name}({num(0)})), NA_real_)", "num"
        if name == "round":
            digits = int(n.args[1].value) if len(args) == 2 else 0
            return f"round({num(0)}, {digits})", "num"
        if name in ("sum", "mean", "min", "max"):
            xs = ", ".join(num(i) for i in range(len(args)))
            fn = {"sum": "sme_rsum", "mean": "sme_rmean"}.get(name)
            if fn:
                return f"{fn}({xs})", "num"
            return f"suppressWarnings({'pmin' if name == 'min' else 'pmax'}({xs}, na.rm = TRUE))", "num"
        if name == "count":
            target = args[0]
            if target[1] == "num":
                hits = [f"(!is.na({num(i)}) & {num(i)} == {target[0]})" for i in range(1, len(args))]
            else:
                hits = [f"(!is.na({txt(i)}) & {txt(i)} == {self.text(target)})" for i in range(1, len(args))]
            return "(" + " + ".join(hits) + ")", "num"
        if name == "count_missing":
            return "(" + " + ".join(f"is.na({a[0]})" for a in args) + ")", "num"
        if name.startswith("col_"):
            fn = {"col_mean": "mean", "col_sum": "sum", "col_min": "min", "col_max": "max", "col_sd": "sd"}[name]
            return f"{fn}({num(0)}, na.rm = TRUE)", "num"
        if name == "lower":
            return f"tolower({txt(0)})", "text"
        if name == "upper":
            return f"toupper({txt(0)})", "text"
        if name == "trim":
            return f'gsub("\\\\s+", " ", trimws({txt(0)}))', "text"
        if name == "length":
            return f"as.numeric(nchar({txt(0)}))", "num"
        if name == "contains":
            return f"grepl({_q(n.args[1].value)}, {txt(0)}, fixed = TRUE) & !is.na({txt(0)})", "bool"
        if name == "starts_with":
            return f"startsWith({txt(0)}, {_q(n.args[1].value)})", "bool"
        if name == "ends_with":
            return f"endsWith({txt(0)}, {_q(n.args[1].value)})", "bool"
        if name == "concat":
            return f"sme_cat({', '.join(txt(i) for i in range(len(args)))})", "text"
        if name == "substr":
            start = int(n.args[1].value)
            stop = f"{start} + {int(n.args[2].value)} - 1" if len(args) == 3 else "100000L"
            return f"substr({txt(0)}, {max(start, 1)}, {stop})", "text"
        if name == "replace":
            return f"gsub({_q(n.args[1].value)}, {_q(n.args[2].value)}, {txt(0)}, fixed = TRUE)", "text"
        if name == "number":
            return num(0), "num"
        if name == "text":
            return txt(0), "text"
        if name == "date":
            return self.date(args[0]), "date"
        if name in ("year", "month", "day"):
            part = {"year": "%Y", "month": "%m", "day": "%d"}[name]
            return f'as.numeric(format({self.date(args[0])}, "{part}"))', "num"
        if name in ("days_between", "minutes_between"):
            units = "days" if name == "days_between" else "mins"
            return f'as.numeric(difftime({self.date(args[1])}, {self.date(args[0])}, units = "{units}"))', "num"
        if name == "age":
            ref = self.date(args[1]) if len(args) == 2 else 'as.POSIXct(Sys.Date(), tz = "UTC")'
            return f"sme_age({self.date(args[0])}, {ref})", "num"
        if name == "today":
            return 'as.POSIXct(Sys.Date(), tz = "UTC")', "date"
        raise FormulaError("unknown_function", n.pos, name=n.value)


def value(text: str, columns: list[str]) -> str:
    c = RCompiler(columns)
    return c.text(c.compile(parse(text)))


def condition(text: str, columns: list[str]) -> str:
    c = RCompiler(columns)
    b = c.boolean(c.compile(parse(text)))
    return f"(!is.na({b}) & {b})"
