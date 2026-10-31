# Conventions

Rules every contribution follows. When in doubt, follow the existing code and ask in the pull request.

## 1. Languages

| What | Language |
|---|---|
| Code, identifiers, code comments, docstrings | English |
| Commit messages, branch names, pull requests, issues, developer docs | English |
| Interface text | French and English, chosen by the user (French is the reference) |
| User documentation | French and English |
| Demo data values (village names, answer labels) | French, as in real field data |

Interface strings live in `apps/desktop/src/renderer/i18n/messages.ts`, never in components. Components call `t("key")` from `useI18n()`. Rules:

- Every key exists in both catalogues. The English catalogue is typed against the French one, so a missing key fails `npm run typecheck`.
- Placeholders use `{name}` and are filled with `t("key", { name })`. Do not build sentences by concatenation: word order differs between languages.
- Numbers and percentages go through `number()` and `percent()` from `useI18n()`, which follow the interface locale (fr-FR or en-GB).
- The engines do not produce interface text. An error the user may see carries a translation key in `data.key` (for example `r_timeout`), and the interface maps it to `errors.<key>`. Results carry keys too (for example `method_key`). Engine messages themselves are in English and meant for logs.
- The chosen language is stored per user; the first start follows the system language.
- End-to-end tests select elements with `data-testid`, never with displayed text.

## 2. Repository layout

```
apps/desktop      Electron + React + TypeScript interface
engine/python     Business engine (project file, import, cleaning, Word report, orchestration)
engine/r          Statistical engine (every statistical computation)
tools/            Build scripts (Windows runtimes), smoke and end-to-end tests
docs/             Developer documentation and architecture decision records
```

The interface talks only to the Python engine. The Python engine is the only writer of the project file and the only caller of R.

## 3. Code style

- **TypeScript**: strict mode, ESLint and Prettier (`npm run lint`, `npm run format`). Functional React components and hooks. No `any` without a comment explaining why.
- **Python**: 3.12 syntax, type hints on public functions, Ruff for lint and formatting (`ruff check`, `ruff format`), line length 120.
- **R**: base R style, two-space indentation, `snake_case`, every exported function prefixed `sme_`. No package added without a reason recorded in an ADR.
- **Naming**: `camelCase` in TypeScript, `snake_case` in Python and R, `kebab-case` for file names in docs and branches.
- **Errors**: messages shown to users are complete sentences that say what went wrong and how to fix it. Technical details go to the log.

## 4. Data handling

- Imported data is **never modified**. Every transformation is a recorded, replayable rule.
- Data passes from Python to R as Arrow IPC streams (`write_ipc_stream` with `CompatLevel.oldest()`), never as JSON.
- No expression supplied by a user is ever passed to `eval`, in Python or R. Rules are structured JSON trees interpreted by the engines.
- No telemetry and no network calls, except an explicit, user-triggered connector and the update check (GitHub releases), which the user or the organisation can turn off.
- Variables flagged as personal data are excluded from exports and reports by default.
- Never commit real beneficiary data, even in tests.

## 5. Statistics

- Every statistical result is computed by **R**, using base R or an established package (`survey`, `effectsize`, `car`, `pwr`).
- Every estimate comes with a **confidence interval**; every test comes with an **effect size**.
- When a dataset has a survey design (weights, strata, clusters), all computations use it.
- Defaults: 95 % confidence, Welch tests rather than Student, Holm correction for multiple comparisons.
- Each R function returns the **R script** that reproduces the result.
- **Achievement rate** of an indicator = (achieved − baseline) / (target − baseline) × 100. Never achieved / target when a baseline exists.
- Status thresholds by default: achieved ≥ 90 %, on track ≥ 60 %, behind below 60 % (configurable per project).

Details and the full catalogue: [statistics.md](statistics.md).

## 6. Interface and design system

The reference is the clickable prototype and the "Identité SuiviEvalLab" design system (tokens in `apps/desktop/src/renderer/styles.css`).

- Calm layout: collapsible sidebar, narrow central column (760 px max), detail panel on the right that opens on selection.
- One action colour (`--action`). Laterite (`--laterite`) only for the logo and the target line in charts.
- A status always shows an icon **and** a word, never colour alone: Atteint, En bonne voie, En retard, Sans valeur.
- Titles in Source Serif 4, text in Source Sans 3, code in IBM Plex Mono. Fonts are bundled; nothing loads from the network.
- Both light and dark themes must work for every screen.
- Avoid generic template looks: no gradients, no glow, no emoji, no nested cards, no big number tiles without a reason, no decorative coloured dots.

## 7. Writing interface text

- Formal "vous", short sentences, the tone of a competent colleague.
- Buttons say what they do: « Importer un fichier », « Ajouter au rapport », « Générer le rapport Word ».
- **No em dash or en dash** used as a separator, and no decorative middle dot. Use a comma, a colon, parentheses or a new sentence.
- No emoji, no exclamation marks, no greetings, no sales adjectives, no "sparkle" icon for automated features: say what the feature does.
- Results: magnitude first, then significance. « Est passé de 52,0 % à 63,4 %, soit une hausse de 11,4 points. »
- Numbers follow the locale: `63,4 %`, `1 184` in French (narrow no-break space before `%`), `63.4%`, `1,184` in English.
- English text follows the same rules: plain verbs on buttons ("Import a file", "Generate the Word report"), British spelling, sentence case.

## 8. Dependencies and licences

- Pin every dependency to an exact version (npm, pip, R package list, GitHub Actions major versions).
- Only licences compatible with GPL-3.0-or-later.
- Prefer small, maintained dependencies; justify any heavy one in an ADR.
