"""검색 기간 문법(date:…, search.py) 시험: py -3 -I -X utf8 tools/test_search_date.py"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import search as s

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def ts(y, m, d, hh=12):
    return time.mktime((y, m, d, hh, 0, 0, 0, 0, -1))


def day(t):
    return time.strftime("%Y%m%d", time.localtime(t))


q, f, t = s.split_date("date:20101011-20240104 만화&아이유")
check("검색식에서 기간을 떼어 냄", q == "만화&아이유" and day(f) == "20101011" and day(t) == "20240104")
check("끝 날은 그날 끝까지", time.strftime("%H%M%S", time.localtime(t)) == "235959")
check("하루·한 달·한 해", day(s.split_date("date:20240315")[2]) == "20240315" and day(s.split_date("date:202402")[2]) == "20240229" and day(s.split_date("date:2024")[1]) == "20240101")
check("열린 기간", s.split_date("date:20240101-")[2] is None and s.split_date("date:-20240104")[1] is None)
check("날짜: 기간: 도 같음", s.split_date("날짜:20240101 기간:20240301")[0] == "")
check("기간이 없으면 그대로", s.split_date("회의록 AND 예산") == ("회의록 AND 예산", None, None))
check("날짜 칸도 여러 모양", day(s.parse_date("2021.01.01")) == "20210101" and day(s.parse_date("20210101")) == "20210101" and day(s.parse_date("2021-1-1")) == "20210101")

notes = [{"title": "a", "mtime": ts(2010, 1, 1), "body": "만화 아이유"}, {"title": "b", "mtime": ts(2015, 5, 5), "body": "만화 아이유"},
         {"title": "c", "mtime": ts(2015, 5, 6), "body": "만화"}, {"title": "d", "mtime": ts(2025, 1, 1), "body": "만화 아이유"}]
out, _ = s.run(notes, "date:20101011-20240104 만화&아이유")
check("기간 안에서 두 단어가 다 든 글만", [n["title"] for n in out] == ["b"])
out, _ = s.run(notes, "date:2015 만화", date_from="2015.05.06")
check("기간 칸과 겹치는 부분만", [n["title"] for n in out] == ["c"])
check("없는 날짜(20222222)는 조용히 무시하지 않고 오류로", s.bad_dates("date:20200202-20222222 시노지키") == ["date:20200202-20222222"])
check("기간 칸의 없는 날짜도 오류, 치는 중인 글은 아님", s.bad_dates("x", "20200202", "20222222") == ["기간 끝 20222222"] and s.bad_dates("x", "2020", "202002") == [])
check("올바른 기간은 오류 없음", s.bad_dates("date:20200202-20221231 x date:2024") == [])

print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
