# Installer le serveur relais

Le serveur relais reçoit les fichiers de changements des membres d'une équipe et les redistribue aux autres. Il ne fait que relayer : les fichiers sont chiffrés et signés par les copies des membres, et le serveur ne peut ni les lire ni en fabriquer. Il ne contrôle qu'une **clé d'accès** par projet.

Il est facultatif : une équipe peut se contenter de paquets ou d'un dossier partagé (voir le [guide de l'administrateur](administration.md)).

## Ce qu'il faut

- Une machine joignable par les membres : un petit serveur Linux, une machine virtuelle ou un serveur Windows de l'organisation. 1 processeur et 1 Go de mémoire suffisent ; l'espace disque dépend du volume échangé (quelques centaines de Mo par projet et par an en général).
- Python 3.10 ou plus récent. Aucun autre paquet.
- Un nom de domaine et un certificat HTTPS. Le serveur lui-même parle HTTP sur la machine ; un **proxy inverse** (Caddy, nginx, IIS) assure le HTTPS. L'application refuse une adresse en `http://` qui n'est pas la machine elle-même.

Le programme est le fichier `server/relay.py` du dépôt.

## Installation sous Linux

```bash
sudo useradd --system --home /srv/suivievallab suivievallab
sudo mkdir -p /srv/suivievallab /opt/suivievallab
sudo cp relay.py /opt/suivievallab/
sudo chown -R suivievallab: /srv/suivievallab
```

Service systemd, `/etc/systemd/system/suivievallab-relay.service` :

```ini
[Unit]
Description=SuiviEvalLab relay server
After=network.target

[Service]
User=suivievallab
ExecStart=/usr/bin/python3 /opt/suivievallab/relay.py --data /srv/suivievallab --host 127.0.0.1 --port 8470
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now suivievallab-relay
```

Proxy inverse avec Caddy, `/etc/caddy/Caddyfile` (Caddy obtient et renouvelle seul le certificat) :

```
sync.mon-organisation.org {
    reverse_proxy 127.0.0.1:8470
}
```

## Installation sous Windows Server

1. Installez Python depuis python.org, pour tous les utilisateurs.
2. Copiez `relay.py` dans `C:\SuiviEvalLab\` et créez le dossier de données `C:\SuiviEvalLab\donnees`.
3. Créez une tâche planifiée qui démarre avec le système, sous un compte de service :
   `python C:\SuiviEvalLab\relay.py --data C:\SuiviEvalLab\donnees --host 127.0.0.1 --port 8470`
4. Dans IIS, avec le module URL Rewrite et Application Request Routing, publiez le site en HTTPS et renvoyez les requêtes vers `http://127.0.0.1:8470`.

## Ajouter un projet

Pour chaque projet, ajoutez une ligne au fichier `keys.txt` du dossier de données :

```
<identifiant du projet> <clé d'accès>
```

- L'**identifiant du projet** s'affiche dans l'onglet Équipe et sécurité de la fiche du projet, section Serveur.
- La **clé d'accès** est une longue suite de caractères tirée au hasard, par exemple avec `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Le fichier est relu à chaque requête : pas besoin de redémarrer. L'administrateur communique ensuite l'adresse du serveur et la clé d'accès aux membres, qui les saisissent une fois dans la section Serveur ; l'application garde la clé sur leur ordinateur, chiffrée par le système, jamais dans le fichier du projet.

## Exploitation

| Sujet | Recommandation |
|---|---|
| Sauvegarde | Le dossier de données contient un sous-dossier par projet. Sa perte n'efface rien chez les membres, dont les copies gardent toutes les données ; il suffit de le sauvegarder comme un dossier ordinaire |
| Retirer un projet | Supprimer sa ligne de `keys.txt`, puis son sous-dossier |
| Changer une clé | Modifier la ligne de `keys.txt` et communiquer la nouvelle clé aux membres |
| Taille des fichiers | 200 Mo au plus par fichier |
| Journaux | Ceux du service (journalctl ou observateur d'événements) |
