**Version préliminaire, à tester avant tout usage réel.**

SuiviEvalLab couvre le parcours complet du suivi-évaluation, sur votre ordinateur et sans connexion internet : cadre de résultats, indicateurs, import et nettoyage des données, calcul par R avec intervalles de confiance et plan d'enquête, rapport Word. Un projet d'exemple fonctionne sur des données d'enquête réelles et publiques (REACH, Irak, 2019 et 2020).

### Nouveautés de la 0.4

- Cadre de résultats selon le modèle de votre bailleur : standard, Union européenne (cadre logique), USAID, Nations unies, Banque mondiale, ou vos propres niveaux (2 à 4). Les noms des niveaux suivent partout, jusqu'au rapport et au plan de suivi. Chaque résultat peut porter ses hypothèses.
- Indicateurs de suivi de routine : les valeurs relevées dans les registres et rapports d'activité (personnes formées, salles réhabilitées, taux de fréquentation), saisies ou collées depuis Excel période par période, avec le prévu, une répartition (femmes et hommes) et le rythme par rapport au prévu.
- Nettoyage avancé, sans écrire de code : calculer une variable (somme, moyenne, différence, rapport, nombre de « oui »), regrouper un nombre en classes, durées d'entretien et âges à partir des dates Kobo ou Excel, contrôles de cohérence (repérer, exclure ou vider les lignes incohérentes), remplacement sous condition, nettoyage du texte (espaces, majuscules, accents).
- Empiler des fichiers de même structure, par exemple un fichier par région ou par équipe d'enquêteurs.
- Le journal de nettoyage s'exporte en script R : un relecteur peut refaire tout le nettoyage sans l'application et obtenir la même table.
- Le projet d'exemple contient maintenant un indicateur de suivi de routine. L'accès à l'exemple et au calcul de taille d'échantillon est déplacé en lien discret sur l'accueil.

### Installer

1. Téléchargez `SuiviEvalLab-<version>-installation.exe` ci-dessous (environ 240 Mo, Windows 10 ou 11, 64 bits).
2. L'installeur n'est pas encore signé. Windows SmartScreen affiche donc « Windows a protégé votre ordinateur » : cliquez sur « Informations complémentaires », puis « Exécuter quand même ».
3. L'installation se fait dans votre compte utilisateur et ne demande pas de droits d'administrateur. R et Python sont inclus.

Si la 0.3 est installée, elle propose cette version d'elle-même : redémarrez l'application pour l'installer. Les projets créés avec une version précédente s'ouvrent dans la 0.4 (leur cadre prend le modèle standard). Pour vérifier le fichier, comparez son empreinte avec `SHA256SUMS.txt` : `Get-FileHash .\SuiviEvalLab-<version>-installation.exe`.

---

**Preview release, to be tested before any real use.**

SuiviEvalLab covers the whole monitoring and evaluation path, on your computer and offline: results framework, indicators, data import and cleaning, calculations in R with confidence intervals and survey design, Word report. An example project runs on real public survey data (REACH, Iraq, 2019 and 2020).

### New in 0.4

- Results framework following your donor's model: standard, European Union (logframe), USAID, United Nations, World Bank, or your own levels (2 to 4). Level names follow everywhere, up to the report and the monitoring plan. Each result can carry its assumptions.
- Routine monitoring indicators: values recorded from registers and activity reports (people trained, classrooms rehabilitated, attendance rates), typed or pasted from Excel period by period, with the planned value, a breakdown (women and men) and progress against the plan.
- Advanced cleaning, without writing code: compute a variable (sum, mean, difference, ratio, number of "yes"), group a number into classes, interview durations and ages from Kobo or Excel dates, consistency checks (flag, exclude or empty inconsistent rows), replacement under conditions, text cleaning (spaces, case, accents).
- Stack files of the same structure, for example one file per region or per enumerator team.
- The cleaning journal exports as an R script: a reviewer can redo the whole cleaning without the app and get the same table.
- The example project now includes a routine monitoring indicator. The example and the sample size calculator are now discreet links on the home screen.

### Install

1. Download `SuiviEvalLab-<version>-installation.exe` below (about 240 MB, Windows 10 or 11, 64-bit).
2. The installer is not signed yet, so Windows SmartScreen shows "Windows protected your PC": click "More info", then "Run anyway".
3. It installs for your user account only, without administrator rights. R and Python are included.

If 0.3 is installed, it offers this version by itself: restart the app to install it. Projects created with an earlier version open in 0.4 (their framework takes the standard model). To check the file, compare its hash with `SHA256SUMS.txt`: `Get-FileHash .\SuiviEvalLab-<version>-installation.exe`.

Example data: REACH Initiative, Iraq Multi-Cluster Needs Assessments VII and VIII, Humanitarian Data Exchange, CC BY 4.0. Test data: REACH-UNICEF Bangladesh WASH surveys 2018, Humanitarian Data Exchange, CC BY 4.0. Licence: GPL-3.0-or-later.
