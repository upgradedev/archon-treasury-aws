"""Hosted-model baseline on the frozen benchmark cases. Spends API tokens.

One unconstrained single pass per case: the model sees a JSON snapshot and
the 21 rule names, and must answer with one rule ID or NONE. That is the
honest hosted counterpart to the coded naive matcher in run_benchmark.py.
Never runs in CI or gates. Expect roughly 62 short Bedrock calls.

Run: PYTHONPATH=src python scripts/run_llm_benchmark.py [--limit N]
"""

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("run_benchmark", ROOT / "scripts" / "run_benchmark.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

from adapters.bedrock_evaluator import bedrock_converse
from kerdon.completeness import RULES


def snapshot_json(snap) -> str:
    def money(m):
        return {"cents": m.amount_cents, "currency": m.currency}

    payload = {
        "as_of": snap.as_of.isoformat(),
        "balances": [{"account": b.account_id, **money(b.amount)} for b in snap.balances],
        "reserve_floors": [money(f) for f in snap.reserve_floors],
        "obligations": [
            {"id": o.obligation_id, "counterparty": o.counterparty_id, **money(o.amount),
             "due_at": o.due_at.isoformat() if o.due_at else None, "status": o.status.value,
             "fx_quote_id": o.fx_quote_id, "settle_currency": o.settle_currency}
            for o in snap.obligations
        ],
        "ledger": [
            {"id": e.entry_id, "counterparty": e.counterparty_id, **money(e.amount), "booked_at": e.booked_at.isoformat()}
            for e in snap.ledger_entries
        ],
        "documents": [
            {"id": d.document_id, "kind": d.kind.value, "counterparty": d.counterparty_id, **money(d.amount),
             "invoice_number": d.invoice_number, "obligation_id": d.obligation_id, "sha256_ok": len(d.content_sha256) == 64}
            for d in snap.documents
        ],
        "fx_quotes": [
            {"id": q.quote_id, "from": q.from_currency, "to": q.to_currency, "expires_at": q.expires_at.isoformat()}
            for q in snap.fx_quotes
        ],
        "executions": [
            {"id": x.execution_id, "request_id": x.request_id, "has_approval": bool(x.approval_sha256)}
            for x in snap.executions
        ],
        "pending_approvals": [{"obligation": p.obligation_id} for p in snap.pending_approvals],
    }
    return json.dumps(payload)


def main(argv) -> int:
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    cases = bench.rule_cases()
    if limit:
        cases = cases[:limit]
    rule_lines = "\n".join(f"{rid} {name}" for rid, name, _fn in RULES)
    correct = 0
    start = time.perf_counter()
    for i, (name, snap, expected) in enumerate(cases, 1):
        prompt = (
            "You audit treasury completeness. Rules:\n" + rule_lines +
            "\n\nCase data (JSON):\n" + snapshot_json(snap) +
            "\n\nIf exactly one rule is violated answer with its ID only (like R07). "
            "If none is violated answer NONE. One token answer."
        )
        answer = bedrock_converse(prompt).strip().upper()
        ok = (expected in answer) if expected else ("NONE" in answer)
        correct += int(ok)
        print(f"{i}/{len(cases)} {name} expected={expected or 'NONE'} got={answer[:24]!r} {'OK' if ok else 'MISS'}", flush=True)
    elapsed = int(time.perf_counter() - start)
    print(json.dumps({
        "cases": len(cases), "llm_correct": correct,
        "llm_accuracy": f"{correct}/{len(cases)}", "elapsed_s": elapsed,
        "model": "eu.anthropic.claude-haiku-4-5-20251001-v1:0 via Bedrock converse, temperature 0",
        "engine_on_same_cases": "see run_benchmark.py (62 rule cases subset of 74/74)",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
