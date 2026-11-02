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
a.new_note()
a.title_var.set("자동 저장 제목")
pump(120)
check("제목 입력이 멈추면 2초 뒤 자동 저장", "자동 저장 제목.md" in files())
a.new_note()
a.title_var.set("포커스 이동 저장 제목")
a.title_entry.event_generate("<FocusOut>")
pump(5)
check("제목 입력칸에서 포커스를 옮겨도 바로 확정하지 않음",
      "포커스 이동 저장 제목.md" not in files())
pump(100)
check("포커스 이동 뒤 조합이 끝나면 제목을 자동 저장",
      "포커스 이동 저장 제목.md" in files())
a.new_note()
a.title_var.set("조합 중 저장 보류")
a.title_entry.focus_force()
pump(3)
composing = notes.ime.composing
complete = notes.ime.complete
ime_state = {"active": True}
notes.ime.composing = lambda: "시" if ime_state["active"] else ""
notes.ime.complete = lambda: ime_state.update(active=False) or True
a.commit_title()
pump(5)
check("IME 조합 중에는 직접 호출된 제목 저장도 미룸",
      "조합 중 저장 보류.md" not in files())
pump(20)
notes.ime.composing = composing
notes.ime.complete = complete
check("IME 조합이 끝나면 대기 중인 제목을 저장",
      "조합 중 저장 보류.md" in files())
a.new_note()
a.title_var.set("전환 전 저장 제목")
a.new_note()
pump()
check("2초 전이라도 다른 노트로 가면 제목을 먼저 저장", "전환 전 저장 제목.md" in files())
a.root.destroy()
sys.exit(1 if fails else 0)
