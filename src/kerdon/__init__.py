"""Kerdon deterministic treasury core for Archon Treasury.

Pure domain: stdlib only, integer cents only, no clock, no network.
Adapters (Airwallex, Bedrock, Metal) live outside this package and
implement the ports in kerdon.ports.
"""

from kerdon.approvals import (
    ApprovalIntent,
    ApprovalState,
    ApprovalToken,
    InvalidationResult,
    RequestIdLedger,
    check_token,
    derive_request_id,
    evidence_sha256_for,
    invalidate_changed,
    verify_for_execution,
)
from kerdon.completeness import RULE_IDS, RULES, blockers, evaluate, is_complete
from kerdon.money import Money
from kerdon.models import (
    Balance,
    DocKind,
    DocumentEvidence,
    ExecutionRecord,
    Finding,
    FxQuote,
    LedgerEntry,
    Obligation,
    ObligationStatus,
    PendingApproval,
    Severity,
    TreasurySnapshot,
)
from kerdon.ports import Actor, Capability, ExecutionGate, evaluator, reader, writer
from kerdon.receipts import SpokenReceipt, build_receipt, merkle_root, verify_proof

__all__ = [
    "RULES",
    "RULE_IDS",
    "Actor",
    "ApprovalIntent",
    "ApprovalState",
    "ApprovalToken",
    "Balance",
    "Capability",
    "DocKind",
    "DocumentEvidence",
    "ExecutionGate",
    "ExecutionRecord",
    "Finding",
    "FxQuote",
    "InvalidationResult",
    "LedgerEntry",
    "Money",
    "Obligation",
    "ObligationStatus",
    "PendingApproval",
    "RequestIdLedger",
    "Severity",
    "SpokenReceipt",
    "TreasurySnapshot",
    "blockers",
    "build_receipt",
    "check_token",
    "derive_request_id",
    "evaluate",
    "evaluator",
    "evidence_sha256_for",
    "invalidate_changed",
    "is_complete",
    "merkle_root",
    "reader",
    "verify_for_execution",
    "verify_proof",
    "writer",
]
