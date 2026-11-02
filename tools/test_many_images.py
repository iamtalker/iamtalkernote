"""그림이 많은 노트를 열 때 화면이 멈추지 않는지 시험: py -3 -I -X utf8 tools/test_many_images.py"""
import json
import os
import sys
import tempfile
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="many-images-")
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


lines = []
for i in range(80):
    name = f"image{i}.png"
    Image.new("RGB", (2400, 1600), (i % 255, (i * 3) % 255, (i * 7) % 255)).save(os.path.join(vault, name))
    lines.extend((f"![image{i}]({name})", ""))
path = os.path.join(vault, "many.md")
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

app = notes.App()
for _ in range(80):
    app.root.update()
    if app.all_notes:
        break
app.open_note(next(n for n in app.all_notes if n["path"] == path))
app.set_mode("view")
start = time.perf_counter()
app.render()
elapsed = time.perf_counter() - start
check("80개 대형 그림이 있어도 첫 렌더링이 1초 이내에 반환",
      elapsed < 1.0 and not app.photos)

deadline = time.monotonic() + 30
while time.monotonic() < deadline and len(app.photos) < 80:
    app.root.update()
    time.sleep(0.01)
check("백그라운드 축소가 끝난 그림 80개를 모두 표시", len(app.photos) == 80)

app.root.destroy()
sys.exit(1 if fails else 0)
