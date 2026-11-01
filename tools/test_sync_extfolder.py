"""외부 폴더를 가져오기와 상관없이 폴더 선택 창으로 아무거나 지정하는 흐름 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_sync_extfolder.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="ext-")
vault = os.path.join(tmp, "v")
other = os.path.join(tmp, "음악 폴더")
os.makedirs(vault)
os.makedirs(other)
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.environ["IAT_NO_SINGLE"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import notes  # noqa: E402
import syncengine  # noqa: E402
import syncpolicy as sp  # noqa: E402
import syncui  # noqa: E402
syncengine.installed = lambda: True

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


# 정책: 가져오기 등록 없이 경로를 정책이 갖는다
pol = sp.new_policy()
mid = sp.add_external(pol, "x1", "음악", sp.BOTH, local=other)
plan = {p["module"]: p for p in sp.plan(pol, vault, "pc", {})}   # 가져오기에 등록된 폴더가 하나도 없다
check("가져오기에 없어도 정책에 적힌 경로로 폴더 계획이 나온다", mid in plan and plan[mid]["path"] == os.path.abspath(other))
old = sp.new_policy()
mid2 = sp.add_external(old, "y1", "예전", sp.BOTH)
check("경로가 없는 예전 외부 폴더는 가져오기 등록 폴더에서 가져온다", sp.plan(old, vault, "pc", {"y1": other}) and
      [p for p in sp.plan(old, vault, "pc", {"y1": other}) if p["module"] == mid2][0]["path"] == os.path.abspath(other))
check("경로를 어디서도 못 찾으면 만들지 않는다", not [p for p in sp.plan(old, vault, "pc", {}) if p["module"] == mid2])

sp.save(vault, sp.new_policy())
a = notes.App()
asked = []
shown = []
syncui.messagebox.showinfo = lambda *x, **k: shown.append(x)


def run(sec):
    a.root.after(int(sec * 1000), a.root.quit)
    a.root.mainloop()


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def btn(top, text):
    return [w for w in walk(top) if w.__class__.__name__ == "Btn" and w.label.cget("text") == text]


# 레거시 가져오기 등록 폴더가 하나 있어도 없어도 같다: 가져오기와 무관하게 고른다
a.docs.folders = lambda: []
run(1.5)
a.show_options("sync")
run(1)
top = [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"][-1]
check("외부 폴더가 없으면 '외부 폴더 지정…' 버튼이 있다", len(btn(top, "외부 폴더 지정…")) == 1)

syncui.filedialog.askdirectory = lambda **k: vault   # 노트 폴더 자체
btn(top, "외부 폴더 지정…")[0].command()
run(0.5)
check("노트 폴더와 겹치면 거절하고 안내한다", len(shown) == 1 and len(btn(top, "외부 폴더 지정…")) == 1)

syncui.filedialog.askdirectory = lambda **k: other
btn(top, "외부 폴더 지정…")[0].command()
run(0.5)
labels = [w.get("1.0", "end").strip() if w.winfo_class() == "Text" else w.cget("text") for w in walk(top) if w.winfo_class() in ("Label", "Text")]
check("고른 폴더가 외부 폴더 줄로 생긴다", any("외부 폴더 · 음악 폴더" in t for t in labels))
check("외부 폴더는 하나만: 지정 버튼이 사라진다", len(btn(top, "외부 폴더 지정…")) == 0)
a.root.destroy()
sys.exit(1 if fails else 0)
