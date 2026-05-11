# Home Reliability and Ransomware Safety Plan

This project is for home use first. The goal is not enterprise complexity; it is rock-solid protection for personal photos, documents, and family records.

## Reliability goal

The daily-use bar is:

1. A Linux desktop engine can back up selected folders automatically.
2. Data lands in at least two independent stations:
   - local/NAS station, such as TrueNAS
   - offsite station, such as IDrive e2/S3
3. Every completed railcar has a verified checksum.
4. A failed transfer resumes without duplicating or losing work.
5. A restore smoke test proves files can be recovered.
6. Configuration and activity history survive restarts and machine loss.

## Home backup strategy

Recommended home pattern:

```text
Linux desktop engine
  -> TrueNAS station with snapshots
  -> IDrive e2 station using restic/S3
  -> optional OneDrive station using rclone
```

Important defaults:

- Keep local/NAS and cloud/offsite stations independent.
- Do not treat file deletion on the desktop as an immediate delete in backups.
- Prefer snapshot-style backups for photos and documents.
- Keep at least one destination with immutable or append-only retention.
- Run scheduled restore tests, not just backup tests.

## Ransomware threat model

Home ransomware usually does one or more of these:

- encrypts many files quickly
- renames many files
- deletes originals after writing encrypted copies
- attempts to access mounted NAS shares
- syncs encrypted files to cloud drives
- tries to delete backup history if credentials permit it

Edge Backup Railway should assume the desktop engine may be compromised.

## Ransomware safety controls

### 1. Panic brake

The engine should stop moving railcars when suspicious activity is detected:

- too many file changes in a short window
- high delete/rename ratio
- many extensions changing to unknown/encrypted-looking suffixes
- canary files modified
- sudden entropy change across many personal files

When the panic brake trips:

```text
state = stopped_for_safety
upload new changed data = paused
dispatcher event = ransomware_suspected
resume requires passkey/manual confirmation
```

The engine may still upload a small diagnostic manifest, but it should not overwrite or advance normal backup routes.

### 2. Canary files

Create harmless canary files in watched folders. If they change, pause all uploads and mark the route unsafe until the user confirms.

### 3. No automatic destructive sync

For home data, deletes should not immediately remove historical backups. Deletions become journal events and require retention policy review.

### 4. Immutable/offline history

Use storage features that ransomware cannot easily alter:

- TrueNAS periodic snapshots with restricted deletion permissions
- restic snapshots in IDrive e2/S3
- S3/Object Lock or bucket versioning where available
- separate credentials for backup writes vs retention deletion

The client should be able to write new backups but should not hold credentials that can purge old recovery points.

### 5. Restore drills

Backups are not real until restore is proven. The MVP should include:

- restore one random file
- restore one photo/document folder sample
- verify checksum after restore
- record restore drill in the yard ledger

## API and dashboard exposure

The dispatcher and Signal Board can become a roadmap for attackers if exposed carelessly. Home default should be private and minimal.

Default safety posture:

- bind dispatcher/dashboard to localhost or LAN only
- no public internet exposure by default
- require authentication before showing paths, station names, or source ids
- redact full paths by default in unauthenticated or locked views
- show aggregate health without revealing folder structure
- separate read-only dashboard access from dangerous operations

## Passkey / fail-safe model

Use a passkey-style unlock for sensitive actions. For a home MVP this can start simple and grow toward WebAuthn/passkeys.

Sensitive actions that should require passkey/manual unlock:

- reveal full file paths and station URIs
- change routes/stations
- restore config from a timetable snapshot
- resume after panic brake
- delete/expire backup history
- export full journal
- show credentials or credential locations

Recommended path:

1. **MVP:** local admin passphrase/passkey gate for sensitive CLI/API actions.
2. **Next:** WebAuthn/passkey for Signal Board unlock.
3. **Later:** optional hardware security key for destructive operations.

Fail-safe behavior:

- if auth/passkey is unavailable, backups may continue in safe append-only mode
- destructive or revealing actions stay locked
- panic brake stays stopped until manually unlocked

## What not to build

Avoid enterprise-only scope for now:

- multi-tenant admin roles
- fleet policy engines
- remote public dashboards
- complex SIEM integrations
- centralized identity provider requirements

Build the home version well: local-first, understandable, recoverable, and safe by default.
