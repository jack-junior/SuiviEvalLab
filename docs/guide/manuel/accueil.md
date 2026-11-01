# Prise en main et accueil

## Installer l'application

1. Téléchargez `SuiviEvalLab-<version>-installation.exe` sur la page *Releases* du dépôt GitHub (Windows 10 ou 11, 64 bits, environ 250 Mo).
2. Lancez-le. L'installeur n'étant pas encore signé, Windows peut afficher « Windows a protégé votre ordinateur » : cliquez sur « Informations complémentaires », puis « Exécuter quand même ».
3. L'installation se fait dans le compte de l'utilisateur, sans droits d'administrateur. Un raccourci est créé sur le bureau.

Pour passer d'une version à la suivante, il n'est pas nécessaire de désinstaller : le nouvel installeur remplace l'ancienne version. Depuis la version 0.3, les mises à jour arrivent d'elles-mêmes (voir [Outils](outils.md)).

## L'écran d'accueil

![Écran d'accueil](../img/01-accueil.png)

*Figure 3. L'écran d'accueil, avec la liste « Mes projets ».*

L'accueil propose deux blocs et deux liens :

| Élément | Action | Ce qui se passe |
|---|---|---|
| **Nouveau projet** | « Créer un projet », saisir un nom, choisir le modèle de cadre de résultats, puis « Choisir l'emplacement » | Un fichier `.sme` vide est créé à l'endroit choisi et le projet s'ouvre sur le cadre de résultats |
| **Ouvrir un projet** | « Ouvrir un fichier » | Ouvre un fichier `.sme` existant, par exemple reçu d'un collègue |
| Lien **« Découvrir avec un projet d'exemple »** | Choisir l'emplacement du fichier | Crée un projet complet à partir de deux enquêtes publiques (REACH, Irak, 2019 et 2020) : cadre, trois indicateurs d'enquête, un indicateur de suivi de routine, données, nettoyage. Idéal pour découvrir l'application |
| Lien **« Calculer une taille d'échantillon »** | Un clic | Ouvre le calculateur sans ouvrir de projet (voir [Outils](outils.md)) |

### Créer un projet

![Création d'un projet](../img/04-nouveau-projet.png)

*Figure 4. Le choix du modèle de cadre de résultats à la création d'un projet.*

Le panneau demande le nom du projet et le **modèle de cadre de résultats**, c'est-à-dire la chaîne de niveaux attendue par le bailleur :

| Modèle | Niveaux |
|---|---|
| **Standard** | Impact, Effet, Extrant, Activité |
| **Union européenne (cadre logique)** | Objectif global, Objectif spécifique, Produit, Activité |
| **USAID (Results Framework)** | But, Objectif de développement, Résultat intermédiaire, Sous-résultat intermédiaire |
| **Nations unies (gestion axée sur les résultats)** | Impact, Effet, Produit, Activité |
| **Banque mondiale** | Objectif de développement du projet, Résultat intermédiaire |
| **Personnalisé** | De 2 à 4 niveaux nommés en français et en anglais, en précisant ceux qui portent des indicateurs |

Le modèle peut être changé plus tard depuis l'écran Cadre de résultats (voir [Cadre de résultats](cadre.md)).

Les boutons qui ont besoin des moteurs de calcul restent grisés pendant leur démarrage, qui prend quelques secondes après l'ouverture de l'application. L'indicateur en bas à gauche passe alors à **« Moteurs prêts »**.

## Mes projets

La liste **Mes projets** rassemble les projets créés ou ouverts sur cet ordinateur, du plus récent au plus ancien.

![Liste Mes projets](../img/80-mes-projets.png)

*Figure 5. Un projet dans la liste, avec l'état de ses indicateurs.*

Pour chaque projet, la ligne indique :

- son nom et l'emplacement du fichier ;
- la date de dernière modification ;
- le nombre d'indicateurs et leur état (atteints, en bonne voie, en retard) au moment de la dernière ouverture ;
- « Fichier introuvable à cet emplacement » si le fichier a été déplacé ou supprimé.

Un clic sur la ligne ouvre le projet. Au survol, trois boutons apparaissent :

| Icône | Action |
|---|---|
| Horloge | **Copies automatiques** : liste des copies du projet et restauration (voir [Outils](outils.md)) |
| Dossier | **Afficher dans le dossier** : ouvre l'explorateur Windows sur le fichier |
| Croix | **Retirer de la liste** : le projet disparaît de la liste, le fichier n'est pas supprimé |

Au-delà de quatre projets, un champ **« Chercher un projet »** filtre la liste par nom ou par emplacement. La case **« Rouvrir le dernier projet au démarrage »** fait ouvrir directement le dernier projet utilisé au lancement de l'application.

## Les éléments communs à tous les écrans

**La barre latérale (à gauche)**

- Le nom du projet ouvert, puis les sept étapes : Vue d'ensemble, Cadre de résultats, Indicateurs, Données, Analyse, Tests, Rapport. Le chiffre à droite de certaines étapes indique le nombre d'éléments (indicateurs, jeux de données, etc.).
- **Fermer le projet** : revient à l'accueil. Rien n'est perdu, tout est déjà enregistré.
- **Moteurs prêts** : état des moteurs de calcul ; un clic ouvre l'écran Moteurs.
- **FR / EN** : langue de l'interface. Le choix est mémorisé.
- **Thème** (cercle à moitié plein) : bascule entre clair et sombre.
- Le bouton en haut de la barre la replie, pour gagner de la place sur un petit écran.

**La barre du haut**

- Le fil d'Ariane : application, projet, écran.
- **« Enregistré automatiquement »** : rappel qu'il n'y a pas de bouton Enregistrer. Pendant un calcul long, le message devient « Traitement en cours ».
- Le numéro de version installée.

**Les panneaux**

Les formulaires (nouvel indicateur, règle de nettoyage, import, fusion, etc.) s'ouvrent dans un panneau à droite. La touche Échap ou la croix le ferme sans rien enregistrer ; le bouton principal en bas du panneau valide.
