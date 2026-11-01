"""옵션 → 동기화: 방향을 고르면 [적용] 없이 자동으로 저장·적용되고, 바로 닫아도 마지막 변경이 저장되는지 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
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
import syncengine  # noqa: E402
import syncpolicy as sp  # noqa: E402
syncengine.installed = lambda: True   # 시험 PC 에는 Syncthing 이 없어도 정책 영역이 그려지게

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


a = notes.App()


def run(sec):
    a.root.after(int(sec * 1000), a.root.quit)
    a.root.mainloop()


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def combos(top):
    return [w for w in walk(top) if w.winfo_class() == "TCombobox"]


def has_apply_button(top):
    return any(w.__class__.__name__ == "Btn" and w.label.cget("text") == "적용" for w in walk(top))


def disk_dir():
    return sp.load(vault)["simple"]["direction"] if sp.exists(vault) else None


run(1.5)
a.show_options("sync")
run(1)
top = [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"][-1]
check("[적용] 버튼이 없다", not has_apply_button(top))
check("옵션 창에 닫기 훅이 있다", hasattr(top, "can_close"))
cb = combos(top)[0]
want = sp.MOBILE2PC if cb.current() != 2 else sp.PC2MOBILE
cb.current(sp.DIRECTIONS.index(want))
cb.event_generate("<<ComboboxSelected>>")
run(0.3)
check("고른 직후에는 아직 저장 전(잠깐 모아서 적용)", disk_dir() != want)
run(2)
check("잠깐 뒤 [적용] 없이 저장된다", disk_dir() == want)

# 연달아 바꾸고 바로 닫아도 마지막 값이 저장된다
cb = combos(top)[0]
last = sp.OFF
cb.current(sp.DIRECTIONS.index(last))
cb.event_generate("<<ComboboxSelected>>")
check("닫을 때 확인 창 없이 닫힌다", top.can_close() is True)
run(2)
check("바로 닫아도 마지막 변경이 저장된다", disk_dir() == last)
a.root.destroy()
sys.exit(1 if fails else 0)
