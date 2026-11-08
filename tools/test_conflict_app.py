"""동기화 충돌 해결 화면(app/dialogs.py conflict_dialog) 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_conflict_app.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="cfl-")
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


def write(name, body):
    with open(os.path.join(vault, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def read(name):
    with open(os.path.join(vault, name), encoding="utf-8") as f:
        return f.read()


def body_of(name):
    """저장할 때 앱이 붙이는 머리말(created·updated)을 떼고 본문만 돌려준다"""
    text = read(name)
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:].lstrip("\n")
    return text


CF = "회의.sync-conflict-20261101-143005-ABCDEFG.md"
write("회의.md", "첫째\n둘째\n")
write(CF, "첫째\n둘째 고침\n셋째\n")
write("딴것.md", "다른 노트\n")
a = notes.App()


def pump(n=30):
    for _ in range(n):
        a.root.update()
        time.sleep(0.02)


def find(title):
    return next((n for n in a.all_notes if n["title"] == title), None)


pump(60)
a.reload_notes()
pump(30)
title = "회의 (충돌 2026-11-01 14:30)"
n = find(title)
check("충돌 사본이 '제목 (충돌 날짜)' 로 목록에 나온다", n is not None)
check("원본은 그대로 나온다", find("회의") is not None)
check("위키 제목 목록에는 충돌 사본이 없다", all("sync-conflict" not in k for _, k in a.store.titles()))

a.conflict_dialog(n)
pump(10)
tops = [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"]
check("충돌 창이 뜬다", len(tops) >= 1)


def texts(w):
    out = []
    for c in w.winfo_children():
        if c.winfo_class() == "Text":
            out.append(c.get("1.0", "end"))
        out += texts(c)
    return out


body = "\n".join(texts(tops[-1]))
check("차이에 사본에만 있는 줄이 보인다", "셋째" in body and "둘째 고침" in body)
for w in tops:
    w.destroy()

# 사본으로 바꾸기: 원본이 사본 내용이 되고 사본은 사라진다 (askyesno 는 예로)
notes.messagebox.askyesno = lambda *x, **k: True
a.conflict_dialog(n)
pump(10)
top = [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"][-1]


def buttons(w):
    out = []
    for c in w.winfo_children():
        out += buttons(c)
        out.append(c)
    return out


def click(w, label):
    for c in buttons(w):
        if isinstance(c, notes.Btn) and c.label.cget("text") == label:
            c.command()
            return True
    return False


# Btn 은 Label 모양이라 눌림 이벤트로 실행된다
done = click(top, notes.tr("사본으로 바꾸기"))
pump(20)
check("단추를 찾아 눌렀다", done)
check("원본이 사본 내용으로 바뀐다", body_of("회의.md") == "첫째\n둘째 고침\n셋째\n")
check("사본 파일은 휴지통으로 간다", not os.path.exists(os.path.join(vault, CF)))

# 원본 두고 사본 지우기
write(CF, "엉뚱한 내용\n")
a.reload_notes()
pump(30)
n2 = find(title)
a.conflict_dialog(n2)
pump(10)
top = [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"][-1]
click(top, notes.tr("원본 두고 사본 지우기"))
pump(20)
check("원본 두기: 원본 그대로", body_of("회의.md") == "첫째\n둘째 고침\n셋째\n")
check("원본 두기: 사본 사라짐", not os.path.exists(os.path.join(vault, CF)))

a.root.destroy()
sys.exit(1 if fails else 0)
