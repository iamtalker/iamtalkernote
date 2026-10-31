"""아웃라이너 항목 편집(outline.py 의 split/indent/outdent/delete) 시험: py -3 -I -X utf8 tools/test_outline_edit.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import outline as ol

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def node(src, text):
    return next(n for n in ol.parse(src)[1] if n.text == text)


S = "- a\n- b\n  - b1\n  - b2\n- c"
n = node(S, "a")
new, pos = ol.split_item(S, n, "새")
check("Enter: 아래 형제 추가", new == "- a\n- 새\n- b\n  - b1\n  - b2\n- c" and new[pos:pos + 1] == "새")
n = node(S, "b")
new, pos = ol.split_item(S, n, "")
check("Enter: 하위가 있으면 첫 자식", new == "- a\n- b\n  - \n  - b1\n  - b2\n- c")
new, pos = ol.split_item("1. x\n2. y", node("1. x\n2. y", "x"), "z")
check("번호 목록은 번호를 올림", new.startswith("1. x\n2. z\n2. y") and new[pos] == "z")
new, pos = ol.split_item("- [x] 끝\n- 다음", node("- [x] 끝\n- 다음", "끝"), "")
check("체크박스는 비운 채", new.startswith("- [x] 끝\n- [ ] \n"))

new, pos = ol.indent_item(S, node(S, "b"))
check("Tab: 앞 형제 a 의 하위로(자기 하위도 함께)", new == "- a\n    - b\n      - b1\n      - b2\n- c" and new[pos:pos + 1] == "b")
check("Tab: 첫 항목은 못 넣음", ol.indent_item(S, node(S, "a")) is None)
check("Tab: 하위의 첫 항목도 못 넣음", ol.indent_item(S, node(S, "b1")) is None)
new, pos = ol.indent_item(S, node(S, "b2"))
check("Tab: b1 의 하위로", new == "- a\n- b\n  - b1\n      - b2\n- c".replace("      - b2", "      - b2") or "b1\n      - b2" in new)

new, pos = ol.outdent_item(S, node(S, "b1"))
check("Shift+Tab: 부모 다음으로(b2 는 b 아래에 남음)", new == "- a\n- b\n  - b2\n- b1\n- c" and new[pos:pos + 2] == "b1")
new, pos = ol.outdent_item("- a\n  - b\n    - c\n- d", node("- a\n  - b\n    - c\n- d", "b"))
check("Shift+Tab: 하위 항목도 함께", new == "- a\n- b\n  - c\n- d")
check("Shift+Tab: 최상위는 None", ol.outdent_item(S, node(S, "a")) is None)

new, pos = ol.delete_item("- a\n- \n- c", node("- a\n- \n- c", ""))
check("빈 항목 지우기: 앞 줄 끝으로", new == "- a\n- c" and pos == 3)
check("하위가 있으면 못 지움", ol.delete_item(S, node(S, "b")) is None)

print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
