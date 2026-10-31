**Version préliminaire, à tester avant tout usage réel.**

SuiviEvalLab couvre le parcours complet du suivi-évaluation, sur votre ordinateur et sans connexion internet : cadre de résultats, indicateurs, import et nettoyage des données, calcul par R avec intervalles de confiance et plan d'enquête, rapport Word. Un projet d'exemple fonctionne sur des données d'enquête réelles et publiques (REACH, Irak, 2019 et 2020).

### Nouveautés de la 0.3

- Un logo, et l'écran « Mes projets » : vos projets récents, leur avancement, la réouverture du dernier projet.
- Libellés Kobo : le questionnaire XLSForm donne aux colonnes et aux codes leurs libellés, en plusieurs langues. Vous pouvez aussi les saisir.
- Nouveaux indicateurs : effectifs, ratios (par exemple pour 100 ménages), conditions sur plusieurs colonnes, désagrégation croisée.
- Assistant de tests : comparer des groupes, une valeur à une cible, les mêmes personnes deux fois. La conclusion est rédigée en phrases et peut aller dans le rapport.
- Rapport Word sur le modèle de votre organisation (page de garde, styles, en-têtes), avec des balises comme `{{contenu}}` et `{{projet}}`.
- Import SPSS (.sav) et Stata (.dta) avec leurs libellés ; fusion de deux fichiers par une clé, par exemple les individus avec leur ménage.
- Partage en lecture seule : un tableau de bord en un seul fichier HTML, sans aucune donnée individuelle, qui s'ouvre dans n'importe quel navigateur.
- Diagnostic qualité des données : doublons, pondérations manquantes, réponses hors questionnaire, valeurs extrêmes... chaque problème se corrige en un clic par une règle du journal.
- Vérifications avant le rapport : ce qui manque (cible, référence, données) et où le corriger.
- Copies automatiques du projet à chaque ouverture, restaurables depuis « Mes projets ».
- Calcul de taille d'échantillon, pour préparer une enquête.
- Plan de suivi en Excel : la fiche de référence des indicateurs, avec méthode, fréquence et responsable.

### Installer

1. Téléchargez `SuiviEvalLab-<version>-installation.exe` ci-dessous (environ 240 Mo, Windows 10 ou 11, 64 bits).
2. L'installeur n'est pas encore signé. Windows SmartScreen affiche donc « Windows a protégé votre ordinateur » : cliquez sur « Informations complémentaires », puis « Exécuter quand même ».
3. L'installation se fait dans votre compte utilisateur et ne demande pas de droits d'administrateur. R et Python sont inclus.

Les projets créés avec la 0.2 s'ouvrent dans la 0.3. Pour vérifier le fichier, comparez son empreinte avec `SHA256SUMS.txt` : `Get-FileHash .\SuiviEvalLab-<version>-installation.exe`.

---

**Preview release, to be tested before any real use.**

SuiviEvalLab covers the whole monitoring and evaluation path, on your computer and offline: results framework, indicators, data import and cleaning, calculations in R with confidence intervals and survey design, Word report. An example project runs on real public survey data (REACH, Iraq, 2019 and 2020).

### New in 0.3

- A logo, and the "My projects" screen: your recent projects, their progress, reopening the last one.
- Kobo labels: the XLSForm questionnaire gives columns and codes their labels, in several languages. You can also type them.
- New indicators: counts, ratios (for example per 100 households), conditions on several columns, crossed breakdowns.
- Test assistant: compare groups, a value against a target, the same people twice. The conclusion is written in sentences and can go into the report.
- Word report on your organisation's template (cover page, styles, headers), with placeholders such as `{{content}}` and `{{project}}`.
- SPSS (.sav) and Stata (.dta) import with their labels; merge of two files by a key, for example individuals with their household.
- Read-only sharing: a dashboard in a single HTML file, with no individual data, that opens in any browser.
- Data quality diagnosis: duplicates, missing weights, answers outside the questionnaire, extreme values... each problem is fixed in one click by a journal rule.
- Checks before the report: what is missing (target, baseline, data) and where to fix it.
- Automatic copies of the project at each opening, restored from "My projects".
- Sample size calculator, to prepare a survey.
- Monitoring plan in Excel: the indicator reference sheet, with method, frequency and responsible person.

### Install

1. Download `SuiviEvalLab-<version>-installation.exe` below (about 240 MB, Windows 10 or 11, 64-bit).
2. The installer is not signed yet, so Windows SmartScreen shows "Windows protected your PC": click "More info", then "Run anyway".
3. It installs for your user account only, without administrator rights. R and Python are included.

Projects created with 0.2 open in 0.3. To check the file, compare its hash with `SHA256SUMS.txt`: `Get-FileHash .\SuiviEvalLab-<version>-installation.exe`.

Example data: REACH Initiative, Iraq Multi-Cluster Needs Assessments VII and VIII, Humanitarian Data Exchange, CC BY 4.0. Test data: REACH-UNICEF Bangladesh WASH surveys 2018, Humanitarian Data Exchange, CC BY 4.0. Licence: GPL-3.0-or-later.
