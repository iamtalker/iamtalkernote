"""아웃라이너 보기 계산(outline.py) 시험: py -3 -I -X utf8 tools/test_outline.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import outline as ol

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


check("목록이 있는지", ol.has_list("글\n\n- 항목\n") and ol.has_list("1. 하나\n") and not ol.has_list("그냥 글\n") and not ol.has_list("```\n- 코드\n```\n"))
src = "# 제목\n\n메모 문단 하나\n\n- A\n  - A1\n  - A2\n    - A2a\n- B\n  메모처럼 이어진 글\n\n끝 메모\n\n1. 번호 하나\n2. 번호 둘\n"
blocks, nodes = ol.parse(src)
kinds = [b[0] for b in blocks]
check("블록 구분: 메모/목록/메모/메모/목록", kinds == ["memo", "memo", "list", "memo", "list"])
check("항목 수와 순서", [n.text for n in nodes] == ["A", "A1", "A2", "A2a", "B", "번호 하나", "번호 둘"])
check("깊이", [n.depth for n in nodes] == [0, 1, 1, 2, 0, 0, 0])
a, b = nodes[0], nodes[4]
check("부모·자식", nodes[1].parent is a and nodes[3].parent is nodes[2] and a.children == [nodes[1], nodes[2]] and b.children == [])
check("항목에 이어진 글은 그 항목의 메모", b.notes == ["메모처럼 이어진 글"])
check("조상 목록(경로)", [n.text for n in ol.ancestors(nodes[3])] == ["A", "A2"] and ol.ancestors(a) == [])
check("계층 순서 걷기(상대 깊이)", [(n.text, d) for n, d in ol.walk(a.children)] == [("A1", 0), ("A2", 0), ("A2a", 1)])
check("번호 목록도 항목", nodes[5].mark == "1." and nodes[6].mark == "2.")

b2, n2 = ol.parse("- [ ] 할 일\n- [x] 한 일\n- 보통\n")
check("체크박스 항목", [n.done for n in n2] == [False, True, None] and [n.text for n in n2] == ["할 일", "한 일", "보통"])
b3, n3 = ol.parse("메모 제목\n- 항목 하나\n- 항목 둘\n")
check("목록 앞에 붙은 글은 메모 블록으로 따로", [b[0] for b in b3] == ["memo", "list"] and b3[0][1] == "메모 제목" and len(n3) == 2)
b4, n4 = ol.parse("```\n- 코드 속 목록\n\n- 둘째\n```\n\n- 진짜 목록\n")
check("코드 블록 속 목록은 항목이 아님", [n.text for n in n4] == ["진짜 목록"])
b5, n5 = ol.parse("- 탭\n\t- 탭 들여쓰기\n- 다음\n")
check("탭 들여쓰기", [n.depth for n in n5] == [0, 1, 0])
b6, n6 = ol.parse("- a\n    - b\n  - c\n")
check("들여쓰기 폭이 들쭉날쭉해도 계층 유지", [(n.text, n.depth) for n in n6] == [("a", 0), ("b", 1), ("c", 1)])
b7, n7 = ol.parse("")
check("빈 글", n7 == [] and all(b[0] == "memo" for b in b7))
# 원문 위치(클릭해서 편집할 때 그 구간만 바꾼다)
src2 = "# 제목\n\n메모 문단\n\n- A\n  - [ ] 할 일\n  - A2 **굵게**\n- B\n"
b8, n8 = ol.parse(src2)
check("항목 글의 원문 구간", [src2[n.tstart:n.tend] for n in n8] == ["A", "할 일", "A2 **굵게**", "B"])
check("메모 블록의 원문 구간", [src2[b[2]:b[3]] for b in b8 if b[0] == "memo"] == ["# 제목", "메모 문단"])
check("목록 블록의 원문 구간", src2[b8[-1][2]:b8[-1][3]].startswith("- A") and src2[b8[-1][2]:b8[-1][3]].rstrip().endswith("- B"))
new = src2[:n8[2].tstart] + "바꾼 글" + src2[n8[2].tend:]
check("구간만 바꾸면 마커·들여쓰기·체크박스 유지", "  - 바꾼 글\n" in new and "- B" in new and "- [ ] 할 일" in new)
b9, n9 = ol.parse("메모 제목\n- 항목 하나\n- 항목 둘\n")
check("메모가 붙은 목록: 위치가 어긋나지 않음", ["메모 제목\n- 항목 하나\n- 항목 둘\n"[n.tstart:n.tend] for n in n9] == ["항목 하나", "항목 둘"])
b10, n10 = ol.parse("```\n코드\n\n```\n\n- 뒤 항목\n")
check("코드 블록(빈 줄 포함) 뒤 항목 위치", ["```\n코드\n\n```\n\n- 뒤 항목\n"[n.tstart:n.tend] for n in n10] == ["뒤 항목"])
print("통과" if not fails else "실패 %d" % fails)
sys.exit(1 if fails else 0)
