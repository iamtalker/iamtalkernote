"""달력·할일·공수(app/planner/model.py) 시험: py -3 -I -X utf8 tools/test_planner.py"""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from planner import model as M

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


h = M.holidays(2026)
check("고정 공휴일", h["2026-01-01"] == "신정" and h["2026-03-01"] == "삼일절" and h["2026-12-25"] == "성탄절")
check("설날·추석 연휴", h["2026-02-17"] == "설날" and h["2026-02-16"] == "설날 연휴" and h["2026-09-25"] == "추석")
check("대체공휴일(2026-03-01 일요일 → 3/2)", h["2026-03-02"] == "대체공휴일" and h["2026-05-25"] == "대체공휴일")
check("평일은 공휴일 아님", "2026-04-15" not in h)
check("2022년 성탄절은 아직 대체 대상 아님·공휴일 표시", M.holidays(2022).get("2022-12-25") is None)
g = M.month_grid(2026, 11)
check("달력은 6주×7일, 일요일 시작", len(g) == 42 and g[0].weekday() == 6 and datetime.date(2026, 11, 1) in g)

with tempfile.TemporaryDirectory() as d:
    p = M.Planner(d)
    t = p.add("보고서 쓰기")
    p.add("회의 준비", "2026-11-05")
    check("할일 저장·날짜 없는 것도 목록에", len(p.todos) == 2 and p.on("2026-11-05")[0]["text"] == "회의 준비")
    p.update(t["id"], date="2026-11-03")
    check("날짜를 주면 그 날에 표시", [x["text"] for x in p.on("2026-11-03")] == ["보고서 쓰기"])
    check("순서: 날짜순, 날짜 없는 것은 뒤", [x["text"] for x in p.ordered()] == ["보고서 쓰기", "회의 준비"])
    p.update(t["id"], done=True)
    check("한 일은 맨 뒤", p.ordered()[-1]["text"] == "보고서 쓰기")
    check("알림: 오늘 이하 날짜·안 한 것만, 한 번만", [x["text"] for x in p.due("2026-11-05")] == ["회의 준비"])
    p.mark_notified(p.on("2026-11-05")[0]["id"], "2026-11-05")
    check("알린 뒤에는 오늘 다시 안 알림", p.due("2026-11-05") == [] and len(p.due("2026-11-06")) == 1)
    p.set_gongsu("2026-11-02", 1)
    p.set_gongsu("2026-11-03", 1.5)
    p.set_gongsu("2026-11-04", 2)
    p.set_gongsu("2026-12-01", 1)
    r = p.summary(2026, 11, wage=150000, meal=20000)
    check("공수 합계·출근일·일당·일비·총액", r == {"gongsu": 4.5, "days": 3, "pay": 675000, "meal": 60000, "sum": 735000})
    p.set_gongsu("2026-11-04", 0)
    check("0 으로 지우면 출근일에서 빠짐", p.summary(2026, 11, 100, 10)["days"] == 2)
    q = M.Planner(d)
    check("다시 열어도 그대로(파일에 저장)", len(q.todos) == 2 and q.gongsu["2026-11-02"] == 1.0)
    q.remove(q.todos[0]["id"])
    check("삭제", len(q.todos) == 1)

ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20261001\r\nDTEND;VALUE=DATE:20261003\r\nDESCRIPTION:공휴일\r\nSUMMARY:임시 연휴\r\nEND:VEVENT\r\n"
       "BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20261008\r\nDTEND;VALUE=DATE:20261009\r\nDESCRIPTION:기념일\r\nSUMMARY:어버이날\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
g = M.parse_ics(ics)
check("구글 달력(iCal) 읽기: 공휴일만, 여러 날은 날마다", g == {"2026-10-01": "임시 연휴", "2026-10-02": "임시 연휴"})
with tempfile.TemporaryDirectory() as d2:
    q = M.Planner(d2)
    check("처음엔 받아 둔 것이 없어 오래된 것으로 봄", q.google_stale("2026-11-01"))
    q.set_google(g, "2026-11-01")
    check("받은 공휴일이 내장 표보다 우선하고 저장됨", q.holidays_for(2026)["2026-10-01"] == "임시 연휴" and M.Planner(d2).google == g)
    check("한 달 안에는 다시 안 받음, 지나면 받음", not q.google_stale("2026-11-20") and q.google_stale("2026-12-05"))

print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
