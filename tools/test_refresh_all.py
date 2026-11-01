"""전체 새로 고침(F5·⟳): 앱 밖에서(탐색기 등) 노트북 폴더나 노트를 지우거나 만들었을 때 껐다 켜지 않고 반영되는지 시험.
임시 APPDATA·임시 노트 폴더만 쓴다.  py -3 -X utf8 tools/test_refresh_all.py"""
import json
import os
import shutil
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="rfa-")
vault = os.path.join(tmp, "v")
for nb in ("업무", "개인"):
    os.makedirs(os.path.join(vault, nb))
    with open(os.path.join(vault, nb, "글.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("본문\n")
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.environ["IAT_NO_SINGLE"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import notes  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


a = notes.App()


def pump(n=40):
    for _ in range(n):
        a.root.update()
        time.sleep(0.02)


pump(60)
a.reload_notes()
pump(20)
check("처음엔 노트북 둘이 보인다", {"업무", "개인"} <= set(a.nb_keys) and len(a.all_notes) == 2)

# 탐색기에서 노트북 하나를 지우고, 새 노트를 하나 만든 것처럼
shutil.rmtree(os.path.join(vault, "개인"))
with open(os.path.join(vault, "업무", "새글.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("밖에서 만든 글\n")
check("새로 고치기 전에는 앱이 아직 모른다", "개인" in a.nb_keys)

a.root.event_generate("<F5>")
end = time.time() + 5   # 컴퓨터가 바쁠 때도 되도록 조건이 될 때까지 최대 5초 기다린다
while time.time() < end and not ("개인" not in a.nb_keys and any(n["title"] == "새글" for n in a.all_notes)):
    pump(5)
check("F5 로 지운 노트북이 사라지고 새 노트가 보인다", "개인" not in a.nb_keys and any(n["title"] == "새글" for n in a.all_notes))
check("상태 줄에 알린다", "새로" in a.status.cget("text"))

# 메뉴·단추
menu_labels = []
bar = a.root.nametowidget(a.root.cget("menu"))
for i in range(bar.index("end") + 1):
    sub = bar.nametowidget(bar.entrycget(i, "menu")) if bar.type(i) == "cascade" else None
    if sub is not None:
        menu_labels += [sub.entrycget(j, "label") for j in range(sub.index("end") + 1) if sub.type(j) == "command"]
check("보기 메뉴에 '새로 고침' 이 있다", "새로 고침" in menu_labels)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


check("노트 목록 위에 ⟳ 단추가 있다", any(w.__class__.__name__ == "Btn" and w.label.cget("text") == "⟳" for w in walk(a.root)))
a.root.destroy()
sys.exit(1 if fails else 0)
