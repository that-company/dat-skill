# Dat Training API

Default base URL:

```text
https://api.thatcompany.ai/v1
```

## Authentication

Public intake can be used without authentication. It creates an approval URL. After a signed-in user approves, the request becomes a Dat session.

Authenticated calls use:

```http
Authorization: Bearer <token>
```

Use a user API key for authenticated intake, or the returned temporary key for one approved training session. Temporary keys expire after roughly 7 days and are limited to the approved session.

## One-Step Upload

Use the one-step endpoint for normal agent integrations:

```http
POST /training/jobs:upload
Content-Type: multipart/form-data
```

Fields:

```text
artifact                file, required
title                   string
instruction             string, required
artifactName            string
artifactContentType     string, usually application/gzip
artifactSizeBytes       decimal string, optional validation
artifactSha256          hex string, optional validation
```

Unauthenticated response shape:

```json
{
  "trainingJob": {
    "jobId": "trj_...",
    "state": "awaiting_approval",
    "title": "Training title",
    "approval": {
      "url": "https://thatcompany.ai/training/jobs/trj_...?token=..."
    },
    "status": {
      "url": "https://api.thatcompany.ai/v1/training/jobs/trj_...?token=..."
    }
  }
}
```

Authenticated response shape includes `sessionId`, `sessionUrl`, API URLs, and a temporary key when the job starts.

Example:

```bash
curl -sS -X POST "https://api.thatcompany.ai/v1/training/jobs:upload" \
  -F "title=Training smoke" \
  -F "instruction=Run ./run_all.sh and publish /tmp/dat-output deliverables." \
  -F "artifactName=artifact.tar.gz" \
  -F "artifactContentType=application/gzip" \
  -F "artifact=@artifact.tar.gz;type=application/gzip"
```

## Two-Step Upload

Two-step upload exists for clients that need to create metadata before streaming bytes.

Create:

```http
POST /training/jobs
Content-Type: application/json
```

Body:

```json
{
  "title": "Training title",
  "instruction": "Run ./run_all.sh and publish /tmp/dat-output deliverables.",
  "artifact": {
    "name": "artifact.tar.gz",
    "contentType": "application/gzip",
    "sizeBytes": 1234,
    "sha256": "..."
  }
}
```

Upload bytes to the returned `upload.url` with `PUT`, then use the returned approval/status URLs.

## Approval

Unauthenticated jobs must be approved in the browser through the returned approval URL. Agents should hand that URL to the user and wait for approval before assuming training has started.

## Status

Poll:

```http
GET /training/jobs/{jobId}
```

Use either the returned status-token URL or `Authorization: Bearer <temporary-key>`.

Important states:

```text
awaiting_upload
awaiting_approval
approved
queued
running
succeeded
failed
cancelled
expired
```

Treat `succeeded`, `failed`, `cancelled`, and `expired` as terminal. If `failed` includes an error payload, quote the exact failure in the user-facing report.

## Artifacts

List:

```http
GET /training/jobs/{jobId}/artifacts
```

Download:

```http
GET /training/jobs/{jobId}/artifacts/{artifactId}/content
```

Use the session temporary key. Public shared session pages may expose downloads, but API clients should use the artifacts endpoint.

Downloaded training result artifacts may be bundles. Inspect them for direct deliverables such as `model.joblib`, `best_model.pt`, `metrics.json`, `REPORT.md`, or a nested `compute-output/dat-output.tar.gz`.

## Cancel

Cancel:

```http
POST /training/jobs/{jobId}/cancel
```

Only cancel when explicitly requested by the user, or when acting under a clear policy for a runaway job.

## Package Contract

Artifacts are `tar.gz` archives. The archive should contain regular files with relative POSIX paths.

Do not include:

```text
.
absolute paths
../ traversal
symlinks
hardlinks
device files
.DS_Store
._*
.git
node_modules
virtual environments
large downloaded datasets
```

The training job should write final user deliverables to:

```text
/tmp/dat-output
```

The agent should not depend on files from an earlier Dat training run. Each remote training run is isolated.
