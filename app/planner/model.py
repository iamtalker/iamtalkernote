"""달력·할일·공수 모델(화면을 모르는 순수 계산). 날짜는 'YYYY-MM-DD' 글자로 다룬다."""
import datetime
import hashlib
import json
import os
import re

DIR = ".planner"           # 앱 상태(구글 공휴일을 받아 둔 것, 알린 기록)
FILE = "data.json"
MD_DIR = "달력"            # 달마다 마크다운 파일 하나: '2026년 11월.md' (공수와 그 달 날짜가 있는 할일), 날짜 없는 할일은 '할일.md'
UNDATED = "할일.md"
MONTH_RE = re.compile(r"^(\d{4})년 (\d{1,2})월\.md$")
TODO_RE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s*(?:(\d{4}-\d{2}-\d{2})\s+)?(.*?)(?:\s*✓(\d{4}-\d{2}-\d{2}))?\s*$")   # 끝의 ✓날짜 = 완료한 날
GONGSU_RE = re.compile(r"^\s*[-*]\s*(\d{4}-\d{2}-\d{2})\s*[:：]\s*(\d+(?:\.\d+)?)")

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


def parse_loose(s):
    """사람이 친 날짜(20260914 · 2026-9-14 · 2026.09.14 · 2026/9/14) → 'YYYY-MM-DD'. 안 읽히면 None"""
    m = re.match(r"^\s*(\d{4})[.\-/]?(\d{1,2})[.\-/]?(\d{1,2})\s*$", s or "")
    if not m:
        return None
    try:
        return iso(datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    except ValueError:
        return None


def month_grid(year, month):
    """달력 칸: 일요일 시작 6주 × 7일의 날짜(date) 목록"""
    first = datetime.date(year, month, 1)
    start = first - datetime.timedelta((first.weekday() + 1) % 7)
    return [start + datetime.timedelta(i) for i in range(42)]


def render_month(year, month, todos, gongsu):
    """그 달 파일의 글: 공수 목록과 할일 목록. 손으로 고쳐도 읽히도록 보통 마크다운 목록이다"""
    out = [f"# {year}년 {month}월", ""]
    if gongsu:
        out += ["## 공수"] + [f"- {d}: {fmt_gongsu(v)}" for d, v in sorted(gongsu.items())] + [""]
    if todos:
        out += ["## 할일"] + [f"- [{'x' if t['done'] else ' '}] {t['date']} {t['text']}" + (f" ✓{t['done_on']}" if t["done"] and t.get("done_on") else "")
                            for t in sorted(todos, key=lambda t: (t["date"], t["text"]))] + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def render_undated(todos):
    return "\n".join(["# 할일", ""] + [f"- [{'x' if t['done'] else ' '}] {t['text']}" + (f" ✓{t['done_on']}" if t["done"] and t.get("done_on") else "") for t in todos]) + "\n"


def parse_md(text):
    """파일 글 → ([(날짜 또는 None, 글, 했나, 완료한 날)], {날짜: 공수}). 못 읽는 줄은 건너뛴다"""
    todos, gongsu = [], {}
    for line in text.split("\n"):
        m = TODO_RE.match(line)
        if m:
            if m.group(3):
                todos.append((m.group(2), m.group(3), m.group(1) in "xX", m.group(4)))
            continue
        m = GONGSU_RE.match(line)
        if m and parse(m.group(1)):
            v = float(m.group(2))
            if v > 0:
                gongsu[m.group(1)] = v
    return todos, gongsu


def _tid(date, text, seen):
    base = hashlib.sha1(f"{date}|{text}".encode("utf-8")).hexdigest()[:8]
    n, tid = 1, base
    while tid in seen:                                 # 같은 날 같은 글이 둘이면 번호를 붙여 구분
        n += 1
        tid = f"{base}{n}"
    seen.add(tid)
    return tid


class Planner:
    """할일·공수 자료. root 는 노트 폴더. 자료는 노트 폴더의 '달력' 폴더에 달마다 마크다운 파일로 저장한다(다른 편집기·폰에서도 열린다).
    바뀔 때마다 바로 저장한다(임시 파일로 쓴 뒤 바꿔치기). 앱 상태(구글 공휴일·알린 기록)는 .planner/data.json"""

    def __init__(self, root):
        self.path = os.path.join(root, DIR, FILE)
        self.dir = os.path.join(root, MD_DIR)
        self.todos, self.gongsu = [], {}
        self.google, self.google_at = {}, ""        # 구글 달력에서 받아 둔 공휴일 {날짜: 이름}, 받은 날
        self.notified = {}                          # {할일 id: 알린 날}
        self._sig = None
        self.load()

    def signature(self):
        try:
            return tuple(sorted((e.name, e.stat().st_mtime_ns, e.stat().st_size) for e in os.scandir(self.dir) if e.name.endswith(".md")))   # 수정 시각이 같은 틱이어도 크기가 달라지면 알아챈다
        except OSError:
            return ()

    def sync(self):
        """밖(다른 편집기·폰 동기화)에서 파일이 바뀌었으면 다시 읽는다 → 바뀌었는가"""
        if self.signature() != self._sig:
            self.load()
            return True
        return False

    def _state(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def load(self):
        st = self._state()
        self.google = {k: v for k, v in st.get("google", {}).items() if parse(k)}
        self.google_at = st.get("google_at", "")
        self.notified = {k: v for k, v in st.get("notified", {}).items() if isinstance(v, str)}
        rows, self.gongsu, found = [], {}, False
        try:
            names = sorted(os.listdir(self.dir))
        except OSError:
            names = []
        for name in names:
            if not (MONTH_RE.match(name) or name == UNDATED):
                continue
            try:
                with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                    todos, gongsu = parse_md(fh.read())
            except OSError:
                continue
            found = True
            rows += todos
            self.gongsu.update(gongsu)
        if not found and (st.get("todos") or st.get("gongsu")):   # 예전 방식(.planner/data.json)의 자료를 마크다운으로 옮긴다
            rows = [(t.get("date"), t["text"], bool(t.get("done")), None) for t in st.get("todos", []) if isinstance(t, dict) and t.get("text")]
            self.gongsu = {k: float(v) for k, v in st.get("gongsu", {}).items() if parse(k) and isinstance(v, (int, float)) and v > 0}
            self.todos = self._make(rows)
            self.save()
            return
        self.todos = self._make(rows)
        self._sig = self.signature()

    def _make(self, rows):
        seen, out = set(), []
        for date, text, done, done_on in rows:
            tid = _tid(date, text, seen)
            t = {"id": tid, "text": text, "date": date or None, "done": done}
            if done and done_on:
                t["done_on"] = done_on
            if self.notified.get(tid):
                t["notified"] = self.notified[tid]
            out.append(t)
        return out

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        months = {}
        for t in self.todos:
            if t.get("date") and parse(t["date"]):
                d = parse(t["date"])
                months.setdefault((d.year, d.month), ([], {}))[0].append(t)
        for k, v in self.gongsu.items():
            d = parse(k)
            months.setdefault((d.year, d.month), ([], {}))[1][k] = v
        want = {f"{y}년 {m:02d}월.md": render_month(y, m, ts, gs) for (y, m), (ts, gs) in months.items()}
        undated = [t for t in self.todos if not (t.get("date") and parse(t["date"]))]
        if undated:
            want[UNDATED] = render_undated(undated)
        for name, text in want.items():
            self._write(os.path.join(self.dir, name), text)
        try:
            for name in os.listdir(self.dir):       # 이제 비어 있는 달 파일은 지운다(우리가 만드는 이름 모양만)
                if (MONTH_RE.match(name) or name == UNDATED) and name not in want:
                    os.remove(os.path.join(self.dir, name))
        except OSError:
            pass
        self.notified = {t["id"]: t["notified"] for t in self.todos if t.get("notified")}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._write(self.path, json.dumps({"google": self.google, "google_at": self.google_at, "notified": self.notified}, ensure_ascii=False, indent=1))
        self._sig = self.signature()

    @staticmethod
    def _write(path, text):
        try:
            with open(path, encoding="utf-8") as fh:
                if fh.read() == text:
                    return                                    # 같으면 다시 쓰지 않는다(동기화·수정 시각을 건드리지 않게)
        except OSError:
            pass
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)

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
        text = " ".join(text.split())
        if text:
            self.todos.append({"id": _tid(date, text, {x["id"] for x in self.todos}), "text": text, "date": date or None, "done": False})
            self.save()
            return self.todos[-1]

    def find(self, tid):
        return next((t for t in self.todos if t["id"] == tid), None)

    def update(self, tid, **kw):
        t = self.find(tid)
        if t:
            t.update(kw)
            if "date" in kw or "done" in kw:
                t.pop("notified", None)
            if "done" in kw:                                   # 끝낸 날을 적어 둔다(그 달까지만 이월 표시)
                if kw["done"]:
                    t["done_on"] = iso(datetime.date.today())
                else:
                    t.pop("done_on", None)
            self.save()

    def set_done_on(self, tid, date):
        """완료한 날을 직접 정한다(그날 끝낸 것으로 표시)"""
        t = self.find(tid)
        if t:
            t["done"], t["done_on"] = True, date
            t.pop("notified", None)
            self.save()

    def remove(self, tid):
        self.todos = [t for t in self.todos if t["id"] != tid]
        self.save()

    def on(self, date):
        """그 날짜의 할일"""
        return [t for t in self.todos if t.get("date") == date]

    def carried(self, year, month):
        """그 달로 넘어와 표시할 할일: 앞선 달에 날짜가 있는데 아직 안 끝낸 것(끝낸 것은 끝낸 달까지만)"""
        first = f"{year:04d}-{month:02d}"
        out = []
        for t in self.todos:
            d = t.get("date")
            if not d or d[:7] >= first:
                continue
            if not t["done"] or (t.get("done_on") and t["done_on"][:7] >= first):
                out.append(t)
        return out

    def span_on(self, date, today=None):
        """그 날짜 칸에 걸쳐 보일 할일 [(할일, 시작날인가)]: 할일은 쓴 날에 시작해서, 끝내기 전까지는 오늘까지 날마다 이어지고(달이 바뀌어도),
        끝내면 끝낸 날까지만 보인다. 앞으로 올 날에는 쓴 날이 아니면 보이지 않는다"""
        today = today or iso(datetime.date.today())
        out = []
        for t in self.todos:
            d = t.get("date")
            if not d or d > date:
                continue
            end = (t.get("done_on") or d) if t["done"] else max(today, d)
            if date <= end:
                out.append((t, d == date))
        return out

    def shown_on(self, date):
        """달력 칸에 보일 그날의 할일: 그날 것 + (그 달 1일이면) 지난달에서 넘어온 것"""
        d = parse(date)
        return self.on(date) + (self.carried(d.year, d.month) if d and d.day == 1 else [])

    def ordered(self, only_date=None):
        """아래 목록 순서: 맨 위가 가장 과거, 맨 아래가 가장 미래(날짜순). 끝낸 것도 자기 날짜 자리에 있다. 날짜 없는 예전 할일은 맨 위"""
        pool = self.shown_on(only_date) if only_date else self.todos
        return sorted(pool, key=lambda t: (t.get("date") or "", t["text"]))

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
