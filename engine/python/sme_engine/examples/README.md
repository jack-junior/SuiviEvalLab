# Example datasets

Real data used by the example project ("Access to education in Iraq") and by the tests.

| File | Source | Licence |
|---|---|---|
| `mcna_irak_2019.xlsx` | REACH Initiative / Assessment Working Group Iraq, Multi-Cluster Needs Assessment VII (2019), household dataset without personal information, [HDX](https://data.humdata.org/dataset/reach-iraq-mcna-vii-dataset) | CC BY 4.0 |
| `mcna_irak_2020.xlsx` | REACH Initiative, Multi-Cluster Needs Assessment VIII (2020), household dataset without personal information, [HDX](https://data.humdata.org/dataset/0f850d6e-2a67-4204-af08-c0237e59020f) | CC BY 4.0 |

Changes: a subset of columns of the representative household sheet; every row and value is unchanged. The files are rebuilt with `tools/datasets/make_examples.py` from the original HDX files.

The 2019 and 2020 rounds are independent samples. In the example they play the roles of baseline and endline of a fictional project; the framework and the targets are illustrative.
