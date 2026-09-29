import unittest

import core


class TestCore(unittest.TestCase):
    def test_01_no_duplicate_register(self):
        state = core.new_game()
        self.assertTrue(core.register(state, "M1", 100))
        self.assertFalse(core.register(state, "M1", 100))

    def test_02_machine_full(self):
        state = core.new_game()
        core.book(state, "M1", "A1")
        core.book(state, "M2", "A1")
        core.book(state, "M3", "A1")
        self.assertFalse(core.machine_available(state, "A1"))

    def test_03_member_fee_exact(self):
        state = core.new_game()
        core.register(state, "M1", 100)
        self.assertEqual(core.member_fee(state, "M1", 4), 3)

    def test_04_cancel_course_releases(self):
        state = core.new_game()
        core.register(state, "M1", 100)
        core.book_course(state, "M1", "C1", "T1")
        core.cancel_course(state, "M1", "C1")
        self.assertEqual(state["members"]["M1"]["courses"], [])

    def test_05_no_course_with_absent_coach(self):
        state = core.new_game()
        core.register(state, "M1", 100)
        result = core.book_course(state, "M1", "C1", "T2")
        self.assertFalse(result)

    def test_06_refund_returns_balance(self):
        state = core.new_game()
        core.register(state, "M1", 100)
        self.assertEqual(core.refund(state, "M1"), 100)

    def test_07_sign_failure_not_counted(self):
        state = core.new_game()
        before = state["sign_id"]
        result = core.sign_in(state, "M1", False)
        self.assertFalse(result)
        self.assertEqual(state["sign_id"], before)

    def test_08_load_preserves_sign_id(self):
        state = core.new_game()
        state["sign_id"] = 9
        loaded = core.load_state(core.save_state(state))
        self.assertEqual(loaded["sign_id"], 9)


if __name__ == "__main__":
    unittest.main()
