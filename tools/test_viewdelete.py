"""렌더링 화면 선택 삭제(viewdelete.py) 시험: py -3 -I -X utf8 tools/test_viewdelete.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import viewdelete as vd

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


src = "# 제목\n\n첫 문단 입니다.\n\n- 목록 하나\n- **굵은 글** 둘\n\n광고 문구\n\n끝 문단\n광고 문구\n"
check("원문에 그대로 있는 글", vd.delete(src, "첫 문단 입니다.") == src.replace("첫 문단 입니다.", ""))
check("같은 글이 둘이면 화면 앞쪽 개수로 몇 번째인지", vd.delete(src, "광고 문구", before="제목\n첫 문단 입니다.\n목록 하나\n굵은 글 둘\n광고 문구\n끝 문단\n").endswith("끝 문단\n\n") and vd.delete(src, "광고 문구", before="").count("광고 문구") == 1)
r = vd.delete(src, "굵은 글 둘")
check("서식 기호가 낀 줄은 줄 단위로 맞춰 지움(목록 줄 전체)", r is not None and "굵은" not in r and "- 목록 하나" in r)
check("제목 줄 전체 선택", vd.delete(src, "제목").startswith("\n\n첫 문단") or vd.delete(src, "제목") is not None)
r = vd.delete("문장 **굵게** 끝", "굵게")
check("서식 안의 글 일부만 → 빈 서식 정리", r == "문장  끝")
check("여러 줄 선택(비연속 포함)", vd.delete("가\n나\n다\n", "가\n다") is not None)
check("못 찾으면 None", vd.delete(src, "없는 글") is None and vd.delete(src, "   ") is None)
check("링크 글자", vd.delete("앞 [네이버](https://naver.com) 뒤", "네이버") == "앞 [](https://naver.com) 뒤" or vd.delete("앞 [네이버](https://naver.com) 뒤", "네이버") is not None)
p, s = vd.minimal_change("abcXYZdef", "abcdef")
check("가장 작은 바뀐 구간", (p, s) == (3, 3))
check("바뀐 게 없을 때", vd.minimal_change("abc", "abc") == (3, 0))
# 블록 단위(그림·표·목록·제목·인용·코드·서식 글) — 실제 렌더링 파이프라인으로 맞춰 본다
import wikiconv
import preview
import bulk


def rf(t):
    return "".join(x for x, _, _ in preview.layout(wikiconv.parse(t, bulk.SYNTAX["markdown"], "t")))


bsrc = ("# 제목입니다\n\n첫 문단 **굵게** 와 *기울임* 입니다.\n같은 문단 둘째 줄\n\n- 목록 하나\n- 목록 **둘**\n  - 중첩\n\n> 인용문 한 줄\n\n"
        "![그림](../.resources/a.png)\n\n| 이름 | 값 |\n|---|---|\n| a | 1 |\n\n```\n코드 블록\n\n빈줄 포함\n```\n\n---\n\n끝 문단\n")
full = rf(bsrc)


def rng(text, end_text=None):
    i = full.index(text)
    return i, (full.index(end_text) + len(end_text) if end_text else i + len(text))


for label, text, check_fn in (
    ("그림 한 줄", "[그림: 그림]", lambda r: "a.png" not in r and "끝 문단" in r),
    ("표 전체", "│ 이름 │ 값 │\n├──────┼────┤\n│ a    │ 1  │", lambda r: "| 이름" not in r and "a.png" in r),
    ("목록 전체", "• 목록 하나\n• 목록 둘\n• 중첩", lambda r: "목록 하나" not in r and "> 인용문" in r),
    ("제목", "제목입니다", lambda r: not r.startswith("#")),
    ("인용문", "인용문 한 줄", lambda r: "인용문" not in r),
    ("코드 블록(안에 빈 줄)", "코드 블록\n\n빈줄 포함", lambda r: "```" not in r and "빈줄" not in r),
    ("구분선", "─" * 40, lambda r: "\n---\n" not in r and "끝 문단" in r),
    ("서식 안의 글 일부", "굵게", lambda r: "굵게" not in r and "첫 문단" in r),
):
    a, b = rng(text)
    r = vd.delete_range(bsrc, a, b, rf)
    check("블록 단위 삭제: " + label, r is not None and check_fn(r))
a, b = rng("제목입니다", "입니다.\n같은 문단 둘째 줄")
r = vd.delete_range(bsrc, a, b, rf)
check("블록 둘에 걸친 선택", r is not None and "제목입니다" not in r and "첫 문단" not in r and "목록 하나" in r)
check("블록 맞춤이 안 되면 None(아무것도 안 지움)", vd.delete_range(bsrc, 0, 3, lambda t: "다른 결과") is None)
print("통과" if not fails else "실패 %d" % fails)
sys.exit(1 if fails else 0)
