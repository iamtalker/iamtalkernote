"""폰과 규칙이 다르면 그 폴더를 멈추고 옵션 → 동기화 화면에 경고를 보이는지 시험(창을 연 채로 폰 파일이 바뀌어도 따라간다).
임시 APPDATA·임시 노트 폴더만 쓴다.  py -3 -X utf8 tools/test_sync_refresh.py"""
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
import syncsettings as ss  # noqa: E402
import syncui  # noqa: E402
syncengine.installed = lambda: True   # 시험 PC 에는 Syncthing 이 없어도 정책 영역이 그려지게

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


pol = sp.new_policy()
sp.set_simple(pol, direction=sp.PC2MOBILE)
mid = sp.add_external(pol, "aaa", "음악", sp.BOTH)
fid = sp.folder_id(pol, mid)
sp.save(vault, pol)
peer_path = os.path.join(ss.control_dir(), ss.PEER_FILE)


def put_peer(obj):
    with open(peer_path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


a = notes.App()
a.docs.folders = lambda: [{"id": "aaa", "path": os.path.join(tmp, "aaa"), "name": "음악"}]   # 가져오기에 등록된 외부 폴더인 것처럼


def run(sec):
    """실제 메인 루프를 sec 초 돌린다(백그라운드 스레드가 after() 로 화면에 알리려면 메인 루프가 돌아야 한다)"""
    a.root.after(int(sec * 1000), a.root.quit)
    a.root.mainloop()


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def warnings(top):
    return [w.cget("text") if w.winfo_class() == "Label" else w.get("1.0", "end") for w in walk(top)
            if w.winfo_class() in ("Label", "Text") and "멈췄습니다" in (w.cget("text") if w.winfo_class() == "Label" else w.get("1.0", "end"))]


# 폴더 계획: 폰과 같으면 멈추지 않고, 다르면 그 폴더만 멈춘다
put_peer({})
plans = {p["module"]: p for p in syncui.current_plans(a, sp.load(vault))}
check("폰이 따로 정한 것이 없으면 아무 폴더도 안 멈춘다", not any(p.get("paused") for p in plans.values()))
put_peer({"ext": {fid: sp.OFF}})
plans = {p["module"]: p for p in syncui.current_plans(a, sp.load(vault))}
check("방향이 다른 외부 폴더만 멈춘다", plans[mid].get("paused") is True and not plans["markdown"].get("paused"))
put_peer({"notes": {"include": {"media": False}}})
plans = {p["module"]: p for p in syncui.current_plans(a, sp.load(vault))}
check("함께 보낼 것이 다르면 노트 폴더가 멈춘다", plans["markdown"].get("paused") is True and not plans[mid].get("paused"))

# 화면: 열 때 경고가 보이고, 연 채로 폰 파일이 같아지면 사라진다
put_peer({"ext": {fid: sp.OFF}})
run(1.5)
a.show_options("sync")
run(1)
top = [w for w in a.root.winfo_children() if w.winfo_class() == "Toplevel"][-1]
def banner_ok(top):
    """맨 위 안내가 줄바꿈돼도 전부 보인다(높이가 줄 수에 맞고 스크롤 없이 처음부터 끝까지)"""
    for w in walk(top):
        if w.winfo_class() == "Text" and "같아야 동기화됩니다" in w.get("1.0", "end"):
            lines = (w.count("1.0", "end", "displaylines") or (1,))[0]   # 창이 넓으면 한 줄, 좁으면 여러 줄 — 몇 줄이든 높이가 줄 수와 같아야 한다
            return int(w.cget("height")) == lines and w.yview() == (0.0, 1.0)
    return False


check("맨 위 '규칙이 같아야 동기화' 안내가 줄바꿈돼도 전부 보인다", banner_ok(top))
check("규칙이 다른 외부 폴더에 경고가 보인다", len(warnings(top)) == 1 and "양방향" in warnings(top)[0] and "동기화 안 함" in warnings(top)[0])
put_peer({})
run(6)
check("폰 값이 컴퓨터와 같아지면(연 채로) 경고가 사라진다", len(warnings(top)) == 0)
put_peer({"notes": {"direction": sp.BOTH}})
run(6)
check("노트 폴더 규칙이 다르면 경고가 다시 보인다", len(warnings(top)) == 1 and "컴퓨터 → 폰" in warnings(top)[0])
a.root.destroy()
sys.exit(1 if fails else 0)
