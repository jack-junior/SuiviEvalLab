# SuiviEvalLab

**FR** : Poste de travail de bureau pour les professionnels du suivi-évaluation : du cadre logique au rapport Word, sur votre ordinateur, sans connexion internet, avec la rigueur statistique de R.

**EN**: A desktop workstation for monitoring and evaluation professionals: from the logframe to the Word report, offline, with the statistical rigour of R.

## Status

Version **1.0** in final acceptance (pilot test with M&E practitioners). It covers the whole M&E workflow:

- project sheet, reporting calendar, places, partners, disaggregations;
- logframe on the donor's model and a library of 146 indicator sheets in 16 sectors;
- targets by period and the monitoring plan;
- reception of partner and site data (entry, Excel forms, KoboToolbox, ODK, DHIS2), checks, validation, period locking;
- indicator tracking with the calculation rules of the specification, gap comments, unique people counted once;
- activities and budget, feedback and complaints, recommendations, risks, learning, evaluations;
- survey analysis in R with confidence intervals and survey design;
- periodic reports in the formats of twenty donors, the survey report and exports;
- agenda and tasks across projects, portfolio dashboard;
- team work, partners included, offline, with signed and encrypted exchanges by package, shared folder or a self-hosted relay server, an audit trail and project encryption.

An example project runs on real public survey data.

## Documentation

The user, administrator, partner, server and contributor guides (French and English) are published at <https://jack-junior.github.io/SuiviEvalLab/>. Its sources are in [docs/guide](docs/guide); `python tools/docs/build_word.py` produces the Word version (`--lang en` for English).

## Example data

The example project uses extracts of the REACH Initiative Iraq Multi-Cluster Needs Assessments VII (2019) and VIII (2020), published on the Humanitarian Data Exchange under CC BY 4.0. Details in [engine/python/sme_engine/examples/README.md](engine/python/sme_engine/examples/README.md).

## Install (Windows 10 and 11)

1. Download `SuiviEvalLab-<version>-installation.exe` from the [Releases](../../releases) page.
2. Run it.
3. Published versions are signed. A working version may not be: if Windows shows "Windows protected your PC", click **More info**, then **Run anyway**.

No administrator rights needed. Python and R are included.

The app updates itself: it downloads new versions in the background and installs them when you restart it. Your projects are separate files and are never touched by an update.

## Develop

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and workflow, [docs/conventions.md](docs/conventions.md) for the rules, and [docs/architecture.md](docs/architecture.md) for how the pieces fit.

```
apps/desktop      Electron + React + TypeScript interface
engine/python     Business engine (Python)
engine/r          Statistical engine (R)
server/           Relay server for team synchronisation (optional, self-hosted)
tools/            Build scripts, smoke, end-to-end and performance tests
docs/             Developer documentation and decision records
```

## Authors and licence

Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou.

SuiviEvalLab is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. It is distributed in the hope that it will be useful, but without any warranty; see [LICENSE](LICENSE) for details.

Any copy or modified version must keep these copyright notices, state its changes, and remain under the same licence with its source code. See [NOTICE](NOTICE).
