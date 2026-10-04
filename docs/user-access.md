# Local Login and Customer Access

This is local demo authentication and API customer authorization, not bank-grade
identity infrastructure or PostgreSQL row-level security. Keep the server bound
to 127.0.0.1 and use only synthetic evidence.

## Accounts and Sessions

Accounts, customer assignments, session token hashes and login failure limits are
stored in ignored `data/auth/accounts.sqlite3`. Banking query and audit roles stay
unchanged; the API does not acquire management privileges over the banking database.
The separate local SQLite store is deliberately small and has no web management
endpoint. OS access to its files is trusted: someone who controls this workspace
can change assignments or run maintenance CLIs outside the API boundary.

Passwords use scrypt with unique random salts. Opaque 256-bit random sessions are
stored hashed, expire after two hours, and are revoked on logout or account update.
Cookies are HttpOnly and SameSite=Strict. Secure is enabled on HTTPS, but is not
set for this localhost HTTP demo. Passwords and session tokens are never stored
in browser local/session storage. Ten failed attempts per source IP trigger a
15-minute login window limit. Shared-localhost IP limits can affect other demo
users; this is not distributed abuse detection or MFA.

Default bootstrap creates `admin` and `reviewer`; reviewer is assigned C003 only.
Random initial passwords are in ignored `data/auth/bootstrap-credentials.txt`.
This temporary plaintext file is for local onboarding only; rotate passwords
with the interactive script and remove the file afterwards. Never commit or
share it, the auth DB or evaluated customer payloads. Protect them with OS ACLs.

```powershell
.\.venv\Scripts\python.exe scripts/setup_local_accounts.py --bootstrap
# Existing accounts are never overwritten by bootstrap.
# Interactive password entry, never command-line passwords:
.\.venv\Scripts\python.exe scripts/setup_local_accounts.py --username admin --role admin
.\.venv\Scripts\python.exe scripts/setup_local_accounts.py --username reviewer --role reviewer --customer C003 --customer C004
```

Updating an account replaces its assignments and revokes all its sessions.
Backing up the auth DB also backs up password hashes/assignments; treat it as
sensitive and do not distribute a workspace snapshot with active sessions.

## API Boundary

- `POST /auth/login`: JSON username/password; generic failure, no body echo.
- `GET /auth/me`: authenticated username, role and current customer assignments.
- `POST /auth/logout`: revoke current session and remove cookie.
- `POST /reviews`: authenticate first; reviewer needs the requested customer
  assignment, while admin can access all customers. Unauthorized requests are
  denied before SQL/model execution. Authorization is rechecked before returning
  a completed review; revocation does not cancel an already-started provider call.
- DeepSeek mode also requires a literal JSON boolean `paid_consent: true` per
  request. A logged-in admin is not implicitly consenting to paid execution.
- `GET /reviews/{id}`: current customer permission is checked before returning
  metadata, report or policy evidence. Unassigned records return 404 like absent
  records, even for historical requests predating login support. Permission is
  by customer, not by report creator; coworkers assigned the same customer share
  its reports. The workbench JSON download re-fetches this protected endpoint.

The audit metadata contains the server-derived actor username and role for API
reviews; clients cannot supply them. CLI reviews are marked local maintenance.
Origin and browser fetch-site restrictions plus Strict cookies protect the local
browser boundary. No CORS access is enabled. These assumptions are not a reviewed
internet deployment model; HTTPS, enterprise SSO/MFA, security-event auditing,
account recovery, network-level limits and production threat testing remain work.

Logout clears rendered report content/history and broadcasts logout to other
open tabs. Downloaded files cannot be revoked after delivery. Client rendering
is not the permission boundary: the server protects every report request.

## Verification

83 unit tests and browser checks at 390/768/1440 widths passed, without paid
model calls. The auth directory and files were restricted to the current Windows
user via file ACLs; local administrators can still take ownership. The account
bootstrap and credential rotation procedures must preserve this protection.

Unit tests cover anonymous requests, role/identity forgery, two reviewers with
different assignments, admin access, expired/revoked sessions, live assignment
revocation, revocation during a review, denied historical reports, secure cookie
properties, hashed password/token storage, rate limits and paid consent.

`scripts/verify_workbench.py` uses temporary bootstrap credentials from the local
file to test actual logins, deterministic reviews, persisted actor identity,
report downloads, customer denial and logout at three viewport widths. Its model
states are mocked; no paid calls are made. After password rotation, replace that
test fixture strategy rather than putting passwords into tracked files.

The prior evaluation-suite CLI remains a trusted local maintenance path, not a
multi-user API. It still requires explicit `--live` to incur provider charges.
