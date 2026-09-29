"""健身房核心逻辑：会员、器械、课程、教练和计费。

规则约定：
- 器械容量默认 2，满员后不可预约，名额不允许为负；
- 课程按教练开设，教练请假（coaches[cid] 为 False）不可排课；
- 会员费按天计，跨 N 天收 N（不足一天按一天计）；
- 余额、名额任何情况下不得为负；
- 签到编号单调递增，读档后不得重复。
"""

import json
import random
import sys

MACHINE_CAPACITY = 2
COURSE_CAPACITY = 2
DEMO_SEED = 20260929

COMMANDS = (
    "register/book/available/fee/cancel/course/refund/sign/save/load/quit"
)


def new_game():
    return {
        "members": {},
        "machines": {"A1": [], "A2": []},
        "machine_capacity": MACHINE_CAPACITY,
        "courses": {},
        "course_capacity": COURSE_CAPACITY,
        "coaches": {"T1": True, "T2": False},
        "day": 1,
        "sign_id": 0,
    }


def save_state(state):
    return json.dumps(state, ensure_ascii=False)


def load_state(text):
    if not text or not text.strip():
        raise ValueError("存档内容为空")
    try:
        state = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("存档不是合法 JSON: %s" % exc) from exc
    if not isinstance(state, dict):
        raise ValueError("存档结构非法")
    base = new_game()
    for key, value in base.items():
        state.setdefault(key, value)
    return state


def register(state, member_id, balance):
    if not member_id:
        return False
    if member_id in state["members"]:
        return False
    if not isinstance(balance, (int, float)) or isinstance(balance, bool):
        return False
    if balance < 0:
        return False
    state["members"][member_id] = {"balance": balance, "courses": []}
    return True


def machine_available(state, machine_id):
    booked = state["machines"].get(machine_id)
    if booked is None:
        return False
    return len(booked) < state.get("machine_capacity", MACHINE_CAPACITY)


def book(state, member_id, machine_id):
    booked = state["machines"].get(machine_id)
    if booked is None:
        return False
    if member_id in booked:
        return False
    if not machine_available(state, machine_id):
        return False
    booked.append(member_id)
    return True


def member_fee(state, member_id, end_day):
    if member_id not in state["members"]:
        return 0
    days = end_day - state["day"]
    if days <= 0:
        return 0
    return days


def book_course(state, member_id, course_id, coach_id):
    if member_id not in state["members"]:
        return False
    if not state["coaches"].get(coach_id, False):
        return False
    course = state["courses"].get(course_id)
    if course is None:
        course = {"coach": coach_id, "members": []}
        state["courses"][course_id] = course
    if course["coach"] != coach_id:
        return False
    if member_id in course["members"]:
        return False
    if len(course["members"]) >= state.get("course_capacity", COURSE_CAPACITY):
        return False
    course["members"].append(member_id)
    state["members"][member_id]["courses"].append(course_id)
    return True


def cancel_course(state, member_id, course_id):
    member = state["members"].get(member_id)
    if member is None or course_id not in member["courses"]:
        return False
    member["courses"].remove(course_id)
    course = state["courses"].get(course_id)
    if course is not None and member_id in course["members"]:
        course["members"].remove(member_id)
    return True


def refund(state, member_id):
    member = state["members"].pop(member_id, None)
    if member is None:
        return 0
    balance = member["balance"]
    for course_id in member["courses"]:
        course = state["courses"].get(course_id)
        if course is not None and member_id in course["members"]:
            course["members"].remove(member_id)
    for booked in state["machines"].values():
        while member_id in booked:
            booked.remove(member_id)
    return balance


def sign_in(state, member_id, ok):
    if not ok:
        return False
    if member_id not in state["members"]:
        return False
    state["sign_id"] += 1
    return True


def dispatch(state, raw):
    """执行一条 CMD 指令，返回要打印的文本。"""
    parts = raw.split()
    if not parts:
        return "空指令"
    cmd, args = parts[0], parts[1:]
    try:
        if cmd == "register" and len(args) == 2:
            ok = register(state, args[0], int(args[1]))
            return "ok" if ok else "登记失败"
        if cmd == "book" and len(args) == 2:
            ok = book(state, args[0], args[1])
            return "ok" if ok else "预约失败"
        if cmd == "available" and len(args) == 1:
            return "yes" if machine_available(state, args[0]) else "no"
        if cmd == "fee" and len(args) == 2:
            return str(member_fee(state, args[0], int(args[1])))
        if cmd == "course" and len(args) == 3:
            ok = book_course(state, args[0], args[1], args[2])
            return "ok" if ok else "排课失败"
        if cmd == "cancel" and len(args) == 2:
            ok = cancel_course(state, args[0], args[1])
            return "ok" if ok else "取消失败"
        if cmd == "refund" and len(args) == 1:
            return str(refund(state, args[0]))
        if cmd == "sign" and len(args) == 2:
            ok = sign_in(state, args[0], args[1] == "ok")
            return "ok" if ok else "签到失败"
        if cmd == "save" and not args:
            return save_state(state)
        if cmd == "load" and not args:
            return "请粘贴 JSON 存档后回车"
        if cmd == "quit" and not args:
            return "quit"
    except (ValueError, TypeError):
        return "参数错误"
    return "未知命令"


def run_demo():
    """固定种子演示：覆盖登记、预约、计费、课程、退卡、签到全流程。"""
    rng = random.Random(DEMO_SEED)
    state = new_game()
    print("== 固定演示 seed=%d ==" % DEMO_SEED)
    print("register M1 100 ->", register(state, "M1", 100))
    print("register M1 100 (重复) ->", register(state, "M1", 100))
    print("register M2 50 ->", register(state, "M2", 50))
    print("book M1 A1 ->", book(state, "M1", "A1"))
    print("book M2 A1 ->", book(state, "M2", "A1"))
    print("available A1 (满员) ->", machine_available(state, "A1"))
    print("fee M1 第4天 ->", member_fee(state, "M1", 4))
    print("course M1 C1 T1 ->", book_course(state, "M1", "C1", "T1"))
    print("course M2 C2 T2 (教练请假) ->", book_course(state, "M2", "C2", "T2"))
    print("cancel M1 C1 ->", cancel_course(state, "M1", "C1"))
    lucky = "M1" if rng.random() < 0.5 else "M2"
    print("sign %s ok ->" % lucky, sign_in(state, lucky, True))
    print("sign M1 fail ->", sign_in(state, "M1", False))
    print("refund M2 ->", refund(state, "M2"))
    print("存档:", save_state(state))
    print("== 演示结束 ==")


def main():
    print("健身房 - 命令: %s" % COMMANDS)
    state = new_game()
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            continue
        out = dispatch(state, raw)
        if out == "quit":
            break
        print(out)
        if raw.split()[0] == "load":
            try:
                state = load_state(input("json> "))
                print("读档成功")
            except (EOFError, KeyboardInterrupt, ValueError) as exc:
                print("读档失败:", exc)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        run_demo()
    else:
        main()
