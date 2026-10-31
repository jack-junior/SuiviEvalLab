# Test kit for human testers

A folder testers use step by step: the original public survey files, an
organisation Word template, and `GUIDE-DE-TEST.docx` (scenarios with expected
results). The data files are not kept in the repository (third-party data,
about 50 MB); they are downloaded and checked by SHA-256.

    python tools/datasets/fetch.py build/hdx
    mkdir -p build/test-kit/donnees build/test-kit/modeles
    cp build/hdx/irq_mcna7_2019.xlsx         build/test-kit/donnees/01_irak_mcna_2019_reference.xlsx
    cp build/hdx/irq_mcna8_2020.xlsx         build/test-kit/donnees/02_irak_mcna_2020_fin_de_projet.xlsx
    cp build/hdx/bgd_wash_baseline_2018.xlsx build/test-kit/donnees/03_bangladesh_wash_2018_reference.xlsx
    cp build/hdx/bgd_wash_followup_2018.xlsx build/test-kit/donnees/04_bangladesh_wash_2018_suivi.xlsx
    cp engine/python/tests/fixtures/wash_bgd_2018.sav build/test-kit/donnees/05_bangladesh_wash_2018_extrait.sav
    cp engine/python/tests/fixtures/wash_bgd_2018.dta build/test-kit/donnees/05_bangladesh_wash_2018_extrait.dta
    cp engine/python/tests/fixtures/modele_organisation.docx build/test-kit/modeles/
    cp tools/test-kit/LISEZMOI.txt tools/test-kit/SOURCES.txt build/test-kit/
    PYTHONPATH=engine/python python tools/test-kit/expected.py build/test-kit   # runs every scenario in the engine
    python tools/test-kit/guide.py build/test-kit                              # writes the guide

`expected.py` plays each scenario through the engine as a tester would and
writes `expected.json`. `check_in_r.R` recomputes the survey estimates of
scenarios 8 to 11 directly with the R `survey` package from the raw files (after
exporting the columns to `/tmp/i19.csv` and `/tmp/i20.csv`, see the script);
both must agree before the guide is handed out.
