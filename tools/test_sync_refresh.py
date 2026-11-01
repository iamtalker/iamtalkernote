"""옵션 → 동기화 화면이 폰이 바꾼 방향(정책 파일의 변경)을 따라가는지 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_sync_refresh.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="rfs-")
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
import syncui  # noqa: E402
syncengine.installed = lambda: True   # 시험 PC 에는 Syncthing 이 없어도 정책 영역이 그려지게

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


pol = sp.new_policy()
sp.set_simple(pol, direction=sp.BOTH)
mid = sp.add_external(pol, "aaa", "음악", sp.BOTH)
sp.save(vault, pol)

a = notes.App()


def pump(sec):
    """실제 메인 루프를 sec 초 돌린다(백그라운드 스레드가 after() 로 화면에 알리려면 메인 루프가 돌아야 한다)"""
    a.root.after(int(sec * 1000), a.root.quit)
    a.root.mainloop()


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def combos(top):
    return [w for w in walk(top) if w.winfo_class() == "TCombobox"]


pump(1.5)
a.show_options("sync")
pump(1)
top = [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"][-1]
cbs = combos(top)
check("방향 콤보가 둘(노트 폴더·외부 폴더)", len(cbs) == 2)
ext_cb = cbs[-1]
check("처음엔 외부 폴더가 '양방향'", ext_cb.get() == sp.LABELS[sp.BOTH])

# 폰이 바꿔서 컴퓨터가 정책을 새로 저장한 것처럼 파일을 고친다
new = sp.load(vault)
sp.set_direction(new, mid, sp.MOBILE2PC)
sp.save(vault, new)
pump(6)
cbs = combos(top)
check("창을 연 채로 몇 초 뒤 외부 폴더 표시가 '폰 → 컴퓨터'로 바뀐다", cbs and cbs[-1].get() == sp.LABELS[sp.MOBILE2PC])

# 사용자가 직접 바꾸고 [적용] 전이면 파일이 바뀌어도 덮어쓰지 않는다
cbs[-1].current(0)
cbs[-1].event_generate("<<ComboboxSelected>>")
pump(0.5)
mine = cbs[-1].get()
new2 = sp.load(vault)
sp.set_direction(new2, mid, sp.OFF)
sp.save(vault, new2)
pump(6)
check("바꾸고 [적용]을 안 눌렀으면 자동 갱신이 내 선택을 덮어쓰지 않는다", combos(top)[-1].get() == mine)
a.root.destroy()
sys.exit(1 if fails else 0)
