"""아웃라이너 모델(app/outliner/model.py) 시험: py -3 -I -X utf8 tools/test_outliner_model.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from outliner import model as m

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def tree(items):
    return [(it.depth, it.text) for it in items]


S = "- a\n- b\n    - b1\n    - b2\n- c\n"
it = m.parse(S)
check("읽기", tree(it) == [(0, "a"), (0, "b"), (1, "b1"), (1, "b2"), (0, "c")])
check("쓰기는 읽기의 거울", m.dump(it) == S)
check("2칸 들여쓰기·탭·번호도 읽음", tree(m.parse("1. x\n  - y\n\t- z\n")) == [(0, "x"), (1, "y"), (2, "z")])
check("목록이 아닌 줄은 앞 항목과 같은 깊이", tree(m.parse("- a\n  - b\n글\n")) == [(0, "a"), (1, "b"), (1, "글")])
check("빈 글 항목·빈 줄", tree(m.parse("- a\n-\n\n- c")) == [(0, "a"), (0, ""), (0, "c")])
check("깊이는 한 단계씩만", tree(m.parse("- a\n        - b")) == [(0, "a"), (1, "b")])

check("끝·하위 여부", m.end_of(it, 1) == 4 and m.has_children(it, 1) and not m.has_children(it, 0))
it[1].collapsed = True
check("접으면 하위가 안 보임", m.visible(it) == [0, 1, 4])
it[1].collapsed = False
check("줌인하면 그 하위만", m.visible(it, 1) == [2, 3])
check("부모 찾기", m.ancestors(it, 2) == [1] and m.ancestors(it, 0) == [])

it = m.parse(S)
pos = m.split(it, 0, 1)
check("Enter: 가운데서 나누면 같은 깊이 다음 항목", pos == (1, 0) and tree(it)[:2] == [(0, "a"), (0, "")])
it = m.parse(S)
pos = m.split(it, 1, 1)
check("Enter: 하위가 있으면 첫 자식", tree(it)[1:3] == [(0, "b"), (1, "")] and pos == (2, 0))
it = m.parse(S)
it[1].collapsed = True
m.split(it, 1, 1)
check("Enter: 접힌 항목은 하위 다음에 형제", tree(it)[3:5] == [(1, "b2"), (0, "")])
it = m.parse("- abc")
m.split(it, 0, 1)
check("Enter: 글 가운데서 나눔", tree(it) == [(0, "a"), (0, "bc")])
it = m.parse("- abc")
pos = m.split(it, 0, 0)
check("Enter: 맨 앞이면 위에 빈 항목, 커서는 글 쪽", tree(it) == [(0, ""), (0, "abc")] and pos == (1, 0))

it = m.parse(S)
check("Tab: 첫 항목은 못 넣음", not m.indent(it, 0))
check("Tab: b 를 a 아래로(하위 함께)", m.indent(it, 1) and tree(it) == [(0, "a"), (1, "b"), (2, "b1"), (2, "b2"), (0, "c")])
it = m.parse(S)
check("Tab: b1(앞 항목 b 보다 깊음)은 못 넣음", not m.indent(it, 2))
check("Tab: b2 를 b1 아래로", m.indent(it, 3) and tree(it)[3] == (2, "b2"))
it = m.parse(S)
check("Shift+Tab: b1 을 바깥으로, 뒤따르는 b2 는 b1 의 하위", m.outdent(it, 2) and tree(it) == [(0, "a"), (0, "b"), (0, "b1"), (1, "b2"), (0, "c")])
check("Shift+Tab: 최상위는 못 함", not m.outdent(it, 0))
check("줌인한 맨 위 아래로는 못 나감", not m.outdent(m.parse(S), 2, floor=1))

it = m.parse(S)
check("위로 옮기기(하위 함께)", m.move(it, 4, True) == 1 and tree(it) == [(0, "a"), (0, "c"), (0, "b"), (1, "b1"), (1, "b2")])
it = m.parse(S)
check("아래로 옮기기", m.move(it, 0, False) == 3 and tree(it) == [(0, "b"), (1, "b1"), (1, "b2"), (0, "a"), (0, "c")])
check("맨 위·맨 아래는 더 못 옮김", m.move(m.parse(S), 0, True) is None and m.move(m.parse(S), 4, False) is None)

it = m.parse("- ab\n- cd\n    - e")
pos = m.merge_prev(it, 1, 0)
check("Backspace: 앞 항목 끝에 붙임(하위는 남음)", pos == (0, 2) and tree(it) == [(0, "abcd"), (1, "e")])
it = m.parse("- ab\n- cd")
pos = m.merge_next(it, 0, 1)
check("Delete: 다음 항목을 붙임", pos == (0, 2) and tree(it) == [(0, "abcd")])

x = m.Item(0, "할 일")
m.toggle_done(x)
check("완료 토글", x.text == "[x] 할 일" and m.is_done(x))
m.toggle_done(x)
m.toggle_done(x)
check("완료 → 미완료 → 완료", x.text == "[x] 할 일")

print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
