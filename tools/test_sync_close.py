"""옵션 → 동기화에서 [적용] 없이 창을 닫을 때 묻는지 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_sync_close.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="cls-")
vault = os.path.join(tmp, "v")
os.makedirs(vault)
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.environ["IAT_NO_SINGLE"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import notes  # noqa: E402
import syncui  # noqa: E402
import syncengine  # noqa: E402
syncengine.installed = lambda: True   # 시험 PC 에는 Syncthing 이 없어도 정책 영역이 그려지게

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


a = notes.App()


def pump(n=20):
    for _ in range(n):
        a.root.update()
        time.sleep(0.02)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def options():
    return [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"]


asked = []
notes.messagebox.askyesno = lambda *x, **k: (asked.append(x), False)[1]   # 확인 창은 '아니오'
syncui.messagebox.askyesno = notes.messagebox.askyesno
pump(40)
a.show_options("sync")
pump(30)
top = options()[-1]
check("옵션 창에 닫기 확인 훅이 있다", hasattr(top, "can_close"))
check("바꾼 것이 없으면 묻지 않고 닫을 수 있다", top.can_close() is True and not asked)

combos = [w for w in walk(top) if w.winfo_class() == "TCombobox"]
check("방향 콤보가 있다", len(combos) >= 1)
if combos:
    cb = combos[0]
    cb.current(2 if cb.current() != 2 else 1)       # 방향을 바꾼다(적용은 안 누름)
    cb.event_generate("<<ComboboxSelected>>")
    pump(5)
    asked.clear()
    check("적용 안 한 변경이 있으면 묻고, 아니오면 닫지 않는다", top.can_close() is False and len(asked) == 1)
    check("창이 그대로 있다", top.winfo_exists() == 1)
    notes.messagebox.askyesno = lambda *x, **k: (asked.append(x), True)[1]
    syncui.messagebox.askyesno = notes.messagebox.askyesno
    check("예라고 하면 닫을 수 있다", top.can_close() is True)
a.root.destroy()
sys.exit(1 if fails else 0)
