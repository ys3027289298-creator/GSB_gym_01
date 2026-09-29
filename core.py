"""健身房核心逻辑：会员、器械、课程、教练和计费。

仅使用标准库；状态以 JSON 序列化保存。所有名额与余额保证不为负。
"""

import json
import random
import shlex

MACHINE_CAPACITY = 3
COURSE_CAPACITY = 2
SEED = 20260929
SAVE_FILE = "gym_save.json"

_DEFAULTS = {
    "members": dict,
    "machines": dict,
    "courses": dict,
    "coaches": dict,
    "day": 1,
    "sign_id": 0,
    "seed": SEED,
}


def new_game():
    return {
        "members": {},
        "machines": {"A1": [], "A2": []},
        "courses": {"C1": [], "C2": []},
        "coaches": {"T1": True, "T2": False},
        "day": 1,
        "sign_id": 0,
        "seed": SEED,
    }


def rng(state):
    """固定种子的随机源，保证演示可复现。"""
    return random.Random(state.get("seed", SEED))


def _as_int(value):
    if isinstance(value, bool):
        raise ValueError("需要整数")
    return int(value)


def _member(state, member_id):
    return state.get("members", {}).get(member_id)


def _coach_present(state, coach_id):
    return bool(state.get("coaches", {}).get(coach_id, False))


def save_state(state):
    return json.dumps(state, ensure_ascii=False)


def load_state(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("空存档")
    state = json.loads(text)
    if not isinstance(state, dict):
        raise ValueError("存档结构非法")
    for key, factory in _DEFAULTS.items():
        if key not in state:
            state[key] = factory() if callable(factory) else factory
    for key in ("members", "machines", "courses", "coaches"):
        if not isinstance(state[key], dict):
            raise ValueError("存档结构非法: %s" % key)
    state["day"] = _as_int(state["day"])
    state["sign_id"] = _as_int(state["sign_id"])
    if state["day"] < 1 or state["sign_id"] < 0:
        raise ValueError("存档计数非法")
    for member in state["members"].values():
        member.setdefault("courses", [])
        member["balance"] = max(0, _as_int(member.get("balance", 0)))
    for key, cap in (("machines", MACHINE_CAPACITY), ("courses", COURSE_CAPACITY)):
        for holder in state[key].values():
            if not isinstance(holder, list):
                raise ValueError("存档名额结构非法")
            del holder[cap:]
    return state


def register(state, member_id, balance):
    """登记会员；重复登记返回 False，非法余额拒绝。"""
    if not isinstance(member_id, str) or not member_id:
        return False
    balance = _as_int(balance)
    if balance < 0:
        return False
    if member_id in state["members"]:
        return False
    state["members"][member_id] = {"balance": balance, "courses": []}
    return True


def book(state, member_id, machine_id):
    """预约器械：id 非空、器械存在、不可重复预约、满员拒绝。"""
    if not isinstance(member_id, str) or not member_id:
        return False
    holders = state.get("machines", {}).get(machine_id)
    if holders is None or not isinstance(holders, list):
        return False
    if member_id in holders or len(holders) >= MACHINE_CAPACITY:
        return False
    holders.append(member_id)
    return True


def machine_available(state, machine_id):
    holders = state.get("machines", {}).get(machine_id)
    if holders is None:
        return False
    return len(holders) < MACHINE_CAPACITY


def member_fee(state, member_id, end_day):
    """跨日按 end_day - day 计费（修复原先少算一天）；非法输入不为负。"""
    if _member(state, member_id) is None:
        return 0
    end_day = _as_int(end_day)
    return max(0, end_day - state["day"])


def course_available(state, course_id):
    holders = state.get("courses", {}).get(course_id)
    if holders is None:
        return False
    return len(holders) < COURSE_CAPACITY


def book_course(state, member_id, course_id, coach_id):
    """排课：会员/课程存在、教练在岗、未满员、未重复报名。"""
    if _member(state, member_id) is None:
        return False
    if not _coach_present(state, coach_id):
        return False
    holders = state.get("courses", {}).get(course_id)
    if holders is None or not isinstance(holders, list):
        return False
    if member_id in holders or len(holders) >= COURSE_CAPACITY:
        return False
    holders.append(member_id)
    state["members"][member_id]["courses"].append(course_id)
    return True


def cancel_course(state, member_id, course_id):
    """取消课程并释放名额；未报名返回 False。"""
    member = _member(state, member_id)
    holders = state.get("courses", {}).get(course_id)
    if member is None or holders is None:
        return False
    if member_id not in holders or course_id not in member["courses"]:
        return False
    holders.remove(member_id)
    member["courses"].remove(course_id)
    return True


def refund(state, member_id):
    """退卡：返还当前余额并清零，同时释放所有名额。会员不存在返回 0。"""
    member = _member(state, member_id)
    if member is None:
        return 0
    for course_id in list(member["courses"]):
        holders = state.get("courses", {}).get(course_id)
        if holders is not None and member_id in holders:
            holders.remove(member_id)
    member["courses"] = []
    for holders in state.get("machines", {}).values():
        while member_id in holders:
            holders.remove(member_id)
    amount = max(0, _as_int(member["balance"]))
    member["balance"] = 0
    state["members"].pop(member_id)
    return amount


def sign_in(state, member_id, ok):
    """打卡：仅成功才消耗签到编号；失败返回 False 且不计数。"""
    if not isinstance(member_id, str) or not member_id:
        return False
    if not ok:
        return False
    state["sign_id"] += 1
    return True


def _parse(raw):
    try:
        return shlex.split(raw.strip())
    except ValueError:
        return []


def _dispatch(state, parts, out):
    cmd = parts[0]
    args = parts[1:]
    try:
        _route(state, cmd, args, out)
    except ValueError as exc:
        out.append("error: %s" % exc)


def _route(state, cmd, args, out):
    if cmd == "register" and len(args) == 2:
        out.append("ok" if register(state, args[0], _as_int(args[1])) else "fail")
    elif cmd == "book" and len(args) == 2:
        out.append("ok" if book(state, args[0], args[1]) else "fail")
    elif cmd == "available" and len(args) == 1:
        out.append("yes" if machine_available(state, args[0]) else "no")
    elif cmd == "fee" and len(args) == 2:
        out.append(str(member_fee(state, args[0], _as_int(args[1]))))
    elif cmd == "course" and len(args) == 3:
        out.append("ok" if book_course(state, args[0], args[1], args[2]) else "fail")
    elif cmd == "cancel" and len(args) == 2:
        out.append("ok" if cancel_course(state, args[0], args[1]) else "fail")
    elif cmd == "refund" and len(args) == 1:
        out.append(str(refund(state, args[0])))
    elif cmd == "sign" and len(args) == 2:
        out.append("ok" if sign_in(state, args[0], args[1] == "ok") else "fail")
    elif cmd == "save" and len(args) <= 1:
        path = args[0] if args else SAVE_FILE
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(save_state(state))
        out.append("ok")
    elif cmd == "load" and len(args) == 1:
        with open(args[0], encoding="utf-8") as handle:
            fresh = load_state(handle.read())
        state.clear()
        state.update(fresh)
        out.append("ok")
    else:
        out.append("error: unknown command")


def run_demo():
    """固定演示：脚本 + 固定种子，全部断言通过即跑通。"""
    state = new_game()
    out = []

    def check(desc, condition):
        out.append(("PASS" if condition else "FAIL") + " " + desc)
        if not condition:
            raise AssertionError(desc)

    check("首次登记", register(state, "M1", 100))
    check("重复登记拒绝", not register(state, "M1", 100))
    check("负余额拒绝", not register(state, "M9", -1))
    register(state, "M2", 50)
    register(state, "M3", 20)
    check("器械预约1", book(state, "M1", "A1"))
    check("器械预约2", book(state, "M2", "A1"))
    check("器械预约3(临界)", book(state, "M3", "A1"))
    check("满员拒绝", not book(state, "M9", "A1"))
    check("重复预约拒绝", not book(state, "M1", "A1"))
    check("满员不可约", not machine_available(state, "A1"))
    check("跨日费用(day1到4=3)", member_fee(state, "M1", 4) == 3)
    check("排课成功", book_course(state, "M1", "C1", "T1"))
    check("请假教练拒绝", not book_course(state, "M1", "C1", "T2"))
    check("取消释放名额", cancel_course(state, "M1", "C1"))
    check("名额已释放", course_available(state, "C1"))
    check("失败打卡不计数", not sign_in(state, "M1", False) and state["sign_id"] == 0)
    check("成功打卡计数", sign_in(state, "M1", True) and state["sign_id"] == 1)
    check("退卡返余额", refund(state, "M2") == 50 and "M2" not in state["members"])
    loaded = load_state(save_state(state))
    check("读档编号不重复", loaded["sign_id"] == state["sign_id"])

    # 容量与余额非负不变量
    for holders in loaded["machines"].values():
        check("器械名额非负", len(holders) <= MACHINE_CAPACITY and len(holders) >= 0)
    for holders in loaded["courses"].values():
        check("课程名额非负", len(holders) <= COURSE_CAPACITY and len(holders) >= 0)
    for member in loaded["members"].values():
        check("会员余额非负", member["balance"] >= 0)
    lottery = rng(loaded).randint(0, 999)
    check("固定种子可复现", lottery == rng(new_game()).randint(0, 999))
    return state, out


def main(argv=None):
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--demo":
        _, lines = run_demo()
        print("健身房固定演示 (seed=%d)" % SEED)
        for line in lines:
            print(line)
        return

    state = new_game()
    print("健身房 - 命令: register/book/available/fee/cancel/course/refund/sign/save/load/quit")
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw or raw == "quit":
            break
        parts = _parse(raw)
        if not parts:
            print("error: bad command")
            continue
        out = []
        try:
            _dispatch(state, parts, out)
        except (ValueError, OSError, KeyError) as exc:
            print("error: %s" % exc)
            continue
        for line in out:
            print(line)


if __name__ == "__main__":
    main()
