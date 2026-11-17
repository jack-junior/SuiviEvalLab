# Data protection: good practice

This chapter describes what the application does to protect personal data and what remains the organisation's responsibility. It follows the principles of the General Data Protection Regulation (GDPR) and of the data protection laws of the countries where the application is used. **It is not legal advice**: each organisation checks its obligations with its data protection officer or a lawyer.

## What the application does

| Principle | In the application |
|---|---|
| Minimisation | Monitoring works on aggregated figures. People are counted only through a pseudonym; original identifiers are never stored |
| Pseudonymisation | The pseudonym is a keyed hash (HMAC) computed with a key of the project that is never exported: the identifier cannot be recovered from it |
| Confidentiality | Project encrypted with a password, required as soon as it holds sensitive cases or identifiers; exchange files encrypted for their readers only; relay server unable to read the data |
| Access limitation | Roles per member; a partner receives only its own data; sensitive cases readable only by the administrator and the feedback manager |
| Accountability | Tamper-evident audit trail of sensitive readings, validations, member changes and removals |
| Storage limitation | Retention period of feedback personal data, with reminder and removal |
| Exports | Reports, data packs, the sharing page and the dashboard hold no personal data and no sensitive case |
| Location | Data stays on the members' computers and, if the organisation chooses, on its own relay server. Nothing is sent to the publisher |

## What remains with the organisation

1. **Lawful basis and information.** People whose data is collected (beneficiaries, complainants) are told how their data is used and what their rights are, according to the lawful basis chosen.
2. **Informed consent** for surveys and interviews, recorded according to the organisation's procedures.
3. **Survey data.** Imported files (Kobo, ODK, Excel) may hold names, phone numbers or GPS coordinates. A copy of the imported file is kept in the project: remove those columns from the file before import when the analysis does not need them (in Kobo or ODK, by an export that leaves them out).
4. **Passwords.** The project password cannot be recovered. Keep it in the organisation's password manager, and change it when a member leaves the team.
5. **Computers.** Encrypt disks (BitLocker), lock sessions, keep Windows up to date.
6. **Shared folders.** Restrict access to the team's folder to its members, even though files are encrypted there.
7. **A member leaves.** Deactivate them in the team: their next changes are refused. Their copy stays on their computer: ask for it to be deleted.
8. **Data breach.** Plan the procedure: whom to tell, how fast, which authority.
9. **Transfers.** If the relay server or shared folder is hosted in another country, check the applicable transfer rules.

## Sensitive cases

Feedback about sexual exploitation and abuse, fraud or staff conduct follows the reporting procedures of the organisation and its donors (for example the Inter-Agency Standing Committee principles on protection from sexual exploitation and abuse). The application keeps track of the case and how it was handled; it does not replace those procedures.
