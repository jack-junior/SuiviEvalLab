# Contribuer au projet

SuiviEvalLab est un logiciel libre, publié sous licence GPL-3.0 ou ultérieure. Le code, la documentation et l'historique des décisions sont dans le dépôt GitHub `jack-junior/SuiviEvalLab`. On peut contribuer sans écrire de code : tester, signaler un problème, améliorer un texte de l'interface ou de cette documentation.

## Les façons de contribuer

| Contribution | Compétence | Comment |
|---|---|---|
| Tester une version | Métier S&E | Suivre le kit de test (chapitre suivant) et remonter les résultats |
| Signaler un problème ou proposer une amélioration | Métier S&E | Ouvrir une *issue* sur GitHub (voir plus bas) |
| Corriger un texte de l'interface | Aucune | Modifier le fichier des traductions, ou le signaler dans une issue |
| Améliorer cette documentation | Aucune | Modifier les fichiers Markdown de `docs/guide/` ; le site est republié automatiquement |
| Développer une fonctionnalité | TypeScript, Python ou R | Cycle de travail décrit ci-dessous |

## Signaler un problème

Sur GitHub, onglet **Issues**, **New issue**. Un bon signalement contient :

- ce que vous faisiez (écran, étapes) ;
- ce que vous attendiez et ce que vous avez obtenu ;
- une capture d'écran ;
- pour un calcul qui semble faux : les données (anonymisées), la valeur attendue et la façon de l'obtenir. **Un chiffre faux est traité comme un défaut critique** ;
- si possible, le fichier journal (son dossier est indiqué dans l'écran Moteurs).

Ne joignez jamais de données personnelles réelles de bénéficiaires.

## Le poste de développement

| Outil | Version | Sert à |
|---|---|---|
| Git | récente | gestion des versions |
| Node.js | 22 LTS | interface et hôte (Electron, React) |
| Python | 3.12 ou plus | moteur métier |
| R | 4.4 | moteur statistique, avec les packages `jsonlite`, `survey`, `nanoarrow` |

```bash
git clone https://github.com/jack-junior/SuiviEvalLab.git
cd SuiviEvalLab

# Moteur Python
cd engine/python
python -m pip install -r requirements.txt "pytest==9.1.1" "ruff==0.17.0"
python -m pytest
cd ../..

# Moteur R
Rscript -e 'install.packages(c("jsonlite", "survey", "nanoarrow"))'
Rscript engine/r/tests/test_estimate.R

# Application
cd apps/desktop
npm ci
npm start
```

Sous Windows avec Git Bash, si `Rscript` n'est pas dans le PATH :

```bash
export SME_RSCRIPT="/c/Program Files/R/R-4.4.3/bin/Rscript.exe"
```

Il n'est pas nécessaire de construire l'installeur sur son poste : l'intégration continue le fait et le teste à chaque modification.

## Les règles du projet

Le détail est dans `docs/conventions.md`. L'essentiel :

**Langues.** Le code, les commentaires, les messages de commit et la documentation technique sont en anglais. L'interface est en français et en anglais ; le français est la référence. Les textes de l'interface sont tous dans `apps/desktop/src/renderer/i18n/messages.ts`, jamais dans le code des écrans ; une vérification automatique refuse une clé absente d'une des deux langues.

**Données.** Les données importées ne sont jamais modifiées ; toute transformation est une règle enregistrée. Aucune formule saisie par l'utilisateur n'est exécutée comme du code. Aucune donnée réelle de bénéficiaires dans le dépôt, même pour les tests.

**Statistiques.** Tout résultat statistique est calculé par R, avec un package reconnu. Toute estimation a son intervalle de confiance, tout test sa taille d'effet. Chaque fonction R renvoie le script qui reproduit le résultat. Chaque nouvelle méthode est vérifiée contre un appel R direct ou une référence publiée.

**Écriture de l'interface.** Des phrases complètes qui disent ce qui se passe et quoi faire ; l'ampleur avant la significativité ; pas de jargon quand un mot du métier existe ; pas de tiret long ni d'émoticône.

**Style de code.** TypeScript strict avec ESLint et Prettier ; Python typé avec Ruff ; R en style de base avec le préfixe `sme_`. Toute nouvelle dépendance est figée à une version exacte et sous une licence compatible avec la GPL.

## Le cycle de travail

1. **Une issue** décrit le changement.
2. **Une branche** part de `main`, nommée par type et sujet : `feat/fiche-indicateur`, `fix/delai-r`, `docs/guide-tests`.
3. **Des commits** courts, au format *Conventional Commits*, en anglais : `feat(indicators): compute achievement rate`, `fix(r-bridge): restart R after a timeout`.
4. **Les vérifications locales** avant de pousser :

```bash
cd engine/python && python -m ruff check . && python -m ruff format --check . && python -m pytest
cd apps/desktop && npm run lint && npm run typecheck && npm run build
```

`npm run lint` vérifie aussi les traductions, les en-têtes de licence et le **contraste des couleurs** de l'interface (niveau AA des WCAG 2.1, en thème clair et sombre).

5. **Une pull request** vers `main`, avec une capture d'écran pour tout changement visible.
6. **L'intégration continue** doit être verte (voir ci-dessous).
7. **Fusion** par « Squash and merge » : la branche devient un seul commit sur `main`. Personne ne pousse directement sur `main`.

Les décisions techniques importantes font l'objet d'une courte fiche dans `docs/adr/` : contexte, décision, conséquences.

## L'intégration continue

À chaque pull request, GitHub Actions exécute deux séries de vérifications :

| Étape | Environnement | Ce qui est vérifié |
|---|---|---|
| Tests R | Linux | Chaque fonction statistique contre l'appel direct au package `survey` et des valeurs de référence |
| Tests Python | Linux | Le moteur métier sur les données d'exemple et sur les fichiers originaux complets téléchargés depuis HDX |
| Interface | Linux | Lint, types, traductions complètes, construction |
| Installeur | Windows | Préparation de Python et R intégrés, test des moteurs, construction de l'installeur |
| Parcours complet | Windows | L'application installée est pilotée de bout en bout : projet, import, nettoyage, indicateurs, analyse, rapport, SPSS, qualité, fusion, tableau de bord, plan, taille d'échantillon, tests, langues |
| Mise à jour | Windows | Une version supérieure est servie localement ; l'application installée doit la trouver, la télécharger et s'installer seule, et respecter la stratégie de groupe qui la bloque |

Les captures d'écran du parcours complet sont conservées 30 jours avec chaque exécution.

## Les tests de recette et de performance

Les **tests de recette** (`engine/python/tests/test_acceptance.py`) jouent les parcours de la section 11 du cahier des charges : un projet de trois ans avec quatre partenaires, trente sites et quarante indicateurs saisis et validés sur douze trimestres (dont deux par canevas Excel), chaque chiffre du tableau de suivi étant recalculé indépendamment ; une équipe de trois membres et deux partenaires synchronisée par paquets, dossier partagé et serveur relais, avec conflits ; un portefeuille de cinq projets.

Les **seuils de performance** de la section 9 se mesurent avec :

```bash
python tools/bench/bench.py [dossier de travail]
```

Le script construit un projet de 300 indicateurs, 40 périodes et 500 sites (2,4 millions de valeurs), vingt projets ordinaires et un fichier de 500 000 lignes, puis chronomètre l'ouverture, le tableau de suivi, le tableau de bord et l'import. Il échoue si un seuil est dépassé. Mesures de référence (machine Linux ordinaire) : ouverture 0,3 s, tableau de suivi 0,3 s, filtré 0,2 s, tableau de bord de 20 projets 0,6 s, import de 500 000 lignes 0,8 s. Le premier affichage après l'arrivée de quarante périodes d'un coup calcule chaque période une fois (environ 8 s), puis le résultat est gardé.

## Signer l'installeur

L'installeur est signé par le workflow de publication quand le certificat de signature de code de l'organisation se trouve dans les secrets du dépôt (Settings, Secrets and variables, Actions) :

| Secret | Contenu |
|---|---|
| `WIN_CSC_LINK` | Le certificat et sa clé privée au format `.pfx`, encodé en base64 (`base64 -w0 certificat.pfx`) |
| `WIN_CSC_KEY_PASSWORD` | Le mot de passe du fichier `.pfx` |

Le workflow vérifie la signature de l'installeur produit et échoue si elle n'est pas valide. Sans ces secrets, l'installeur est construit sans signature et un avertissement l'indique.

Les certificats délivrés depuis 2023 sont souvent conservés sur un module matériel ou un service en ligne (Azure Trusted Signing, SSL.com eSigner, DigiCert KeyLocker) plutôt que dans un fichier `.pfx`. Dans ce cas, la signature se fait par l'outil du fournisseur, appelé depuis le workflow à la place des deux secrets ci-dessus ; electron-builder accepte une commande de signature personnalisée (`win.signtoolOptions.sign`).

Une fois le certificat en place, renseigner `publisherName` dans la configuration `build.win` de `apps/desktop/package.json` avec le nom exact du certificat : les mises à jour automatiques vérifieront alors que chaque nouvelle version est signée par le même éditeur.

## Publier une version

1. Mettre le nouveau numéro de version dans `apps/desktop/package.json` et `engine/python/sme_engine/__init__.py`, compléter `.github/release-notes.md`, fusionner dans `main`.
2. Poser l'étiquette de version sur ce commit et la pousser :

```bash
git checkout main
git pull
git tag v1.0.0
git push origin v1.0.0
```

3. Le workflow de publication construit l'installeur, refait les tests, et publie la version sur GitHub avec l'installeur, son empreinte SHA-256 et les fichiers lus par les mises à jour automatiques. Les versions inférieures à 1.0 sont publiées comme préversions.
4. Les applications installées trouvent la nouvelle version dans les six heures.

Si la publication échoue après la pose de l'étiquette, on corrige le workflow sur `main`, puis on relance le workflow « Release » à la main depuis l'onglet Actions avec la même étiquette. On ne déplace jamais une étiquette.

## Mettre à jour cette documentation

La documentation est écrite en Markdown dans `docs/guide/`. Le site est republié automatiquement à chaque fusion dans `main`, et le document Word est produit à partir des mêmes fichiers.

- Pour un changement de texte : modifier le fichier Markdown dans la même pull request que la fonctionnalité.
- Pour refaire les captures d'écran après un changement d'interface : `xvfb-run -a node tools/docs/screenshots.mjs apps/desktop build/test-kit/donnees` (sous Linux) ; les images de `docs/guide/img/` sont remplacées.
- Pour produire le document Word : `python tools/docs/build_word.py`.
