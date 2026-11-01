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
# ---- 개수 기준 속도(용량 속도는 큰 파일에 좌우돼 실제 진행과 안 맞았다)
cr = spg.CountRate()
check("표본 하나로는 속도를 모름", cr.update(1000.0, 100, 1000) == (0.0, 0.0, 0.0))
check("60초 안에는 아직 모름", cr.update(1030.0, 110, 1100) == (0.0, 0.0, 0.0))
r, rn, rm = cr.update(1120.0, 160, 1760)   # 120초: 글 +60 · 그림 +760
check("120초에 글 60·그림 760 → 전체 초당 6.83, 글 0.5, 그림 6.33", abs(r - 820 / 120) < 1e-9 and abs(rn - 0.5) < 1e-9 and abs(rm - 760 / 120) < 1e-9)
cr.update(1400.0, 200, 2000)
r2 = cr.update(1520.0, 230, 2500)
check("창(300초) 밖의 옛 표본은 버림", len(cr.samples) <= 4 and r2[0] > 0)
check("같은 시각 표본은 갈아 끼움(2분마다 갱신되는 값을 4초마다 읽어도 표본이 안 불어남)", (lambda c: (c.update(5.0, 1, 1), c.update(5.0, 2, 2), len(c.samples))[2])(spg.CountRate()) == 1)
c3 = spg.CountRate()
c3.update(0.0, 100, 100); c3.update(100.0, 150, 200)
c3.update(200.0, 10, 20)
check("개수가 줄면(다시 훑는 중) 새로 센다", len(c3.samples) == 1)
check("남은 시간: 모르면 계산 중, 끝났으면 0분", spg.eta_text(100, 0) == "계산 중" and spg.eta_text(0, 5) == "0분" and spg.eta_text(600, 2) == "약 5분")
d_ = {"notesHave": 4201, "notesAll": 13670, "mediaHave": 31863, "mediaAll": 53316}
blk = spg.phone_block(d_, (12.8, 0.55, 12.3), "열린 단계 13 / 14" + chr(10), (3 << 30, 1 << 30), 14 << 20)
check("폰과 같은 문구: 전체 N / M개 (P%)", "전체 36,064 / 66,986개 (53%)" in blk)
check("글·그림 줄", "글 4,201 / 13,670개 (30%) · 그림 31,863 / 53,316개 (59%)" in blk)
check("받음·남음 줄", "전체 66,986개 중 받음 36,064개 · 남음 30,922개" in blk)
check("속도: 개수 기준 + 글/그림 분당 + 남은 시간", "속도 초당 12.8개 (글 분당 33개 · 그림 분당 738개) · 남은 시간 약 40분" in blk)
check("용량 줄은 참고용(순간 속도라고 표시)", "지금 받는 범위 용량 2.0GB / 3.0GB · 순간 속도 14MB/초" in blk)
check("단계 줄이 맨 위", blk.startswith("열린 단계 13 / 14"))
check("속도를 모르면 계산 중", "남은 시간 계산 중" in spg.phone_block(d_, (0.0, 0.0, 0.0)))
dd = dict(d_, notesHave=13670, mediaHave=53316)
check("다 받으면 속도 줄 없음", "속도" not in spg.phone_block(dd))
print("통과" if not fails else "실패 %d" % fails)
sys.exit(1 if fails else 0)
