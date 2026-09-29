import io
import json
import unittest
from contextlib import redirect_stdout

import core


class TestIllegalCommands(unittest.TestCase):
    def test_unknown_command(self):
        state = core.new_game()
        self.assertEqual(core.dispatch(state, "hack M1"), "未知命令")

    def test_bad_args_and_empty(self):
        state = core.new_game()
        self.assertEqual(core.dispatch(state, "register M1"), "未知命令")
        self.assertEqual(core.dispatch(state, "register M1 abc"), "参数错误")
        self.assertEqual(core.dispatch(state, ""), "空指令")

    def test_quit_passthrough(self):
        state = core.new_game()
        self.assertEqual(core.dispatch(state, "quit"), "quit")


class TestEmptyData(unittest.TestCase):
    def test_empty_state_ops(self):
        state = core.new_game()
        self.assertEqual(core.member_fee(state, "NOBODY", 9), 0)
        self.assertEqual(core.refund(state, "NOBODY"), 0)
        self.assertFalse(core.cancel_course(state, "NOBODY", "C1"))
        self.assertFalse(core.sign_in(state, "NOBODY", True))
        self.assertFalse(core.machine_available(state, "ZZ"))

    def test_load_rejects_bad_data(self):
        with self.assertRaises(ValueError):
            core.load_state("")
        with self.assertRaises(ValueError):
            core.load_state("   ")
        with self.assertRaises(ValueError):
            core.load_state("{broken")
        with self.assertRaises(ValueError):
            core.load_state("[1, 2]")

    def test_load_fills_missing_keys(self):
        loaded = core.load_state('{"members": {}, "sign_id": 5}')
        self.assertEqual(loaded["sign_id"], 5)
        self.assertIn("machines", loaded)


class TestCapacityBoundary(unittest.TestCase):
    def test_machine_capacity_boundary(self):
        state = core.new_game()
        cap = state["machine_capacity"]
        for i in range(cap):
            self.assertTrue(core.book(state, "M%d" % i, "A1"))
        self.assertFalse(core.machine_available(state, "A1"))
        self.assertFalse(core.book(state, "MX", "A1"))
        self.assertEqual(len(state["machines"]["A1"]), cap)

    def test_course_capacity_boundary(self):
        state = core.new_game()
        cap = state["course_capacity"]
        for i in range(cap):
            core.register(state, "M%d" % i, 10)
            self.assertTrue(core.book_course(state, "M%d" % i, "C1", "T1"))
        core.register(state, "MX", 10)
        self.assertFalse(core.book_course(state, "MX", "C1", "T1"))
        self.assertEqual(len(state["courses"]["C1"]["members"]), cap)

    def test_cancel_releases_slot(self):
        state = core.new_game()
        for i in range(state["course_capacity"]):
            core.register(state, "M%d" % i, 10)
            core.book_course(state, "M%d" % i, "C1", "T1")
        self.assertTrue(core.cancel_course(state, "M0", "C1"))
        core.register(state, "MN", 10)
        self.assertTrue(core.book_course(state, "MN", "C1", "T1"))


class TestDuplicateInput(unittest.TestCase):
    def test_duplicate_booking_rejected(self):
        state = core.new_game()
        self.assertTrue(core.book(state, "M1", "A1"))
        self.assertFalse(core.book(state, "M1", "A1"))
        self.assertEqual(state["machines"]["A1"], ["M1"])

    def test_duplicate_course_rejected(self):
        state = core.new_game()
        core.register(state, "M1", 10)
        self.assertTrue(core.book_course(state, "M1", "C1", "T1"))
        self.assertFalse(core.book_course(state, "M1", "C1", "T1"))
        self.assertEqual(state["members"]["M1"]["courses"], ["C1"])

    def test_double_cancel_and_double_refund(self):
        state = core.new_game()
        core.register(state, "M1", 80)
        core.book_course(state, "M1", "C1", "T1")
        self.assertTrue(core.cancel_course(state, "M1", "C1"))
        self.assertFalse(core.cancel_course(state, "M1", "C1"))
        self.assertEqual(core.refund(state, "M1"), 80)
        self.assertEqual(core.refund(state, "M1"), 0)


class TestNonNegative(unittest.TestCase):
    def test_negative_balance_rejected(self):
        state = core.new_game()
        self.assertFalse(core.register(state, "M1", -5))
        self.assertFalse(core.register(state, "", 10))

    def test_fee_never_negative(self):
        state = core.new_game()
        core.register(state, "M1", 100)
        self.assertEqual(core.member_fee(state, "M1", 1), 0)
        self.assertEqual(core.member_fee(state, "M1", 0), 0)

    def test_slots_never_negative(self):
        state = core.new_game()
        core.register(state, "M1", 10)
        core.book_course(state, "M1", "C1", "T1")
        core.cancel_course(state, "M1", "C1")
        core.cancel_course(state, "M1", "C1")
        self.assertEqual(state["courses"]["C1"]["members"], [])

    def test_refund_cleans_machines_and_courses(self):
        state = core.new_game()
        core.register(state, "M1", 60)
        core.book(state, "M1", "A1")
        core.book_course(state, "M1", "C1", "T1")
        self.assertEqual(core.refund(state, "M1"), 60)
        self.assertEqual(state["machines"]["A1"], [])
        self.assertEqual(state["courses"]["C1"]["members"], [])
        self.assertNotIn("M1", state["members"])


class TestSignAndPersistence(unittest.TestCase):
    def test_sign_id_monotonic_after_reload(self):
        state = core.new_game()
        core.register(state, "M1", 10)
        core.sign_in(state, "M1", True)
        loaded = core.load_state(core.save_state(state))
        self.assertEqual(loaded["sign_id"], state["sign_id"])
        self.assertTrue(core.sign_in(loaded, "M1", True))
        self.assertEqual(loaded["sign_id"], state["sign_id"] + 1)

    def test_failed_sign_in_not_counted(self):
        state = core.new_game()
        core.register(state, "M1", 10)
        self.assertFalse(core.sign_in(state, "M1", False))
        self.assertEqual(state["sign_id"], 0)

    def test_save_is_valid_json(self):
        state = core.new_game()
        json.loads(core.save_state(state))


class TestDemo(unittest.TestCase):
    def test_demo_deterministic(self):
        out1, out2 = io.StringIO(), io.StringIO()
        with redirect_stdout(out1):
            core.run_demo()
        with redirect_stdout(out2):
            core.run_demo()
        self.assertEqual(out1.getvalue(), out2.getvalue())
        self.assertIn("seed=%d" % core.DEMO_SEED, out1.getvalue())


if __name__ == "__main__":
    unittest.main()
