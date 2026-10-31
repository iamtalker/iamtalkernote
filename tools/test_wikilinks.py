"""위키 링크 규칙(wikilinks.py) 시험: py -3 -I -X utf8 tools/test_wikilinks.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import wikilinks as wl

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


check("제목 비교: 대소문자·공백 무시", wl.norm("  Hello   World ") == wl.norm("hello world"))
check("링크 나누기: 제목만", wl.split_target("가나다") == ("가나다", "", ""))
check("링크 나누기: 절·표시글", wl.split_target("가나다#둘째 |보이는 글") == ("가나다", "둘째", "보이는 글"))
text = "앞 [[A]] 와 [[B#c|씨]] 그리고 `[[코드]]` 와\n```\n[[펜스]]\n```\n끝 [[ ]] \\[[이스케이프]]"
check("본문에서 링크 뽑기(코드·빈 링크·이스케이프 제외)", wl.links_in(text) == [("A", "", ""), ("B", "c", "씨")])

notes = [
    {"title": "회의록", "mtime": 100, "path": "a/회의록.md"},
    {"title": "회의록", "mtime": 300, "path": "b/회의록.md"},
    {"title": "회의록 ", "mtime": 200, "path": "c/회의록.md"},
    {"title": "Todo", "mtime": 5, "path": "todo.md"},
]
check("같은 제목이면 가장 최근 노트", wl.latest(notes, "회의록")["path"] == "b/회의록.md")
check("대소문자 달라도 찾음", wl.latest(notes, "TODO")["path"] == "todo.md")
check("없는 제목은 None", wl.latest(notes, "없음") is None)
check("mtime 같으면 경로로 정해 항상 같은 결과", wl.latest([{"title": "x", "mtime": 1, "path": "a"}, {"title": "x", "mtime": 1, "path": "b"}], "x")["path"] == "b")
check("index 는 제목마다 하나", len(wl.index(notes)) == 2)

titles = [("회의록", "a.md"), ("회의록 (2)", "b.md")]
check("겹침 판정", wl.taken("회의록", titles) and wl.taken("  회의록", titles) and not wl.taken("다른", titles))
check("자기 자신은 겹침 아님", not wl.taken("회의록", titles, own="a.md"))
check("겹치지 않는 제목 만들기", wl.free_title("회의록", titles) == "회의록 (3)" and wl.free_title("새", titles) == "새")

print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
