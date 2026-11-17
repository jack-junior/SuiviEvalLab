# Contributing and testing

SuiviEvalLab is free software under GPL-3.0-or-later. Code, documentation and the record of decisions are in the GitHub repository `jack-junior/SuiviEvalLab`. One can contribute without writing code: testing, reporting a problem, improving a text of the interface or of this documentation.

## Reporting a problem

On GitHub, **Issues**, **New issue**: what you were doing (screen, steps), what you expected and what you got, a screenshot and, for a figure that looks wrong, the data (anonymised), the expected value and how to get it. **A wrong figure is a critical defect.** Never attach real personal data of beneficiaries.

## Development setup

| Tool | Version | Used for |
|---|---|---|
| Git | recent | version control |
| Node.js | 22 LTS | interface and host (Electron, React) |
| Python | 3.12 or later | business engine |
| R | 4.4 | statistics engine, with `jsonlite`, `survey`, `nanoarrow` |

```bash
git clone https://github.com/jack-junior/SuiviEvalLab.git
cd SuiviEvalLab/engine/python
python -m pip install -r requirements.txt "pytest==9.1.1" "ruff==0.17.0"
python -m pytest
cd ../../apps/desktop
npm ci
npm start
```

## Rules

- Code, comments, commit messages and technical documentation in English; interface in French and English, all texts in `apps/desktop/src/renderer/i18n/messages.ts`.
- Imported data is never changed; every transformation is a recorded rule. No user formula runs as code. No real beneficiary data in the repository.
- Every statistical result is computed by R with a recognised package, with its confidence interval or effect size, and the script that reproduces it.
- Every source file starts with its SPDX licence header and the copyright notice.
- Checks before pushing:

```bash
cd engine/python && python -m ruff check . && python -m ruff format --check . && python -m pytest
cd apps/desktop && npm run lint && npm run typecheck && npm run build
```

`npm run lint` also checks translations, licence headers and the **colour contrast** of the interface (WCAG 2.1 level AA, light and dark themes).

## Work cycle

An issue, a branch from `main`, short Conventional Commits, a pull request with a screenshot for visible changes, green continuous integration, then "Squash and merge". Nobody pushes to `main` directly.

## Automated tests

| Series | Count | What it guarantees |
|---|---|---|
| R statistical functions | 4 test files | Every estimate, interval, comparison, test and sample size equals the direct call to the reference package or a published value |
| Python engine | 145 tests | Project file and upgrades, every calculation rule of section 6, reception, checks, Excel forms, simulated Kobo, ODK and DHIS2 servers, registers, every donor report, exports, portfolio, team, synchronisation, encryption, audit, copies and integrity; survey import, cleaning, analysis and report with independently recomputed figures |
| Acceptance | 3 paths | The paths of section 11 of the specification (below) |
| Original files | 4 tests | The four full HDX surveys import, merge and analyse correctly |
| End-to-end | 1 scenario | The installed Windows application is driven like a user, from the project sheet to encryption |
| Update | 1 scenario | The installed application updates itself and follows group policy |
| Performance | 1 script | The thresholds of section 9 |

The **acceptance tests** (`engine/python/tests/test_acceptance.py`) play a three-year project with four partners, thirty sites and forty indicators entered and validated over twelve quarters (two by Excel form), every tracking figure recomputed independently; a team of three members and two partners synchronised by packages, shared folder and relay server, with conflicts; and a portfolio of five projects.

The **performance thresholds** are measured with `python tools/bench/bench.py [work folder]`. It builds a project of 300 indicators, 40 periods and 500 sites (2.4 million values), twenty ordinary projects and a 500 000-row file, then times opening, tracking, the dashboard and the import, and fails if a threshold is missed. Reference figures (ordinary Linux machine): opening 0.3 s, tracking 0.3 s, filtered 0.2 s, dashboard of 20 projects 0.6 s, import of 500 000 rows 0.8 s.

## Signing the installer

The release workflow signs the installer when the organisation's code signing certificate is in the repository secrets:

| Secret | Content |
|---|---|
| `WIN_CSC_LINK` | The certificate with its private key as a `.pfx` file, base64-encoded (`base64 -w0 certificate.pfx`) |
| `WIN_CSC_KEY_PASSWORD` | The password of the `.pfx` file |

The workflow checks the signature of the installer and fails if it is not valid. Without these secrets the installer is built unsigned, with a warning.

Certificates issued since 2023 are often kept on a hardware module or an online service (Azure Trusted Signing, SSL.com eSigner, DigiCert KeyLocker) rather than in a `.pfx` file. Signing is then done by the provider's tool, called from the workflow instead of the two secrets above; electron-builder accepts a custom signing command (`win.signtoolOptions.sign`).

Once the certificate is in place, set `publisherName` in the `build.win` configuration of `apps/desktop/package.json` to the exact name on the certificate: automatic updates will then check that each new version is signed by the same publisher.

## Publishing a version

Set the version in `apps/desktop/package.json` and `engine/python/sme_engine/__init__.py`, complete `.github/release-notes.md`, merge into `main`, then tag that commit (`git tag v1.0.0`, `git push origin v1.0.0`). The release workflow builds the installer, runs the tests again and publishes the release with the installer, its SHA-256 hash and the update files. Installed applications find it within six hours.
