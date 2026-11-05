# HackerEarth form fields, copy-paste ready for the owner submit

Every value below is consistent with README.md and docs/SUBMISSION.md. Update the demo line only if the URL changes; keep numbers identical everywhere (gate G1).

Project name: Archon Treasury (powered by Kerdon)

One-line summary: Archon Treasury recalculates Airwallex FX and supplier payouts when a deposit lands, invalidating stale approvals so cross-border teams never breach their cash reserve floor.

Live demo (no login): https://pjlgavqdkhrcserxuqjz6icit40vbfxv.lambda-url.eu-west-1.on.aws/

Repository: https://github.com/upgradedev/archon-treasury-aws (MIT)

Video: PENDING (script in docs/VIDEO_SCRIPT.md; record by 2026-11-10, public YouTube, under 3 minutes).

Built with: Airwallex Sandbox API shape (fake transport in the public demo, labelled on the page; live transport coded), Amazon Bedrock (Claude Haiku evaluator, verified live), AWS Lambda Function URL, Python standard library, SHA-256 content-addressed approvals, Merkle-sealed spoken receipts, Metal USDZ spend governor (offline model).

Starter kits: Kit 1 Adaptive Treasury Controller, Kit 3 Payment Ops Incident Commander, Kit 11 Metal x402 Business Agents (governor model).

Description: paste docs/SUBMISSION.md in full.

Try it in 60 seconds: open the demo, approve one USD and one EUR payout, land a EUR 500 deposit, execute the USD payout, then try the stale EUR one and read the refusal.
