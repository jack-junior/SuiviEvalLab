"""The cleaning journal written as an R script.

The script reads the raw data (exported next to it as CSV, every column as text),
turns the missing-value codes into NA and applies the enabled rules in order, with
base R only. It gives the same table as the application, so a reviewer can check
or rerun the cleaning without the application.
"""

from __future__ import annotations

from typing import Any

TEXT = {
    "fr": {
        "head": "Nettoyage du fichier {name}, tel que défini dans SuiviEvalLab {version}.",
        "read": "Données brutes, toutes les colonnes en texte",
        "na": "Codes de valeur manquante",
        "rule": "Règle {n}",
        "off": "Règle {n} désactivée, non appliquée",
        "done": "Table nettoyée",
        "derived": (
            "Ce fichier est construit à partir d'autres fichiers (fusion ou empilement) : "
            "les données brutes exportées sont déjà la table construite."
        ),
    },
    "en": {
        "head": "Cleaning of the file {name}, as defined in SuiviEvalLab {version}.",
        "read": "Raw data, every column as text",
        "na": "Missing-value codes",
        "rule": "Rule {n}",
        "off": "Rule {n} disabled, not applied",
        "done": "Cleaned table",
        "derived": (
            "This file is built from other files (merge or stacking): the exported raw data "
            "are already the built table."
        ),
    },
}

HELPERS = r"""sme_num <- function(x) suppressWarnings(as.numeric(sub(",", ".", x, fixed = TRUE)))
sme_text <- function(x) {
  x <- round(as.numeric(x), 6)
  vapply(x, function(v) {
    if (is.na(v) || is.infinite(v)) NA_character_
    else format(v, scientific = FALSE, digits = 15, drop0trailing = TRUE, trim = TRUE)
  }, "", USE.NAMES = FALSE)
}
sme_dt <- function(x) {
  x <- trimws(x)
  h <- sub("T", " ", substr(x, 1, 19), fixed = TRUE)
  out <- as.POSIXct(h, format = "%Y-%m-%d %H:%M:%S", tz = "UTC")
  i <- is.na(out)
  out[i] <- as.POSIXct(substr(x[i], 1, 10), format = "%Y-%m-%d", tz = "UTC")
  i <- is.na(out)
  out[i] <- as.POSIXct(substr(x[i], 1, 10), format = "%d/%m/%Y", tz = "UTC")
  s <- suppressWarnings(as.numeric(x))
  i <- is.na(out) & !is.na(s) & s > 20000 & s < 80000
  out[i] <- as.POSIXct("1899-12-30", tz = "UTC") + floor(s[i]) * 86400
  out
}
sme_rows <- function(f) {
  m <- sapply(f, identity)
  if (is.null(dim(m))) m <- matrix(m, nrow = 1)
  m
}
"""


def q(value: Any) -> str:
    """An R string literal."""
    s = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'


def vec(values: list[Any]) -> str:
    return "c(" + ", ".join("NA" if v is None else q(v) for v in values) + ")"


def num(x: float) -> str:
    return repr(float(x))


def col(name: str) -> str:
    return f"d[[{q(name)}]]"


def _condition(c: dict[str, Any]) -> str:
    x, op = col(c["column"]), c["op"]
    if op == "missing":
        return f"is.na({x})"
    if op == "present":
        return f"!is.na({x})"
    if op == "eq":
        return f"(!is.na({x}) & {x} == {q(c['value'])})"
    if op == "ne":
        return f"(is.na({x}) | {x} != {q(c['value'])})"
    if op == "in":
        return f"({x} %in% {vec(c['values'])})"
    if op == "not_in":
        return f"!({x} %in% {vec(c['values'])})"
    sign = {"lt": "<", "le": "<=", "gt": ">", "ge": ">="}[op]
    return f"(!is.na(sme_num({x})) & sme_num({x}) {sign} {num(c['value'])})"


def _mask(rule: dict[str, Any]) -> str:
    joiner = " | " if rule.get("combine") == "any" else " & "
    return joiner.join(_condition(c) for c in rule["conditions"])


def _rule(rule: dict[str, Any]) -> list[str]:
    kind = rule["kind"]
    if kind == "duplicates":
        return [f"d <- d[!duplicated(d[{vec(rule['columns'])}]), , drop = FALSE]"]
    if kind == "recode":
        to = "NA" if rule["to"] is None else q(rule["to"])
        from_ = [v for v in rule["from"] if v is not None]
        return [f"{col(rule['column'])}[{col(rule['column'])} %in% {vec(from_)}] <- {to}"]
    if kind == "range":
        x = f"sme_num({col(rule['column'])})"
        parts = []
        if rule["min"] is not None:
            parts.append(f"x < {num(rule['min'])}")
        if rule["max"] is not None:
            parts.append(f"x > {num(rule['max'])}")
        return [f"x <- {x}", f"{col(rule['column'])}[!is.na(x) & ({' | '.join(parts)})] <- NA"]
    if kind == "exclude":
        values = [v for v in rule["values"] if v is not None]
        drop = f"{col(rule['column'])} %in% {vec(values)}"
        if None in rule["values"]:
            drop += f" | is.na({col(rule['column'])})"
        return [f"d <- d[!({drop}), , drop = FALSE]"]
    if kind == "compute":
        cols = rule["columns"]
        nums = f"sme_rows(lapply({vec(cols)}, function(c) sme_num(d[[c]])))"
        op, target = rule["op"], col(rule["target"])
        if op == "sum":
            expr = "ifelse(rowSums(!is.na(m)) > 0, rowSums(m, na.rm = TRUE), NA)"
        elif op == "mean":
            expr = "rowMeans(m, na.rm = TRUE)"
        elif op == "min":
            expr = "suppressWarnings(apply(m, 1, function(r) if (all(is.na(r))) NA else min(r, na.rm = TRUE)))"
        elif op == "max":
            expr = "suppressWarnings(apply(m, 1, function(r) if (all(is.na(r))) NA else max(r, na.rm = TRUE)))"
        elif op == "difference":
            expr = "m[, 1] - m[, 2]"
        elif op == "ratio":
            expr = "ifelse(!is.na(m[, 2]) & m[, 2] != 0, m[, 1] / m[, 2], NA)"
        else:
            hits = f"sme_rows(lapply({vec(cols)}, function(c) d[[c]] %in% {vec(rule['values'])}))"
            return [f"{target} <- sme_text(rowSums({hits}))"]
        return [f"m <- {nums}", f"{target} <- sme_text({expr})"]
    if kind == "classes":
        lines = [f"x <- sme_num({col(rule['column'])})", "out <- rep(NA_character_, nrow(d))"]
        for c in rule["classes"]:
            cond = ["!is.na(x)"]
            if c["from"] is not None:
                cond.append(f"x >= {num(c['from'])}")
            if c["to"] is not None:
                cond.append(f"x < {num(c['to'])}")
            lines.append(f"out[is.na(out) & {' & '.join(cond)}] <- {q(c['label'])}")
        lines.append(f"{col(rule['target'])} <- out")
        return lines
    if kind == "conditional":
        target = col(rule["target"])
        value = "NA" if rule["value"] is None else q(rule["value"])
        lines = [f"hit <- {_mask(rule)}"]
        lines.append(f"if (is.null({target})) {target} <- NA_character_")
        lines.append(f"{target}[hit] <- {value}")
        return lines
    if kind == "check":
        lines = [f"hit <- {_mask(rule)}"]
        if rule["action"] == "flag":
            lines.append(f'{col(rule["target"])} <- ifelse(hit, "1", "0")')
        elif rule["action"] == "exclude":
            lines.append("d <- d[!hit, , drop = FALSE]")
        else:
            lines.append(f"{col(rule['column'])}[hit] <- NA")
        return lines
    if kind == "text":
        x = col(rule["column"])
        lines = []
        for op in rule["ops"]:
            expr = {
                "trim": f"trimws({x})",
                "squeeze": f'gsub("\\\\s+", " ", {x}, perl = TRUE)',
                "lower": f"tolower({x})",
                "upper": f"toupper({x})",
                "title": f'gsub("(^|[^[:alnum:]])([[:alpha:]])", "\\\\1\\\\U\\\\2", tolower({x}), perl = TRUE)',
                "accents": f'iconv({x}, to = "ASCII//TRANSLIT")',
            }[op]
            lines.append(f"{x} <- {expr}")
        return lines
    if kind == "date":
        start = f"sme_dt({col(rule['column'])})"
        target = col(rule["target"])
        mode = rule["mode"]
        if mode == "duration":
            return [f'{target} <- sme_text(as.numeric(difftime(sme_dt({col(rule["end"])}), {start}, units = "mins")))']
        if mode in ("year", "month"):
            part = "%Y" if mode == "year" else "%m"
            return [f'{target} <- sme_text(as.numeric(format({start}, "{part}")))']
        ref = (
            f"sme_dt({col(rule['ref_column'])})"
            if rule.get("ref_column")
            else f'as.POSIXct({q(rule["ref_date"])}, tz = "UTC")'
        )
        return [
            f"b <- {start}",
            f"r <- {ref}",
            'years <- as.numeric(format(r, "%Y")) - as.numeric(format(b, "%Y"))',
            'before <- format(r, "%m%d") < format(b, "%m%d")',
            f"{target} <- sme_text(years - before)",
        ]
    return [f"# {kind}"]


def journal(
    name: str, raw_file: str, na_values: list[str], rules: list[dict[str, Any]], lang: str, version: str, derived: bool
) -> str:
    t = TEXT[lang]
    out = [f"# {t['head'].format(name=name, version=version)}"]
    if derived:
        out.append(f"# {t['derived']}")
    out += ["", HELPERS.strip(), "", f"# {t['read']}"]
    out.append(
        f'd <- read.csv({q(raw_file)}, colClasses = "character", na.strings = "", '
        'check.names = FALSE, encoding = "UTF-8", fileEncoding = "UTF-8-BOM")'
    )
    if na_values:
        out += ["", f"# {t['na']}", f"d[] <- lapply(d, function(x) {{ x[x %in% {vec(na_values)}] <- NA; x }})"]
    for i, rule in enumerate(rules, start=1):
        out.append("")
        if not rule.get("enabled", True):
            out.append(f"# {t['off'].format(n=i)}")
            continue
        note = (
            f" : {rule['note']}"
            if rule.get("note") and lang == "fr"
            else f": {rule['note']}"
            if rule.get("note")
            else ""
        )
        out.append(f"# {t['rule'].format(n=i)}{note}".replace("\n", " "))
        out += _rule(rule)
    out += ["", f"# {t['done']}", "rownames(d) <- NULL", "clean <- d", ""]
    return "\n".join(out)
