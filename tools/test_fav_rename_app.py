"""앱에서 즐겨찾기한 노트의 제목을 바꾸거나 다른 노트북으로 옮겨도 즐겨찾기가 유지되는지 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_fav_rename_app.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="fav-")
vault = os.path.join(tmp, "v")
os.makedirs(os.path.join(vault, "업무"))
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
with open(os.path.join(vault, "클로드 변경.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("본문\n")
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
a.reload_notes()
pump(20)
n = next(x for x in a.all_notes if x["title"] == "클로드 변경")
a.open_note(n)
pump(10)
a.toggle_favorite(n)
check("즐겨찾기에 넣었다", a.fav.is_fav("클로드 변경.md"))

a.title_var.set("클로드 변경2")
a.commit_title()
pump(10)
check("제목을 바꿔도 즐겨찾기가 유지된다", a.fav.is_fav("클로드 변경2.md") and not a.fav.is_fav("클로드 변경.md"))
check("파일 이름이 바뀌었다", os.path.exists(os.path.join(vault, "클로드 변경2.md")))

a.reload_notes()
pump(20)
m = next(x for x in a.all_notes if x["title"] == "클로드 변경2")
a.move_note(m, "업무")
pump(10)
check("다른 노트북으로 옮겨도 즐겨찾기가 유지된다", a.fav.is_fav("업무/클로드 변경2.md") and not a.fav.is_fav("클로드 변경2.md"))
a.root.destroy()
sys.exit(1 if fails else 0)
