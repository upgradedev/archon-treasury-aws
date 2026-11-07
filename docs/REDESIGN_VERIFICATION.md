# Isolated redesign verification

Branch: `design/archon-gtm-ui`.
Base: `808afd4a4c1101715785ca82798309c993cbe4c6`.

## Scope
Original React frontend redesigned into 13 navigable task views. Same-origin API requests retain original session cookie handling. Backend, adapters, domain, infrastructure and CI unchanged. Confirmations, serialized mutations, error display and refreshed state added. Unsupported FX/floor/configuration operations disabled; simulations labeled.

## Verified locally
- Baseline and post-change Python unittest suites: 115 passed, 0 failed, 0 skipped each.
- Frontend tsgo --noEmit and Vite production build passed.
- Browser test against the original local Python backend: all 13 views; EUR approval, EUR 500.00 deposit, INVALIDATED, reapproval, execution, PAID, service receipt.
- Invalidated execution disabled in UI; existing backend tests enforce stale-execution rejection.
- Card issued, MCC 5812 refused, MCC 5045 authorized and single-use closure returned by service.
- Custom invoice evaluation read back through the UI.
- Desktop 1280x1800 and mobile 390x844 screenshots inspected; no document overflow or browser page errors.

## Not verified
No production deployment, real payment, authenticated journey or provider credentials verified. Tests use synthetic state with the original backend. Full CI coverage/domain-check matrix and security scan not run. Not every incident/agent/evaluator mutation has browser coverage. Production persistence and tenant authorization not supplied by UI work. AWS packaging currently does not deploy React. Native meter style is browser-dependent. Confirmation focus management, narrow navigation and compact money formatting need further hardening.

Tests: PYTHONPATH=src:tests python3 -m unittest discover -s tests -v; start backend at 8765, frontend at 5173; python3 frontend/tests/treasury_journeys.py. See ANTIGRAVITY_HANDOFF.md.
