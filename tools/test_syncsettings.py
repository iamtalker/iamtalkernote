"""설정 양방향 맞추기(syncsettings.py) 시험: py -3 -I -X utf8 tools/test_syncsettings.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import syncpolicy as sp
import syncsettings as ss

fails = 0


def check(name, ok):
    global fails
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
print("통과 %d / %d" % (14 - fails, 14) if fails == 0 else "실패 %d" % fails)
sys.exit(1 if fails else 0)
