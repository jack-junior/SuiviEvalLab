# Rapports périodiques et exports

L'écran **Rapport** a trois onglets : les rapports périodiques, le rapport d'enquête (voir [Rapport et livrables](rapport.md)) et les exports.

## Les rapports périodiques

Un rapport périodique se prépare en trois choix.

1. **Le canevas.** Vingt canevas de bailleurs sont fournis : Union européenne, ECHO, USAID, AFD, Expertise France, Banque mondiale, BAD, PNUD, UNICEF, PAM, HCR, FNUAP, OMS, Fonds mondial, Gavi, FICR, GIZ, Enabel, FCDO et Fondation Gates. S'y ajoutent un canevas générique d'ONG, le plan de S&E et les fiches indicateurs. Chaque canevas reprend les sections et l'ordre attendus par le bailleur.
2. **La période couverte** : une période (rapport trimestriel), plusieurs (rapport annuel) ou tout le projet (rapport final).
3. **La langue** : français ou anglais.

Chaque section est soit **remplie depuis le projet**, soit **rédigée** dans l'application.

| Sections remplies | Contenu |
|---|---|
| Suivi des indicateurs | Référence, cibles, réalisé de la période et cumulé, taux, statut |
| Avancement par résultat | Pour chaque résultat, ses indicateurs et ses activités |
| Écarts | Les écarts à la cible et leurs commentaires |
| Activités | Réalisées, en cours, en retard |
| Budget | Prévu, dépensé, taux d'exécution par ligne |
| Bénéficiaires | Personnes atteintes, ventilées |
| Retours et plaintes | Nombre de cas par catégorie et délais (jamais le contenu d'un cas sensible) |
| Recommandations, risques, leçons | Leur état à la fin de la période |
| Enquêtes et évaluations | Résultats et état d'avancement |
| Cadre logique, calendrier de collecte, fiches indicateurs | Tels que définis dans le projet |

Le texte d'une section rédigée est gardé : il revient à la génération suivante du même rapport, pour être relu plutôt que réécrit. Si le modèle Word de l'organisation est chargé (en-tête, styles, logo), il est utilisé.

On peut aussi créer un **canevas personnel** : renommer, réordonner, retirer ou ajouter des sections, à partir d'un canevas existant.

Avant de générer, les **vérifications** signalent ce qui fragiliserait le rapport : envois non validés, écarts sans commentaire, période non verrouillée, indicateurs sans cible.

## Les exports

| Export | Format | Usage |
|---|---|---|
| Tableau de suivi d'une période | Excel | Envoi au bailleur, avec les valeurs de chaque période |
| Données validées à plat | Excel ou CSV | Une ligne par valeur : indicateur, période, lieu, partenaire, catégorie |
| Paquet de données | `.smepack` | Pour le siège ou le bailleur qui suit plusieurs projets : les indicateurs et leurs valeurs, sans aucune donnée personnelle ; il s'ajoute au tableau de bord du destinataire |
| Page de partage | HTML | Une page autonome avec le tableau de suivi et les résultats d'enquête, lisible dans un navigateur |
| Agenda | `.ics` | Les échéances du projet dans un autre agenda |
