"""도구 > 글자로 박힌 그림 일괄 분리 시험: py -3 -I -X utf8 tools/test_embedded_images.py"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="embedded-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
vault = os.path.join(tmp, "vault")
os.makedirs(vault)

import store as st  # noqa: E402
import embedded  # noqa: E402

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


s = st.Store(root=vault)
body_img = f"# 그림 노트\n\n![그림](data:image/png;base64,{PNG})\n\n끝\n"
p1 = os.path.join(vault, "그림 노트.md")
p2 = os.path.join(vault, "글만.md")
with open(p1, "w", encoding="utf-8", newline="") as f:
    f.write(body_img)
with open(p2, "w", encoding="utf-8", newline="") as f:
    f.write("# 글만\n\n그림 없음\n")
notes = [{"nb": "", "title": "그림 노트", "path": p1}, {"nb": "", "title": "글만", "path": p2}]

found = embedded.scan_embedded(notes)
check("scan finds only the note with base64 image", len(found) == 1 and found[0][0]["path"] == p1)
check("scan counts one image", found and found[0][1] == 1)

changed, moved, failed = embedded.convert_embedded(s, found)
check("convert changes one note", changed == 1 and moved == 1 and not failed)
after = open(p1, encoding="utf-8").read()
check("no base64 left in note", "base64," not in after)
check("note now points at a file", "](" in after and ".resources" in after)
check("text after image kept", "끝" in after)
rel = after.split("](", 1)[1].split(")", 1)[0]
check("image file exists", os.path.isfile(os.path.join(vault, rel)))
check("second scan finds nothing", embedded.scan_embedded(notes) == [])

print("FAILS:", fails)
sys.exit(1 if fails else 0)
