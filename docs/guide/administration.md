# Guide de l'administrateur

Ce guide s'adresse à la personne qui met un projet en partage : en général le responsable S&E du projet. Il couvre la protection du projet, l'équipe et ses rôles, les échanges entre copies, les conflits, le journal d'audit et les données personnelles. Tout se trouve dans l'onglet **Équipe et sécurité** de la fiche du projet.

## Principes

Chaque membre travaille sur **sa propre copie** du projet, sur son ordinateur, même sans connexion. Les copies échangent leurs **changements**, pas le fichier entier. Chaque changement est signé par son auteur et chaque fichier d'échange est chiffré. L'administrateur fixe qui peut faire quoi ; une copie refuse tout changement qu'un membre n'avait pas le droit de faire.

Un projet utilisé par une seule personne n'a besoin de rien de tout cela : l'équipe ne se met en place que lorsqu'on en a besoin.

## Protéger le projet par un mot de passe

Le bouton **Protéger par un mot de passe** chiffre le fichier du projet (chiffrement AES-GCM, clé tirée du mot de passe par scrypt). Le fichier ne s'ouvre alors qu'avec le mot de passe, demandé à chaque ouverture.

- La protection est **obligatoire** dès que le projet contient un retour sensible ou des identifiants de personnes. L'application le rappelle et refuse d'enregistrer ces données tant que le projet n'est pas protégé.
- Le mot de passe compte au moins 8 caractères. **Il ne peut pas être retrouvé** : sans lui, le projet est perdu. Gardez-le dans un gestionnaire de mots de passe de l'organisation.
- Pendant le travail, l'application garde une copie de travail déchiffrée dans son dossier propre et l'écrit chaque minute dans le fichier chiffré. Après un arrêt brutal, la copie de travail la plus récente est reprise à l'ouverture suivante.
- Les copies automatiques ne sont pas faites pour un projet chiffré, puisqu'elles seraient en clair.

Le mot de passe peut être changé ; la protection peut être retirée tant que le projet ne contient pas de données qui l'exigent.

## Mettre l'équipe en place

1. Donnez votre nom et cliquez sur **Mettre l'équipe en place**. Vous devenez l'administrateur du projet. L'application crée les clés du projet et signe la liste des membres.
2. Chaque futur membre installe l'application, ouvre l'écran Projets, suit le lien **Rejoindre un projet d'équipe** et enregistre son **fichier d'identité** (`.smeid`). Il vous l'envoie.
3. Vous cliquez sur **Ajouter un membre**, choisissez son fichier d'identité et lui donnez ses rôles. **Vérifiez l'empreinte** affichée avec lui, de vive voix ou par message : elle garantit que le fichier vient bien de lui.
4. Vous enregistrez son **invitation** (`.smejoin`) avec un mot de passe, que vous lui communiquez par un autre canal (téléphone, message) que l'invitation elle-même.
5. Il ouvre l'invitation, saisit le mot de passe et choisit où enregistrer sa copie.

### Les rôles

| Rôle | Peut |
|---|---|
| Administrateur | Tout, dont les membres, les cibles et le verrouillage des périodes |
| Chargé de S&E | Saisir, importer, vérifier, préparer les rapports ; pas changer les cibles ni verrouiller |
| Point focal partenaire | Saisir et soumettre les données de son partenaire ; il ne reçoit que la conception du projet et les données de son partenaire |
| Validateur | Valider ou renvoyer les envois |
| Gestionnaire des retours | Seul, avec l'administrateur, à lire les cas sensibles |
| Lecteur | Consulter sans rien modifier |

Un membre peut cumuler plusieurs rôles. Un membre **désactivé** garde ses changements passés, mais ses changements suivants sont refusés par toutes les copies.

## Échanger les changements

Trois façons existent ; on peut les combiner dans une même équipe.

| Façon | Comment | Quand l'utiliser |
|---|---|---|
| **Paquet** | Un fichier `.smesync` préparé pour un membre, envoyé par courriel, clé USB ou messagerie, puis reçu de l'autre côté | Partenaires peu connectés, échanges ponctuels |
| **Dossier partagé** | Un dossier synchronisé (OneDrive, Google Drive, Dropbox, serveur de fichiers de l'organisation) ; l'application y dépose ses changements et lit ceux des autres toutes les cinq minutes | Équipe d'un même bureau |
| **Serveur relais** | Un petit serveur auto-hébergé reçoit et redistribue les fichiers, en temps quasi réel (voir [Installer le serveur relais](serveur.md)) | Équipe répartie sur plusieurs sites |

Les fichiers d'échange sont chiffrés **pour leurs destinataires** : la conception du projet pour tous les membres, les données d'un partenaire pour ce partenaire et le bureau, le reste pour le bureau seulement. Un point focal partenaire qui a accès au dossier partagé ou au serveur peut donc récupérer tous les fichiers, mais il ne peut lire que ceux qui le concernent. Le serveur, lui, ne peut en lire aucun.

L'administrateur fait aussi le lien entre les façons : ce qu'il reçoit d'un partenaire par paquet repart vers le dossier partagé et le serveur, pour que toutes les copies finissent avec les mêmes données.

## Conflits et demandes

| Cas | Ce qui se passe |
|---|---|
| Deux copies changent la même donnée avant d'avoir échangé | La version la plus récente est gardée ; l'autre apparaît dans **Conflits et demandes**, où l'administrateur peut la reprendre ou l'écarter. Son choix est transmis aux autres copies |
| Un membre change une donnée **validée** ou une période **verrouillée** sans en avoir le droit | Le changement n'est jamais appliqué : il devient une **demande**, que l'administrateur accepte ou écarte |
| Un changement vient d'un membre inconnu, désactivé, ou sort de ses droits | Il est refusé et compté comme tel |
| Un fichier a été modifié après sa signature | Il est refusé en entier |

## Le journal d'audit

Le journal d'audit inscrit chaque validation, verrouillage et réouverture, chaque lecture d'un cas sensible, chaque changement de membre, chaque réception de changements, chaque conflit tranché, chaque changement de mot de passe et chaque suppression de données personnelles. Une entrée ne peut être ni modifiée ni supprimée ; chaque entrée est liée à la précédente par son empreinte, et l'application vérifie la chaîne à chaque affichage (« intact » ou « chaîne rompue »).

## Données personnelles

L'onglet fixe la **durée de conservation** des données personnelles des retours et plaintes (personne concernée, détail du cas). Passé ce délai, une tâche rappelle de les supprimer pour les cas clos, et le bouton **Supprimer les données échues** le fait ; la suppression est inscrite au journal d'audit. Voir aussi le [guide de protection des données](protection-donnees.md).

## Copies automatiques et intégrité

À chaque ouverture d'un projet non chiffré, l'application vérifie l'intégrité du fichier puis en fait une copie dans son dossier propre (les dix dernières sont gardées). Si le fichier est endommagé (erreur de disque, copie interrompue), un bandeau le signale, aucune copie n'écrase les bonnes, et l'on rétablit la dernière copie depuis l'écran Projets, « Copies automatiques ».

## Accessibilité

La taille du texte se règle dans le bas du menu (les deux boutons A, petit et grand) ou au clavier (Ctrl et +, Ctrl et -, Ctrl et 0). Toute l'application se parcourt au clavier : Tab et Maj+Tab pour passer d'un élément à l'autre, Entrée pour ouvrir une ligne de tableau, Échap pour fermer un panneau ; le lien « Aller au contenu » apparaît à la première tabulation. Le thème clair ou sombre est gardé d'une session à l'autre.

## Mises à jour

L'application cherche ses mises à jour au démarrage et les installe à la fermeture. Une organisation peut couper cette recherche par une stratégie de groupe (voir [Outils](manuel/outils.md)). Les versions publiées avec le certificat de signature de code affichent le nom de l'éditeur à l'installation (voir [Contribuer](contribuer.md), « Signer l'installeur »).
