# Production Gaps and Roadmap

## Purpose and Decision Boundary

This is a proposed engineering roadmap for discussing a bank-hosted analyst
assistant. It is NOT implemented functionality, a regulatory checklist, legal
advice, a certification or an approved implementation plan. No bank has reviewed
or signed off this project. Applicability, obligations and acceptance criteria
must be determined by that bank's business, compliance, legal and risk teams.

Current delivery is a localhost portfolio MVP using synthetic data and two public
SPF/STRO sources. Fixed SQL identifies demo candidates; AI explains evidence for
human review. Text-to-SQL, full policy coverage and production hosting are absent.
See [architecture](architecture.md) and [observed evaluation](final-evaluation.md).

Proposed first production use: prepare evidence-linked draft summaries for an
authorized analyst. Exclude autonomous account freezing, customer rejection,
regulatory filing, risk certification and laundering conclusions. A reviewer
must approve any downstream action. Human review alone is not a sufficient
control: workflow permissions must prevent the assistant from executing actions.

## Gap Register

All proposed controls below are pending; existing controls are local-demo scope.
Owners are suggested bank functions, not people assigned to this repository.
P0 blocks any real-data pilot; P1 blocks operational use; P2 supports expansion.

| Priority / area | Existing evidence | Gap and proposed work | Suggested owner | Acceptance evidence |
| --- | --- | --- | --- | --- |
| P0: use-case governance | Human-review flag and caveats | Define intended users, prohibited decisions, harm scenarios, review responsibilities and escalation | Business sponsor, compliance, model risk | Approved use-case scope, risk classification, accountability matrix and tested action boundaries |
| P0: data and privacy | Synthetic fixtures; ignored local artifacts | Authorize data use, minimize/redact fields, classify information, map cross-border/provider flows, define retention and deletion including backups | Data owner, privacy/legal, security | Approved data-flow assessment, access matrix, retention schedule and deletion/access tests |
| P0: model supplier | Explicit DeepSeek calls and consent; no retries | Review provider contracts, processing/storage/training terms, locations, subprocessors, incident support and exit strategy; select approved hosting | Procurement, legal, third-party risk, security | Written approval of supplier/deployment and data transfer; tested restricted egress; do not assume existing API is approved |
| P0: identity and access | Local scrypt login, customer assignment and DB roles | Integrate enterprise SSO/MFA, service identities, least privilege, joiner/mover/leaver process and privileged-access controls | IAM, security, application owner | Approved access design, deprovision/revocation tests, cross-customer tests and privileged-operation review |
| P1: evidence and policy | Two cited source snapshots, fixed SQL and pair provenance | Validate source authority/rights, expand only to approved relevant policies, version effective dates, resolve superseded/conflicting rules; validate data definitions | Compliance content owner, data engineering | Reviewed corpus manifest, effective-date retrieval cases and reconciled SQL/business calculations |
| P1: independent model validation | 116 unit tests, 11 free scenarios, small version-mixed live history | Build representative independently labeled holdout cases; repeat tests on frozen versions; evaluate factual support, missing evidence, unsafe advice and bias | Independent model validation, subject-matter experts | Approved protocol, protected holdout results, uncertainty/failure analysis and documented release decision |
| P1: threat testing | Local same-origin boundary, narrow validation, one injection example | Test malicious documents, multilingual attacks, unauthorized data disclosure, indirect injection, supply chain and resource abuse | Security testing, application team | Threat model, red-team and penetration reports, remediation retests; broad security claims prohibited |
| P1: reliability and spending | Timeout, no retries, audit-start blocking and partial success | Set concurrency limits, durable job states, client retry/idempotency rules, cancellation behavior and per-user/batch spend budgets | Engineering, platform/SRE, finance | Load/fault tests, no duplicate billed jobs, bounded queues/spend and verified safe fallback |
| P1: audit and retention | Start/completion snapshots and constrained write roles | Centralize security/business events, manage encryption and retention, restrict exports, detect tampering and validate privileged access | Audit, security, records management | Traceability of decisions to versions/evidence; approved retention and tamper/access tests; current hashes alone are not tamper-proof |
| P1: operations and recovery | Local readiness and historical fresh-environment check | Managed infrastructure, encrypted transport, backups, restore/disaster recovery, actionable alerts and incident runbooks | Platform/SRE, security, application owner | Approved service objectives, measured restore/failover exercises, on-call ownership and incident drills |
| P1: release governance | Locked package versions, path-based publication guard | Isolate environments, scan source/dependencies, protect CI, review changes, version model/prompt/corpus/schema and support rollback | Engineering, security, change management | Reproducible signed-off build, vulnerability disposition, staged rollout and demonstrated rollback |
| P2: outcomes and expansion | Demo workflow only | Measure reviewer workload, error/rework and usefulness before wider rollout; define drift/revalidation triggers | Product, operations, model risk | Controlled pilot outcomes, monitoring baseline and approval for each expanded use case |

## Evaluation Design Before a Pilot

Freeze code, prompts, schema, provider model/configuration and corpus versions.
Preserve provenance for every test. Model aliases may change upstream: record
provider-reported versions when available and do not claim reproducibility that
the provider cannot guarantee.

Use independently reviewed cases spanning no-rule customers, real review
candidates, absent/obsolete/conflicting policy, incomplete data, language variants,
adversarial evidence and provider outages. Separate training/development cases
from holdout evaluation; prevent customer/document leakage across splits. The
existing synthetic fixtures are useful regressions, not representative samples.

Measure separately:

- Claim correctness and supporting-evidence entailment, not JSON acceptance.
- Citation correctness, policy applicability and acknowledgment of missing evidence.
- Unsupported allegations/actions, data disclosure and unsafe retrieval behavior.
- Refusal/abstention quality and analyst corrections or disagreements.
- Repeat-call variability, latency, failure rates and per-completed-review cost.
- End-to-end analyst outcomes against an approved non-AI baseline. The assistant
  is not a validated fraud classifier; do not report classifier recall as its
  capability unless that distinct task and labels are explicitly validated.

Sample size and pass thresholds must follow harm severity, use-case scope and
desired statistical confidence. Do not pick an arbitrary accuracy percentage or
reuse this project's unit-test count as the acceptance threshold. Severe unsafe
events need explicit investigation and risk-owner disposition, even with a good
aggregate score. Independent validators should not be the only developers who
tuned the prompts. Human reviewer agreement and uncertainty must be recorded.

## Staged Gates

### Gate A: Admission Assessment

Complete P0 decisions, stakeholder ownership, threat/data flows and supplier
approval. Until approval, keep synthetic data only and do not send real customer
data through the current API. Produce an approved use-case charter and scoped
pilot plan. A bank may decline external hosting or require a different model.

### Gate B: Controlled Shadow Pilot

After Gate A, run an isolated, authorized pilot using only approved data and
deployment. Outputs do not affect customers or regulatory actions. Complete P1
controls relevant to that pilot, independent testing, recovery and security
reviews. Track analyst corrections and operational failures. Data approval is
not blanket permission to use every supplier or reuse every customer field.

Exit needs evidence that approved safety/quality/service criteria are met, all
material findings are resolved or accepted by accountable owners, and rollback
and incident responsibilities are exercised. This repository cannot supply
these approvals itself.

### Gate C: Limited Operational Rollout

Require bank change, business, model-risk, compliance and security approvals as
applicable. Limit users/data/workflows; preserve mandatory human decisions and
technical action boundaries. Monitor, support manual-only fallback, and stop or
revert if agreed limits are breached. Expansion is a new risk decision, not an
automatic consequence of one successful pilot.

Revalidate on material model/provider, prompt, schema, policy, data-population or
use-case changes. Agree periodic reviews and emergency suspension rules with
owners; a fixed schedule alone does not cover upstream changes.

## Trade-offs and Costs

External hosting adds contractual/privacy and dependency risks; internal hosting
adds infrastructure, patching and model-operation effort. More retention helps
failure analysis but increases sensitive-data exposure: use approved redaction,
access controls and bounded diagnostic samples instead of keeping raw answers
by default. Stricter rejection can reduce unsupported prose while increasing
manual workload. Independent labeling, reviewers, IAM integration, security tests
and resilience exercises are real costs beyond token spending.

No production duration, staffing or money estimate is defensible without the
bank's scope, environment, procurement process and risk appetite. Confirm these
inputs before estimating. This roadmap does not imply a few more coding days
will achieve bank acceptance.

## Portfolio Next Step

The gap register and gate plan are a design artifact only. For the portfolio,
continue with source/secret publication review, license selection and a short
demonstration. Do not implement bank-specific infrastructure or spend on further
model tests without a defined need. No new paid calls, real data, account changes
or production integrations were introduced in preparing this document.
