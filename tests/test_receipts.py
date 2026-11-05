"""Merkle-sealed spoken receipts: seal holds, tampering shows, amounts speak."""

import unittest
from dataclasses import replace

from fixtures import NOW, clean_snapshot, obligation
from kerdon.approvals import ApprovalIntent, ApprovalToken
from kerdon.receipts import build_receipt, merkle_root, verify_proof


class ReceiptsTest(unittest.TestCase):
    def setUp(self):
        self.snap = clean_snapshot()
        self.token = ApprovalToken(
            ApprovalIntent.from_snapshot(self.snap, obligation(), "net-14"), "elena-vance", NOW
        )
        self.receipt = build_receipt(self.token, self.snap)

    def test_root_is_stable_and_verifies(self):
        again = build_receipt(self.token, self.snap)
        self.assertEqual(again.root_sha256, self.receipt.root_sha256)
        self.assertTrue(self.receipt.verify())

    def test_every_leaf_proof_verifies(self):
        for i, line in enumerate(self.receipt.lines):
            self.assertTrue(verify_proof(line, self.receipt.proof_for(i), self.receipt.root_sha256), i)

    def test_tampered_line_breaks_the_seal(self):
        forged_lines = (self.receipt.lines[0], "Pay counterparty attacker.") + self.receipt.lines[2:]
        self.assertNotEqual(merkle_root(forged_lines), self.receipt.root_sha256)
        forged = replace(self.receipt, lines=forged_lines)
        self.assertFalse(forged.verify())
        proof = self.receipt.proof_for(1)
        self.assertFalse(verify_proof("Pay counterparty attacker.", proof, self.receipt.root_sha256))

    def test_spoken_amount_uses_major_units_and_cents(self):
        # Trap T2 read aloud: 5000 cents must sound like 50.00, never 5000.00.
        self.assertIn("USD 50.00 (5000 cents)", self.receipt.spoken_text)
        self.assertNotIn("5000.00", self.receipt.spoken_text)
        self.assertIn(self.token.sha256, self.receipt.spoken_text)

    def test_accessible_renderings(self):
        self.assertEqual(self.receipt.aria_label, self.receipt.spoken_text)
        self.assertEqual(
            len(self.receipt.braille_transcript.splitlines()), len(self.receipt.lines)
        )
        self.receipt.braille_transcript.encode("ascii")  # raises if not Braille-safe ASCII


if __name__ == "__main__":
    unittest.main()
