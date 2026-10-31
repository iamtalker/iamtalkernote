"""달력·할일 화면(app/planner/view.py)의 할일·날짜 생성·변경·삭제와 오른쪽 클릭 메뉴 시험: py -3 -I -X utf8 tools/test_planner_view.py"""
import datetime
import os
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox, simpledialog

os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from planner import model as M
from planner.view import PlannerView

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


root = tk.Tk()
root.geometry("800x800")
C = {"bg": "#fff", "text": "#222", "muted": "#888", "accent": "#26b", "sel": "#cde", "panel": "#f5f5f5", "line": "#ddd", "soft": "#eef", "danger": "#c33"}
d = tempfile.mkdtemp()
pl = M.Planner(d)
pv = PlannerView(root, C, "Malgun Gothic", pl, lambda: {"gongsu": False, "wage": 0, "meal": 0, "hide_done": False})
pv.pack(fill="both", expand=True)
root.update()
answer = {"v": ""}
simpledialog.askstring = lambda *a, **k: answer["v"]
messagebox.askyesno = lambda *a, **k: True
messagebox.showinfo = lambda *a, **k: None

# ---- 할일: 생성·변경·삭제
answer["v"] = "병원"
pv.new_todo()
t = pl.todos[0]
check("할일 생성(목록, 날짜 없음)", t["text"] == "병원" and t["date"] is None)
pv.sel = "2026-11-20"
answer["v"] = "회의"
pv.add_dated()
check("할일 생성(달력의 날, 날짜 있음)", any(x["text"] == "회의" and x["date"] == "2026-11-20" for x in pl.todos))
answer["v"] = "치과"
pv.rename_todo(t)
check("할일 변경(내용)", t["text"] == "치과")

# ---- 추가한 날: 만들기·변경·삭제
answer["v"] = "2026-11-05"
pv.bulk([t], "date")
check("추가한 날 만들기", t["date"] == "2026-11-05")
answer["v"] = "20261107"
pv.bulk([t], "date")
check("추가한 날 변경", t["date"] == "2026-11-07")
pv.bulk([t], "nodate")
check("추가한 날 삭제", t["date"] is None)
answer["v"] = "20261107"
pv.bulk([t], "date")

# ---- 완료한 날: 만들기(그 날짜로 완료)·변경·삭제(완료 취소)
answer["v"] = "20261109"
pv.bulk([t], "done_on")
check("완료한 날 만들기(그 날짜로 완료)", t["done"] and t["done_on"] == "2026-11-09")
answer["v"] = "20261110"
pv.bulk([t], "done_on")
check("완료한 날 변경", t["done_on"] == "2026-11-10")
answer["v"] = "20261101"
pv.bulk([t], "done_on")
check("완료한 날이 추가한 날보다 빠르면 거절", t["done_on"] == "2026-11-10")
pv.bulk([t], "undone")
check("완료한 날 삭제(완료 취소)", not t["done"] and "done_on" not in t)

# ---- 여러 개 고르기
for n in "xyz":
    pl.add(n, "2026-10-0" + str("xyz".index(n) + 1))
pv.changed()
ids = [i for i in pv.tree.get_children() if pv.tree.set(i, "text")[3:] in ("x", "y", "z")]
pv.tree.selection_set(ids)
picked = [pl.find(i) for i in pv.tree.selection()]
check("Ctrl·Shift 다중 선택(extended)", len(picked) == 3 and str(pv.tree.cget("selectmode")) == "extended")
pv.bulk(picked, "done")
check("고른 것 모두 오늘 날짜로 완료", all(x["done"] and x["done_on"] == M.iso(datetime.date.today()) for x in picked))
pv.bulk(picked, "delete")
check("고른 것 모두 삭제", all(x["text"] not in "xyz" for x in pl.todos))

# ---- 오른쪽 클릭 메뉴: 칸마다 이것뿐
labels = []
tk.Menu.tk_popup = lambda self, *a, **k: labels.append([self.entrycget(i, "label") for i in range(self.index("end") + 1) if self.type(i) != "separator"])
root.update()
rows = list(pv.tree.get_children())


def event(row, col):
    bb = pv.tree.bbox(row, col)
    return type("E", (), {"x": bb[0] + 5, "y": bb[1] + 5, "x_root": 0, "y_root": 0})()


def menu(row, col):
    labels.clear()
    pv.on_tree_menu(event(row, col))
    return labels[-1] if labels else None


dated = next(i for i in rows if pl.find(i)["date"] and not pl.find(i)["done"])
undated = next((i for i in rows if not pl.find(i)["date"]), None)
check("할일 칸 메뉴: 할일 생성·변경·삭제", menu(dated, "#3") == ["할일 생성", "할일 변경", "할일 삭제"])
check("추가한 날 칸 메뉴(날짜 있음): 날짜 변경·삭제", menu(dated, "#1") == ["날짜 변경", "날짜 삭제"])
check("완료한 날 칸 메뉴(완료 전): 날짜 만들기", menu(dated, "#2") == ["날짜 만들기"])
pl.add("날짜 없음")
pv.changed()
undated = next(i for i in pv.tree.get_children() if not pl.find(i)["date"])
check("추가한 날 칸 메뉴(날짜 없음): 날짜 만들기", menu(undated, "#1") == ["날짜 만들기"])
pl.update(dated, done=True)
pv.changed()
check("완료한 날 칸 메뉴(완료 후): 날짜 변경·삭제", menu(dated, "#2") == ["날짜 변경", "날짜 삭제"])
labels.clear()
pv.on_tree_menu(type("E", (), {"x": 5, "y": 780, "x_root": 0, "y_root": 0})())
check("빈 곳 메뉴: 할일 생성", labels and labels[-1] == ["할일 생성"])
check("파일에도 반영", len(M.Planner(d).todos) == len(pl.todos))

root.destroy()
print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
