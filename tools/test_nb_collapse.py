"""노트북 목록: 가져온 폴더의 하위 폴더는 기본으로 접혀 있고, 사용자가 펼친 것은 목록을 다시 그려도 그대로이며, 모두 펼침·모두 접음 단추가 듣는지 시험.
임시 APPDATA·임시 노트 폴더·임시 가져오기 폴더만 쓴다.  py -3 -X utf8 tools/test_nb_collapse.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="nbcol-")
vault = os.path.join(tmp, "v")
src = os.path.join(tmp, "소설")
os.makedirs(os.path.join(vault, "업무", "회의"))
os.makedirs(os.path.join(src, "A 소설"))
os.makedirs(os.path.join(src, "B 소설", "외전"))
for rel in (os.path.join("A 소설", "a1.txt"), os.path.join("B 소설", "외전", "x.txt")):
    with open(os.path.join(src, rel), "w", encoding="utf-8") as fh:
        fh.write("글")
with open(os.path.join(vault, "업무", "회의", "n.md"), "w", encoding="utf-8") as fh:
    fh.write("본문\n")
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


def pump(n=30):
    for _ in range(n):
        a.root.update()
        time.sleep(0.02)


pump(60)
a.docs.add_folder(src)
a.docs.scan()
fid = a.docs.folders()[0]["id"]
a.reload_notes()
pump(20)
root_key, a_key, b_key, g_key = "@doc:" + fid, "@doc:" + fid + "/A 소설", "@doc:" + fid + "/B 소설", "@doc:" + fid + "/B 소설/외전"


def is_open(key):
    return bool(a.nbtree.item(f"nb{a.nb_keys.index(key)}", "open"))


check("'가져온 폴더' 머리글은 펼쳐져 폴더 이름이 보인다", is_open("@docs"))
check("가져온 폴더(맨 위)는 기본으로 접혀 있다", not is_open(root_key))
check("가져온 폴더의 하위 폴더도 기본으로 접혀 있다", not is_open(b_key))
check("내 노트북은 그대로 펼쳐져 있다", is_open("업무"))

# 사용자가 하나 펼치면(삼각형) 목록을 다시 그려도 그대로
iid = f"nb{a.nb_keys.index(root_key)}"
a.nbtree.focus(iid)
a.nbtree.item(iid, open=True)
a.nbtree.event_generate("<<TreeviewOpen>>")
pump(5)
a.reload_notebooks()
pump(5)
check("사용자가 펼친 폴더는 목록을 다시 그려도 펼쳐진 채다", is_open(root_key) and not is_open(b_key))

# 모두 펼침 / 모두 접음
a.nb_set_all(True)
pump(5)
check("모두 펼침: 하위가 있는 항목이 전부 펼쳐진다", all(is_open(k) for k in (root_key, b_key, "업무")))
a.reload_notebooks()
pump(5)
check("모두 펼침 뒤 목록을 다시 그려도 펼쳐진 채다", all(is_open(k) for k in (root_key, b_key, "업무")))
a.nb_set_all(False)
pump(5)
check("모두 접음: 하위가 있는 항목이 전부 접힌다", not any(is_open(k) for k in (root_key, b_key, "업무", "@docs")))
a.reload_notebooks()
pump(5)
check("모두 접음 뒤 목록을 다시 그려도 접힌 채다", not any(is_open(k) for k in (root_key, b_key, "업무")))

# 접힌 폴더 안의 항목이 선택돼 있으면 그 위쪽은 펼쳐 보인다
a.go_nb(g_key)
pump(20)
check("접힌 폴더 안의 하위 폴더를 고르면 그 위쪽이 펼쳐져 보인다", is_open(root_key) and is_open(b_key) and a.nbtree.selection() == (f"nb{a.nb_keys.index(g_key)}",))

# 단추가 실제로 있고 눌린다
def find_buttons(w):
    for c in w.winfo_children():
        if getattr(c, "label", None) is not None and c.label.cget("text") in ("📁", "📂"):
            yield c
        yield from find_buttons(c)


btns = {b.label.cget("text"): b for b in find_buttons(a.root)}
check("노트북 머리글에 📂(모두 펼침)·📁(모두 접음) 단추가 있다", set(btns) == {"📁", "📂"})
btns["📂"].command()
pump(5)
check("📂 단추가 모두 펼친다", is_open(root_key) and is_open("업무"))
btns["📁"].command()
pump(5)
check("📁 단추가 모두 접는다", not is_open(root_key) and not is_open("업무"))
a.root.destroy()
sys.exit(1 if fails else 0)
