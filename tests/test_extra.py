import io
import json
import unittest
from contextlib import redirect_stdout

import core


class TestExtra(unittest.TestCase):
    def test_duplicate_inputs(self):
        state = core.new_game()
        self.assertTrue(core.register(state, "M1", 100))
        self.assertFalse(core.register(state, "M1", 100))
        self.assertTrue(core.book(state, "M1", "A1"))
        self.assertFalse(core.book(state, "M1", "A1"))
        self.assertTrue(core.book_course(state, "M1", "C1", "T1"))
        self.assertFalse(core.book_course(state, "M1", "C1", "T1"))

    def test_capacity_boundary_machine(self):
        state = core.new_game()
        for i in range(core.MACHINE_CAPACITY):
            self.assertTrue(core.book(state, "M%d" % i, "A1"))
        self.assertFalse(core.book(state, "Mx", "A1"))
        self.assertFalse(core.machine_available(state, "A1"))

    def test_capacity_boundary_course(self):
        state = core.new_game()
        for i in range(core.COURSE_CAPACITY):
            core.register(state, "M%d" % i, 10)
            self.assertTrue(core.book_course(state, "M%d" % i, "C1", "T1"))
        self.assertTrue(core.register(state, "Mx", 10))
        self.assertFalse(core.book_course(state, "Mx", "C1", "T1"))
        self.assertFalse(core.course_available(state, "C1"))

    def test_cancel_then_rebook(self):
        state = core.new_game()
        core.register(state, "M1", 10)
        core.book_course(state, "M1", "C1", "T1")
        self.assertTrue(core.cancel_course(state, "M1", "C1"))
        self.assertFalse(core.cancel_course(state, "M1", "C1"))
        self.assertTrue(core.book_course(state, "M1", "C1", "T1"))

    def test_refund_releases_everything(self):
        state = core.new_game()
        core.register(state, "M1", 42)
        core.book(state, "M1", "A1")
        core.book_course(state, "M1", "C1", "T1")
        self.assertEqual(core.refund(state, "M1"), 42)
        self.assertEqual(state["machines"]["A1"], [])
        self.assertEqual(state["courses"]["C1"], [])
        self.assertEqual(core.refund(state, "M1"), 0)

    def test_fee_non_negative(self):
        state = core.new_game()
        core.register(state, "M1", 0)
        self.assertEqual(core.member_fee(state, "M1", 0), 0)
        self.assertEqual(core.member_fee(state, "M1", 1), 0)
        self.assertEqual(core.member_fee(state, "M1", 4), 3)

    def test_invalid_register(self):
        state = core.new_game()
        self.assertFalse(core.register(state, "", 10))
        self.assertFalse(core.register(state, "M9", -5))
        self.assertFalse(core.book(state, "M1", "NOPE"))
        self.assertFalse(core.machine_available(state, "NOPE"))
        self.assertFalse(core.book_course(state, "M1", "C1", "T1"))
        self.assertFalse(core.book_course(state, "M9", "NOPE", "T1"))

    def test_empty_and_corrupt_data(self):
        with self.assertRaises(ValueError):
            core.load_state("")
        with self.assertRaises(ValueError):
            core.load_state("   ")
        with self.assertRaises(json.JSONDecodeError):
            core.load_state("{bad json")
        loaded = core.load_state(core.save_state(core.new_game()))
        self.assertEqual(loaded["sign_id"], 0)

    def test_load_roundtrip_repairs_over_capacity(self):
        state = core.new_game()
        state["machines"]["A1"] = ["X", "Y", "Z", "W"]
        loaded = core.load_state(core.save_state(state))
        self.assertLessEqual(len(loaded["machines"]["A1"]), core.MACHINE_CAPACITY)

    def test_save_load_idempotent_ids(self):
        state = core.new_game()
        state["sign_id"] = 7
        once = core.load_state(core.save_state(state))
        twice = core.load_state(core.save_state(once))
        self.assertEqual(twice["sign_id"], 7)

    def test_seed_is_fixed(self):
        a = core.rng(core.new_game()).randrange(10 ** 6)
        b = core.rng(core.new_game()).randrange(10 ** 6)
        self.assertEqual(a, b)

    def test_cmd_invalid_and_unknown(self):
        state = core.new_game()
        out = []
        core._dispatch(state, core._parse("register M1 notanumber"), out)
        self.assertTrue(out[0].startswith("error: "))
        out = []
        core._dispatch(state, ["bogus"], out)
        self.assertEqual(out, ["error: unknown command"])
        self.assertEqual(core._parse('register "M1 100'), [])

    def test_cmd_happy_path_via_stdin(self):
        import core as c
        import sys
        old_stdin, old_stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(
            "register M1 100\nregister M1 100\nbook M1 A1\n"
            "available A1\nfee M1 4\nsign M1 no\nsign M1 ok\nrefund M1\n\n"
        )
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                c.main([])
        finally:
            sys.stdin, sys.stdout = old_stdin, old_stdout
        text = buf.getvalue()
        self.assertIn("ok", text)
        self.assertIn("fail", text)


if __name__ == "__main__":
    unittest.main()
