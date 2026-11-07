# Isolated Redesign & Production Gaps Verification

Branch: `design/archon-gtm-ui`
Base: `808afd4a4c1101715785ca82798309c993cbe4c6`

## Scope Delivered on `design/archon-gtm-ui`

1. **Deployment & Static React SPA Hosting (Gap 1):**
   - `src/archon_demo/lambda_handler.py` serves the built React SPA (`frontend/dist/index.html`) at `/app` and deep links (`/app/*`), serves `/assets/*` with `Cache-Control: public, max-age=31536000, immutable` and path-traversal protection, preserves the legacy Python HTML at `/` by default (and at `/legacy`), and switches `/` to the React SPA when `ARCHON_SERVE_REACT_UI=1`.
   - `scripts/package_lambda.py` deterministically bundles `frontend/dist` into `archon_demo/static/` inside `temp/archon-lambda.zip` (`frontend_bundled: true`).

2. **Transactional Tenant Durability Across Cold Starts & Concurrent Workers (Gap 2):**
   - `src/archon_demo/persistence.py` and `src/archon_demo/sessions.py` persist tenant-scoped snapshots, balances, obligations, reserve floors, FX quotes/conversions, deposit history, 7-day `RequestIdLedger` entries, Merkle receipts, sessions, users, webhook replay IDs, and audit events in SQLite WAL with SHA-256 state checksum verification.
   - Live authenticated tenants created via `POST /api/auth/signup` (`is_live_tenant=true`) use `DemoService.empty_tenant()` and never receive synthetic demo money (`0` cents across all accounts).

3. **Authentication, Tenant Isolation, Least-Privilege RBAC, Separation of Duties & CSRF (Gap 3):**
   - `src/archon_demo/auth.py` implements PBKDF2-HMAC-SHA256 password hashing/verification, tenant-scoped `SessionPrincipal`, 5 least-privilege roles (`READER`, `EVALUATOR`, `APPROVER`, `WRITER`, `ADMIN`), Separation of Duties (`check_separation_of_duties` prevents the operator who approved an obligation from executing it), and constant-time `X-CSRF-Token` verification.
   - Routes added: `GET /api/auth/session`, `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/role`.

4. **Decoupled Provider Configuration & Signed Webhooks with Replay Protection (Gap 4):**
   - `src/adapters/live_transport.py` decouples `airwallex_enabled()` and `resolve_airwallex_mode_label()` (`ARCHON_AIRWALLEX_MODE` / `ARCHON_ENABLE_LIVE_AIRWALLEX`) from `ARCHON_ENABLE_LIVE_BEDROCK`.
   - `src/adapters/webhook.py` and `POST /api/webhooks/airwallex` enforce HMAC-SHA256 verification (`401` on invalid signature) and event-ID replay protection (`409 DuplicateWebhookError` on replay).
   - Metal (`simulated-metal-x402-adapter`) and Visa (`deterministic-mcc-mandate-engine`) are explicitly labeled as local deterministic adapters rather than live external rails.

5. **Missing Operations Implemented End-to-End (Gap 5):**
   - `POST /api/reserve-floor`: updates currency reserve floor and selectively invalidates pending approvals in that currency when bound evidence changes.
   - `POST /api/deposits`: records authenticated inbound deposits into the persistent tenant deposit ledger (`deposit_history`).
   - `POST /api/fx/quote` and `POST /api/fx/convert`: locks integer-ratio standalone FX quotes and executes conversions while refusing expired quotes (`409` + completeness rule `R12`) and reserve-floor breaches.
   - `GET /api/integrations` and `POST /api/integrations/verify`: returns decoupled provider readiness and ledger reconciliation.

6. **UI Hardening & Modularization (Gap 6):**
   - Extracted `ConfirmDialog.tsx` (with keyboard `Tab`/`Shift+Tab` focus trap, `Escape` dismissal, and focus restoration), `ReceiptInspector.tsx`, `OperatorAuthBar.tsx`, and `formatters.ts` (`compactMoney`).
   - Added `staleAfterMutation` lock in `TreasuryDashboard.tsx` so if post-mutation state refresh fails after an accepted request, mutating controls remain locked until state is refreshed.

7. **Operations, Redaction, Telemetry & Checksummed Backup/Restore (Gap 7):**
   - `src/archon_demo/observability.py` redacts credentials, cookies, CSRF tokens, Bearer tokens, and raw invoice text (`redact_payload`) and exposes operational counters/alerts at `GET /api/metrics`.
   - `GET /api/reconcile`, `GET /api/backup`, and `POST /api/restore` provide ledger reconciliation and SHA-256 checksummed tenant state backup and restore.

## Verified Locally (Actual Command Results)

- **Python Unit & Integration Suite (`PYTHONPATH=src:tests python -m unittest discover -s tests -v`):**
  - `122` tests run, `122` passed (`0` failures, `0` errors), including `7` multi-assertion production-gap regression suites in `tests/test_production_gaps.py`.
- **Offline Gate Runner (`python scripts/verify_gates.py --self-test`):**
  - `RESULT: PASS auto-gates=10 failed=none` (`122` unit tests, pure-domain imports, file sizes `<= 800` lines, integer cents only, text hygiene with zero em dashes, 21 completeness rules, `74/74` benchmark bound).
- **Security Audit (`python scripts/security_audit.py`):**
  - `SECURITY AUDIT: PASS checks=5 failed=none` (Python AST SAST, Frontend TS/TSX SAST, Secret Pattern Scan across 97 files, Terraform IaC Audit, OWASP HTTP Headers & 413 DoS cap).
- **Coverage Check (`python scripts/coverage_check.py 85`):**
  - `kerdon`: `95%` (`935/975`)
  - `archon_demo`: `92%` (`2104/2280`)
  - `adapters`: `88%` (`608/685`)
- **Deterministic Lambda Packaging (`python scripts/package_lambda.py`):**
  - Produces `temp/archon-lambda.zip` with `frontend_bundled: true`.
- **Frontend Build (`npm run build` in `frontend/`):**
  - `tsc && vite build` succeeded with `0` errors (`dist/index.html` and `dist/assets/*`).
- **Playwright Browser Regression (`python frontend/tests/treasury_journeys.py`):**
  - Verified all 13 navigable views, keyboard `Escape` dialog dismissal, EUR approval -> EUR 500.00 deposit selective invalidation -> re-approval -> execution -> Merkle receipt inspection, reserve-floor update, standalone FX quote lock & conversion execution, Virtual card issue -> MCC 5812 refusal -> MCC 5045 authorization & single-use closure, custom invoice evaluation, integration verification & reconciliation, page reload durability, and desktop (`1280x1800`) + mobile (`390x844`, `scrollWidth <= innerWidth`) layouts with `Errors: []`.

## Gated on Explicit User Approval (Not Run on `main`)

- Per branch instructions, `main` has **not** been modified, merged into, or redeployed.
- The live AWS Lambda endpoint continues serving the current `main` deployment until explicit cutover approval is granted.
