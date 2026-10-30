"""새 정책(simple)과 옛 정책을 실제 Syncthing 에 적용해 보는 시험(전환·설정 변경·끄기, 사용자 파일이 안 바뀌는지).
임시 APPDATA·임시 볼트를 쓰고 127.0.0.1 만 듣는다. 사용자의 실제 설정은 건드리지 않는다.
실행:  py -3 tools/test_sync_engine.py <syncthing.exe 경로>   (방화벽 창을 피하려면 같은 경로를 재사용한다)"""
import json, os, shutil, sys, tempfile, urllib.parse

if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
    sys.exit("사용법: py -3 tools/test_sync_engine.py <syncthing.exe 경로>")
SRC = os.path.abspath(sys.argv[1])
tmp = tempfile.mkdtemp(prefix="engsimple-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
import syncengine as se, syncpolicy as sp
se.exe_path = lambda: SRC
se.installed = lambda: True

vault = os.path.join(tmp, "vault")
for d, files in {"ScrapBook": ["a.md", "b.md"], ".resources": ["x.png", "y.jpg"], ".history": ["h1.md"], ".trash": ["t1.md"], ".imported": ["docs.jsonl"], "업무": ["c.md"]}.items():
    os.makedirs(os.path.join(vault, d), exist_ok=True)
    for f in files:
        open(os.path.join(vault, d, f), "w", encoding="utf-8").write("x" * 10)
before = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(vault) for f in fs)

ok = []
def check(desc, cond):
    ok.append(bool(cond)); print(("  ✔ " if cond else "  ✘ ") + desc, flush=True)

e = se.Engine()
try:
    assert e.start()
    e.api("/rest/config/options", "PATCH", {"listenAddresses": ["tcp://127.0.0.1:22005"], "globalAnnounceEnabled": False, "localAnnounceEnabled": False,
                                            "relaysEnabled": False, "natEnabled": False, "urAccepted": -1})

    def folders():
        return {f["id"]: f for f in e.api("/rest/config/folders") if f["id"].startswith(sp.ID_PREFIX)}

    def ignores(fid):
        return e.api("/rest/db/ignores?folder=" + urllib.parse.quote(fid))["ignore"]

    # 1) 옛 정책 → 폴더 여러 개
    old = sp.new_legacy_policy()
    sp.add_notebook(old, "업무", sp.BOTH)
    plans = sp.plan(old, vault, "pc")
    made, gone = e.apply(plans)
    f1 = folders()
    check("옛 정책: 폴더 %d개 만들어짐(노트·미디어·가져온 요약·노트북)" % len(f1), len(f1) == 4 and gone == 0)

    # 2) 새 방식으로 전환(같은 볼트 ID) → 노트 폴더 하나만 남고 옛 폴더는 지워짐
    dropped = sp.to_simple(old)
    plans = sp.plan(old, vault, "pc")
    made, gone = e.apply(plans)
    f2 = folders()
    mar = sp.folder_id(old, "markdown")
    check("전환 후 폴더는 노트 폴더 하나만(지운 옛 폴더 %d개)" % gone, list(f2) == [mar] and gone == 3)
    check("노트 폴더의 ID 가 전환 전과 같음", mar in f1)
    left = [os.path.relpath(os.path.join(dp, f), vault) for dp, _, fs in os.walk(vault) for f in fs if f == ".stignore"]
    check("옛 폴더의 .stignore 정리, 노트 폴더 것만 남음 → %s" % left, left == [".stignore"])
    # 사용자가 직접 쓴 줄이 든 .stignore 는 건드리지 않는다(옛 폴더가 지워질 때)
    check("종류·경로: sendreceive, 노트 폴더 전체", f2[mar]["type"] == "sendreceive" and os.path.normpath(f2[mar]["path"]) == os.path.normpath(vault))
    ign = ignores(mar)
    check("제외 목록: 이력·휴지통·복원 지점 제외, 미디어·가져온 요약은 포함 → %s" % [x for x in ign if x.startswith("/")],
          "/.history" in ign and "/.trash" in ign and "/.snapshots" in ign and "/.resources" not in ign and "/.imported" not in ign)
    check("받는 순서 smallestFirst 유지", f2[mar].get("order") == "smallestFirst")

    # 3) 설정 바꾸기: 미디어 빼고 이력 켜고, 방향 PC→모바일
    sp.set_simple(old, direction=sp.PC2MOBILE, media=False, history=True)
    e.apply(sp.plan(old, vault, "pc"))
    f3 = folders(); ign = ignores(mar)
    check("방향 PC→모바일 → sendonly", f3[mar]["type"] == "sendonly")
    check("미디어 제외·이력 포함으로 제외 목록이 바뀜", "/.resources" in ign and "/.history" not in ign and "/.trash" in ign)

    # 4) 동기화 안 함 → 노트 폴더가 사라진다
    sp.set_simple(old, direction=sp.OFF)
    made, gone = e.apply(sp.plan(old, vault, "pc"))
    check("동기화 안 함 → 폴더 0개", folders() == {} and gone == 1)

    after = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(vault) for f in fs if not f.startswith(".syncthing") and ".stfolder" not in dp)
    after = [x for x in after if ".stfolder" not in x]
    print("   추가:", [os.path.relpath(x, vault) for x in after if x not in before], "사라짐:", [os.path.relpath(x, vault) for x in before if x not in after])
    check("노트·미디어 등 사용자 파일은 하나도 안 바뀜(%d개)" % len(before), all(x in after for x in before) and all(open(x).read() == "x" * 10 for x in before))
finally:
    try:
        e.stop()
    except Exception:
        pass
    shutil.rmtree(tmp, ignore_errors=True)
print("통과 %d / %d" % (sum(ok), len(ok)))
