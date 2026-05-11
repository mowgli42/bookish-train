# Edge Backup Railway Architecture

This project uses a railway metaphor for both product language and implementation concepts. The goal is to make the system easy to reason about: clients load trains with information, move them over rails, and report where each car is stored.

## Vocabulary

| Railway term | Software concept | Responsibility |
|--------------|------------------|----------------|
| **Engine** | Client running on a personal computer or server | Moves data. Watches files, builds packages, copies to destinations, verifies checksums, and reports status. |
| **Railcar** | Backup package or file payload | Unit of data being moved. |
| **Consist** | Group of railcars for one run | A backup run that may include many files/package types. |
| **Manifest** | Package metadata | Path, package type, size, checksum, destination, status, timestamps, and resume token. |
| **Route** | Configured destination plan | Ordered destinations such as local repository, TrueNAS, OneDrive, IDrive e2/S3, or restic repository. |
| **Station / Yard** | Storage destination | Where data is actually stored. Examples: local repo, TrueNAS share, S3 bucket, OneDrive remote, IDrive e2 bucket. |
| **Dispatcher** | API backend formerly called Catcher | Control plane. Tracks manifests, routes, status, configuration, resume instructions, and activity journal. It does not move payload bytes. |
| **Signal Board** | Web dashboard / text UI | Read-only operations view over dispatcher state: trains, cars, stations, errors, and resume status. |
| **Switch list** | Resume/work queue from the dispatcher | Instructions an engine uses after restart or failure to continue unfinished railcars. |
| **Yard ledger** | Append-only activity journal | Durable audit trail of config changes, client reports, route changes, transfer attempts, verification, failures, and resumes. |
| **Timetable** | Versioned configuration snapshot | Backup of routes, retention rules, destination definitions, and client defaults. |

## Control plane vs data plane

The architecture is intentionally decoupled.

```text
DATA PLANE
  Engine/client
    -> local repo / TrueNAS / OneDrive / IDrive e2 / S3 / restic repo
    -> verifies checksums at the storage station

CONTROL PLANE
  Engine/client
    -> Dispatcher API: manifest, progress, destination status, checksum, errors
  Signal Board/webpage
    -> Dispatcher API: read status, routes, journal, resume work
```

Rules:

1. Engines move payload data. The dispatcher API does not copy user files between destinations.
2. Engines verify data before marking a railcar complete.
3. The dispatcher records where data is stored, what checksum was verified, and what remains unfinished.
4. The Signal Board reads dispatcher state; it does not talk directly to storage stations for normal status.
5. Storage stations are independent. A local repo can succeed while S3 fails; each destination gets its own manifest/status.

## Resume model

Every railcar movement needs enough metadata for an engine to resume safely:

- stable `manifest_id` / resume token
- `source_id` (engine)
- source path and package type
- destination station id and display URI
- size and checksum
- current state: queued, loading, in_transit, verified, registered, complete, failed
- last successful checkpoint
- retry count and last error
- timestamps for created, updated, completed

After a client restart or failure, the engine asks the dispatcher for its switch list:

```text
GET /api/v1/sources/{source_id}/resume
```

The response should include unfinished railcars and enough checkpoint data to decide whether to skip, verify, retry, or mark failed. Clients remain authoritative for actual file movement and checksum verification.

## Configuration backup

Configuration is operationally important and must not exist only in process memory.

The dispatcher should keep versioned timetable snapshots for:

- route definitions
- storage station definitions
- retention rules
- package type policies
- client defaults
- dashboard-visible labels

Minimum operations:

- create snapshot after every config change
- export config snapshot to JSON
- restore config from a selected snapshot
- show current config version/hash in the Signal Board
- include config changes in the yard ledger

## Activity journal

The yard ledger is append-only. It should record:

- client registration
- route/config changes
- package manifest creation
- transfer started/completed/failed
- checksum verified/mismatch
- resume requested
- retry scheduled
- config snapshot/export/restore

Journal records should include:

- event id
- timestamp
- actor/source
- event type
- related manifest/package id
- destination/station id when applicable
- before/after status where applicable
- checksum/hash where applicable
- error details when applicable

The journal should be exportable for backup and troubleshooting.

## Naming guidance for code

New code should prefer railway names where it does not break existing API compatibility:

- `engine` for client-side data movement code
- `manifest` for package metadata
- `route` for destination plan
- `station` for storage destination
- `dispatcher` for API/control-plane internals
- `signal_board` or `dashboard` for UI
- `journal` for append-only event records
- `timetable` for versioned configuration snapshots

Existing public endpoints can keep `/packages`, `/sources`, and `/buckets` until compatibility work is planned. New fields and internal modules should move toward the railway vocabulary.
