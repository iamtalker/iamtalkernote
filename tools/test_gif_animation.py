"""렌더링된 GIF가 자동으로 재생되고 다시 그릴 때 정리되는지 확인한다."""
import os
import sys
import tempfile
import time
import tkinter as tk

from PIL import Image

tmp = tempfile.mkdtemp(prefix="gif-")
os.environ["APPDATA"] = tmp
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import notes  # noqa: E402

root = tk.Tk()
root.withdraw()
app = notes.App.__new__(notes.App)
app.root = root
app.view = tk.Text(root)
app.view.pack()
app.photos = []
app.img_files = {}
app.gif_jobs, app.gif_sources, app.gif_generation = set(), [], 0
fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def pump(ms):
    until = time.time() + ms / 1000
    while time.time() < until:
        root.update()
        time.sleep(0.01)


path = os.path.join(tmp, "two-frames.gif")
Image.new("RGB", (4, 4), "red").save(
    path,
    save_all=True,
    append_images=[Image.new("RGB", (4, 4), "blue")],
    duration=80,
    loop=0,
)
app.img_avail = lambda: 100
app.find_local_image = lambda _: path
check("노트의 GIF 그림 링크를 렌더링함", app.show_image("two-frames.gif"))
image = app.photos[-1]
first = root.tk.call(str(image), "get", 1, 1)
pump(120)
second = root.tk.call(str(image), "get", 1, 1)
check("GIF 프레임이 자동으로 바뀜", first != second)
check("렌더링 중인 GIF 타이머가 등록됨", bool(app.gif_jobs))
app.stop_gifs()
check("렌더링 갱신 때 GIF 타이머와 파일이 정리됨",
      not app.gif_jobs and not app.gif_sources)
root.destroy()
sys.exit(1 if fails else 0)
