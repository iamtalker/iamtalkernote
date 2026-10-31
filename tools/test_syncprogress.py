"""진행 상황 계산(syncprogress.py) 시험"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import syncprogress as spg

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


e = spg.Eta()
check("처음엔 속도를 모름", e.update(1000, 0) == 0 and e.update(900, 10) == 0)
r = e.update(800, 20)
check("20초에 200바이트 → 초당 10", abs(r - 10) < 1e-9)
check("남은 시간 80초 → 약 1분", spg.remaining(800, r) == "약 1분")
check("남은 시간 글자", spg.remaining(3000, 10) == "약 5분" and spg.remaining(100, 10) == "1분 미만" and spg.remaining(0, 10) == "" and spg.remaining(50, 0) == "")
check("시간·일 단위", spg.remaining(73800, 10) == "약 2시간 3분" and spg.remaining(936000, 10) == "약 1일 2시간")
check("남은 용량이 늘면 다시 셈", e.update(5000, 25) == 0)
check("용량 글자", spg.size(12 << 20) == "12MB" and spg.size(3 << 29) == "1.5GB")
s = spg.line(1000, 250, 1 << 30, 1 << 28, 0)
check("줄: 개수·퍼센트·용량", "전체 1000개" in s and "받음 750개" in s and "남음 250개" in s and "75%" in s and "속도" not in s)
check("줄: 속도 있으면 시간도", "남은 시간" in spg.line(1000, 250, 1 << 30, 1 << 28, 1 << 20))
s2 = spg.line(1000, 250, 1 << 30, 1 << 28, 0, 5000)
check("전체 파일 수 기준: 5,000 중 750 받음 15%", "전체 5,000개" in s2 and "받음 750개" in s2 and "남음 4,250개" in s2 and "15%" in s2)
import json, tempfile, time as _t
with tempfile.TemporaryDirectory() as d_:
    check("폰이 적은 값이 없으면 None", spg.read_phone(d_) is None)
    json.dump({"updated": int(_t.time() * 1000), "notesHave": 400, "notesAll": 13666, "mediaHave": 1500, "mediaAll": 53314}, open(d_ + "/progress.json", "w"))
    ph = spg.read_phone(d_)
    check("폰이 적은 값을 읽음", ph and ph["notesHave"] == 400)
    ln = spg.phone_line(ph)
    check("줄: 전체 66,980 중 1,900 · 글/그림", "66,980개 중 1,900개 (2%)" in ln and "글 400 / 13,666개" in ln and "그림 1,500 / 53,314개" in ln)
    json.dump({"updated": 1000, "notesHave": 1, "notesAll": 2, "mediaHave": 3, "mediaAll": 4}, open(d_ + "/progress.json", "w"))
    check("오래된 값은 안 믿음", spg.read_phone(d_) is None)
print("통과" if not fails else "실패 %d" % fails)
sys.exit(1 if fails else 0)
