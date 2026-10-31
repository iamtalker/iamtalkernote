"""표 읽기·그리기 시험(대시 1~2개 구분줄, 칸 정렬, 칸 폭에 맞춘 줄바꿈, 아주 좁을 때 카드): py -3 -I -X utf8 tools/test_table.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import preview  # noqa: E402
import wikiconv  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def draw(src, cols=None):
    return "".join(t for t, _, _ in preview.layout(wikiconv.parse(src, "markdown", "t"), cols=cols))


def blocks(src):
    return [b[0] for b in wikiconv.parse(src, "markdown", "t").blocks]


print("구분줄")
for sep in ("|---|---|", "|:--|--:|", "|:-:|:-:|", "| - | - |", "|:-|-:|", "---|---", "--|--"):
    check("표로 읽음: " + sep, blocks("| a | b |\n%s\n| 1 | 2 |\n" % sep) == ["table"])
check("파이프 없는 '-' 한 줄은 표가 아님", "table" not in blocks("a | b\n-\n"))
check("파이프 없는 '--' 도 표가 아님", "table" not in blocks("a | b\n--\n"))

print("정렬")
t = draw("| 이름 | 나이 | 설명 |\n|:--|--:|:-:|\n| 홍길동 | 30 | 짧음 |\n| 김 | 4 | 가운데 맞춤 |\n")
lines = t.split("\n")
check("오른쪽 맞춤: 숫자가 칸 오른쪽 끝", "│   30 │" in lines[2] and "│    4 │" in lines[3])
check("가운데 맞춤", lines[2].split("│")[3].startswith("  ") and lines[2].split("│")[3].rstrip().endswith("짧음"))
check("머리행은 왼쪽 맞춤", lines[0].startswith("│ 이름   │ 나이 │ 설명"))

print("폭에 맞춤")
src = "| 이름 | 나이 | 설명 |\n|:--|--:|:-:|\n| 홍길동 | 30 | 짧은 설명 |\n| 김철수 | 4 | **굵게**와 `코드`가 든 조금 더 긴 설명입니다 |\n| Alice | 100 | English text and 한글 섞기 |\n"
wide = draw(src)
check("cols 없으면 그대로", draw(src, None) == wide)
check("충분히 넓으면 그대로", draw(src, 80) == wide)
for c in (44, 32):
    out = draw(src, c)
    rows = [ln for ln in out.split("\n") if ln.startswith(("│", "├"))]
    check("cols=%d: 상자가 폭 안(%d칸 이하)" % (c, c), all(preview.width(ln) <= c for ln in rows))
    check("cols=%d: 모든 줄 너비가 같음(상자 유지)" % c, len({preview.width(ln) for ln in rows}) == 1)
    check("cols=%d: 글 보존(줄바꿈만)" % c, "홍길동" in out and "English" in out and "섞기" in out)
card = draw(src, 20)
check("아주 좁으면 카드('머리글: 값')", "이름: 홍길동" in card and "설명: 짧은 설명" in card and "│" not in card)
check("카드도 글 보존", "English text and 한글 섞기" in card)
check("행이 하나뿐인(머리행만) 표는 카드로 바꾸지 않음", "│" in draw("| a | b |\n|---|---|\n", 10))

print("낱말 줄바꿈")
check("wrap_cell 영문 낱말 경계", preview.wrap_cell("aaa bbb ccc", 7) == ["aaa bbb", "ccc"])
check("wrap_cell 한글 글자 단위(전각 2칸)", preview.wrap_cell("가나다라마", 4) == ["가나", "다라", "마"])
check("wrap_cell 긴 낱말 자름", preview.wrap_cell("abcdefgh", 3) == ["abc", "def", "gh"])
check("wrap_cell 빈 글", preview.wrap_cell("", 5) == [""])
check("fit_columns: 좁은 열은 그대로", preview.fit_columns([3, 40, 40], 30)[0] == 3 and sum(preview.fit_columns([3, 40, 40], 30)) <= 30)
check("fit_columns: 합이 작으면 그대로", preview.fit_columns([3, 4], 30) == [3, 4])

print("픽셀 방식(탭 정지점)")
ms = lambda s: sum(12 if ord(c) > 0x2000 else 7 for c in s)  # noqa: E731   한글 12px · 그 밖 7px 인 가짜 글꼴(고정폭이 아님)


def px(src, avail):
    segs = preview.layout(wikiconv.parse(src, "markdown", "t"), avail=avail, measure=ms)
    return segs


segs = px(src, 900)
tags = [t for _, tg, _ in segs for t in tg if t.startswith("T:")]
check("탭 태그가 나옴(머리행·본문 모두)", len(tags) >= 4 and len(set(tags)) == 1)
stops = [(int(p[:-1]), p[-1]) for p in tags[0][2:].split(";")]
check("정지점은 늘어나는 순서", [x for x, _ in stops] == sorted(x for x, _ in stops))
check("정렬: 오른쪽 r, 가운데 c, 왼쪽 l 이 열 순서대로", [s for _, s in stops[0::2]] == ["l", "r", "c"])
CELL = ("tb00", "tb01", "tb10", "tb11", "th0", "th1")
cells = [(t, [x for x in tg if x in CELL][0]) for t, tg, _ in segs if any(x in CELL for x in tg)]
check("칸마다 '<탭>글<탭>' 조각(세로줄 문자 없음)", cells[0][0] == "	이름	" and all(t.startswith("	") and t.endswith("	") and "│" not in t for t, _ in cells))
check("머리행은 th(굵게·회색), 본문은 tb", cells[0][1].startswith("th") and cells[3][1].startswith("tb") and all(c.startswith("th") for _, c in cells[:3]))
grid = [[c for _, c in cells[i:i + 3]] for i in range(0, len(cells), 3)]
check("가로로 이웃한 칸의 태그가 다름(격자선이 합쳐지지 않게)", all(r[j] != r[j + 1] for r in grid for j in range(2)))
check("세로로 이웃한 칸의 태그도 다름", all(grid[i][j] != grid[i + 1][j] for i in range(len(grid) - 1) for j in range(3)))
# 좁으면 줄바꿈, 아주 좁으면 카드
narrow = "".join(t for t, _, _ in px(src, 300))
check("좁으면 줄이 늘고 글 보존", narrow.count("\n") > "".join(t for t, _, _ in segs).count("\n") and "English" in narrow and "섞기" in narrow)
card_px = "".join(t for t, _, _ in px(src, 90))
check("아주 좁으면 카드", "이름: 홍길동" in card_px and "\t" not in card_px)
check("wrap_px: 영문 낱말 경계", preview.wrap_px("aaa bbb ccc", 7 * 7, ms) == ["aaa bbb", "ccc"])
check("wrap_px: 한글(12px) 글자 단위", preview.wrap_px("가나다라마", 24, ms) == ["가나", "다라", "마"])
check("fit_px: 합이 크면 줄임", sum(preview.fit_px([50, 300, 300], 400, 14)) <= 400 and preview.fit_px([50, 300, 300], 400, 14)[0] == 50)
check("tab_tag", preview.tab_tag([(14, "l"), (150, "r")]) == "T:14l;150r")

print("\n%s" % ("모두 통과" if not fails else "실패 %d" % fails))
sys.exit(1 if fails else 0)
