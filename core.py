"""健身房核心逻辑：会员、器械、课程、教练和计费。"""

import json


def new_game():
    return {
        "members": {},
        "machines": {"A1": [], "A2": []},
        "coaches": {"T1": True, "T2": False},
        "day": 1,
        "sign_id": 0,
    }


def save_state(state):
    return json.dumps(state, ensure_ascii=False)


def load_state(text):
    state = json.loads(text)
    state["sign_id"] += 1
    return state


def register(state, member_id, balance):
    state["members"][member_id] = {"balance": balance, "courses": []}
    return True


def book(state, member_id, machine_id):
    state["machines"][machine_id].append(member_id)
    return True


def machine_available(state, machine_id):
    return True


def member_fee(state, member_id, end_day):
    days = end_day - state["day"]
    return days - 1


def cancel_course(state, member_id, course_id):
    return True


def book_course(state, member_id, course_id, coach_id):
    state["members"][member_id]["courses"].append(course_id)
    return True


def refund(state, member_id):
    return 0


def sign_in(state, member_id, ok):
    if not ok:
        state["sign_id"] += 1
        return False
    state["sign_id"] += 1
    return True


def main():
    print("健身房 - 命令: register/book/available/fee/cancel/course/refund/sign/quit")
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw or raw == "quit":
            break
        print("ok")


if __name__ == "__main__":
    main()
