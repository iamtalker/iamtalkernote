"""랜덤 단추 시험: 노트가 목록 아래쪽(첫 덩어리 밖)에 있어도 목록에서 선택되고 보이는지. py -3 -I -X utf8 tools/test_random_note.py"""
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="random-note-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
vault = os.path.join(tmp, "vault")
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
os.makedirs(vault)
json.dump({"root": vault}, open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w"))
for i in range(350):
    with open(os.path.join(vault, f"노트{i:03d}.md"), "w", encoding="utf-8") as f:
        f.write(f"# 노트{i:03d}\n\n본문 {i}\n")

import notes  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


app = notes.App()
app.root.update()
app.reload_notes()
app.root.update()
random.seed(7)
for trial in range(3):
    app.open_random_note()
    app.root.update()
    cur = app.cur["path"]
    in_results = any(m["path"] == cur for m in app.results)
    drawn = any(m["path"] == cur for _a, _b, m in app.cards)
    idx = next(i for i, m in enumerate(app.results) if m["path"] == cur)
    check(f"trial {trial}: note is in the drawn cards (index {idx})", in_results and drawn)
    sel = [a for a, b, m in app.cards if m["path"] == cur]
    tagged = bool(sel) and "selcard" in app.lst.tag_names(f"{sel[0]}.0")
    check(f"trial {trial}: note is highlighted in the list", tagged)
    view = app.lst.bbox(f"{sel[0]}.0") if sel else None
    check(f"trial {trial}: note is scrolled into view", view is not None)
# ← → 단추: 목록 순서대로 앞·뒤 노트를 열고 목록에서 선택한다
app.open_random_note()
app.root.update()
i0 = next(i for i, m in enumerate(app.results) if m["path"] == app.cur["path"])
app.step_note(1)
app.root.update()
check("next: opens the following note in list order", app.cur["path"] == app.results[min(i0 + 1, len(app.results) - 1)]["path"])
i1 = next(i for i, m in enumerate(app.results) if m["path"] == app.cur["path"])
a1 = next(a for a, _b, m in app.cards if m["path"] == app.cur["path"])
check("next: highlighted in the list", "selcard" in app.lst.tag_names(f"{a1}.0"))
app.step_note(-1)
app.root.update()
check("prev: back to the previous note", app.cur["path"] == app.results[i1 - 1]["path"])
check("← → buttons exist", hasattr(app, "prev_btn") and hasattr(app, "next_btn"))
app.root.destroy()
print("FAILS:", fails)
sys.exit(1 if fails else 0)
