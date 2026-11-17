# La fiche du projet

La fiche du projet décrit ce sur quoi tout le reste s'appuie : qui finance, quand, où, avec qui, et comment les données sont ventilées. Elle s'ouvre par **Fiche du projet**, en bas du menu, et compte six onglets.

| Onglet | Contenu |
|---|---|
| **Profil** | Nom, code, pays, secteurs, bailleurs (avec leur convention et leur rythme de rapport), dates de début et de fin, devise, couleur du projet dans l'espace de travail |
| **Calendrier** | Périodes de rapportage générées à partir des dates, échéances, verrouillage |
| **Lieux** | Arbre des zones et des sites (région, district, site) |
| **Partenaires** | Organisations de mise en œuvre, leurs sites, leur rôle |
| **Désagrégations** | Sexe, âge, handicap, statut et ventilations propres au projet |
| **Équipe et sécurité** | Mot de passe du projet, membres et rôles, échanges, journal d'audit (voir le [guide de l'administrateur](../administration.md)) |

Un nouveau projet s'ouvre directement sur l'onglet Profil : on donne les dates, puis le calendrier se construit.

## Le profil

Les **bailleurs** s'ajoutent un par un, chacun avec le numéro de la convention et sa fréquence de rapport. Le **rapportage par** indique l'unité qui envoie les données à chaque période :

| Choix | Qui envoie | Exemple |
|---|---|---|
| Projet | Une seule saisie pour tout le projet | Petit projet mis en œuvre par une seule équipe |
| Partenaire | Chaque partenaire envoie ses chiffres | Consortium de plusieurs ONG |
| Lieu | Chaque site envoie ses chiffres | Centres de santé, écoles |
| Partenaire et lieu | Chaque partenaire, pour chacun de ses sites | Consortium présent sur plusieurs districts |

Ce choix détermine les envois attendus à chaque période (écran Réception) et les canevas Excel produits.

## Le calendrier

À partir des dates du projet, de la **périodicité** (mensuelle, trimestrielle, semestrielle, annuelle) et du **début de l'exercice**, l'application crée les périodes de rapportage : T1 2026, T2 2026, et ainsi de suite. Pour chaque période, deux échéances sont calculées : la date limite de remise des données par les partenaires et la date de remise du rapport au bailleur. Elles alimentent l'agenda et les tâches.

Une période passe par trois états :

| État | Sens |
|---|---|
| Ouverte | Les données peuvent être saisies et corrigées |
| Rapportée | Le rapport de la période a été remis ; les données restent modifiables |
| Verrouillée | Plus aucune valeur ne peut changer. Le verrouillage n'est possible que si tous les envois de la période sont validés |

Rouvrir une période verrouillée demande un motif écrit, gardé dans l'historique de la période et dans le journal d'audit.

## Les lieux

Les lieux forment un arbre : un district contient des sites, une région contient des districts. On peut les saisir un par un ou **coller une liste depuis Excel** (une colonne par niveau) : l'application construit l'arbre et signale les doublons. Un code peut être donné à chaque lieu (code administratif, identifiant DHIS2).

Quand on filtre le tableau de suivi sur un district, les valeurs de tous ses sites sont additionnées.

## Les partenaires

Chaque partenaire a un nom, un sigle, un rôle (mise en œuvre ou financement) et la liste de ses sites. Les sites d'un partenaire servent à préparer ses envois et ses canevas, et à limiter ce que voit son point focal quand le projet est partagé.

## Les désagrégations

Les ventilations courantes sont proposées toutes faites : sexe, tranches d'âge (découpage général ou découpage santé), handicap, statut de résidence (déplacés, retournés, population hôte), milieu (urbain, rural). On peut en créer d'autres. Chaque désagrégation reçoit automatiquement une catégorie **« Non précisé »**, pour les cas où la ventilation n'est pas connue : le total reste juste sans qu'il faille inventer une répartition.

Une désagrégation est ensuite choisie indicateur par indicateur (onglet Indicateurs).
