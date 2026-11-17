# SuiviEvalLab

SuiviEvalLab is a desktop application for monitoring and evaluation teams. It brings together, in one application, the work of an M&E officer or manager, from the project document to the report handed to the donor:

- describe the project: donors, reporting calendar, places, partners, disaggregations;
- build the logframe on the donor's model (European Union, USAID, United Nations, World Bank, IFRC, or custom levels) and pick indicators from a library of 146 reference sheets in 16 sectors;
- set targets by period and keep the monitoring plan;
- receive data from partners and sites (entry, Excel forms, KoboToolbox, ODK, DHIS2), check it, validate it, lock periods;
- read where each indicator stands and explain the gaps;
- follow activities, budget, feedback and complaints, recommendations, risks and evaluations;
- analyse surveys with R (weights, survey design, confidence intervals, comparisons);
- produce periodic reports in the formats of twenty donors, the survey report and exports;
- keep the agenda and tasks of all one's projects, and see the portfolio at a glance;
- work together, partners included, even offline, with encrypted data.

It is free software (GPL-3.0-or-later), written by GAYI Komi Selassi and SANOUSSI Moudjibou. It runs on Windows 10 and 11.

## Works offline, data stays with the team

The application works **without an internet connection**. Data stays on the team's computers: nothing is sent to the publisher. The only connections are those the user chooses (data collection servers, the team's shared folder or relay server) and the update check, which an organisation can turn off.

## One file per project

All the work of a project is in **one file** with the `.sme` extension. There is no Save button: every change is written at once. A copy is made automatically each time the project is opened, so one can go back after a mistake. A project can be protected by a password; it is then encrypted.

## Versions

| Version | Content |
|---|---|
| 0.1 to 0.5 | Surveys: results framework, indicators, import, traced cleaning, R calculations, comparisons, tests, free analyses, Word report |
| 1.0 | The complete M&E tool: project sheet and calendar, data reception and checks, indicator tracking, Kobo, ODK and DHIS2, activities and budget, accountability and evaluations, donor periodic reports, agenda and tasks, portfolio and dashboard, encrypted team work |

Projects made with versions 0.2 to 0.5 open in 1.0 without loss; a copy is made before they are upgraded.

## This documentation

- [User guide](user-guide.md): every screen, in the order of the work.
- [Administrator guide](administration.md): team, roles, synchronisation, security.
- [Partner guide](partner.md): for the focal point of a partner organisation.
- [Installing the relay server](server.md).
- [Data protection](data-protection.md): good practice.
- [Contributing and testing](contributing.md), and the [pilot test](pilot.md) of version 1.0.

The French documentation is more detailed on the survey and analysis screens.
