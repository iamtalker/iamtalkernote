"""중복 이미지 합치기와 창(미리보기) 시험: py -3 -I -X utf8 tools/test_dup_media_merge.py"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="dupmedia-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
vault = os.path.join(tmp, "vault")
os.makedirs(vault)

import store as st  # noqa: E402
import cleanup  # noqa: E402

import io  # noqa: E402
from PIL import Image  # noqa: E402
_buf = io.BytesIO()
Image.new("RGB", (8, 6), (200, 30, 30)).save(_buf, "PNG")
PNG = _buf.getvalue()
fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


s = st.Store(root=vault)
media = s.ensure_media()
for name in ("a.png", "b.png", "xb.png"):   # a·b 는 같은 내용, xb 는 이름만 b 로 끝나는 다른 내용
    with open(os.path.join(media, name), "wb") as f:
        f.write(PNG if name != "xb.png" else PNG + b"\x00")
os.makedirs(os.path.join(vault, "sub"))
texts = {
    "n1": "# n1\n\n![](.resources/a.png)\n",
    "n2": "# n2\n\n![](.resources/b.png) 와 ![](.resources/xb.png) 와 [링크](.resources/b.png)\n",
    "sub/n3": "# n3\n\n![](../.resources/b.png)\n",
}
notes = []
for key, t in texts.items():
    p = os.path.join(vault, *key.split("/")) + ".md"
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    notes.append({"nb": os.path.dirname(key), "title": os.path.basename(key), "path": p})

groups = cleanup.duplicate_media(s)
check("one group of identical files", len(groups) == 1 and sorted(os.path.basename(p) for p in groups[0]) == ["a.png", "b.png"])
refs = {os.path.basename(p): [] for g in groups for p in g}
import re  # noqa: E402
for n in notes:
    for name in set(re.findall(r"\.resources/([^)\s\"'<>]+)", open(n["path"], encoding="utf-8").read())) & set(refs):
        refs[name].append(n)
check("keeps the most used file", cleanup.keep_name(["a.png", "b.png"], refs) == "b.png")

changed, links, merged, failed = cleanup.merge_duplicate_media(s, groups, refs)
check("one note fixed, one link", changed == 1 and links == 1 and merged == 1 and not failed)
after = {n["title"]: open(n["path"], encoding="utf-8").read() for n in notes}
check("n1 now points at b.png", ".resources/b.png" in after["n1"] and "a.png" not in after["n1"])
check("n2 untouched (xb.png kept)", "xb.png" in after["n2"] and after["n2"].count("b.png") == 3)
check("a.png file not deleted", os.path.isfile(os.path.join(media, "a.png")))
check("second run changes nothing", cleanup.merge_duplicate_media(s, groups, refs)[:2] == (0, 0))

# 창: 미리보기가 그림을 보여 주는지
try:
    import tkinter as tk
    from tkinter import ttk  # noqa: F401
    import embedded
    import toolsmenu

    root = tk.Tk()
    root.geometry("900x600+50+50")

    class Fake(embedded.EmbeddedMixin):
        ui = "Malgun Gothic"
        tool_window = toolsmenu.ToolsMenuMixin.tool_window if hasattr(toolsmenu, "ToolsMenuMixin") else None

        def __init__(self):
            self.root, self.store = root, s

        def goto_note(self, p):
            pass

    fake = Fake()
    if fake.tool_window is None:
        raise RuntimeError("no tool_window mixin")
    fake.duplicate_media_dialog((groups, refs))
    root.update()
    tops = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    check("dialog opened", len(tops) == 1)
    labels = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                labels.append(c)
            walk(c)
    walk(tops[0])
    root.update()
    check("preview shows an image for the first group", any(str(l.cget("image")) for l in labels))
    root.destroy()
except Exception as e:  # noqa: BLE001
    check("dialog smoke: %r" % e, False)

print("FAILS:", fails)
sys.exit(1 if fails else 0)
