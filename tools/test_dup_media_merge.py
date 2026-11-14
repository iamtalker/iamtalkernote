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

# 합치고 남은 파일은 휴지통으로: 아직 글자로 쓰이는 파일은 남긴다
buf2 = io.BytesIO()
Image.new("RGB", (5, 5), (10, 200, 10)).save(buf2, "PNG")
for name in ("c.png", "d.png", "e.png"):
    with open(os.path.join(media, name), "wb") as f:
        f.write(buf2.getvalue())
more = {"n4": "![](.resources/c.png)\n![](.resources/c.png)\n", "n5": "![](.resources/d.png)\n", "n6": "![](.resources/e.png)\n", "n7": "참고: d.png 파일 이름만 글로 적음\n"}
for key, t in more.items():
    p = os.path.join(vault, key + ".md")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    notes.append({"nb": "", "title": key, "path": p})
groups2 = [g for g in cleanup.duplicate_media(s) if any(os.path.basename(q) == "c.png" for q in g)]
refs2 = {os.path.basename(q): [] for g in groups2 for q in g}
for n in notes:
    for name in set(re.findall(r"\.resources/([^)\s\"'<>]+)", open(n["path"], encoding="utf-8").read())) & set(refs2):
        refs2[name].append(n)
res = cleanup.merge_and_remove(s, groups2, refs2, notes)
ch, ln, mg, fl, trashed, left = res
check("kept c.png (most used), fixed n5 and n6", ch == 2 and ln == 2 and mg == 1 and not fl)
check("e.png trashed, d.png left (still named in n7)", trashed == 1 and left == 1 and not os.path.exists(os.path.join(media, "e.png")) and os.path.exists(os.path.join(media, "d.png")))
check("c.png still there and n6 points at it", os.path.exists(os.path.join(media, "c.png")) and "c.png" in open(os.path.join(vault, "n6.md"), encoding="utf-8").read())
check("trash holds the file for restore", any(it.get("into") for it in s.trash_items()))

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
    fake.duplicate_media_dialog((groups, refs, notes))
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
