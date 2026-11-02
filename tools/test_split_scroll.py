"""좌우 분할에서 입력 중 미리보기 스크롤 유지 시험: py -3 -I -X utf8 tools/test_split_scroll.py"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="split-scroll-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
vault = os.path.join(tmp, "vault")
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
os.makedirs(vault)
json.dump({"root": vault}, open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w"))

import notes  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


body = " ".join(f"word{i}" for i in range(5000))
path = os.path.join(vault, "scroll.md")
with open(path, "w", encoding="utf-8") as f:
    f.write(body)

app = notes.App()
for _ in range(60):
    app.root.update()
    time.sleep(0.03)
    if app.all_notes:
        break
app.open_note(next(n for n in app.all_notes if n["path"] == path))
app.set_mode("split")
for _ in range(10):
    app.root.update()

view = app.view
view.yview("1.0+2500c")
app.root.update_idletasks()
source_pos = app.w2s(app.wcount(view, view.index("@0,0")))
app._pair_side = "edit"
app.text.mark_set("insert", f"1.0+{source_pos + 100}c")
before_pair = view.index("@0,0")
app.pair_run()
after_pair = view.index("@0,0")
check("강조는 유지하고 화면 안에 걸친 블록은 스크롤하지 않음",
      before_pair == after_pair and bool(view.tag_ranges("pair")))

view.yview("1.0+2500c")
app.root.update_idletasks()
before_index = view.index("@0,0")
before_render = view.get(before_index, f"{before_index}+100c")
app.text.insert("end-1c", " added" * 10000)
app.text.edit_modified(False)
app.render()
for _ in range(5):
    app.root.update()
after_index = view.index("@0,0")
after_render = view.get(after_index, f"{after_index}+100c")
check("본문 길이가 늘어도 미리보기의 문서 위치를 유지함",
      before_render == after_render)

app.root.destroy()
sys.exit(1 if fails else 0)
