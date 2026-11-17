# Installing the relay server

The relay server receives the change files of a team's members and passes them on to the others. It only relays: files are encrypted and signed by the members' copies, and the server can neither read them nor make valid ones. It only checks an **access key** per project.

It is optional: a team can use packages or a shared folder instead (see the [administrator guide](administration.md)).

## Requirements

- A machine the members can reach: a small Linux server, a virtual machine or a Windows server of the organisation. One processor and 1 GB of memory are enough; disk space depends on the volume exchanged (a few hundred MB per project per year in general).
- Python 3.10 or later. No other package.
- A domain name and an HTTPS certificate. The server speaks HTTP on the machine; a **reverse proxy** (Caddy, nginx, IIS) provides HTTPS. The application refuses an `http://` address that is not the machine itself.

The program is the file `server/relay.py` of the repository.

## On Linux

```bash
sudo useradd --system --home /srv/suivievallab suivievallab
sudo mkdir -p /srv/suivievallab /opt/suivievallab
sudo cp relay.py /opt/suivievallab/
sudo chown -R suivievallab: /srv/suivievallab
```

systemd service, `/etc/systemd/system/suivievallab-relay.service`:

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

Reverse proxy with Caddy, `/etc/caddy/Caddyfile` (Caddy gets and renews the certificate by itself):

```
sync.my-organisation.org {
    reverse_proxy 127.0.0.1:8470
}
```

## On Windows Server

1. Install Python from python.org, for all users.
2. Copy `relay.py` to `C:\SuiviEvalLab\` and create the data folder `C:\SuiviEvalLab\data`.
3. Create a scheduled task that starts with the system, under a service account:
   `python C:\SuiviEvalLab\relay.py --data C:\SuiviEvalLab\data --host 127.0.0.1 --port 8470`
4. In IIS, with URL Rewrite and Application Request Routing, publish the site over HTTPS and forward requests to `http://127.0.0.1:8470`.

## Adding a project

For each project, add a line to the `keys.txt` file of the data folder:

```
<project identifier> <access key>
```

- The **project identifier** is shown in the Team and security tab of the project sheet, Server section.
- The **access key** is a long random string, for example from `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

The file is read again at each request: no restart is needed. The administrator then gives the server address and the access key to the members, who type them once in the Server section; the application keeps the key on their computer, encrypted by the system, never in the project file.

## Running it

| Topic | Advice |
|---|---|
| Backup | The data folder holds one subfolder per project. Losing it deletes nothing on the members' side, whose copies keep all the data; back it up like any folder |
| Removing a project | Delete its line in `keys.txt`, then its subfolder |
| Changing a key | Edit the line in `keys.txt` and give the new key to the members |
| File size | 200 MB at most per file |
| Logs | Those of the service (journalctl or the event viewer) |
