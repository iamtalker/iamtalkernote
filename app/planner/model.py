"""달력·할일·공수 모델(화면을 모르는 순수 계산). 날짜는 'YYYY-MM-DD' 글자로 다룬다."""
import datetime
import json
import os
import uuid

DIR = ".planner"
FILE = "data.json"

# 양력 공휴일(고정). 신정·현충일·성탄절 말고는 대체공휴일 대상이다(성탄절은 2023년부터).
FIXED = {(1, 1): "신정", (3, 1): "삼일절", (5, 5): "어린이날", (6, 6): "현충일", (8, 15): "광복절", (10, 3): "개천절", (10, 9): "한글날", (12, 25): "성탄절"}
NO_SUBSTITUTE = {"신정", "현충일"}
# 음력 공휴일은 해마다 날짜가 달라 표로 둔다(설날·추석은 앞뒤 하루씩 연휴). 표에 없는 해는 음력 공휴일이 표시되지 않는다 → 해마다 확인해 넣는다.
LUNAR = {
    2024: {"설날": (2, 10), "부처님오신날": (5, 15), "추석": (9, 17)},
    2025: {"설날": (1, 29), "부처님오신날": (5, 5), "추석": (10, 6)},
    2026: {"설날": (2, 17), "부처님오신날": (5, 24), "추석": (9, 25)},
    2027: {"설날": (2, 7), "부처님오신날": (5, 13), "추석": (9, 15)},
    2028: {"설날": (1, 27), "부처님오신날": (5, 2), "추석": (10, 3)},
    2029: {"설날": (2, 13), "부처님오신날": (5, 20), "추석": (9, 22)},
    2030: {"설날": (2, 3), "부처님오신날": (5, 9), "추석": (9, 12)},
}


def iso(d):
    return d.isoformat()


def parse(s):
    try:
        return datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def holidays(year):
    """{날짜(YYYY-MM-DD): 이름} — 고정 공휴일 + 음력 공휴일 + 대체공휴일"""
    groups = []                                              # [(이름, [날짜들])]
    for (m, d), name in FIXED.items():
        if name == "성탄절" and year < 2023:
            continue
        groups.append((name, [datetime.date(year, m, d)]))
    for name, (m, d) in LUNAR.get(year, {}).items():
        c = datetime.date(year, m, d)
        groups.append((name, [c - datetime.timedelta(1), c, c + datetime.timedelta(1)] if name != "부처님오신날" else [c]))
    out = {}
    for name, days in groups:
        for i, day in enumerate(days):
            out[iso(day)] = name if len(days) == 1 else (name if i == 1 else name + " 연휴")
    for name, days in sorted(groups, key=lambda g: g[1][0]):  # 대체공휴일: 주말·다른 공휴일과 겹치면 그 뒤 첫 평일
        if name in NO_SUBSTITUTE:
            continue
        clash = any(d.weekday() == 6 or (len(days) == 1 and d.weekday() == 5) or sum(1 for g in groups if d in g[1]) > 1 for d in days)
        if clash:
            d = days[-1] + datetime.timedelta(1)
            while d.weekday() >= 5 or iso(d) in out:
                d += datetime.timedelta(1)
            out[iso(d)] = "대체공휴일"
    return out


def month_grid(year, month):
    """달력 칸: 일요일 시작 6주 × 7일의 날짜(date) 목록"""
    first = datetime.date(year, month, 1)
    start = first - datetime.timedelta((first.weekday() + 1) % 7)
    return [start + datetime.timedelta(i) for i in range(42)]


class Planner:
    """할일·공수 자료. path 는 노트 폴더. 바뀔 때마다 바로 저장한다(작은 파일 하나, 임시 파일로 쓴 뒤 바꿔치기)"""

    def __init__(self, root):
        self.path = os.path.join(root, DIR, FILE)
        self.todos, self.gongsu = [], {}
        self.google, self.google_at = {}, ""        # 구글 달력에서 받아 둔 공휴일 {날짜: 이름}, 받은 날
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            d = {}
        self.todos = [t for t in d.get("todos", []) if isinstance(t, dict) and t.get("text")]
        self.gongsu = {k: float(v) for k, v in d.get("gongsu", {}).items() if parse(k) and isinstance(v, (int, float)) and v > 0}
        self.google = {k: v for k, v in d.get("google", {}).items() if parse(k)}
        self.google_at = d.get("google_at", "")

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"todos": self.todos, "gongsu": self.gongsu, "google": self.google, "google_at": self.google_at}, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    # ---- 공휴일(내장 표 + 구글 달력에서 받은 것: 구글 것이 우선)
    def holidays_for(self, year):
        return {**holidays(year), **{k: v for k, v in self.google.items() if k.startswith(f"{year:04d}-")}}

    def google_stale(self, today):
        a, b = parse(self.google_at), parse(today)
        return not self.google or a is None or b is None or (b - a).days >= STALE_DAYS

    def set_google(self, days, today):
        if days:
            self.google, self.google_at = days, today
            self.save()

    # ---- 할일
    def add(self, text, date=None):
        t = {"id": uuid.uuid4().hex[:8], "text": text.strip(), "date": date or None, "done": False}
        if t["text"]:
            self.todos.append(t)
            self.save()
            return t

    def find(self, tid):
        return next((t for t in self.todos if t["id"] == tid), None)

    def update(self, tid, **kw):
        t = self.find(tid)
        if t:
            t.update(kw)
            if "date" in kw or "done" in kw:
                t.pop("notified", None)
            self.save()

    def remove(self, tid):
        self.todos = [t for t in self.todos if t["id"] != tid]
        self.save()

    def on(self, date):
        """그 날짜의 할일"""
        return [t for t in self.todos if t.get("date") == date]

    def ordered(self, only_date=None):
        """아래 목록 순서: 안 한 것(날짜 있는 것은 날짜순, 날짜 없는 것은 그 뒤) → 한 것"""
        pool = self.on(only_date) if only_date else self.todos
        return sorted(pool, key=lambda t: (t["done"], t.get("date") is None, t.get("date") or "", t["text"]))

    def due(self, today):
        """오늘(이전 날짜 포함) 알릴 할일: 안 했고 날짜가 오늘 이하이며 오늘 아직 안 알린 것"""
        return [t for t in self.todos if not t["done"] and t.get("date") and t["date"] <= today and t.get("notified") != today]

    def mark_notified(self, tid, today):
        t = self.find(tid)
        if t:
            t["notified"] = today
            self.save()

    # ---- 공수
    def set_gongsu(self, date, value):
        if value and value > 0:
            self.gongsu[date] = float(value)
        else:
            self.gongsu.pop(date, None)
        self.save()

    def summary(self, year, month, wage=0, meal=0):
        """그 달의 공수 합계·출근일수·일당 합계·일비 합계·총액"""
        pre = f"{year:04d}-{month:02d}-"
        vals = [v for k, v in self.gongsu.items() if k.startswith(pre)]
        total, days = sum(vals), len(vals)
        pay, food = round(total * wage), days * meal
        return {"gongsu": total, "days": days, "pay": pay, "meal": food, "sum": pay + food}


def fmt_gongsu(v):
    return ("%g" % v)


# ---- 구글 달력의 공개 한국 공휴일(로그인 필요 없는 iCal 주소). 받아 두었다가 쓰고, 못 받으면 위의 내장 표를 쓴다
GOOGLE_ICS = "https://calendar.google.com/calendar/ical/ko.south_korea%23holiday%40group.v.calendar.google.com/public/basic.ics"
STALE_DAYS = 30


def parse_ics(text):
    """iCal 글 → {YYYY-MM-DD: 이름}. 설명이 '공휴일'인 것만(어버이날 같은 기념일은 뺀다). 하루짜리·여러 날짜 일정을 날마다 펼친다"""
    out = {}
    text = text.replace("\r\n ", "").replace("\r\n", "\n").replace("\n ", "")
    for block in text.split("BEGIN:VEVENT")[1:]:
        f = {}
        for line in block.split("\n"):
            key, _, val = line.partition(":")
            f[key.split(";")[0]] = val.strip()
        start, end, name = f.get("DTSTART", ""), f.get("DTEND", ""), f.get("SUMMARY", "")
        if "공휴일" not in f.get("DESCRIPTION", "") or len(start) != 8 or not name:
            continue
        a = datetime.date(int(start[:4]), int(start[4:6]), int(start[6:]))
        b = datetime.date(int(end[:4]), int(end[4:6]), int(end[6:])) if len(end) == 8 else a + datetime.timedelta(1)
        d = a
        while d < b:
            out[iso(d)] = name
            d += datetime.timedelta(1)
    return out


def fetch_google(url=GOOGLE_ICS, timeout=20):
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return parse_ics(r.read().decode("utf-8", "replace"))
