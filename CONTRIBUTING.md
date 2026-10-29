# Contributing to SuiviEvalLab

Thank you for helping build SuiviEvalLab. This guide explains how to set up your machine, how we work together and what a change needs before it is merged.

Read [docs/conventions.md](docs/conventions.md) before writing code: it holds the rules every contribution follows (languages, naming, interface writing, statistics, data handling).

## 1. Set up your machine

| Tool | Version | Used for |
|---|---|---|
| Git | any recent | version control |
| Node.js | 22 LTS | desktop app (Electron, React) |
| Python | 3.12 or newer | business engine |
| R | 4.4 | statistical engine |

R packages: `install.packages(c("jsonlite", "survey", "nanoarrow"))`.

```bash
git clone https://github.com/jack-junior/SuiviEvalLab.git
cd SuiviEvalLab

# Python engine
cd engine/python
python -m pip install -r requirements.txt "pytest==9.1.1" "ruff==0.17.0"
python -m pytest
cd ../..

# R engine
Rscript engine/r/tests/test_proportion.R

# Desktop app
cd apps/desktop
npm ci
npm start
```

On Windows with Git Bash, use forward slashes in paths (`engine/python`, not `engine\python`). If `Rscript` is not on your PATH, point to it before `npm start`:

```bash
export SME_RSCRIPT="/c/Program Files/R/R-4.4.3/bin/Rscript.exe"
```

You do not need to build the Windows installer locally: the CI builds and tests it on every push. If you want to, run `pwsh tools/windows/prepare-runtimes.ps1` then `npm run dist:win` in `apps/desktop`.

## 2. How we work

1. **Pick or open an issue** describing the change. Assign it to yourself so nobody duplicates work.
2. **Create a branch** from `main`, named by type and subject:
   - `feat/indicator-sheet`, `fix/r-timeout`, `docs/statistics-catalogue`, `chore/ci-cache`, `refactor/rpc-errors`, `test/proportion-edge-cases`.
3. **Commit in small steps** with clear messages (see section 4).
4. **Open a pull request** to `main` using the template. Link the issue (`Closes #12`).
5. **CI must be green**: tests, lint, Windows installer and end-to-end test.
6. **One approval** from a maintainer is required before merging. Maintainers squash-merge.

Nobody pushes directly to `main`.

## 3. Before you open a pull request

```bash
# Python
cd engine/python && python -m ruff check . && python -m ruff format --check . && python -m pytest

# R
Rscript engine/r/tests/test_proportion.R

# Desktop app
cd apps/desktop && npm run lint && npm run typecheck && npm run build
```

`npm run format` and `python -m ruff format .` fix formatting automatically.

Checklist:

- Tests added or updated for the behaviour you changed.
- Every statistical result is computed in R and checked against a direct R call or a published reference (see [docs/statistics.md](docs/statistics.md)).
- User-facing text follows the writing rules in [docs/conventions.md](docs/conventions.md).
- Screens follow the design system; include a screenshot in the pull request for any visual change.
- New dependencies are pinned to an exact version and have a GPL-3.0-compatible licence.
- Significant technical decisions get a short record in [docs/adr](docs/adr).

## 4. Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/), in English:

```
feat(indicators): compute achievement rate from baseline and target
fix(r-bridge): restart R after a timeout
docs: add statistics catalogue
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`, `style`. Keep the first line under 72 characters; explain the why in the body when it is not obvious.

## 5. Reporting problems

Use the issue templates. For a calculation that looks wrong, include the input data (anonymised), the expected value and how you obtained it. Wrong numbers are treated as critical bugs.

Never attach real personal data of programme beneficiaries to an issue.

## 6. Licence

By contributing, you agree that your contribution is licensed under the GPL-3.0-or-later licence of the project.
