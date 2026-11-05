"""One live Bedrock evaluator round trip. Spends roughly 100 tokens.

Run with AWS credentials: PYTHONPATH=src python scripts/run_evaluator_live.py
Prints the proposed ApprovalIntent digest on a match, or the deterministic
refusal reasons on a mismatch. Never runs in CI or in verify_gates.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from adapters.bedrock_evaluator import BedrockEvaluator
from kerdon.money import Money
from kerdon.models import Balance, Obligation, TreasurySnapshot


def main() -> int:
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    obl = Obligation("obl-1", "supplier-a", Money(50_00, "USD"), now + timedelta(days=10))
    snap = TreasurySnapshot(
        as_of=now,
        balances=(Balance("acct-USD", Money(1_000_00, "USD")),),
        obligations=(obl,),
        reserve_floors=(Money(100_00, "USD"),),
    )
    evaluator = BedrockEvaluator()
    for label, text in (
        ("matching", "Invoice INV-1. Counterparty: Supplier-A. Total due USD 50.00."),
        ("mismatched", "Invoice INV-2. Counterparty: Supplier-A. Total due USD 51.00."),
    ):
        try:
            intent = evaluator.propose_from_text(snap, "obl-1", text)
            print(f"{label}: PROPOSED sha256={intent.sha256}")
        except Exception as exc:  # refusal is the expected second outcome
            print(f"{label}: REFUSED {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
