# Edge Backup Python Client User Guide

The Python client watches a folder, classifies files into package types, optionally copies each file to repository destinations, and reports completed packages to Catcher.

## Quick demo: local repository + S3-style repository

Start Catcher in one terminal:

```bash
cd backend
python3 -m uvicorn main:app --port 8000
```

Start the web dashboard in another terminal:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Run the repository demo in another terminal:

```bash
python3 scripts/client-repository-demo.py
```

The demo:

1. Creates sample data under `/tmp/edge-client-repository-demo/watch`.
2. Runs the Python client once with `CLIENT_TEXT_UI=1`.
3. Copies each package to:
   - local repository: `/tmp/edge-client-repository-demo/repositories/local`
   - S3-style repository: `/tmp/edge-client-repository-demo/repositories/s3`
4. Verifies each repository copy by checksum.
5. Reports completed `local/...` and `s3/...` package rows to Catcher.

Open the dashboard after completion:

```text
http://127.0.0.1:5173/#packages
```

The Packages page should show completed rows such as:

| Path | Type | Status |
|------|------|--------|
| `local/Documents/family-notes.txt` | `user_data` | `completed` |
| `s3/Documents/family-notes.txt` | `user_data` | `completed` |
| `local/logs/desktop-app.log` | `app_logs` | `completed` |
| `s3/audit/login-audit.json` | `audit_logs` | `completed` |
| `local/exports/budget.csv` | `business_data` | `completed` |
| `s3/exports/documents-package.tar.gz` | `job_package` | `completed` |

Optional screenshot capture:

```bash
npx playwright install chromium
npx playwright screenshot --browser chromium --wait-for-timeout=2000 \
  http://127.0.0.1:5173/#packages /tmp/edge-client-repository-demo/artifacts/catcher-packages.png
```

## Run the client manually

```bash
export CATCHER_URL=http://127.0.0.1:8000
export WATCH_DIR=/path/to/data
export SOURCE_ID=linux-desktop
export CLIENT_TEXT_UI=1
export LOCAL_REPOSITORY_DIR=/mnt/truenas/backups/linux-desktop
export S3_REPOSITORY_DIR=/tmp/s3-demo/linux-desktop
export S3_REPOSITORY_URI=s3://my-demo-bucket/linux-desktop
python3 clients/docker-client/watch_and_ingest.py
```

For demo use, `S3_REPOSITORY_DIR` is a local filesystem directory that stands in for an S3 bucket. For a real S3-compatible service, use the future rclone/restic destination work and keep `S3_REPOSITORY_URI` as the display label.

## Client options

| Environment variable | Purpose | Example |
|----------------------|---------|---------|
| `CATCHER_URL` | Catcher API base URL | `http://127.0.0.1:8000` |
| `WATCH_DIR` | Folder to scan | `/home/alex/Documents` |
| `SOURCE_ID` | Client/source name in Catcher | `linux-desktop` |
| `POLL_INTERVAL` | Seconds between scans | `5` |
| `CLIENT_TEXT_UI` | Enable terminal table | `1` |
| `CLIENT_TEXT_UI_LIMIT` | Recent rows to display | `20` |
| `CLIENT_RUN_ONCE` | Scan once and exit, useful for demos/tests | `1` |
| `DEFAULT_PACKAGE_TYPE` | Fallback type for unknown extensions | `user_data` |
| `LOCAL_REPOSITORY_DIR` | Local/NAS repository directory | `/mnt/truenas/backups/linux-desktop` |
| `S3_REPOSITORY_DIR` | Filesystem-backed S3 demo repository | `/tmp/s3-demo/linux-desktop` |
| `S3_REPOSITORY_URI` | Label shown for S3-style destination | `s3://bucket/prefix` |

If no repository variables are set, the client only reports metadata to Catcher.

## Text UI states

| State | Meaning |
|-------|---------|
| `hashing` | Client is computing the SHA-256 checksum. |
| `uploading` | Client is copying to a configured repository destination. |
| `verified` | Repository copy exists and checksum matches. |
| `registering` | Client is posting package metadata to Catcher. |
| `in_progress` | Catcher registered the package; client is patching completion. |
| `completed` | Repository upload and Catcher status are complete. |
| `failed` | Copy, verification, or Catcher request failed. |
| `skipped` | Client could not safely checksum the file. |

## Package type classification

| File/path pattern | Package type |
|-------------------|--------------|
| default/unmatched files | `user_data` |
| `*.log`, `*.out`, `*.err` | `app_logs` |
| any path containing `audit` | `audit_logs` |
| `*.csv`, `*.db`, `*.sqlite`, `*.sql`, spreadsheets | `business_data` |
| `*.tar.gz`, `*.zip`, `*.7z`, archive packages | `job_package` |
| `.cache/`, `cache/`, `*.tmp`, `*.temp` | `cache` |

Set `DEFAULT_PACKAGE_TYPE` to change the fallback for files that do not match a pattern.

## Real-world mapping

For a Linux desktop with TrueNAS, OneDrive, and IDrive e2:

```text
LOCAL_REPOSITORY_DIR=/mnt/truenas/backups/linux-desktop
S3_REPOSITORY_URI=s3://idrive-e2-bucket/linux-desktop
```

OneDrive and IDrive e2 should be handled by the rclone/restic destination tasks in the personal-computer MVP. Until those adapters are implemented, this client demo uses filesystem-backed repositories to prove the upload/status flow.
