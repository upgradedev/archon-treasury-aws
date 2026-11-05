"""Session isolation: the deployed-UAT finding, pinned as a regression."""

import unittest

from archon_demo.sessions import SessionStore, cookie_value, parse_cookie


class SessionsTest(unittest.TestCase):
    def test_visitors_get_isolated_services(self):
        store = SessionStore()
        a_id, alice, a_new = store.resolve(None)
        b_id, bob, b_new = store.resolve(None)
        self.assertTrue(a_new and b_new)
        self.assertNotEqual(a_id, b_id)
        alice.approve("obl-usd-1")
        alice.execute("obl-usd-1")
        self.assertEqual(alice.transport.transfer_count, 1)
        self.assertEqual(bob.transport.transfer_count, 0)
        self.assertEqual(bob.state()["obligations"][3]["approval_state"], "NOT_APPROVED")

    def test_same_cookie_resumes_same_service(self):
        store = SessionStore()
        first_id, first, _ = store.resolve(None)
        first.approve("obl-eur-1")
        again_id, again, is_new = store.resolve(first_id)
        self.assertFalse(is_new)
        self.assertEqual(again_id, first_id)
        self.assertIs(again, first)

    def test_forged_cookie_gets_fresh_session(self):
        store = SessionStore()
        sid, _svc, is_new = store.resolve(parse_cookie("archon-session=../../etc"))
        self.assertTrue(is_new)
        self.assertEqual(len(sid), 32)

    def test_cookie_round_trip(self):
        sid, _svc, _new = SessionStore().resolve(None)
        self.assertEqual(parse_cookie(cookie_value(sid)), sid)

    def test_seeded_findings_are_alive_on_first_load(self):
        _sid, service, _new = SessionStore().resolve(None)
        rules = {f["rule_id"] for f in service.state()["findings"]}
        self.assertIn("R01", rules)
        self.assertIn("R02", rules)


if __name__ == "__main__":
    unittest.main()
