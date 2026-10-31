"""새 노트 제목(app/notes.py new_note·auto_title) 시험: 제목칸은 비어 있고, 제목 없이 본문만 쓰고 떠나면 본문 첫 줄이 제목이 된다.
임시 APPDATA·임시 노트 폴더만 쓴다.  py -3 -X utf8 tools/test_newnote_title.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="ttl-")
vault = os.path.join(tmp, "v")
os.makedirs(vault)
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
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


def files():
    return sorted(f for f in os.listdir(vault) if f.endswith(".md"))


pump(60)
a.new_note()
pump()
check("새 노트: 제목칸이 비어 있다", a.title_var.get() == "")
a.text.insert("1.0", "## 장보기 목록\n우유 계란")
a.on_modified()
a.text.edit_modified(True)
a.on_modified()
pump(5)
a.new_note()                       # 노트를 떠난다
pump()
check("제목 없이 본문만 쓰고 떠나면 첫 줄이 제목(파일 이름)", "장보기 목록.md" in files())
check("그 노트의 '제목 없음' 은 남지 않는다(새 빈 노트 하나만)", files().count("제목 없음.md") == 1 and len(files()) == 2)
a.title_var.set("내가 쓴 제목")
a.commit_title()
a.text.insert("1.0", "본문")
a.on_modified()
a.text.edit_modified(True)
a.on_modified()
pump(5)
a.new_note()
pump()
check("제목을 직접 쓰면 그 제목을 쓴다(첫 줄로 덮지 않는다)", "내가 쓴 제목.md" in files() and "본문.md" not in files())
a.root.destroy()
sys.exit(1 if fails else 0)
