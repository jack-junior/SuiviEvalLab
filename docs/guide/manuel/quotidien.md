# Aujourd'hui, agenda et tâches

L'application s'ouvre sur ce qu'il y a à faire. Deux niveaux existent : l'**espace de travail**, qui réunit tous les projets de l'utilisateur, et le **projet** ouvert.

## L'espace de travail

Sans projet ouvert, le menu propose quatre écrans.

| Écran | Contenu |
|---|---|
| **Aujourd'hui** | Ce qui est en retard et ce qui arrive dans les jours suivants, pour tous les projets : envois attendus, rapports à remettre, tâches, plus les tâches personnelles qui ne dépendent d'aucun projet |
| **Agenda** | Le calendrier commun de tous les projets, mois par mois, avec les événements personnels |
| **Tableau de bord** | La situation de chaque projet et du portefeuille (voir [Portefeuille](portefeuille.md)) |
| **Projets** | La liste des projets, leur création, leur ouverture, leurs copies automatiques, l'archivage |

Les projets sont lus sans être modifiés : ouvrir l'espace de travail n'écrit rien dans les fichiers. Un projet protégé par un mot de passe apparaît avec la mention « Protégé par un mot de passe » : ses échéances ne sont visibles qu'une fois le projet ouvert.

## Aujourd'hui du projet

Dans un projet, l'écran **Aujourd'hui** regroupe :

- les envois de la période en cours : reçus, à vérifier, en retard ;
- les alertes de contrôle qui attendent une correction ou une justification ;
- les écarts entre réalisé et cible qui n'ont pas encore de commentaire ;
- les activités en retard, les retours et plaintes hors délai, les actions de recommandations dépassées ;
- les tâches générées par l'application et celles saisies par l'équipe ;
- ce qui a changé depuis la dernière ouverture du projet.

Chaque ligne mène à l'écran où l'on traite le sujet.

## L'agenda

L'agenda du projet présente deux vues, le mois et les tâches. Il montre les échéances tirées du calendrier (remise des données, remise du rapport), les étapes des évaluations, les réunions, les jalons des activités et les événements saisis. Un événement peut être ponctuel ou répété.

L'agenda s'exporte au format iCalendar (`.ics`) pour Outlook, Google Agenda ou Thunderbird, et un fichier `.ics` reçu peut être importé.

## Les tâches

Il existe deux sortes de tâches.

| Sorte | Origine | Comment elle se ferme |
|---|---|---|
| **Générée** | L'application, à partir de l'état du projet : relancer un partenaire en retard, valider un envoi, commenter un écart, revue de qualité annuelle d'un indicateur, données personnelles à supprimer | D'elle-même, quand la situation est réglée |
| **Saisie** | L'équipe : titre, échéance, priorité, responsable, répétition éventuelle | À la main |

Le **tableau des tâches** les classe par état (à faire, en cours, en attente, faite). Les actions décidées en réunion et les actions des recommandations deviennent aussi des tâches.
