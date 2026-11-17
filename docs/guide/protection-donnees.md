# Protection des données : bonnes pratiques

Ce chapitre décrit ce que fait l'application pour protéger les données personnelles et ce qui reste de la responsabilité de l'organisation. Il suit les principes du règlement général sur la protection des données (RGPD) et des lois de protection des données des pays où l'application est utilisée. **Ce n'est pas un conseil juridique** : chaque organisation vérifie ses obligations avec son délégué à la protection des données ou un juriste.

## Ce que fait l'application

| Principe | Dans l'application |
|---|---|
| Minimisation | Le suivi porte sur des chiffres agrégés. Les personnes ne sont comptées que par un pseudonyme ; les identifiants d'origine ne sont jamais enregistrés |
| Pseudonymisation | Le pseudonyme est une empreinte (HMAC) calculée avec une clé propre au projet, qui n'est jamais exportée : on ne peut pas remonter à l'identifiant |
| Confidentialité | Projet chiffré par mot de passe, obligatoire dès qu'il contient des cas sensibles ou des identifiants ; fichiers d'échange chiffrés pour leurs seuls destinataires ; serveur relais incapable de lire les données |
| Limitation de l'accès | Rôles par membre ; un partenaire ne reçoit que ses données ; les cas sensibles ne sont lisibles que par l'administrateur et le gestionnaire des retours |
| Traçabilité | Journal d'audit non modifiable des lectures de cas sensibles, des validations, des changements de membres et des suppressions |
| Limitation de la conservation | Durée de conservation réglable des données personnelles des retours, avec rappel et suppression |
| Exports | Les rapports, les paquets de données, la page de partage et le tableau de bord ne contiennent aucune donnée personnelle ni aucun cas sensible |
| Localisation | Les données restent sur les ordinateurs des membres et, si l'organisation le choisit, sur son propre serveur relais. Rien n'est envoyé à l'éditeur |

## Ce qui reste à l'organisation

1. **Base légale et information.** Les personnes dont on collecte les données (bénéficiaires, plaignants) sont informées de l'usage de leurs données et de leurs droits, selon la base légale retenue.
2. **Consentement éclairé** pour les enquêtes et les entretiens, consigné selon les procédures de l'organisation.
3. **Données d'enquête.** Les fichiers importés (Kobo, ODK, Excel) peuvent contenir des noms, des numéros de téléphone ou des coordonnées GPS. Une copie du fichier importé est gardée dans le projet : retirez ces colonnes du fichier avant l'import quand l'analyse n'en a pas besoin (dans Kobo ou ODK, par un export qui les exclut).
4. **Mots de passe.** Le mot de passe du projet ne peut pas être retrouvé. Gardez-le dans le gestionnaire de mots de passe de l'organisation, et changez-le quand un membre quitte l'équipe.
5. **Ordinateurs.** Chiffrez les disques des ordinateurs (BitLocker), verrouillez les sessions, tenez Windows à jour.
6. **Dossiers partagés.** Limitez l'accès au dossier de l'équipe aux seuls membres, même si les fichiers y sont chiffrés.
7. **Départ d'un membre.** Désactivez-le dans l'équipe : ses changements suivants seront refusés. Sa copie reste sur son ordinateur : demandez sa suppression.
8. **Violation de données.** Prévoyez la procédure : qui prévenir, dans quel délai, auprès de quelle autorité.
9. **Transferts.** Si le serveur relais ou le dossier partagé est hébergé dans un autre pays, vérifiez les règles de transfert applicables.

## Cas sensibles

Les retours qui touchent à l'exploitation et aux abus sexuels, à la fraude ou à la conduite du personnel suivent les procédures de signalement de l'organisation et des bailleurs (par exemple les principes du Comité permanent interorganisations sur la protection contre l'exploitation et les abus sexuels). L'application garde la trace du cas et de son traitement ; elle ne remplace pas ces procédures.
