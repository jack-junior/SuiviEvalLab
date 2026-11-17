# Présentation de SuiviEvalLab

## À quoi sert l'application

SuiviEvalLab est un logiciel de bureau pour les équipes de suivi-évaluation. Il réunit dans une seule application le travail d'un chargé ou d'un responsable S&E, du document de projet jusqu'au rapport remis au bailleur :

- décrire le projet : bailleurs, calendrier de rapportage, lieux, partenaires, désagrégations ;
- construire le cadre logique selon le modèle du bailleur (Union européenne, USAID, Nations unies, Banque mondiale, FICR, ou niveaux propres) et choisir les indicateurs dans une bibliothèque de 146 fiches en 16 secteurs ;
- fixer les cibles par période et tenir le plan de suivi ;
- recevoir les données des partenaires et des sites (saisie, canevas Excel, KoboToolbox, ODK, DHIS2), les contrôler, les valider, verrouiller les périodes ;
- lire où en est chaque indicateur, expliquer les écarts ;
- suivre les activités, le budget, les retours et plaintes, les recommandations, les risques et les évaluations ;
- analyser les enquêtes avec R (pondération, plan de sondage, intervalles de confiance, comparaisons) ;
- produire les rapports périodiques au format de vingt bailleurs, le rapport d'enquête et les exports ;
- tenir l'agenda et les tâches de tous ses projets, et voir le portefeuille d'un coup d'œil ;
- travailler à plusieurs, partenaires compris, même hors ligne, avec des données chiffrées.

## Pour qui

L'application vise d'abord les chargés et responsables de suivi-évaluation des ONG nationales et internationales, puis les consultants en évaluation et les services de S&E des administrations. Elle suppose une bonne connaissance du métier (cadre logique, indicateurs, enquêtes), mais aucune compétence en programmation ni en logiciel statistique.

## Ce qui la distingue des outils habituels

Un chargé de S&E travaille en général avec plusieurs outils : Kobo pour la collecte, Excel pour le nettoyage et les tableaux, SPSS, Stata ou R pour les statistiques quand l'équipe en a les compétences, puis Word pour le rapport. Chaque passage d'un outil à l'autre est une copie manuelle, donc une source d'erreur, et le lien entre un chiffre du rapport et les données d'origine se perd.

SuiviEvalLab garde ce lien de bout en bout :

| Besoin | Pratique courante | Dans SuiviEvalLab |
|---|---|---|
| Nettoyer les données | Modifications directes dans Excel, sans trace | Le fichier d'origine n'est jamais modifié ; chaque correction est une règle du journal, justifiée, réversible, citée dans le rapport et exportable en script R |
| Calculer un pourcentage pondéré | Formules Excel, souvent sans pondération ni intervalle | Calcul par R avec le package `survey`, pondération, strates et grappes, intervalle de confiance à 95 % |
| Comparer deux enquêtes | Différence de deux pourcentages, sans test | Différence, intervalle de la différence, valeur p et taille d'effet, avec la conclusion rédigée |
| Choisir un test statistique | Demander à un statisticien | L'assistant pose la question en termes de métier et choisit le test adapté |
| Rédiger le rapport | Copier-coller les chiffres et les graphiques | Rapport Word produit à partir du projet, sur le modèle de l'organisation |
| Vérifier un résultat | Difficile | Chaque résultat fournit le script R qui le reproduit |

L'application fonctionne **sans connexion internet**. Les données restent sur les ordinateurs de l'équipe : rien n'est envoyé à l'éditeur. Les seules connexions sont celles que l'utilisateur choisit (serveurs de collecte, dossier partagé ou serveur relais de l'équipe) et la recherche de mises à jour, que l'organisation peut couper.

## Le fichier projet

Tout le travail d'un projet tient dans **un seul fichier** à l'extension `.sme` : le cadre de résultats, les indicateurs, une copie des données importées, le journal de nettoyage, les tests enregistrés et le modèle Word de l'organisation. Il n'y a pas de bouton « Enregistrer » : chaque modification est écrite immédiatement.

Ce fichier peut être copié, sauvegardé ou envoyé à un collègue qui a l'application : il retrouvera le projet dans l'état exact où il a été laissé. Une copie automatique est faite à chaque ouverture, ce qui permet de revenir en arrière après une erreur (voir [Outils](manuel/outils.md)).

## Versions

| Version | Contenu |
|---|---|
| 0.1 à 0.5 | Enquêtes : cadre de résultats, indicateurs, import, nettoyage tracé, calculs par R, comparaisons, tests, analyses libres, rapport Word |
| 1.0 | L'outil complet du S&E : fiche du projet et calendrier, réception et contrôle des données, suivi des indicateurs, Kobo, ODK et DHIS2, activités et budget, redevabilité et évaluations, rapports périodiques des bailleurs, agenda et tâches, portefeuille et tableau de bord, travail en équipe chiffré |

Les projets créés avec les versions 0.2 à 0.5 s'ouvrent dans la 1.0 sans perte ; une copie est faite avant leur mise à niveau.

## Organisation de ce document

1. **Présentation** (ce chapitre) et **architecture**.
2. **Manuel de l'application** : chaque écran, dans l'ordre du travail.
3. **Guides** : administrateur (équipe, sécurité), partenaire, installation du serveur relais, protection des données.
4. **Contribuer**, **tester** et **test pilote**.
5. **Annexes** : glossaire, méthodes statistiques, sources des données.

Une version anglaise de la documentation est disponible (section *English*).
