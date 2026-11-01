**Version préliminaire, à tester avant tout usage réel.**

SuiviEvalLab couvre le parcours complet du suivi-évaluation, sur votre ordinateur et sans connexion internet : cadre de résultats, indicateurs, import et nettoyage des données, calcul par R avec intervalles de confiance et plan d'enquête, rapport Word. Un projet d'exemple fonctionne sur des données d'enquête réelles et publiques (REACH, Irak, 2019 et 2020).

### Nouveautés de la 0.5

- Analyses libres, sur le modèle de JASP : statistiques descriptives, tableaux croisés avec le test du khi-deux adapté aux enquêtes, comparaison de moyennes, corrélations, régressions linéaire et logistique, différence de différences. Les résultats se mettent à jour à chaque changement d'option, avec une lecture en mots, les tableaux, les graphiques et le code R qui les reproduit. Tout suit le plan d'enquête du fichier (pondération, strates, grappes).
- Nettoyage libre : un tableau des données où l'on trie, filtre et corrige une cellule d'un double clic (chaque correction entre dans le journal), et un éditeur de formules en français ou en anglais, par exemple `si(age >= 18 et sexe = "F"; 1; 0)`, qui signale l'erreur et propose la bonne colonne.
- Scripts R pour les utilisateurs avancés, dans le nettoyage comme dans les analyses. Un projet reçu d'une autre personne qui contient du code R l'affiche et demande votre accord avant de l'exécuter.
- Contenu du rapport au choix : sections et ordre, indicateurs et ce qui est montré pour chacun, analyses, tests, journal de nettoyage. Le choix est enregistré avec le projet.

### Installer

1. Téléchargez `SuiviEvalLab-<version>-installation.exe` ci-dessous (environ 240 Mo, Windows 10 ou 11, 64 bits).
2. L'installeur n'est pas encore signé. Windows SmartScreen affiche donc « Windows a protégé votre ordinateur » : cliquez sur « Informations complémentaires », puis « Exécuter quand même ».
3. L'installation se fait dans votre compte utilisateur et ne demande pas de droits d'administrateur. R et Python sont inclus.

Si une version précédente est installée, elle propose celle-ci d'elle-même : redémarrez l'application pour l'installer. Les projets créés avec une version précédente s'ouvrent dans la 0.5. Pour vérifier le fichier, comparez son empreinte avec `SHA256SUMS.txt` : `Get-FileHash .\SuiviEvalLab-<version>-installation.exe`.

---

**Preview release, to be tested before any real use.**

SuiviEvalLab covers the whole monitoring and evaluation path, on your computer and offline: results framework, indicators, data import and cleaning, calculations in R with confidence intervals and survey design, Word report. An example project runs on real public survey data (REACH, Iraq, 2019 and 2020).

### New in 0.5

- Custom analyses, in the spirit of JASP: descriptive statistics, crosstabs with the chi-square test adapted to surveys, comparison of means, correlations, linear and logistic regressions, difference in differences. Results update at each change of option, with a reading in words, tables, charts and the R code that reproduces them. Everything follows the file's sampling design (weights, strata, clusters).
- Free cleaning: a data table where you sort, filter and correct a cell by double-clicking it (each correction goes into the journal), and a formula editor in French or English, for example `if(age >= 18 and sex = "F", 1, 0)`, that points at the error and suggests the right column.
- R scripts for advanced users, in cleaning and in analyses. A project received from someone else that contains R code shows it and asks for your agreement before running it.
- Report content of your choice: sections and their order, indicators and what is shown for each, analyses, tests, cleaning journal. The choice is saved with the project.

### Install

1. Download `SuiviEvalLab-<version>-installation.exe` below (about 240 MB, Windows 10 or 11, 64-bit).
2. The installer is not signed yet, so Windows SmartScreen shows "Windows protected your PC": click "More info", then "Run anyway".
3. It installs for your user account only, without administrator rights. R and Python are included.

If an earlier version is installed, it offers this one by itself: restart the app to install it. Projects created with an earlier version open in 0.5. To check the file, compare its hash with `SHA256SUMS.txt`: `Get-FileHash .\SuiviEvalLab-<version>-installation.exe`.

Example data: REACH Initiative, Iraq Multi-Cluster Needs Assessments VII and VIII, Humanitarian Data Exchange, CC BY 4.0. Test data: REACH-UNICEF Bangladesh WASH surveys 2018, Humanitarian Data Exchange, CC BY 4.0. Licence: GPL-3.0-or-later.
