# Ransomware README: Passkey and Canary Configuration

This README describes the intended home-use ransomware safety configuration. Some controls are planned implementation work, but the configuration shape below is the target for the personal-computer MVP.

## Goals

- Protect personal photos, documents, and family records.
- Stop suspicious mass changes before they overwrite good recovery points.
- Avoid turning the dashboard/API into a map for attackers.
- Require passkey/manual unlock for sensitive or destructive actions.
- Keep backups append-only and restorable even when the dashboard is locked.

## Example safety config

Future client config should support a `safety` section like this:

```yaml
source_id: linux-desktop
watch_paths:
  - /home/alex/Pictures
  - /home/alex/Documents

stations:
  local:
    type: filesystem
    path: /mnt/truenas/backups/linux-desktop
    snapshots_required: true
  idrive_e2:
    type: restic_s3
    repository: s3:s3.us-east-1.idrivee2.example.com/family-backups/linux-desktop
    immutable_history_required: true

safety:
  mode: home
  destructive_sync: false
  panic_brake:
    enabled: true
    max_changes_per_minute: 200
    max_delete_ratio: 0.20
    max_rename_ratio: 0.30
    suspicious_extensions:
      - .locked
      - .encrypted
      - .crypt
      - .enc
    entropy_sample_files: 20
  canaries:
    enabled: true
    directory_name: .edge-backup-canaries
    files:
      - family-photos-canary.txt
      - documents-canary.txt
    expected_text: "Do not modify. Edge Backup Railway ransomware canary."
  restore_drills:
    enabled: true
    interval_days: 30
    sample_count: 3
  passkey:
    enabled: true
    mode: local_passphrase
    required_for:
      - reveal_paths
      - change_routes
      - export_journal
      - restore_timetable
      - resume_after_panic
      - expire_history
```

## Canary files

Canaries are harmless files placed inside watched folders. Ransomware often modifies everything it can see. If a canary changes, the engine should assume the station route is unsafe.

Target behavior:

1. Engine creates canary files during setup.
2. Engine records expected checksum in local config/state.
3. Every scan verifies canary content first.
4. If a canary changes:
   - stop normal uploads
   - set status `stopped_for_safety`
   - write a yard-ledger event `ransomware_suspected`
   - require passkey/manual unlock before resume

Example canary layout:

```text
/home/alex/Pictures/.edge-backup-canaries/family-photos-canary.txt
/home/alex/Documents/.edge-backup-canaries/documents-canary.txt
```

Recommended content:

```text
Do not modify. Edge Backup Railway ransomware canary.
```

## Panic brake thresholds

Start conservative for home use:

| Signal | Suggested threshold | Action |
|--------|---------------------|--------|
| Changed files per minute | `> 200` | stop for safety |
| Delete ratio | `> 20%` of observed changes | stop for safety |
| Rename ratio | `> 30%` of observed changes | stop for safety |
| Canary changed | any | stop immediately |
| Suspicious extension burst | any common ransomware suffix across many files | stop for safety |

When stopped, the engine may still report diagnostic status to the dispatcher, but it should not advance normal backup routes.

## Passkey / local unlock

The MVP should begin with a local passphrase/passkey gate. Later, the Signal Board can use WebAuthn/passkeys.

Sensitive actions requiring unlock:

- reveal full file paths
- reveal station URIs
- change routes/stations
- export full journal
- restore timetable/config snapshots
- resume after panic brake
- delete or expire recovery history

Example environment shape for local development:

```bash
export EDGE_UNLOCK_MODE=local_passphrase
export EDGE_UNLOCK_SECRET_FILE=$HOME/.config/edge-backup/unlock.secret
```

The secret file should be readable only by the user:

```bash
mkdir -p "$HOME/.config/edge-backup"
printf '%s\n' 'replace-with-generated-secret' > "$HOME/.config/edge-backup/unlock.secret"
chmod 600 "$HOME/.config/edge-backup/unlock.secret"
```

Target CLI shape:

```bash
edge-backup unlock
edge-backup resume --after-panic
edge-backup journal export --unlocked
edge-backup routes edit --unlocked
```

Fail-safe behavior:

- If locked, append-only backups may continue.
- If locked, destructive operations are denied.
- If panic brake is active, normal movement remains paused until unlocked.
- If unlock is unavailable, recovery should still be possible from existing TrueNAS/restic/IDrive e2 snapshots.

## Storage hardening checklist

TrueNAS:

- Enable periodic snapshots on the backup dataset.
- Do not mount the snapshot management account on the desktop.
- Use a write-only or limited-permission share for the engine where possible.
- Test restoring from a snapshot.

IDrive e2 / S3:

- Use restic snapshots or S3 versioning/Object Lock where available.
- Use credentials that can write new objects but cannot purge old history.
- Store restic password outside the watched folders.
- Test `restic restore` on a sample photo/document.

OneDrive:

- Treat as convenient offsite sync, not the only recovery point.
- Do not rely on OneDrive alone for ransomware recovery.

## Validation scenario

The ransomware-safe validation should:

1. Create sample photo/document data and canaries.
2. Run a successful backup.
3. Simulate mass rename/delete/encryption-like changes.
4. Verify panic brake triggers.
5. Verify no destructive sync removes recovery points.
6. Require unlock before resume.
7. Restore a pre-event file from TrueNAS/restic-style history.
8. Record all events in the yard ledger.
