# Antigravity continuation prompt

Copy everything below into Antigravity.

---

Continue work on https://github.com/upgradedev/archon-treasury-aws on branch `design/archon-gtm-ui`. Do not work on, merge into, or deploy `main` without my explicit approval. Deliver a genuinely live, tested treasury application—not a mockup. Preserve existing backend integrations and financial safety rules.

## Read first
Read the entire repository, especially AGENTS.md, docs/REDESIGN_VERIFICATION.md, frontend/src/features/treasury/, src/archon_demo/, src/kerdon/, src/adapters/, infra/, packaging scripts and CI. Inspect current code and deployed configuration; do not infer readiness from this prompt or a healthy endpoint.

This branch adapts the design into the original React 18/Vite 5/Tailwind 3 application, not the separate Lovable TanStack review project. It adds 13 task views, backend-driven data, confirmations, refresh/error states and browser regression tests. Existing Python backend, treasury rules, AWS deployment configuration and adapters are unchanged.

Keep Navy Trust with azure accent; Instrument Serif display, Geist interface, JetBrains Mono money. Keep role colors in global CSS and reusable controls.

## Establish baseline
Run `PYTHONPATH=src:tests python3 -m unittest discover -s tests -v` from root. Start backend with `PYTHONPATH=src python3 -m archon_demo.server --port 8765`. In frontend/, install dependencies, run the existing build script and start on 5173; development proxy targets 8765. Install Python Playwright in your environment if needed and run `python3 frontend/tests/treasury_journeys.py` from root. The test allows localhost only and uses a fresh synthetic session. Run CI's full coverage, domain checks, packaging and smoke stages. Report actual results, never unrun checks as passed.

## Preserve financial correctness
Never bypass Writer gate checks, evidence-bound SHA-256 approvals, expired FX rejection, reserve floors, 21 completeness rules, selective deposit-triggered invalidation, deterministic request IDs, request-ledger payload identity, single-use closure, MCC restrictions or spend caps. Never move authoritative money, approval, permission or settlement decisions into browser code. Preserve integer-cent money and currencies. Add regression tests before changing a rule. Failed requests, retries, double clicks, concurrency, cold starts and timeouts must not create duplicate transfers or falsely claim settlement.

## Finish production gaps
1. Deployment: AWS currently serves Python-generated HTML at /. CI checks React but Lambda packaging excludes it. Design/test AWS-compatible static frontend plus same-origin /api routing, secure cookies, HTTPS, CSP, caching, deep links and rollback. Preserve the old UI until approved cutover. Changing frontend alone does not update the live site.
2. Durability: current sessions/ledger are in memory and reseed on cold start. Implement persistent tenant-scoped balances/evidence, approvals, idempotency records, receipts, audit and reconciliation suitable for AWS. Test concurrent workers, cold starts, recovery and transactional integrity. Do not seed synthetic money into live tenants.
3. Authentication/authorization: implement real identity, tenant isolation, least-privilege roles, approval permissions and separation of duties. Scope reads, writes and exports server-side. Add cookie-compatible CSRF protection, secure session lifecycle, access-control tests and verified signup/sign-in settings. Currency scope is a display filter, not authorization or tenancy.
4. Providers: independently configure Airwallex and Bedrock; current live Airwallex selection is coupled to ARCHON_ENABLE_LIVE_BEDROCK. Inspect and decouple safely. Metal uses a fake adapter. Verify sandbox first, permissions, beneficiaries, signed webhooks, replay protection, retries, reconciliation and receipts. Distinguish demo/sandbox/live; do not describe fake adapters as live. Keep credentials server-side in a secrets manager, never commit them.
5. Missing operations: implement persistent deposits, floor management, standalone FX quotes/conversions and integration setup through authenticated endpoints and tests. Unsupported operations are intentionally disabled; do not replace them with fake success.
6. UI hardening: split orchestration into focused modules; improve compact money display, narrow navigation, keyboard focus/trapping in confirmation dialogs, accessibility and receipt inspection without dropping actions. Surface service refusals. After accepted actions with refresh failures, prevent misleading retries and duplicate execution.
7. Operations: implement safe structured logs, metrics/tracing, alerts, reconciliation, incident recovery, dependency/security checks, backups/restore and rollback. Never log credentials or private invoice content unnecessarily.

## Existing contract inventory
GET /api/state and /api/audit-export.csv.
POST /api/approve/{obligation_id} {}; /api/execute/{obligation_id} {approval_sha256}; /api/simulate-deposit {currency,amount} (demo); /api/visa-issue {}; /api/visa-charge {charge_cents,merchant_mcc} (synthetic); /api/evaluate-invoice {obligation_id,mode,custom_text?}; /api/customer-email {contradicts} (demo); /api/metal-call/{agent_id} {}; /api/metal-rebalance {agent_id,new_price}; /api/metal-mandate {agent_id,new_max_price_cents}; /api/metal-dispute {}; /api/incident-fail {failure_type} (demo); /api/incident-resolve {}; /api/reset {} (demo).
Confirm response shapes and valid values from source; do not silently alter contracts or weaken error responses.

## Required release evidence
Verify authenticated tenant-scoped staging journeys with actual data: persisted deposit readback; selective approval invalidation; stale execution refused; reapproval and one-time execution; sealed receipts and audit export; floor breaches; expired quotes; duplicate/concurrent requests; card MCC/cap/single-use; invoice evaluation and provider failures; incidents/recovery; agent spending permissions/limits. Test desktop/mobile with screenshots and console/network checks. Prove survival through reload, session renewal and backend cold starts.

Separate implemented, tested, skipped and blocked work. Supply commands, test counts, staging URL, configuration names without secret values, deployment/rollback steps and remaining risks. Obtain my approval before main merge, production deployment, real payments or production-data changes. Name missing access as a blocker; do not invent success. A final live claim requires a deployed authenticated end-to-end journey with persisted readback—not a screenshot or green health check.
