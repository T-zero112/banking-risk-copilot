# Deployment Verification: 2026-10-04

## Delivered

- `start.ps1`: explicit dependency installation/initialization, daily startup,
  check-only mode, selectable API port and no destructive reset commands.
- `requirements-lock.txt`: exact tested Python package versions, including
  transitive dependencies, with Windows-only package markers.
- `scripts/start_project.py`: runtime checks, safe actionable errors, restricted
  connections, additive initialization, hidden API launch and own-instance reuse.
- `/ready`: dependency readiness distinct from `/health` process liveness.
- `.env.example`, README and deployment guide: optional provider keys, separate
  initialization, policy cache/download prerequisites and secret-handling limits.
- `scripts/verify_deployment.py`: isolated verification, leaving the primary
  database/accounts alone and stopping only generated test services afterwards.
- `scripts/check_release.py`: reject private/generated files among Git publishing
  candidates. This is a path guard, not a general secret-content scanner.

## Observed Results

Run `82a58ee87e8d` created an independent Python 3.12 environment and successfully
installed the exact dependency lock, including a passing `pip check`. It used
fresh DB/auth stores, rebuilt policy chunks offline and passed API/audit/access
checks plus repeat startup. Its source snapshot then had 83 passing unit tests.

Run `e943b3eab2d7` reused that independently installed Python environment while
re-copying the newer source into another isolated workspace and creating another
fresh DB/auth store. It passed readiness, API success/failure persistence,
reviewer denial on C004 and its history, permitted C003 review, and paid-consent
denial without invoking DeepSeek. Its newer snapshot passed 89 unit tests.

Both results report `passed: true`, `paid_calls: 0`,
`public_policy_cache_reused: true` and `external_downloads_verified: false`.
Both copied only cached public PDFs/manifests, not primary `.env`, auth stores,
sessions or audit payloads. Two SPF sources were rebuilt; MAS/FATF had no cache
and were reported unavailable. Embedding weights and browser binaries were not
downloaded by these deployment checks.

The test APIs and containers were stopped; their diagnostic directories and named
volumes remain intentionally retained, using extra disk and containing newly
generated test secrets. They are ignored by Git and must not be shared wholesale.

After restoring Docker Desktop, the primary project passed `start.ps1`,
`start.ps1 -CheckOnly`, `/ready`, and repeat daily startup with the existing
API reused. No primary schema reset or account/credential rotation was requested.
Docker-unavailable diagnostics and test cleanup were then improved locally.
The final primary-workspace unit suite passed 91 tests, and the publication-path
guard passed 109 Git candidates with private/generated paths excluded. These
checks made no model calls. The isolated snapshot counts above are intentionally
not relabelled as if they had run those later-added tests.

## Limits

This is verified local Windows reproduction, not a production/cloud deployment,
second physical machine test or comprehensive security audit. External source
availability, native browser downloads, embedding-model downloads and package
artifact hashes remain separate concerns. Existing live model quality issues
and unperformed paid retests remain unchanged by deployment work.
