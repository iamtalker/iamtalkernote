"""태그 자동완성(tagac.py) 시험: py -3 -I -X utf8 tools/test_tagac.py"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import tagac

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


counts = {"여행": 10, "여름": 3, "영화": 7, "회의": 5, "Python": 4, "python3": 1, "신규": 2}
check("낱말 찾기: 공백·쉼표 뒤", tagac.current_token("#a #b #여") == (6, "#여") and tagac.current_token("#a, #b") == (4, "#b") and tagac.current_token("#a ") == (3, ""))
check("앞부분이 같은 것 먼저, 많이 쓴 순", tagac.suggest(counts, "#여") == ["여행", "여름"])
check("글자가 들어 있는 것도(앞부분 일치 뒤에)", tagac.suggest(counts, "행") == ["여행"] and tagac.suggest(counts, "py")[:2] == ["Python", "python3"])
check("대소문자 무시", tagac.suggest(counts, "PYTHON") == ["python3"] or tagac.suggest(counts, "PYTHON") == ["python3", ] or "Python" not in tagac.suggest(counts, "PYTHON"))
check("이미 쓴 태그와 똑같은 글은 후보에서 뺌", "여행" not in tagac.suggest(counts, "#여", have=["여행"]))
check("빈 낱말이면 많이 쓴 태그", tagac.suggest(counts, "#", limit=3) == ["여행", "영화", "회의"])
check("개수 제한", len(tagac.suggest({str(i): i for i in range(30)}, "", limit=8)) == 8)
check("넣기", tagac.complete("#a #여", 3, "여행") == "#a #여행 ")
check("입력 글의 태그들", tagac.tags_in("#a, #b  c") == ["a", "b", "c"])

# 실제 Tk 입력칸에서
root = tk.Tk()
C = dict(bg="#fff", panel="#f5f5f5", line="#ddd", text="#111", soft="#e0e0e0")
ent = tk.Entry(root, width=36); ent.pack(); root.update()
ac = tagac.TagComplete(ent, lambda: counts, C, ("Malgun Gothic", 9))
ent.insert(0, "#여"); ent.focus_force(); root.update()
ac.refresh(); root.update()
check("후보 목록이 뜸", ac.visible() and ac.items == ["여행", "여름"])
ac._move(1); ac._move(1)
check("↓ 두 번 → 둘째 후보 고름", ac._selected() == "여름")
check("Enter: 고른 것이 있으면 넣고 저장 안 함", ac.on_return() is True and ent.get() == "#여름 ")
check("넣은 뒤 이어서 후보가 다시 계산됨(많이 쓴 태그)", ac.visible() and "여행" in ac.items)
ent.delete(0, "end"); ent.insert(0, "#회"); ac.refresh(); root.update()
check("Enter: 고른 것이 없으면 False(저장)", ac.on_return() is False and ent.get() == "#회")
check("Tab: 첫 후보를 넣음", ac._tab() == "break" and ent.get() == "#회의 ")
ent.delete(0, "end"); ent.insert(0, "#zzzz"); ac.refresh()
check("맞는 게 없으면 목록이 닫힘", not ac.visible())
root.destroy()
print("통과" if not fails else "실패 %d" % fails)
sys.exit(1 if fails else 0)
