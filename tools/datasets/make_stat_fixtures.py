"""Build SPSS and Stata test files from real survey data (REACH Bangladesh WASH
follow-up 2018, HDX, CC BY 4.0), with variable and value labels from its XLSForm.

    python tools/datasets/make_stat_fixtures.py <folder with bgd_wash_followup_2018.xlsx>

Output: engine/python/tests/fixtures/wash_bgd_2018.sav and .dta (first 600
households, 12 columns). Values are unchanged; codes become numbers with labels,
as in an SPSS or Stata export.
"""

import sys
from pathlib import Path

import polars as pl
import pyreadstat

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "python"))
from sme_engine import xlsform  # noqa: E402

src = Path(sys.argv[1]) / "bgd_wash_followup_2018.xlsx"
out = Path("engine/python/tests/fixtures")
cols = ["_uuid", "camp_id", "enu_gen", "consent", "res_age", "res_gen", "head_gen", "num_mem", "drnk_wat",
        "access_wat", "sat_wat", "trt_wat", "_index"]
df = pl.read_excel(src, sheet_name="Household Dataset", infer_schema_length=0)
cols = [c for c in cols if c in df.columns]
df = df.select(cols).head(600)
labels = xlsform.parse(src, "Tool - Questions", "Tool - Choices", df.columns)["labels"]

value_labels, variable_labels, data = {}, {}, {}
for c in df.columns:
    variable_labels[c] = xlsform.pick(labels["columns"].get(c), "en") or c
    choices = labels["values"].get(c)
    series = df[c]
    if choices and series.drop_nulls().is_in(list(choices)).all():
        codes = {code: i + 1 for i, code in enumerate(choices)}
        data[c] = [codes.get(v) if v is not None else None for v in series.to_list()]
        value_labels[c] = {n: xlsform.pick(choices[code], "en") or code for code, n in codes.items()}
    else:
        num = series.cast(pl.Float64, strict=False)
        data[c] = num.to_list() if num.null_count() == series.null_count() else series.to_list()
frame = pl.DataFrame(data, strict=False)
# SPSS and Stata names cannot start with "_": "_uuid" becomes "uuid", as Kobo's own SPSS export does.
names = {c: c.lstrip("_") for c in frame.columns}
frame = frame.rename(names)
import pandas as pd  # noqa: E402  (pyreadstat writers take pandas frames)

pdf = pd.DataFrame(frame.to_dict(as_series=False))
col_labels = {names[k]: v[:80] for k, v in variable_labels.items()}
val_labels = {names[k]: v for k, v in value_labels.items()}
pyreadstat.write_sav(pdf, out / "wash_bgd_2018.sav", column_labels=col_labels, variable_value_labels=val_labels)
pyreadstat.write_dta(pdf, out / "wash_bgd_2018.dta", column_labels=col_labels, variable_value_labels=val_labels)
print(frame.shape, sorted(val_labels))
