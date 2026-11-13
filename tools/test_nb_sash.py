"""노트북·태그 경계: 끌어 놓은 높이가 음악·PDF 를 고를 때(show_doc → relayout) 밀리지 않고, 태그를 껐다 켜도 돌아오는지 시험.
앱 창은 띄우지 않고, 진짜 App.relayout·place_nb_sash 를 작은 Tk 창(스스로 닫힘)에 붙여 돌린다.  py -3 -X utf8 tools/test_nb_sash.py"""
import os
import sys
import types
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import notes  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    print(("OK  " if ok else "FAIL") + "  " + name + ("" if ok else "   " + detail))
    fails += not ok


def settle(r, n=10):
    for _ in range(n):
        r.after(30)
        r.update()


r = tk.Tk()
r.geometry("800x600+60+60")
a = types.SimpleNamespace(root=r, nb_h=0, widths={"left": 200, "list": 240, "syntax": 220},
                          show={"notebooks": True, "tags": True, "list": True, "syntax": False})
a.pane = tk.PanedWindow(r, orient="horizontal")
a.pane.pack(fill="both", expand=True)
a.leftf, a.listf, a.editf, a.sidebar = (tk.Frame(a.pane) for _ in range(4))
a.left_pane = tk.PanedWindow(a.leftf, orient="vertical", sashwidth=4)
a.left_pane.pack(fill="both", expand=True)
a.nb_sec = tk.Frame(a.left_pane, height=124)   # 실제 앱처럼 노트북 칸이 원하는 높이(124)가 있음
a.tag_sec = tk.Frame(a.left_pane, height=200)
for f in (a.nb_sec, a.tag_sec):
    for i in range(4):
        tk.Label(f, text=f"줄 {i}").pack()
a.place_nb_sash = lambda tries=0: notes.App.place_nb_sash(a, tries)
a.capture_nb_height = lambda: notes.App.capture_nb_height(a)
relayout = lambda: notes.App.relayout(a)  # noqa: E731

relayout()
settle(r)
for drag in (90, 380):
    a.left_pane.sash_place(0, 0, drag)   # 사용자가 경계를 끌어 놓음
    settle(r, 3)
    a.capture_nb_height()
    start = a.nb_sec.winfo_height()
    hs = []
    for _ in range(5):   # 음악 파일을 하나씩 고름: show_doc 이 relayout 뒤 update_idletasks
        relayout()
        r.update_idletasks()
        settle(r, 3)
        hs.append(a.nb_sec.winfo_height())
    check(f"경계 {drag}: 파일을 다섯 번 골라도 그대로", all(h == start for h in hs), f"처음 {start}, 그 뒤 {hs}")
    check(f"경계 {drag}: 기억한 높이 그대로", a.nb_h == start, f"nb_h={a.nb_h}")

    a.show["tags"] = False   # 보기 → 태그 끔 → 켬
    relayout()
    settle(r)
    a.show["tags"] = True
    relayout()
    settle(r)
    check(f"경계 {drag}: 태그를 껐다 켜도 돌아옴", abs(a.nb_sec.winfo_height() - start) <= 4, f"처음 {start}, 지금 {a.nb_sec.winfo_height()}")

r.destroy()
print("FAILS:", fails)
sys.exit(1 if fails else 0)
