"""Bedrock Evaluator: Claude extracts, deterministic code decides.

Verified live 2026-11-05 in eu-west-1 (one 92-token probe returned correct
JSON). The model sees invoice text and returns three fields. Everything
after that is the shared deterministic comparison in evaluator.py, so a
model mistake becomes a refusal, never a payment. boto3 is imported lazily:
this module loads fine in environments without the SDK and fails with a
clear error only when a live extraction is actually requested.

Not exposed on the public demo URL on purpose: an anonymous endpoint that
spends model tokens would be a cost-abuse surface. Judges can run
scripts/run_evaluator_live.py with AWS credentials.
"""

import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from adapters.airwallex_client import parse_major_amount
from adapters.evaluator import ParsedInvoice, propose_from_parsed
from kerdon.approvals import ApprovalIntent
from kerdon.errors import DomainError
from kerdon.models import TreasurySnapshot

DEFAULT_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

ConverseFn = Callable[[str], str]  # prompt -> model text


def extract_json(text: str) -> dict:
    match = _FENCE_RE.search(text)
    raw = match.group(1) if match else text
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise DomainError("model response carries no JSON object")
    try:
        parsed = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        raise DomainError("model response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise DomainError("model response JSON must be an object")
    return parsed


def parsed_from_model_json(payload: dict) -> ParsedInvoice:
    try:
        currency = str(payload["currency"]).strip().upper()
        amount_raw = payload["amount"]
        counterparty = str(payload["counterparty"]).strip().lower().replace(" ", "-")
    except KeyError as exc:
        raise DomainError(f"model extraction is missing field {exc}") from exc
    if isinstance(amount_raw, bool) or not isinstance(amount_raw, (str, int, float)):
        raise DomainError("model amount must be a string or number")
    # Decimal(str(...)) keeps the boundary exact; parse_major_amount then
    # re-validates as a 2-decimal string and converts to integer cents.
    money = parse_major_amount(format(Decimal(str(amount_raw)), "f"), currency)
    if not counterparty:
        raise DomainError("model extraction has an empty counterparty")
    return ParsedInvoice(money.currency, money.amount_cents, counterparty)


def bedrock_converse(prompt: str, model_id: str | None = None, region: str = "eu-west-1") -> str:
    try:
        import boto3
    except ImportError as exc:
        raise DomainError("boto3 is required for the live Bedrock evaluator (pip extra: aws)") from exc
    client = boto3.client("bedrock-runtime", region_name=region)
    out = client.converse(
        modelId=model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 200, "temperature": 0},
    )
    return out["output"]["message"]["content"][0]["text"]


@dataclass(slots=True)
class BedrockEvaluator:
    converse: ConverseFn = bedrock_converse

    def propose_from_text(
        self, snapshot: TreasurySnapshot, obligation_id: str, invoice_text: str
    ) -> ApprovalIntent:
        prompt = (
            "Extract JSON only with keys currency, amount, counterparty from this invoice text. "
            "Amount in major units as written. Counterparty exactly as named.\n\n" + invoice_text
        )
        parsed = parsed_from_model_json(extract_json(self.converse(prompt)))
        return propose_from_parsed(snapshot, obligation_id, parsed)

    def propose(self, snapshot: TreasurySnapshot, obligation_id: str) -> ApprovalIntent:
        doc = next((d for d in snapshot.documents if d.obligation_id == obligation_id), None)
        if doc is None:
            raise DomainError("Bedrock evaluator needs an invoice document or invoice text")
        invoice_text = (
            f"Invoice {doc.invoice_number or doc.document_id}. "
            f"Counterparty: {doc.counterparty_id}. "
            f"Total due {doc.amount.currency} {doc.amount.to_major_str()}."
        )
        return self.propose_from_text(snapshot, obligation_id, invoice_text)
