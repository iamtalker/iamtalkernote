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


counts = {"여행": 10, "여름": 3, "영화": 7, "회의": 5, "Python": 4, "python3": 1, "신규": 2, "리얼리티 트랜서핑": 1}
check("낱말 찾기: 공백·쉼표 뒤", tagac.current_token("#a #b #여") == (6, "#여") and tagac.current_token("#a, #b") == (4, "#b") and tagac.current_token("#a ") == (3, ""))
check("앞부분이 같은 것 먼저, 많이 쓴 순", tagac.suggest(counts, "#여") == ["여행", "여름"])
check("입력한 글자로 시작하는 태그만 추천",
      tagac.suggest(counts, "티") == [] and tagac.suggest(counts, "리얼") == ["리얼리티 트랜서핑"]
      and tagac.suggest(counts, "py")[:2] == ["Python", "python3"])
check("대소문자 무시", tagac.suggest(counts, "PYTHON") == ["python3"] or tagac.suggest(counts, "PYTHON") == ["python3", ] or "Python" not in tagac.suggest(counts, "PYTHON"))
check("이미 쓴 태그와 똑같은 글은 후보에서 뺌", "여행" not in tagac.suggest(counts, "#여", have=["여행"]))
check("빈 낱말이면 많이 쓴 태그", tagac.suggest(counts, "#", limit=3) == ["여행", "영화", "회의"])
check("개수 제한", len(tagac.suggest({str(i): i for i in range(30)}, "", limit=8)) == 8)
check("넣기", tagac.complete("#a #여", 3, "여행") == "#a #여행 ")
check("입력 글의 태그들", tagac.tags_in("#a, #b  c") == ["a", "b", "c"])
body_words = "사과는 사과를 사과가 사과는 바나나를 바나나는 바나나가 포도는 포도를 포도는 그리고 이것은\n태그: #사과"
check("본문에서 조사 떼고 자주 나온 단어 3개 추천",
      tagac.content_suggestions(body_words) == ["사과", "바나나", "포도"])
check("이미 붙은 태그는 추천에서 빼고 다른 태그는 유지",
      tagac.content_suggestions(body_words, ["사과"]) == ["바나나", "포도"])

# 실제 Tk 입력칸에서
root = tk.Tk()
C = dict(bg="#fff", panel="#f5f5f5", line="#ddd", text="#111", soft="#e0e0e0", muted="#888", accent="#0a7")
ent = tk.Entry(root, width=36); ent.pack(); root.update()
ac = tagac.TagComplete(ent, lambda: counts, C, ("Malgun Gothic", 9))
ent.insert(0, "#여"); ent.focus_force(); root.update()
ac.refresh(); root.update()
check("후보 목록이 뜸", ac.visible() and ac.items == ["여행", "여름"])
ent.delete(0, "end"); ac.refresh(); root.update()
check("빈 입력칸에는 후보를 띄우지 않음", not ac.visible() and not ac.items)
ent.insert(0, "행"); ac.refresh(); root.update()
check("부분 문자열만 일치하는 태그는 후보에 없음", not ac.visible() and not ac.items)
ent.delete(0, "end"); ent.insert(0, "#여"); ac.refresh(); root.update()
ac._move(1); ac._move(1)
check("↓ 두 번 → 둘째 후보 고름", ac._selected() == "여름")
check("Enter: 고른 것이 있으면 넣고 저장 안 함", ac.on_return() is True and ent.get() == "#여름 ")
check("태그 선택 뒤 후보는 닫히고 새 입력을 기다림", not ac.visible() and not ac.items)
ent.delete(0, "end"); ent.insert(0, "#회"); ac.refresh(); root.update()
check("Enter: 고른 것이 없으면 False(저장)", ac.on_return() is False and ent.get() == "#회")
check("Tab: 첫 후보를 넣음", ac._tab() == "break" and ent.get() == "#회의 ")
ent.delete(0, "end"); ent.insert(0, "#zzzz"); ac.refresh()
check("맞는 게 없으면 목록이 닫힘", not ac.visible())
root.destroy()

# 하단 박스(칩 + 확인/취소)
root = tk.Tk(); root.geometry("700x200")
done = {}
btns = {}
def make_button(parent, text, cmd, **kw):
    b = tk.Button(parent, text=text, command=cmd); btns[text] = b; return b
box = tagac.TagBox(root, ["기존"], lambda: counts, C, ("Malgun Gothic", 9), lambda t: done.update(ok=t), lambda: done.update(cancel=True), make_button)
box.pack(fill="x"); root.update()
check("처음엔 기존 태그가 칩으로", box.tags == ["기존"])
box.ent.focus_force(); box.ent.insert(0, "만화"); box._enter(); root.update()
check("Enter → 칩이 되고 입력칸은 비고 박스는 그대로", box.tags == ["기존", "만화"] and box.ent.get() == "" and not done)
box.ent.insert(0, "작품 "); box._split(); root.update()
check("공백을 치면 그 낱말이 칩", box.tags == ["기존", "만화", "작품"] and box.ent.get() == "")
box.ent.insert(0, "만화"); box._enter()
check("같은 태그는 한 번만", box.tags.count("만화") == 1)
box.ent.insert(0, "a/b"); box._enter()
check("쓸 수 없는 이름(/)은 무시", "a/b" not in box.tags)
box.ent.insert(0, "#여"); box.ac.refresh(); root.update()
check("치는 동안 후보가 뜸", box.ac.visible() and box.ac.items[:2] == ["여행", "여름"])
box.ac._move(1); box._enter(); root.update()
check("후보를 골라 Enter → 칩으로 추가(박스 유지)", "여행" in box.tags and not done and box.ent.get() == "")
box.remove("기존"); root.update()
check("× 로 태그를 뺌", "기존" not in box.tags)
box.ent.insert(0, "x"); box._backspace()
check("글이 있을 때 BackSpace 는 평소대로", box.tags[-1] == "여행")
box.ent.delete(0, "end"); box._backspace(); root.update()
check("빈 칸에서 BackSpace → 마지막 칩 삭제", "여행" not in box.tags)
box.ent.insert(0, "마지막"); btns["확인"].invoke(); root.update()
check("[확인] → 목록 전달(치다 만 낱말 포함)", done.get("ok") == ["만화", "작품", "마지막"])
box3 = tagac.TagBox(root, [], lambda: counts, C, ("Malgun Gothic", 9), lambda t: None, lambda: None, make_button)
box3.pack(fill="x"); root.update()
for tag in ("aaa", "bbb"):
    box3.ent.insert(0, tag); box3._enter(); root.update()
box3.ent.insert(0, "ccc"); root.update()
last_chip = box3._chips["bbb"]
check("이어 입력한 낱말은 앞선 태그 칩과 겹치지 않는다",
      box3.ent.winfo_x() >= last_chip.winfo_x() + last_chip.winfo_width())
check("세 태그는 각각 별도 칩으로 확인된다",
      (box3._enter() == "break") and box3.tags == ["aaa", "bbb", "ccc"])
box2 = tagac.TagBox(root, [], lambda: counts, C, ("Malgun Gothic", 9), lambda t: done.update(ok2=t), lambda: done.update(cancel=True), make_button)
box2.pack(fill="x"); box2.ent.insert(0, "버릴것"); box2._enter(); btns["취소"].invoke()
check("[취소] → on_cancel, 확인 전달 없음", done.get("cancel") is True and "ok2" not in done)
box3 = tagac.TagBox(root, [], lambda: counts, C, ("Malgun Gothic", 9), lambda t: done.update(ok3=t), lambda: None, make_button)
box3.pack(fill="x"); box3.ent.insert(0, "하나"); box3._enter(); root.update()
box3._enter()
check("빈 칸에서 Enter → 확인", done.get("ok3") == ["하나"])
many = tagac.TagBox(root, ["태그%d" % i for i in range(40)], lambda: counts, C, ("Malgun Gothic", 9), lambda t: None, lambda: None, make_button)
many.pack(fill="x"); root.update(); many.reflow(); root.update()
check("태그가 많으면 줄을 바꿔 높이가 늘어남", int(many.flow.cget("height")) > 40)
# 한글 조합 중인 마지막 글자(입력칸 값에 아직 없음)
ime_state = {"extra": "", "cancelled": 0}
def ime_cancel(): ime_state["cancelled"] += 1; ime_state["extra"] = ""
hb = tagac.TagBox(root, [], lambda: counts, C, ("Malgun Gothic", 9), lambda t: done.update(okh=t), lambda: None, make_button, lambda: ime_state["extra"], ime_cancel)
hb.pack(fill="x"); root.update()
hb.ent.insert(0, "만"); ime_state["extra"] = "화"; hb._enter(); root.update()
check("조합 중인 마지막 글자까지 칩이 됨('만'+'화' → 만화)", hb.tags == ["만화"] and hb.ent.get() == "")
check("조합을 버려 입력칸에 되살아나지 않게 함", ime_state["cancelled"] == 1 and ime_state["extra"] == "")
hb.ent.insert(0, "작"); ime_state["extra"] = "품"; hb.confirm()
check("[확인] 도 조합 중인 글자를 포함", done.get("okh") == ["만화", "작품"])
hb.ent.delete(0, "end"); hb.ent.insert(0, "#여"); ime_state["extra"] = ""; hb.ac.refresh(); root.update(); hb.ac._move(1)
ime_state["extra"] = "x"; hb.ac.accept(); 
check("후보 고르기 때도 조합을 버림", ime_state["cancelled"] == 2 and "여행" in hb.tags)
box4 = None
def recommend():
    return tagac.content_suggestions(body_words, box4.tags)
box4 = tagac.TagBox(root, ["사과"], lambda: counts, C, ("Malgun Gothic", 9), lambda t: done.update(ok4=t),
                    lambda: None, make_button, suggest_tags=recommend)
box4.pack(fill="x"); root.update()
btns["본문에서 추천"].invoke(); root.update()
check("본문 추천 버튼은 기존 태그를 두고 새 후보만 칩으로 더함",
      box4.tags == ["사과", "바나나", "포도"] and not done.get("ok4"))
root.destroy()
print("통과" if not fails else "실패 %d" % fails)
sys.exit(1 if fails else 0)
