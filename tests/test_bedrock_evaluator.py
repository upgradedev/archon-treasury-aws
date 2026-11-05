"""Bedrock evaluator contract with a fake converse. Live calls stay out of CI."""

import unittest

from adapters.bedrock_evaluator import BedrockEvaluator, extract_json, parsed_from_model_json
from fixtures import clean_snapshot
from kerdon.errors import DomainError


def fake_converse(reply):
    return lambda _prompt: reply


class BedrockEvaluatorTest(unittest.TestCase):
    def test_fenced_json_is_extracted(self):
        payload = extract_json('Here you go:\n```json\n{"currency": "USD", "amount": 50.00, "counterparty": "Supplier-A"}\n```')
        self.assertEqual(payload["currency"], "USD")

    def test_numeric_amount_becomes_integer_cents(self):
        parsed = parsed_from_model_json({"currency": "eur", "amount": 12.3, "counterparty": "Supplier B"})
        self.assertEqual((parsed.currency, parsed.amount_cents, parsed.counterparty_id), ("EUR", 1230, "supplier-b"))

    def test_matching_extraction_proposes(self):
        evaluator = BedrockEvaluator(converse=fake_converse('{"currency": "USD", "amount": "50.00", "counterparty": "Supplier-A"}'))
        intent = evaluator.propose_from_text(clean_snapshot(), "obl-1", "any invoice text")
        self.assertEqual(intent.amount_cents, 5000)
        intent_via_port = evaluator.propose(clean_snapshot(), "obl-1")
        self.assertEqual(intent_via_port.amount_cents, 5000)
        with self.assertRaises(DomainError):
            evaluator.propose(clean_snapshot(), "obl-missing")

    def test_model_mistake_becomes_refusal_not_payment(self):
        evaluator = BedrockEvaluator(converse=fake_converse('{"currency": "USD", "amount": "999.00", "counterparty": "Supplier-A"}'))
        with self.assertRaises(DomainError):
            evaluator.propose_from_text(clean_snapshot(), "obl-1", "any invoice text")

    def test_garbage_and_missing_fields_refused(self):
        with self.assertRaises(DomainError):
            extract_json("no json at all")
        with self.assertRaises(DomainError):
            parsed_from_model_json({"currency": "USD"})


if __name__ == "__main__":
    unittest.main()
