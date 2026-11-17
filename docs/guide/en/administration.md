# Administrator guide

This guide is for the person who shares a project, usually the project's M&E manager. It covers protecting the project, the team and its roles, exchanges between copies, conflicts, the audit trail and personal data. Everything is in the **Team and security** tab of the project sheet.

## Principles

Each member works on **their own copy** of the project, on their computer, even offline. Copies exchange their **changes**, not the whole file. Each change is signed by its author and each exchange file is encrypted. The administrator decides who may do what; a copy refuses any change a member was not allowed to make.

A project used by one person needs none of this: the team is set up only when needed.

## Protecting the project with a password

**Protect with a password** encrypts the project file (AES-GCM, key derived from the password with scrypt). The file then opens only with the password, asked at each opening.

- Protection is **required** as soon as the project holds a sensitive feedback case or people's identifiers. The application says so and refuses to store such data until the project is protected.
- The password has at least 8 characters. **It cannot be recovered**: without it, the project is lost. Keep it in the organisation's password manager.
- While working, the application keeps a decrypted working copy in its own folder and writes it into the encrypted file every minute. After a crash, the newest working copy is taken back at the next opening.
- No automatic copies are made of an encrypted project, since they would be in clear.

The password can be changed; protection can be removed while the project holds no data that requires it.

## Setting up the team

1. Give your name and click **Set up the team**. You become the project's administrator. The application creates the project's keys and signs the member list.
2. Each future member installs the application, opens the Projects screen, follows **Join a team project** and saves their **identity file** (`.smeid`). They send it to you.
3. Click **Add a member**, choose their identity file and give their roles. **Check the fingerprint** shown with them, by voice or message: it proves the file comes from them.
4. Save their **invitation** (`.smejoin`) with a password, which you give them through another channel (phone, message) than the invitation itself.
5. They open the invitation, type the password and choose where to save their copy.

### Roles

| Role | May |
|---|---|
| Administrator | Everything, including members, targets and locking periods |
| M&E officer | Enter, import, check, prepare reports; not change targets nor lock |
| Partner focal point | Enter and submit the data of their partner; receives only the project's design and their partner's data |
| Validator | Validate or return submissions |
| Feedback manager | The only one, with the administrator, to read sensitive cases |
| Reader | Read without changing anything |

A member may hold several roles. A **deactivated** member keeps their past changes, but their next changes are refused by every copy.

## Exchanging changes

There are three ways; a team can combine them.

| Way | How | When |
|---|---|---|
| **Package** | A `.smesync` file prepared for one member, sent by email, USB key or messaging, then received on the other side | Partners with poor connectivity, occasional exchanges |
| **Shared folder** | A synchronised folder (OneDrive, Google Drive, Dropbox, the organisation's file server); the application drops its changes there and reads the others' every five minutes | A team in one office |
| **Relay server** | A small self-hosted server receives and passes on the files, in near real time (see [Installing the relay server](server.md)) | A team spread over several sites |

Exchange files are encrypted **for their readers**: the project's design for every member, a partner's data for that partner and the office, everything else for the office only. A partner focal point with access to the shared folder or the server can fetch every file, but can read only those meant for them. The server can read none.

The administrator also links the ways: what arrives from a partner by package goes on to the shared folder and the server, so that every copy ends with the same data.

## Conflicts and requests

| Case | What happens |
|---|---|
| Two copies change the same data before exchanging | The newest version is kept; the other appears in **Conflicts and requests**, where the administrator can take it or set it aside. The choice reaches the other copies |
| A member changes **validated** data or a **locked** period without the right to | The change is never applied: it becomes a **request** the administrator accepts or sets aside |
| A change comes from an unknown or deactivated member, or is outside their rights | It is refused and counted as such |
| A file was changed after it was signed | It is refused as a whole |

## Audit trail

The audit trail records each validation, locking and reopening, each reading of a sensitive case, each member change, each reception of changes, each settled conflict, each password change and each removal of personal data. An entry can be neither changed nor deleted; each entry is linked to the previous one by its hash, and the application checks the chain each time it is shown ("intact" or "chain broken").

## Personal data

The tab sets how long the personal data of feedback cases (person concerned, detail) is kept. After that, a task reminds you to remove it for closed cases, and **Remove expired data** does it; the removal is in the audit trail. See also [Data protection](data-protection.md).

## Automatic copies and integrity

Each time a project that is not encrypted is opened, the application checks the file's integrity, then copies it into its own folder (the last ten are kept). If the file is damaged (disk error, interrupted copy), a banner says so, no copy overwrites the good ones, and the latest copy is restored from the Projects screen, "Automatic copies".

## Updates

The application looks for updates at start-up and installs them when it closes. An organisation can turn this off by group policy. Versions published with the code signing certificate show the publisher's name at installation (see [Contributing](contributing.md), "Signing the installer").
