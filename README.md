# SuiviEvalLab

Poste de travail de bureau pour les professionnels du suivi-évaluation : du cadre logique au rapport Word, sur votre ordinateur, sans connexion internet, avec la rigueur statistique de R.

*A desktop workstation for monitoring and evaluation professionals: from the logframe to the Word report, offline, with the statistical rigour of R.*

## État du projet

Version **0.1, étape 0 (fondations)**. Cette version vérifie que l'application et ses deux moteurs de calcul fonctionnent sur Windows. Elle ne contient pas encore les fonctions métier.

| Étape | Contenu | État |
|---|---|---|
| 0. Fondations | Application Windows, moteurs Python et R embarqués, calcul de démonstration | En cours |
| 1. Démonstrateur | Parcours complet en version simple sur un projet exemple | À venir |
| 2 à 6 | Cadre, indicateurs, données, statistiques, rapport, bêta | À venir |

## Installer (Windows 10 et 11)

1. Ouvrez l'onglet **Actions** du dépôt, choisissez la dernière construction réussie, et téléchargez l'artefact `SuiviEvalLab-installation-windows`.
2. Décompressez-le et lancez `SuiviEvalLab-0.1.0-installation.exe`.
3. L'installateur n'est pas encore signé : Windows peut afficher « Windows a protégé votre ordinateur ». Cliquez sur **Informations complémentaires**, puis **Exécuter quand même**.

Aucun droit administrateur n'est nécessaire. Python et R sont inclus : rien d'autre à installer.

## Architecture

```
apps/desktop      Interface (Electron, React, TypeScript)
engine/python     Moteur métier (Python) : fichiers, nettoyage, rapports, orchestration
engine/r          Moteur statistique (R) : tous les calculs statistiques
tools/            Construction des moteurs embarqués, tests de fumée
```

L'interface dialogue avec le moteur Python en JSON-RPC sur l'entrée et la sortie standard. Le moteur Python pilote un processus R persistant ; les tableaux de données passent au format Arrow IPC. Aucune communication réseau entre les composants.

## Développer

Prérequis : Node.js 22, Python 3.12 ou plus, R 4.4 avec les packages de `engine/r/packages.txt`.

```bash
# Moteurs
cd engine/python && pip install -r requirements.txt pytest && python -m pytest
Rscript engine/r/tests/test_proportion.R

# Interface
cd apps/desktop && npm ci && npm start
```

## Licence

GPL-3.0-or-later. Voir [LICENSE](LICENSE).
