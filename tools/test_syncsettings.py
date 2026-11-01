"""설정 양방향 맞추기(syncsettings.py) 시험: py -3 -I -X utf8 tools/test_syncsettings.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import syncpolicy as sp
import syncsettings as ss

fails = 0
TOTAL = 0


def check(name, ok):
    global fails, TOTAL
    TOTAL += 1
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


with tempfile.TemporaryDirectory() as d:
    pol = sp.new_policy()
    check("처음엔 바꾼 시각 없음(0)", ss.snapshot(pol)["updated"] == 0)
    sp.set_simple(pol, direction=sp.BOTH)
    check("같은 값으로 두면 시각이 안 찍힘", ss.snapshot(pol)["updated"] == 0)
    sp.set_simple(pol, direction=sp.PC2MOBILE)
    t = ss.snapshot(pol)["updated"]
    check("바꾸면 시각이 찍힘", t > 0)
    check("설정 파일이 없으면 내 것을 적는다", ss.reconcile(pol, d) == "push" and ss.read(d)["updated"] == t)
    check("같으면 할 일 없음", ss.reconcile(pol, d) is None)
    # 폰에서 더 나중에 바꿈
    ss.write(d, {"updated": t + 5000, "direction": sp.BOTH, "include": {"media": False, "imported": True, "history": True, "trash": False}})
    check("상대가 더 최근이면 받아들인다", ss.reconcile(pol, d) == "pull")
    s = pol["simple"]
    check("방향·항목이 상대 것으로", s["direction"] == sp.BOTH and s["include"]["media"] is False and s["include"]["history"] is True)
    check("시각도 상대 것 그대로(되돌려 쓰지 않음)", s["updated"] == t + 5000 and ss.reconcile(pol, d) is None)
    check("modules 도 따라 바뀜(옛 폰 앱 호환)", pol["modules"]["media"]["direction"] == sp.OFF and pol["modules"]["history"]["direction"] == sp.BOTH)
    # 컴퓨터에서 더 나중에 바꿈
    sp.set_simple(pol, media=True)
    pol["simple"]["updated"] += 10000
    check("내가 더 최근이면 적는다", ss.reconcile(pol, d) == "push" and ss.read(d)["include"]["media"] is True)
    # 깨진 파일은 없는 것처럼
    with open(os.path.join(d, ss.FILE), "w") as fh:
        fh.write("{oops")
    check("깨진 파일은 무시하고 내 것을 다시 적는다", ss.reconcile(pol, d) == "push" and ss.read(d) is not None)
    # 폴더 계획
    plans = sp.plan(pol, d, "pc", {}, os.path.join(d, "cfg"))
    cfg = [p for p in plans if p["module"] == "control"]
    check("설정 폴더는 항상 양방향", len(cfg) == 1 and cfg[0]["type"] == "sendreceive" and "-cfg-" in cfg[0]["id"])
    check("설정 폴더 ID 규칙(폰과 같음)", cfg[0]["id"] == ss.control_id(pol))
    check("경로를 안 주면 만들지 않음", not [p for p in sp.plan(pol, d, "pc", {}) if p["module"] == "control"])
    plan = {"tiers": [{"files": ["a.md", ".resources/x.png"]}, {"files": ["b.md", ".resources/y.png", ".resources/z.png"]}]}
    check("총수를 적음(글 2·그림 3)", ss.write_totals(d, plan) and json.load(open(os.path.join(d, ss.TOTALS_FILE))) == {"notesAll": 2, "mediaAll": 3})
    check("같으면 다시 쓰지 않음", ss.write_totals(d, plan) is False)
# 외부 폴더별 방향(ext)
with tempfile.TemporaryDirectory() as d:
    pol = sp.new_policy()
    sp.set_simple(pol, direction=sp.BOTH)
    ma = sp.add_external(pol, "aaa", "음악")
    mb = sp.add_external(pol, "bbb", "문서")
    fa, fb = sp.folder_id(pol, ma), sp.folder_id(pol, mb)
    check("외부 폴더마다 Syncthing 폴더 ID 로 기록", set(ss.snapshot(pol)["ext"]) == {fa, fb})
    check("바꾼 적 없으면 시각 0", ss.snapshot(pol)["ext"][fa]["updated"] == 0)
    sp.set_direction(pol, ma, sp.PC2MOBILE)
    t = ss.snapshot(pol)["ext"][fa]["updated"]
    check("외부 폴더 방향을 바꾸면 그 폴더만 시각이 찍힘", t > 0 and ss.snapshot(pol)["ext"][fb]["updated"] == 0)
    check("노트 폴더 시각은 그대로", ss.snapshot(pol)["updated"] == 0)
    check("처음엔 파일에 적는다", ss.reconcile(pol, d) == "push" and ss.read(d)["ext"][fa]["direction"] == sp.PC2MOBILE)
    check("같으면 할 일 없음", ss.reconcile(pol, d) is None)
    # 폰이 음악만 더 최근에 바꿈
    r = ss.read(d)
    r["ext"][fa] = {"direction": sp.MOBILE2PC, "updated": t + 5000}
    ss.write(d, r)
    check("폰이 더 최근이면 그 폴더만 받아들인다", ss.reconcile(pol, d) == "pull" and pol["modules"][ma]["direction"] == sp.MOBILE2PC
          and pol["modules"][ma]["updated"] == t + 5000 and pol["modules"][mb]["direction"] == sp.BOTH)
    check("받은 뒤에는 할 일 없음", ss.reconcile(pol, d) is None)
    # 컴퓨터에서 문서만 더 최근에 바꿈, 폰의 음악 값은 그대로
    pol["modules"][mb]["direction"], pol["modules"][mb]["updated"] = sp.OFF, t + 9000
    check("내가 더 최근인 폴더만 적는다", ss.reconcile(pol, d) == "push" and ss.read(d)["ext"][fb]["direction"] == sp.OFF
          and ss.read(d)["ext"][fa]["direction"] == sp.MOBILE2PC)
    # 노트 폴더와 외부 폴더가 각자 따로 이긴다
    r = ss.read(d)
    r["updated"] = ss.snapshot(pol)["updated"] + 7000
    r["direction"] = sp.PC2MOBILE
    r["ext"][fb] = {"direction": sp.OFF, "updated": t + 9000}
    ss.write(d, r)
    pol["modules"][ma]["direction"], pol["modules"][ma]["updated"] = sp.BOTH, t + 20000
    check("노트는 폰이, 외부(음악)는 컴퓨터가 이긴다", ss.reconcile(pol, d) == "pull" and pol["simple"]["direction"] == sp.PC2MOBILE
          and ss.read(d)["ext"][fa]["direction"] == sp.BOTH)
    # ext 가 없는 옛 폰 파일은 그대로 받아도 외부 폴더 값을 잃지 않는다
    old = ss.read(d)
    old.pop("ext")
    ss.write(d, old)
    ss.reconcile(pol, d)
    check("ext 없는 옛 파일이면 내 값으로 채워 적는다", set(ss.read(d)["ext"]) == {fa, fb})
print("통과 %d / %d" % (TOTAL - fails, TOTAL) if fails == 0 else "실패 %d" % fails)
sys.exit(1 if fails else 0)
