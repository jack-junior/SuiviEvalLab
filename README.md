# SuiviEvalLab

**FR** : Poste de travail de bureau pour les professionnels du suivi-évaluation : du cadre logique au rapport Word, sur votre ordinateur, sans connexion internet, avec la rigueur statistique de R.

**EN**: A desktop workstation for monitoring and evaluation professionals: from the logframe to the Word report, offline, with the statistical rigour of R.

## Status

Version **0.1.0**, step 0 (foundations): the Windows app starts, its Python and R engines run, and a demo computation goes through the whole chain. Business features start with step 1. See the [roadmap](docs/roadmap.md).

## Install (Windows 10 and 11)

1. Open the **Actions** tab, pick the latest green run on `main`, download the `SuiviEvalLab-installation-windows` artifact (GitHub sign-in required).
2. Unzip it and run `SuiviEvalLab-<version>-installation.exe`.
3. The installer is not signed yet. If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**.

No administrator rights needed. Python and R are included.

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
