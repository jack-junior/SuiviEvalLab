"""Build the example datasets bundled with the app from the REACH Iraq MCNA files.

Input: the original HDX files (see datasets/README.md for sources and licence).
Output: engine/python/sme_engine/examples/*.xlsx, a subset of columns of the
representative household sheet, every row kept and every value unchanged.

    python tools/datasets/make_examples.py <folder with the original files>
"""

import sys
from pathlib import Path

import polars as pl

SRC = Path(sys.argv[1])
OUT = Path("engine/python/sme_engine/examples")
OUT.mkdir(parents=True, exist_ok=True)

ATTRIBUTION = [
    ("Source", "REACH Initiative, Iraq Multi-Cluster Needs Assessment (MCNA), via the Humanitarian Data Exchange"),
    ("Licence", "Creative Commons Attribution 4.0 (CC BY 4.0)"),
    ("Original file", ""),
    ("Changes", "Subset of columns of the representative household sheet. Rows and values unchanged."),
    ("Weights", "The weights column comes from the original file (strata: district x population group)."),
]

FILES = [
    (
        "awg_irq_dataset_mcna_vii_september2019_public_nopi.xlsx",
        "irq_mcna7_2019.xlsx",
        "HH data - representative",
        "mcna_irak_2019.xlsx",
        "https://data.humdata.org/dataset/reach-iraq-mcna-vii-dataset",
        [
            "X_uuid",
            "population_group",
            "governorate_mcna",
            "district",
            "tot_child",
            "primary_school_place",
            "secondary_school_place",
            "child_dropout_school",
            "weights",
        ],
    ),
    (
        "reach_irq_mcna-viii-2020-nopi_dataset-090221.xlsx",
        "irq_mcna8_2020.xlsx",
        "HH - Representative",
        "mcna_irak_2020.xlsx",
        "https://data.humdata.org/dataset/0f850d6e-2a67-4204-af08-c0237e59020f",
        [
            "hh_id",
            "population_group",
            "governorate_mcna",
            "tot_child",
            "primary_school_place",
            "secondary_school_place",
            "child_dropout_school",
            "weights",
        ],
    ),
]

for original, local, sheet, target, page, cols in FILES:
    src = SRC / local if (SRC / local).exists() else SRC / original
    df = pl.read_excel(src, sheet_name=sheet, infer_schema_length=0).select(cols)
    # Columns that are numbers in the original file are written back as numbers.
    for c in df.columns:
        num = df[c].cast(pl.Float64, strict=False)
        if num.null_count() == df[c].null_count():
            df = df.with_columns(num.alias(c))
    readme = pl.DataFrame(
        {
            "item": [a for a, _ in ATTRIBUTION] + ["Page"],
            "value": [b if a != "Original file" else original for a, b in ATTRIBUTION] + [page],
        }
    )
    with __import__("xlsxwriter").Workbook(OUT / target) as wb:
        df.write_excel(wb, worksheet="Donnees menages", autofit=False)
        readme.write_excel(wb, worksheet="Lisez-moi", include_header=False, autofit=False)
    print(target, df.shape)
