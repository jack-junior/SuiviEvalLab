# Tester l'application

Deux sortes de tests se complètent. Les **tests automatiques** vérifient à chaque modification que rien ne casse. Les **tests par des personnes** trouvent ce qu'une machine ne voit pas : un écran confus, un message incompréhensible, une attente trop longue, un enchaînement qui ne correspond pas à la pratique du terrain.

## Les tests automatiques

| Série | Nombre | Ce qu'elle garantit |
|---|---|---|
| Fonctions statistiques R | 4 fichiers de tests | Chaque estimation, intervalle, comparaison, test et taille d'échantillon égale l'appel direct au package de référence (écart inférieur à 10⁻⁹) ou une valeur publiée |
| Moteur Python | 36 tests | Fichier projet et migration, import de tous les formats, libellés Kobo, nettoyage, qualité, fusion, indicateurs, tests, rapport Word et modèle d'organisation, plan Excel, tableau de bord, copies, vérifications ; les chiffres sont recalculés indépendamment avec polars |
| Fichiers originaux | 2 tests | Les quatre enquêtes complètes de HDX (jusqu'à 436 colonnes) s'importent et se fusionnent correctement |
| Parcours complet | 1 scénario | L'application installée sous Windows est pilotée comme par un utilisateur, du projet vide au rapport |
| Mise à jour | 1 scénario | L'application installée se met à jour seule et respecte la stratégie de groupe |

Ils tournent sur chaque pull request (voir [Contribuer](contribuer.md)). Une modification ne peut pas être fusionnée si l'un d'eux échoue.

## Le kit de test

Le kit de test est un dossier à remettre aux testeurs. Il contient :

| Élément | Contenu |
|---|---|
| `GUIDE-DE-TEST.docx` | 19 scénarios pas à pas, avec le résultat attendu et un tableau où noter ce qui a été obtenu |
| `donnees/01` à `04` | Les fichiers originaux de quatre enquêtes publiques (Irak 2019 et 2020, Bangladesh 2018 référence et suivi), identiques octet pour octet à ceux publiés sur HDX |
| `donnees/05` | Un extrait au format SPSS et Stata, avec libellés |
| `modeles/` | Un modèle Word d'organisation pour tester le rapport |
| `LISEZMOI.txt`, `SOURCES.txt` | Mode d'emploi, origine, licence et empreinte de chaque fichier |

Les **résultats attendus** du guide ont été obtenus deux fois : par l'application, en suivant exactement les étapes, puis directement dans R avec le package `survey` à partir des fichiers bruts, sans l'application. Les deux concordent à la dernière décimale affichée. Si un testeur obtient autre chose, c'est un problème à signaler.

### Les scénarios

| N° | Scénario | Ce qui est vérifié |
|---|---|---|
| 1 | Installation et premier lancement | Installation sans droits d'administrateur, démarrage des moteurs |
| 2 | Projet d'exemple | Vue d'ensemble et statuts |
| 3 | Créer un projet et son cadre | Projet vide, impact, effet |
| 4 | Importer l'enquête de référence | Fichier original de 436 colonnes, feuille et pondération proposées |
| 5 | Diagnostic qualité | Valeurs extrêmes signalées sur des données réelles |
| 6 | Nettoyage | Exclusion de lignes et recodage, effet de chaque règle |
| 7 | Enquête de fin de projet | Plan stratifié, poids normalisés |
| 8 | Indicateur en pourcentage | Valeurs, intervalles, comparaison, réalisation, désagrégation |
| 9 | Indicateur en effectif | Avertissement sur des poids à des échelles différentes |
| 10 | Indicateur en moyenne | Différence non significative |
| 11 | Assistant de tests | Test de Rao-Scott, conclusion rédigée |
| 12 | Fichier Kobo avec questionnaire | Libellés, doublons, correction en un clic |
| 13 | Fusion | Contenants rattachés à leur ménage |
| 14 | Fusion refusée | Clé répétée détectée |
| 15 | SPSS et Stata | Libellés des variables et des valeurs |
| 16 | Rapport et livrables | Vérifications, rapport Word, modèle d'organisation, plan Excel, tableau de bord |
| 17 | Taille d'échantillon | 641 et 646 enquêtés |
| 18 | Copies automatiques | Restauration après une suppression |
| 19 | Langue et mises à jour | Interface en anglais, vérification des mises à jour |

Quelques valeurs de référence du guide, sur les fichiers originaux d'Irak :

| Indicateur | Référence 2019 | Fin de projet 2020 | Comparaison |
|---|---|---|---|
| Ménages avec une école primaire à moins de 2 km | 76,5 % (IC 74,5 à 78,5 ; n = 8 838) | 85,9 % (IC 83,2 à 88,2 ; n = 3 838) | + 9,4 points (IC 6,2 à 12,5), p < 0,001 |
| Nombre moyen d'enfants par ménage | 2,19 (IC 2,09 à 2,28) | 2,19 (IC 2,10 à 2,29) | Non significatif, p = 0,935 |

### Ce qu'on attend des testeurs

Pour chaque scénario, noter dans le guide ce qui a été obtenu, puis « OK » ou « Problème », et surtout les **remarques** : un bouton difficile à trouver, un mot peu clair, un calcul qui a pris longtemps, une étape qui ne correspond pas à la façon de travailler sur le terrain. Ces retours sont aussi utiles que les erreurs de calcul.

### Refaire le kit pour une nouvelle version

Le générateur est dans le dépôt (`tools/test-kit/`). Il télécharge les fichiers originaux en vérifiant leur empreinte, rejoue chaque scénario dans le moteur, puis écrit le guide avec les nouveaux résultats attendus. Le mode d'emploi est dans `tools/test-kit/README.md`.

## Un cas réel trouvé par le kit

En préparant le kit sur les fichiers originaux d'Irak, l'indicateur « ménages ayant retiré un enfant de l'école » passait de 24 304 ménages en 2019 à 47 en 2020, une baisse « statistiquement significative ». En réalité, les poids de 2019 extrapolent à la population (poids moyen 96,6) alors que ceux de 2020 sont normalisés (poids moyen 1,15) : comparer ces deux effectifs n'a aucun sens. L'application affichait le résultat sans prévenir ; elle avertit désormais dans l'analyse, dans les vérifications avant le rapport et dans le diagnostic qualité. C'est exactement le type de problème que seuls des tests sur des données réelles révèlent.
