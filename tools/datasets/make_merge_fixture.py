"""Build a small two-sheet workbook for the merge tests from real data: households
and their water containers (a Kobo repeat), REACH-UNICEF Bangladesh WASH baseline
2018 (HDX, CC BY 4.0).

    python tools/datasets/make_merge_fixture.py <folder with bgd_wash_baseline_2018.xlsx>

Output: engine/python/tests/fixtures/wash_bgd_containers.xlsx. The first 300
household rows (in file order) and every container row whose _parent_index is
below 320, so some containers have no household in the extract, as in real
exports with deleted submissions.
"""

import sys
from pathlib import Path

import polars as pl
import xlsxwriter

src = Path(sys.argv[1]) / "bgd_wash_baseline_2018.xlsx"
hh = pl.read_excel(src, sheet_name="Dataset", infer_schema_length=0)
hh = hh.select(["reported_camp_name", "Camp weights", "_index"]).head(300)
ct = pl.read_excel(src, sheet_name="Dataset_containergroup", infer_schema_length=0)
ct = ct.select(
    [
        "water_collection/containers_group/container_type",
        "water_collection/containers_group/volume",
        "water_collection/containers_group/containers_protected",
        "_index",
        "_parent_index",
    ]
).filter(pl.col("_parent_index").cast(pl.Int64) < 320)
out = Path("engine/python/tests/fixtures/wash_bgd_containers.xlsx")
with xlsxwriter.Workbook(out) as wb:
    hh.write_excel(wb, worksheet="Menages")
    ct.write_excel(wb, worksheet="Contenants")
print(hh.height, ct.height)
