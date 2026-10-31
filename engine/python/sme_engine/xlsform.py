"""Labels from a Kobo or ODK questionnaire (XLSForm), and label storage.

A dataset exported from Kobo holds codes (`within_2km`, `idp_out_camp`); the
questionnaire holds the readable labels, often in several languages. Labels are
kept in the dataset spec as:

    {"columns": {column: {lang: text}}, "values": {column: {code: {lang: text}}}}

`lang` is a language code taken from the XLSForm header ("label::French (fr)" ->
"fr", "label::bangla" -> "bangla") or "default" for a plain "label" column.
Labels typed by the user are stored the same way.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import polars as pl

from .rpc import INVALID_PARAMS, RpcError

LANG_NAMES = {
    "fr": ("fr", "french", "francais", "français"),
    "en": ("en", "english", "anglais"),
    "ar": ("ar", "arabic", "arabe"),
    "es": ("es", "spanish", "espanol", "español"),
    "pt": ("pt", "portuguese", "portugues", "português"),
}
SELECT_MULTIPLE_SEPARATORS = ("/", ".", "_")


def _err(message: str, key: str) -> RpcError:
    return RpcError(message, INVALID_PARAMS, data={"key": key})


def lang_of(header: str) -> str | None:
    """'label' -> 'default'; 'label::French (fr)' -> 'fr'; 'label::bangla' -> 'bangla'; others -> None."""
    h = header.strip()
    if h.lower() == "label":
        return "default"
    m = re.match(r"(?i)^label\s*::\s*(.+)$", h)
    if not m:
        return None
    raw = m.group(1).strip()
    code = re.search(r"\(([A-Za-z-]{2,8})\)\s*$", raw)
    if code:
        return code.group(1).lower()
    low = raw.lower()
    for code_, names in LANG_NAMES.items():
        if low in names:
            return code_
    return low


def _read(path: Path, sheet: str) -> pl.DataFrame:
    return pl.read_excel(path, sheet_name=sheet, engine="calamine", infer_schema_length=0)


def _columns_lower(df: pl.DataFrame) -> dict[str, str]:
    return {c.strip().lower(): c for c in df.columns}


def find_form(path: Path, sheets: list[str]) -> dict[str, str] | None:
    """Find the survey and choices sheets of an XLSForm in a workbook, if any."""
    if path.suffix.lower() not in (".xlsx", ".xlsm", ".xls"):
        return None
    survey = choices = None
    for s in sheets:
        try:
            head = _read(path, s).head(0)
        except Exception:  # noqa: BLE001 - unreadable sheets are just skipped
            continue
        cols = _columns_lower(head)
        has_label = any(lang_of(c) for c in head.columns)
        if survey is None and "type" in cols and "name" in cols and has_label:
            survey = s
        elif choices is None and "list_name" in cols and "name" in cols and has_label:
            choices = s
    return {"survey": survey, "choices": choices} if survey else None


def _labels_of(row: dict[str, Any], label_cols: dict[str, str]) -> dict[str, str]:
    out = {}
    for header, lang in label_cols.items():
        v = row.get(header)
        if v is not None and str(v).strip():
            out[lang] = re.sub(r"<[^>]+>", "", str(v)).strip()  # Kobo labels may carry HTML or markdown tags
    return out


def parse(path: Path, survey_sheet: str, choices_sheet: str | None, data_columns: list[str]) -> dict[str, Any]:
    """Labels for the columns of a dataset, from its XLSForm. Returns labels and match counts."""
    try:
        survey = _read(path, survey_sheet)
        choices = _read(path, choices_sheet) if choices_sheet else None
    except Exception as exc:  # noqa: BLE001
        raise _err(f"Cannot read the questionnaire: {exc}", "form_unreadable") from None

    s_cols = _columns_lower(survey)
    if "type" not in s_cols or "name" not in s_cols:
        raise _err("The survey sheet has no type and name columns", "form_invalid")
    s_labels = {c: lang_of(c) for c in survey.columns if lang_of(c)}

    lists: dict[str, dict[str, dict[str, str]]] = {}
    if choices is not None:
        c_cols = _columns_lower(choices)
        c_labels = {c: lang_of(c) for c in choices.columns if lang_of(c)}
        for row in choices.iter_rows(named=True):
            ln, name = row.get(c_cols.get("list_name", "")), row.get(c_cols["name"])
            if ln and name is not None:
                lists.setdefault(str(ln).strip(), {})[str(name).strip()] = _labels_of(row, c_labels)

    data = set(data_columns)
    columns: dict[str, dict[str, str]] = {}
    values: dict[str, dict[str, dict[str, str]]] = {}
    for row in survey.iter_rows(named=True):
        qtype = str(row.get(s_cols["type"]) or "").strip()
        name = str(row.get(s_cols["name"]) or "").strip()
        if not name or qtype.startswith(("begin", "end", "note")):
            continue
        labels = _labels_of(row, s_labels)
        parts = qtype.split()
        kind = parts[0] if parts else ""
        list_name = parts[1] if len(parts) > 1 else None
        options = lists.get(list_name or "", {})
        # Kobo exports may prefix columns with group names: "group/question".
        matches = [c for c in data if c == name or c.endswith(f"/{name}")]
        for col in matches:
            if labels:
                columns[col] = labels
            if kind == "select_one" and options:
                values[col] = options
        if kind == "select_multiple" and options:
            for code, opt_labels in options.items():
                for sep in SELECT_MULTIPLE_SEPARATORS:
                    for base in matches or [name]:
                        col = f"{base}{sep}{code}"
                        if col in data:
                            columns[col] = {
                                lang: f"{labels.get(lang, name)} : {text}" for lang, text in opt_labels.items()
                            } or labels
                            values[col] = {"1": {"default": "1"}, "0": {"default": "0"}}
    languages = sorted(
        {lang for d in columns.values() for lang in d}
        | {lang for v in values.values() for o in v.values() for lang in o}
    )
    return {
        "labels": {"columns": columns, "values": values},
        "languages": languages,
        "matched_columns": len(columns),
        "matched_value_lists": len(values),
    }


def merge(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """Questionnaire labels completed by, never overwriting, labels already typed by the user."""
    old = old or {"columns": {}, "values": {}}
    columns = {**new.get("columns", {})}
    for col, langs in old.get("columns", {}).items():
        columns[col] = {**columns.get(col, {}), **langs}
    values = {c: {k: dict(v) for k, v in m.items()} for c, m in new.get("values", {}).items()}
    for col, codes in old.get("values", {}).items():
        target = values.setdefault(col, {})
        for code, langs in codes.items():
            target[code] = {**target.get(code, {}), **langs}
    return {"columns": columns, "values": values}


def pick(labels: dict[str, str] | None, lang: str) -> str | None:
    """The label in `lang`, else the default label, else English, else any."""
    if not labels:
        return None
    for key in (lang, "default", "en"):
        if labels.get(key):
            return labels[key]
    return next(iter(labels.values()), None)
