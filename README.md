# SuiviEvalLab

**FR** : Poste de travail de bureau pour les professionnels du suivi-évaluation : du cadre logique au rapport Word, sur votre ordinateur, sans connexion internet, avec la rigueur statistique de R.

**EN**: A desktop workstation for monitoring and evaluation professionals: from the logframe to the Word report, offline, with the statistical rigour of R.

## Status

Version **0.3.0**: results framework, indicators (shares with one or several conditions, means, counts, ratios, crossed breakdowns), import of Excel, Kobo (with questionnaire labels), CSV, SPSS or Stata data, merge of households and individuals, cleaning journal, indicators estimated in R with their confidence intervals and survey design, baseline and endline comparison, a test assistant that concludes in words, a Word report in French or English on your organisation's own template, a read-only HTML dashboard to share, a data quality diagnosis, checks before the report, automatic project copies, a sample size calculator and the monitoring plan in Excel. An example project runs on real public survey data. See the [roadmap](docs/roadmap.md).

## Documentation

The user and contributor guide (French) is published at <https://jack-junior.github.io/SuiviEvalLab/>. Its sources are in [docs/guide](docs/guide); `python tools/docs/build_word.py` produces the Word version.

## Example data

The example project uses extracts of the REACH Initiative Iraq Multi-Cluster Needs Assessments VII (2019) and VIII (2020), published on the Humanitarian Data Exchange under CC BY 4.0. Details in [engine/python/sme_engine/examples/README.md](engine/python/sme_engine/examples/README.md).

## Install (Windows 10 and 11)

1. Download `SuiviEvalLab-<version>-installation.exe` from the [Releases](../../releases) page.
2. Run it.
3. The installer is not signed yet. If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**.

No administrator rights needed. Python and R are included.

From 0.3.0 on, the app updates itself: it downloads new versions in the background and installs them when you restart it. Your projects are separate files and are never touched by an update.

## Develop

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and workflow, [docs/conventions.md](docs/conventions.md) for the rules, and [docs/architecture.md](docs/architecture.md) for how the pieces fit.

```
apps/desktop      Electron + React + TypeScript interface
engine/python     Business engine (Python)
engine/r          Statistical engine (R)
tools/            Build scripts, smoke and end-to-end tests
docs/             Developer documentation and decision records
```

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
