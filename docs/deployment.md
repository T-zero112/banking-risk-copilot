# Local Deployment and Reproduction

Target: Windows, Python 3.12, PowerShell and a running Docker Desktop Linux
engine. This is a localhost portfolio/demo deployment, not internet hosting.
PostgreSQL uses the existing pinned Compose image; `requirements-lock.txt` pins
the tested Python packages, including transitive and browser-test dependencies.
This is a version snapshot, not a hash-verified supply-chain lock. Linux/macOS
dependency installation and API cleanup have not been independently validated.

## First Run

From the repository root:

```powershell
.\start.ps1 -InstallDependencies -Initialize
```

The `py -3.12` launcher is needed only to create a missing `.venv`; an existing
Python 3.12 `.venv` can be used directly. If PowerShell blocks local scripts,
use a process-scoped invocation rather than changing machine policy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -InstallDependencies -Initialize
```

Initialization explicitly creates a missing `.env` from the example with a
random DB owner password, generates missing synthetic fixtures, starts the
database, applies additive migrations, prepares the policy index and restricted
roles, and bootstraps missing local accounts. It does not drop volumes, rerun
the base schema over existing business data, overwrite existing accounts or
silently rotate configured runtime passwords/API keys. Existing policy indexes
are left active. Existing configuration errors stop startup instead of being
overwritten. Initial role provisioning needs the admin connection; daily runtime
uses only the configured reader/audit connections.

If no active policy index exists, initialization calls the policy ingestion
script. That may download public source files and take time; unavailable MAS/FATF
sources are recorded, not claimed as coverage. At least one verified source is
required for indexing. This does not invoke a model provider. For cached PDFs:

```powershell
.\start.ps1 -Initialize -OfflinePolicies
```

A Git clone does not contain ignored public snapshots. Offline initialization
will fail without a verified cache; transfer only the public raw PDFs and policy
manifest, or perform normal ingestion. Never transfer `.env`, auth databases,
session records, credentials or customer audit payloads as a demo bundle.

Log in at the printed local URL using the generated account file described in
[user access](user-access.md). The temporary file contains plaintext onboarding
passwords: protect it with OS ACLs, rotate accounts and delete it afterwards.

## Daily Startup

```powershell
.\start.ps1
.\start.ps1 -CheckOnly
.\start.ps1 -Port 8001
```

Daily startup checks exact package versions, configured roles, the active policy
index and local accounts; starts the existing DB; and launches the API hidden
with stdout/stderr in ignored `data/runtime/`. It reuses a live API only if the
health response matches this project root. An unrelated occupied port is not
terminated: select another port explicitly. `-CheckOnly` does not initialize,
install packages, launch containers or start the API; dependencies must already
be running. Do not automatically retry a paid review after a startup failure.

`/health` checks process liveness only. `/ready` checks DB read connections,
policy state and admin-account presence, returning safe 503 errors when missing.
Neither endpoint writes an audit or calls a provider; write permissions are
tested separately by integration checks. DeepSeek is optional and is not probed
by readiness; a key is required only for an explicitly selected paid mode.

Local embedding weights and Playwright Chromium are not in the Python lock.
Download embedding weights when building the semantic index; install the browser
for UI checks using `.\.venv\Scripts\python.exe -m playwright install chromium`.
The basic SQL/lexical review requires neither embedding downloads nor an API key.

## Isolated Verification

Before publishing, run `.\.venv\Scripts\python.exe scripts/check_release.py`.
It checks tracked and non-ignored candidate paths, including accidentally tracked
secrets despite `.gitignore`; it does not scan arbitrary source content for keys.
See [observed verification results](deployment-verification.md) for actual scope.

```powershell
.\.venv\Scripts\python.exe scripts/verify_deployment.py
```

This creates an ignored verification directory, independent Python environment,
random owner credentials, fresh auth accounts, a separate named Compose project,
fresh PostgreSQL volume and separate ephemeral ports. It copies source files
and only the public PDF cache/manifest, never original secrets/accounts/audits.
Policy parsing/indexing are rebuilt offline. It checks the dependency install,
unit tests, API review, persisted success/failure, customer isolation, explicit
paid-consent denial, readiness and repeat startup. Provider keys are removed
from the test environment and no model calls are made.

`--reuse-python` skips the fresh Python install and is explicitly reported as
such. Package downloads need network/cache and disk space. Policy download
availability and embedding weight downloads are not covered by the offline test.
This is fresh DB/runtime verification on the same Windows host, not a second
physical machine or a production deployment/security assessment.

The generated API and only its test Compose project are stopped afterwards.
The test volume and directory are intentionally retained for diagnostics, using
extra disk. The directory contains new temporary secrets and must remain private.
Inspect its `result.json` and `verification.log`; do not upload the whole directory.
No automatic recursive filesystem or volume deletion occurs. Never use an
unverified computed path or the primary project name when cleaning it up.
