# Annexes

## Glossaire

| Terme | Définition |
|---|---|
| **Cadre de résultats** | La chaîne logique du projet : impact, effets, extrants, activités. Équivalent du cadre logique |
| **Collecte** | Une enquête ou une série de données à un moment du projet : référence, mi-parcours, fin de projet, suivi |
| **Référence** | La valeur de l'indicateur au début du projet (*baseline*) |
| **Cible** | La valeur que le projet vise pour l'indicateur |
| **Taux de réalisation** | La part du chemin parcouru entre la référence et la cible |
| **Désagrégation** | Le calcul de l'indicateur pour chaque groupe (sexe, région, groupe de population) |
| **Plan d'enquête** (plan de sondage) | La façon dont l'échantillon a été tiré : pondération, strates, grappes. Il change les estimations et surtout leurs intervalles |
| **Pondération** (poids) | Le nombre de personnes ou de ménages de la population que représente chaque enquêté |
| **Poids normalisés** | Des poids mis à l'échelle pour que leur moyenne vaille 1 : ils corrigent les pourcentages et les moyennes, mais pas les effectifs |
| **Strate** | Un sous-ensemble de la population dans lequel l'échantillon a été tiré séparément (région, milieu) |
| **Grappe** | Un groupe d'unités tirées ensemble (village, zone de dénombrement), dans un sondage à plusieurs degrés |
| **Effet de plan** | Le facteur par lequel le plan d'enquête augmente la variance par rapport à un tirage aléatoire simple de même taille |
| **Intervalle de confiance à 95 %** (IC) | La fourchette dans laquelle se trouve très probablement la vraie valeur dans la population, compte tenu de l'échantillon |
| **Valeur p** | La probabilité d'observer une différence au moins aussi grande si, en réalité, il n'y en avait aucune. En dessous de 0,05, on parle de différence statistiquement significative |
| **Taille d'effet** | Une mesure de l'importance pratique d'une différence, indépendante de la taille de l'échantillon (h et d de Cohen, V de Cramér, g de Hedges) |
| **Puissance** | La probabilité qu'une enquête détecte un changement réel d'une taille donnée |
| **XLSForm** | Le format Excel des questionnaires Kobo et ODK : une feuille des questions (`survey`), une feuille des choix (`choices`) |
| **Libellé** | Le texte lisible d'une colonne ou d'un code (« À moins de 2 km » pour `within_2km`) |
| **Journal de nettoyage** | La liste ordonnée des règles appliquées aux données, avec leurs justifications et leurs effets |
| **Fusion** | Le rattachement des lignes d'un fichier à celles d'un autre par une clé (individus à leur ménage) |
| **Fichier `.sme`** | Le fichier projet de SuiviEvalLab, qui contient tout le projet |

## Méthodes statistiques

Toutes les méthodes sont celles du package R `survey` (Lumley) ou des fonctions de base de R. Le détail technique et les références de validation sont dans `docs/statistics.md`.

**Estimation d'un pourcentage.** Avec un plan d'enquête : `svyciprop(method = "logit")`, qui garde l'intervalle entre 0 et 100 %. Sans plan : intervalle de Wilson.

**Estimation d'une moyenne, d'un effectif, d'un ratio.** Avec un plan : `svymean`, `svytotal`, `svyratio`, erreurs types par linéarisation de Taylor. Sans plan : intervalle de Student pour la moyenne, méthode delta pour le ratio.

**Désagrégation.** Chaque groupe est estimé sur le sous-ensemble du même plan d'enquête (et non en refaisant un plan par groupe), ce qui donne des erreurs types correctes. Les strates qui n'ont qu'une unité primaire sont traitées par la méthode « adjust ».

**Comparaison de deux enquêtes indépendantes.** Chaque enquête est estimée avec son propre plan. La différence a pour erreur type la racine de la somme des carrés des deux erreurs types ; elle est testée par un test z. Sans plan : khi-deux pour deux proportions, test t de Welch pour deux moyennes.

**Taux de réalisation et statut.** (valeur actuelle − référence) / (cible − référence). Atteint à partir de 90 %, en bonne voie de 60 à 90 %, en retard en dessous. Une valeur actuelle déjà au niveau de la cible, dans le sens souhaité, est toujours « atteinte ».

**Taille d'échantillon.** Formule de Cochran pour estimer une part ou une moyenne ; `power.prop.test` et `power.t.test` pour détecter un changement entre deux collectes ; puis effet de plan, correction pour population finie (estimations seulement), nombre de domaines et taux de réponse.

**Diagnostic qualité.** Valeurs extrêmes au-delà de trois écarts interquartiles, sur échelle logarithmique pour les montants positifs dont le maximum dépasse vingt fois la médiane ; non signalées si elles dépassent 2 % des valeurs.

**Validation.** Chaque fonction R est comparée à l'appel direct du package de référence. Les résultats du moteur sont recalculés indépendamment avec polars dans les tests Python. Les valeurs du kit de test sont recalculées dans R à partir des fichiers bruts.

## Données d'exemple et de test

Toutes les données utilisées sont publiques, publiées sur Humanitarian Data Exchange (HDX) sous licence Creative Commons Attribution 4.0 (CC BY 4.0).

| Données | Producteur | Usage |
|---|---|---|
| Iraq Multi-Cluster Needs Assessment VII, 2019 | REACH Initiative, Assessment Working Group Iraq | Projet d'exemple (extrait), kit de test (fichier complet) |
| Iraq Multi-Cluster Needs Assessment VIII, 2020 | REACH Initiative | Projet d'exemple (extrait), kit de test (fichier complet) |
| Bangladesh WASH household baseline survey in camps, avril 2018 | REACH Initiative, UNICEF | Libellés Kobo, diagnostic qualité, fusion |
| Bangladesh WASH household survey, monsoon follow-up, octobre 2018 | REACH Initiative, UNICEF | Fusion refusée, extraits SPSS et Stata |

Les fichiers sont téléchargés par `tools/datasets/fetch.py`, qui vérifie leur empreinte SHA-256 ; leurs adresses figurent dans `tools/datasets/sources.json`.

## Versions des composants (version 0.3)

| Composant | Version |
|---|---|
| Electron | 44.7 |
| React | 19.3 |
| TypeScript | 5.9 |
| Python intégré | 3.12.10 |
| polars | 2.0.0 |
| python-docx | 1.2.0 |
| pyreadstat | 1.3.7 |
| xlsxwriter | 3.2.9 |
| R intégré | 4.4.3 |
| survey (R) | 4.5 |
| nanoarrow (R) | 0.8.0 |
| electron-updater | 6.8.10 |
