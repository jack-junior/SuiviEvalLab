# Réception des données et suivi des indicateurs

Le suivi est le cœur du travail quotidien : recevoir les chiffres des partenaires ou des sites, les vérifier, les valider, puis lire où en est chaque indicateur par rapport à sa cible.

## Le plan de suivi

L'écran **Plan de suivi** rassemble, pour chaque indicateur, sa fiche (définition, méthode de calcul, source, fréquence, responsable), sa valeur de référence et ses **cibles par période**. Une cible révisée garde l'ancienne valeur et la raison de la révision dans son historique. Le plan s'exporte en Excel, et le calendrier de collecte (qui collecte quoi, quand) en découle.

Un indicateur de suivi a un **type**, qui fixe la façon dont ses valeurs s'additionnent :

| Type | Saisie | Entre partenaires ou lieux | Dans le temps (par défaut) |
|---|---|---|---|
| Nombre | Une valeur | Somme | Cumul |
| Pourcentage, taux pour une base, ratio | Numérateur et dénominateur | Somme des numérateurs sur somme des dénominateurs | Dernière période |
| Moyenne | Valeur et effectif | Moyenne pondérée par les effectifs | Dernière période |
| Médiane, score, échelle | Une valeur | Non additionnable : affichée par unité | Dernière période |
| Jalon | Fait ou non fait | Atteint quand toutes les unités l'ont atteint | Dernière période |

Un pourcentage n'est jamais calculé comme la moyenne de pourcentages : sans numérateur ni dénominateur, l'application refuse d'agréger et l'explique. Le mode de cumul dans le temps peut être changé (somme, dernière valeur, moyenne, maximum).

La **cible à date** est la somme des cibles des périodes écoulées. Sans cibles par période, l'application trace une ligne droite de la référence à la cible finale et le signale.

## La réception

L'écran **Réception** montre, pour la période choisie, les envois attendus selon le mode de rapportage du projet (voir [Fiche du projet](projet.md)) et leur état.

| État | Sens |
|---|---|
| Brouillon | En cours de saisie |
| Soumis | Envoyé par le partenaire ou le site |
| En vérification | Ouvert par la personne qui contrôle |
| Renvoyé | Retourné avec un commentaire, à corriger |
| Validé | Accepté : ses valeurs comptent dans le suivi |
| Verrouillé | La période est close |

Seules les valeurs **validées** comptent dans le tableau de suivi. Une option permet d'afficher aussi les valeurs provisoires, toujours marquées comme telles.

Les données arrivent de quatre façons :

1. **Saisie** dans la grille de l'envoi, avec les catégories de chaque désagrégation.
2. **Canevas Excel** : un classeur protégé par partenaire (ou site) et par période, à remplir sans l'application. Au retour, le classeur est refusé s'il vient d'un autre projet, si ses lignes ont été déplacées ou si les indicateurs ont changé depuis. Un canevas renvoyé pour un envoi déjà validé est traité comme une **révision** : les différences sont affichées et ne s'appliquent qu'en rouvrant l'envoi avec un motif.
3. **DHIS2** : un indicateur dont la source est DHIS2 reçoit les valeurs de l'élément de données ou de l'indicateur DHIS2 correspondant, par période et par lieu. Les envois validés ne sont jamais modifiés par un import.
4. **Partenaires équipés de l'application** : leurs envois arrivent par synchronisation (voir le [guide du partenaire](../partenaire.md)).

Chaque envoi peut porter des **pièces justificatives** (listes de présence, registres scannés, rapports) : 50 Mo par fichier, 2 Go par projet.

## Les contrôles

À chaque enregistrement, l'application contrôle les valeurs.

| Contrôle | Gravité |
|---|---|
| Valeur manquante pour un indicateur attendu dans la période (selon sa fréquence) | À vérifier |
| Ventilation manquante | À vérifier |
| Total différent de la somme des catégories | À vérifier |
| Numérateur supérieur au dénominateur | Bloquant |
| Pourcentage hors de 0 à 100, nombre négatif | Bloquant |
| Valeur hors des bornes plausibles fixées pour l'indicateur | À vérifier |
| Écart inhabituel avec la période précédente | Information |
| Envoi en retard | Information |

Une alerte **bloquante** doit être corrigée. Une alerte **à vérifier** se corrige ou se justifie par écrit ; la justification reste attachée à la valeur. Un envoi ne peut être validé tant qu'une alerte reste ouverte.

## Le suivi des indicateurs

L'écran **Suivi des indicateurs** donne, pour la période choisie et pour chaque indicateur : la valeur de la période, la valeur cumulée, la cible à date, le taux de réalisation, la tendance et le statut.

| Statut | Règle |
|---|---|
| Atteint | La cible finale est atteinte |
| En bonne voie | Au moins 90 % de la cible à date (seuil réglable) |
| En retard | En dessous du seuil |
| Sans données | Rien de validé encore |

Le tableau se filtre par lieu (un district additionne ses sites), par partenaire et par catégorie de désagrégation. Un clic sur un indicateur ouvre sa ventilation et son historique. Les estimations d'enquête rattachées à une période (voir [Données](donnees.md)) apparaissent dans le même tableau, marquées « enquête », avec leur intervalle de confiance au survol.

Un écart à la cible se **commente** : le commentaire est repris dans le rapport de la période. Un tableau croisé rapide permet de lire un indicateur par lieu et par catégorie.

## Les personnes uniques

Pour un indicateur qui compte des personnes (personnes formées, ménages assistés), la même personne peut être comptée à plusieurs périodes ou par plusieurs partenaires. Si l'on colle la liste des identifiants à la réception, l'application ne garde que leur **pseudonyme** (une empreinte calculée avec une clé propre au projet, qui ne permet pas de retrouver l'identifiant) et compte chaque personne une seule fois dans le cumul. Les doublons possibles sont signalés.

## Les serveurs de collecte

Le bouton **Serveurs** (écrans Données et Réception) relie le projet à KoboToolbox, ODK Central ou DHIS2. Le jeton ou le mot de passe est gardé par l'application sur l'ordinateur, chiffré par le système, jamais dans le fichier projet. Pour Kobo et ODK, le formulaire choisi devient un jeu de données ; chaque synchronisation relit les soumissions, et le nettoyage et les calculs sont refaits.
