"""글 정리 메뉴와 찾아 바꾸기(Ctrl+H)를 실제 창으로 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_tidy_app.py"""
import json
import os
import sys
import tempfile
import time

NL = chr(10)
tmp = tempfile.mkdtemp(prefix="tidy-")
vault = os.path.join(tmp, "v")
os.makedirs(os.path.join(vault, "업무"))
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
note = os.path.join(vault, "업무", "회의.md")
SRC = NL.join(["  첫 줄", "", "", "", "   둘째 줄", "셋째 줄", ""])
with open(note, "w", encoding="utf-8", newline=NL) as f:
    f.write(SRC)
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


def saved():
    with open(note, encoding="utf-8") as fh:
        return fh.read()


pump(60)
a.reload_notes()
pump(20)
a.open_note(next(x for x in a.all_notes if x["title"] == "회의"))
pump(20)
a.set_mode("edit")
pump(10)

mb = a.root.nametowidget(a.root.cget("menu"))
casc = [i for i in range(mb.index("end") + 1) if mb.type(i) == "cascade"]
tops = [mb.entrycget(i, "label") for i in casc]
check("메뉴줄에 '글 정리'가 편집 다음에 있다", tops[:3] == ["파일", "편집", "글 정리"])
td = mb.nametowidget(mb.entrycget(casc[2], "menu"))
items = [i for i in range(td.index("end") + 1) if td.type(i) == "command"]
labels = [td.entrycget(i, "label") for i in items]
check("글 정리 메뉴 항목 12개", len(labels) == 12 and "줄 앞 공백 지우기" in labels and "여러 빈 줄을 하나로" in labels)

td.invoke(items[labels.index("줄 앞 공백 지우기")])
pump(10)
body = a.text.get("1.0", "end-1c")
check("메뉴로 줄 앞 공백 지우기", body.startswith("첫 줄") and NL + "둘째 줄" in body)
check("상태 줄에 결과", "2" in a.status.cget("text"))
a.tidy("blank")
pump(60)
check("여러 빈 줄을 하나로", a.text.get("1.0", "end-1c").rstrip(NL) == NL.join(["첫 줄", "", "둘째 줄", "셋째 줄"]))
check("자동 저장된다(머리말 뒤에 정리된 글)", saved().rstrip(NL).endswith(NL + NL.join(["첫 줄", "", "둘째 줄", "셋째 줄"])))
a.text.edit_undo()
a.text.edit_undo()
pump(5)
check("되돌리기 두 번으로 처음 글", a.text.get("1.0", "end-1c").rstrip(NL) == SRC.rstrip(NL))

a.text.focus_force()
pump(5)
a.text.event_generate("<Control-h>")
pump(15)
check("Ctrl+H: 찾기 막대와 바꿀 글 줄이 뜬다", a.findbar.winfo_ismapped() and a.replbar.winfo_ismapped())
check("Ctrl+H 가 글자를 지우지 않는다", a.text.get("1.0", "end-1c").rstrip(NL) == SRC.rstrip(NL))
check("바꿀 글 줄이 찾기 막대 바로 아래", a.replbar.winfo_y() > a.findbar.winfo_y() and a.replbar.winfo_y() < a.body.winfo_y())
a.find_var.set("줄")
a.repl_var.set("행")
pump(10)
check("찾은 곳 3곳", len(a.find_hits) == 3)
a.replace_one()
pump(10)
check("바꾸기: 한 곳", a.text.get("1.0", "end-1c").count("행") == 1 and len(a.find_hits) == 2)
a.replace_all()
pump(60)
check("모두 바꾸기", a.text.get("1.0", "end-1c").count("행") == 3 and "줄" not in a.text.get("1.0", "end-1c"))
check("바꾼 글이 저장된다", saved().count("행") == 3)
a.set_mode("view")
pump(10)
a.show_replace()
pump(10)
check("렌더링만 보기에서 열면 편집 칸이 보이게 바뀐다", a.mode == "split" and a.replbar.winfo_ismapped())
a.hide_find()
pump(5)
check("Esc(닫기): 두 줄 다 사라진다", not a.findbar.winfo_ismapped() and not a.replbar.winfo_ismapped())
a.root.destroy()
sys.exit(1 if fails else 0)
