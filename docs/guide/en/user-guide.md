# User guide

## Installing

1. Download `SuiviEvalLab-<version>-installation.exe` from the *Releases* page of the GitHub repository (Windows 10 or 11, 64-bit, about 250 MB).
2. Run it. It installs in the user's account, without administrator rights, and adds a desktop shortcut. Published versions are signed and show the publisher's name; a working version may not be, in which case Windows shows "Windows protected your PC": click "More info", then "Run anyway".
3. Updates arrive by themselves: they are downloaded in the background and installed when the application closes.

The interface is in French and English (buttons FR and EN at the bottom of the menu). Text size is set with the two A buttons next to them, or with Ctrl and +, Ctrl and -, Ctrl and 0. The whole application can be used with the keyboard: Tab and Shift+Tab move between elements, Enter opens a table row, Escape closes a panel; "Skip to content" appears at the first Tab.

## The workspace

Without an open project, the menu offers four screens.

| Screen | Content |
|---|---|
| **Today** | What is late and what is coming, for all projects: expected submissions, reports due, tasks, and personal tasks that belong to no project |
| **Agenda** | The common calendar of all projects, month by month, with personal events |
| **Dashboard** | The situation of each project and of the portfolio (see below) |
| **Projects** | Creating, opening, joining a team project, automatic copies, archiving |

Projects are read without being changed. A project protected by a password shows "Protected by a password": its deadlines appear once it is opened.

The link "Discover with an example project" creates a complete project from two public surveys (REACH, Iraq, 2019 and 2020).

## The project sheet

The **Project sheet** (bottom of the menu) describes what everything else builds on. A new project opens on it.

| Tab | Content |
|---|---|
| Profile | Name, code, country, sectors, donors (agreement and reporting frequency), dates, currency, colour; **reporting by**: project, partner, place, or partner and place |
| Calendar | Reporting periods generated from the dates, the frequency and the start of the financial year; two deadlines per period (data from partners, report to the donor) |
| Places | A tree of areas and sites, typed, pasted from Excel, imported from a country's administrative divisions, or placed on a map |
| Partners | Organisations, their role and their sites |
| Disaggregations | Sex, age groups (general or health), disability, residence status, area, and custom ones; each gets a "Not specified" category so totals stay right |
| Team and security | Password, members, exchanges, audit trail (see the [administrator guide](administration.md)) |

**Administrative divisions** adds the regions, districts or communes of a country at once: choose the country and the levels (keep the project's last level for sites), see what will be added, import. Each division goes under the one containing it; places already typed with the same name are kept, and importing again adds nothing twice. The divisions come from geoBoundaries (William & Mary geoLab, CC BY 4.0), are downloaded once and then available offline; boundaries and names may differ from the official ones in force.

**Search on the map** adds a site with its position: type a name and choose a result, or click on the map. The site goes under the division containing it when divisions were imported; otherwise choose the place above it. Map and search come from OpenStreetMap and need an internet connection; only the name searched is sent. Latitude and longitude can also be typed in the place's sheet.

A period is **open**, **reported** (the report was sent, data can still change) or **locked** (nothing changes). Locking needs every submission of the period to be validated; reopening needs a written reason, kept in the history and the audit trail.

## Today, agenda and tasks

The project's **Today** screen lists the submissions of the current period, the alerts waiting for a correction or a justification, gaps without comment, late activities, feedback past its deadline, overdue recommendation actions, tasks, and what changed since the project was last opened.

The **agenda** shows the calendar deadlines, evaluation steps, meetings, activity milestones and events typed in. It exports to iCalendar (`.ics`) and imports `.ics` files.

**Generated tasks** come from the state of the project (follow up a late partner, validate a submission, comment a gap, yearly data quality review, personal data to remove) and close by themselves when the situation is settled. **Typed tasks** have a title, due date, priority, owner and optional repetition. The task board sorts them by state: to do, doing, waiting, done.

## Logframe and indicators

The **Results chain** follows the donor's model (2 to 5 levels) and can also be edited as a logframe matrix, with assumptions. **Indicators** are created or taken from the **library** (146 sheets, 16 sectors, with definitions and public references).

An indicator's **type** sets how its values add up:

| Type | Entry | Across partners or places | Over time (default) |
|---|---|---|---|
| Number | One value | Sum | Cumulative |
| Percentage, rate per base, ratio | Numerator and denominator | Sum of numerators over sum of denominators | Latest period |
| Mean | Value and count | Mean weighted by counts | Latest period |
| Median, score, scale | One value | Not additive: shown by unit | Latest period |
| Milestone | Done or not done | Reached when every unit reached it | Latest period |

A percentage is never the mean of percentages: without numerators and denominators the application refuses to aggregate and says why. The **monitoring plan** holds each indicator's sheet, baseline and **targets by period** (a revised target keeps its history and reason), and exports to Excel. The **target to date** is the sum of the targets of past periods; without them, a straight line from baseline to final target is used and flagged.

## Reception and checks

The **Reception** screen shows, for a period, the expected submissions and their state: draft, submitted, under review, returned (with a comment), validated, locked. Only **validated** values count in tracking; provisional values can be shown, always marked.

Data arrives by entry, by **Excel form** (a protected workbook per partner or site and period, refused on return if it comes from another project, if lines moved or if indicators changed; a form sent again for a validated submission is a **revision**, shown and applied only by reopening with a reason), by **DHIS2** import (validated submissions are never touched), or by synchronisation from partners who use the application. Supporting documents can be attached (50 MB per file, 2 GB per project).

Checks run at every save: missing value or breakdown, total different from the sum of categories, numerator above denominator, percentage outside 0 to 100, negative number, value outside plausible bounds, unusual change from the previous period, late submission. A **blocking** alert must be corrected; a **review** alert is corrected or justified in writing. A submission cannot be validated while an alert is open.

## Indicator tracking

The **Indicator tracking** screen gives, for each indicator and period: value of the period, cumulative value, target to date, achievement rate, trend and status (achieved, on track at 90 % of the target to date or more, late, no data; the threshold can be set). It filters by place (a district adds up its sites), partner and category. Gaps are commented, and comments go into the report. Survey estimates placed in a period appear in the same table, marked "survey".

**Unique people**: for indicators counting people, pasting the list of identifiers keeps only their **pseudonym** (a keyed hash with a key of the project), so each person counts once in the cumulative total; possible duplicates are flagged.

**Servers**: KoboToolbox, ODK Central and DHIS2 connect from the Data and Reception screens. Tokens and passwords stay on the computer, encrypted by the system, never in the project file.

## Activities and budget

The work plan links activities to results, with planned and actual dates, status, progress, owner, places, partner, milestones and one level of sub-activities (a parent follows its sub-activities, weighted by length). The button "Add the M&E activities of the plan" creates the M&E activities from the calendar and the monitoring plan. An activity is late when its end date passed before it was done, or its start date passed before it started. The timeline shows a Gantt chart.

The budget has lines with planned amounts by period. Expenses are typed or imported from an accounting export in Excel or CSV (lines matched by code then label, duplicates set aside, preview before import). Time elapsed, physical progress and financial execution are shown side by side, with an alert when spending runs ahead of progress.

## Accountability, learning and evaluations

**Feedback and complaints**: channel, category, response deadline by category, circuit (received, forwarded, in progress, answered, closed), person concerned kept as a pseudonym. **Sensitive** cases (sexual exploitation and abuse, fraud, staff conduct, or marked sensitive) never appear in lists, agenda, tasks or reports; in a team only the administrator and the feedback manager read them, and every reading is in the audit trail; a project holding one must be protected by a password.

**Recommendations** get the management response and actions with owner and due date, which become tasks. **Risks and assumptions** have probability, severity, matrix, mitigation and periodic review; the logframe's assumptions can be taken in one click. **Learning questions**, **lessons** and **meeting minutes** are kept; meeting decisions become tasks.

**Evaluations** (mid-term, final, thematic, ex post): sheet, five steps in the agenda (terms of reference, recruitment, data collection, draft report, final report), evaluation questions by OECD DAC criterion in a matrix, qualitative notes coded by theme and question, and linked recommendations.

## Surveys and analysis

Survey data is imported from Excel, Kobo or ODK exports, CSV, SPSS or Stata; the original file is never changed. Every cleaning step is a rule in a journal (recode, exclusion, computed variable, classes, dates and durations, consistency checks, formulas, corrections by hand, accepted R scripts), justified, reversible and exportable as an R script. Indicators are computed by R with the `survey` package, with weights, strata and clusters and a 95 % confidence interval. Baseline and endline are compared with the difference, its interval, the p-value and the effect size; the test assistant chooses the right test from a question asked in plain words; free analyses (cross tables, regressions) follow the survey design. Each result gives the R script that reproduces it.

## Periodic reports and exports

The **Report** screen has three tabs: periodic reports, the survey report and exports.

A periodic report is set by its **format** (European Union, ECHO, USAID, AFD, Expertise France, World Bank, AfDB, UNDP, UNICEF, WFP, UNHCR, UNFPA, WHO, Global Fund, Gavi, IFRC, GIZ, Enabel, FCDO, Gates Foundation, a generic NGO format, the M&E plan, the indicator sheets, or a custom format), its **period** (one period, several, the whole project) and its **language**. Sections are filled from the project (tracking, progress by result, gaps, activities, budget, beneficiaries, feedback statistics, recommendations, risks, lessons, surveys, evaluations, logframe, data collection calendar, indicator sheets) or written in the application and kept for the next generation. The organisation's Word template is used when loaded. Checks before the report flag unvalidated submissions, gaps without comment, unlocked periods.

| Export | Format |
|---|---|
| Tracking table of a period | Excel |
| Validated values, one per line | Excel or CSV |
| Data pack for headquarters or a donor, without personal data | `.smepack` |
| Sharing page | HTML |
| Agenda | `.ics` |

## Dashboard and portfolio

The workspace **Dashboard** shows, for each project, time elapsed, indicators on track, activity progress, financial execution, next deadline and an overall status (on track, to watch, in difficulty) with its reasons, on thresholds the organisation can set. Filters: donor, country, sector, owner, status. **Common indicators** (the same library sheet in several projects) are added up when they are numbers, with "possible double counting" for people. Data packs from other offices join the dashboard. It exports to a Word note, PDF and HTML. Finished projects can be archived; a project can serve as the model of a new one (design kept, data removed).

## Automatic copies and integrity

Each time a project that is not encrypted is opened, its integrity is checked and a copy is made in the application's folder (the last ten are kept). A damaged file is reported by a banner, no copy overwrites the good ones, and the latest copy is restored from the Projects screen, "Automatic copies".
