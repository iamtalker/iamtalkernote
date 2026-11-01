"""컴퓨터·폰 동기화 규칙 맞춰 보기(syncsettings.py) 시험: py -3 -I -X utf8 tools/test_syncsettings.py
규칙(방향·함께 보낼 것)이 양쪽이 같아야 동기화하고, 다르면 그 폴더는 멈춘다."""
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


def put_peer(d, obj):
    with open(os.path.join(d, ss.PEER_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


with tempfile.TemporaryDirectory() as d:
    pol = sp.new_policy()
    sp.set_simple(pol, direction=sp.PC2MOBILE, media=True, imported=False, history=False, trash=False)
    ma = sp.add_external(pol, "aaa", "음악", sp.BOTH)
    mb = sp.add_external(pol, "bbb", "문서", sp.MOBILE2PC)
    fa, fb = sp.folder_id(pol, ma), sp.folder_id(pol, mb)

    # 컴퓨터의 규칙을 적는다
    mine = ss.own(pol)
    check("컴퓨터 규칙: 노트 폴더 방향·함께 보낼 것", mine["notes"]["direction"] == sp.PC2MOBILE and mine["notes"]["include"]["media"] is True and mine["notes"]["include"]["imported"] is False)
    check("컴퓨터 규칙: 외부 폴더마다 Syncthing 폴더 ID 로 방향", mine["ext"] == {fa: sp.BOTH, fb: sp.MOBILE2PC})
    check("처음엔 파일에 적는다", ss.write_own(d, pol) and json.load(open(os.path.join(d, ss.OWN_FILE))) == mine)
    check("같으면 다시 쓰지 않는다", ss.write_own(d, pol) is False)
    sp.set_direction(pol, ma, sp.OFF)
    check("바뀌면 다시 쓴다", ss.write_own(d, pol) and json.load(open(os.path.join(d, ss.OWN_FILE)))["ext"][fa] == sp.OFF)
    sp.set_direction(pol, ma, sp.BOTH)

    # 폰이 따로 정한 것이 없으면 모두 컴퓨터를 따른다(같은 것)
    check("폰 파일이 없으면 다른 것 없음(옛 폰 앱도 멈추지 않는다)", ss.read_peer(d) == {} and ss.mismatches(pol, ss.read_peer(d)) == {})
    put_peer(d, {})
    check("빈 파일도 다른 것 없음", ss.mismatches(pol, ss.read_peer(d)) == {})
    with open(os.path.join(d, ss.PEER_FILE), "w") as fh:
        fh.write("{oops")
    check("깨진 파일은 없는 것처럼", ss.read_peer(d) == {})

    # 노트 폴더 방향이 다르면 멈춘다
    put_peer(d, {"notes": {"direction": sp.BOTH}})
    diff = ss.mismatches(pol, ss.read_peer(d))
    check("노트 폴더 방향이 다르면 노트 폴더가 멈춘다(외부 폴더는 그대로)", list(diff) == ["markdown"] and "컴퓨터 → 폰" in diff["markdown"][0] and "양방향" in diff["markdown"][0])
    # 같은 값이면 멈추지 않는다(폰이 따로 적어 둔 값이 컴퓨터와 같아진 경우)
    put_peer(d, {"notes": {"direction": sp.PC2MOBILE}})
    check("폰이 적은 값이 컴퓨터와 같으면 멈추지 않는다", ss.mismatches(pol, ss.read_peer(d)) == {})
    # 함께 보낼 것이 다르면 멈춘다
    put_peer(d, {"notes": {"include": {"media": False}}})
    diff = ss.mismatches(pol, ss.read_peer(d))
    check("함께 보낼 것(미디어)이 다르면 노트 폴더가 멈춘다", list(diff) == ["markdown"] and "미디어" in diff["markdown"][0] and "켬" in diff["markdown"][0] and "끔" in diff["markdown"][0])
    put_peer(d, {"notes": {"include": {"media": True, "imported": False}}})
    check("함께 보낼 것이 같으면 멈추지 않는다", ss.mismatches(pol, ss.read_peer(d)) == {})
    # 외부 폴더는 폴더마다 따로
    put_peer(d, {"ext": {fa: sp.PC2MOBILE, fb: sp.MOBILE2PC}})
    diff = ss.mismatches(pol, ss.read_peer(d))
    check("방향이 다른 외부 폴더만 멈춘다(같은 것은 그대로)", list(diff) == [ma])
    put_peer(d, {"notes": {"direction": sp.BOTH}, "ext": {fa: sp.OFF}})
    check("노트 폴더와 외부 폴더가 함께 다르면 둘 다 멈춘다", set(ss.mismatches(pol, ss.read_peer(d))) == {"markdown", ma})
    # 컴퓨터가 폰 값에 맞추면 풀린다
    sp.set_simple(pol, direction=sp.BOTH)
    sp.set_direction(pol, ma, sp.OFF)
    check("컴퓨터를 폰에 맞추면 멈춤이 풀린다", ss.mismatches(pol, ss.read_peer(d)) == {})
    # 알 수 없는 값·폴더는 무시
    put_peer(d, {"notes": {"direction": "zzz"}, "ext": {"inn-xxxx-ext-ffffffff": sp.OFF, fa: "zzz"}})
    check("알 수 없는 값·폴더는 무시한다", ss.mismatches(pol, ss.read_peer(d)) == {})
    # 옛 방식 정책은 맞춰 볼 것이 없다
    legacy = sp.new_legacy_policy()
    put_peer(d, {"notes": {"direction": sp.OFF}})
    check("옛 방식 정책은 멈추지 않는다", ss.own(legacy) is None and ss.mismatches(legacy, ss.read_peer(d)) == {} and ss.write_own(d, legacy) is False)

    # 폴더 계획: 설정 폴더는 항상 양방향
    plans = sp.plan(pol, d, "pc", {}, os.path.join(d, "cfg"))
    cfg = [p for p in plans if p["module"] == "control"]
    check("설정 폴더는 항상 양방향", len(cfg) == 1 and cfg[0]["type"] == "sendreceive" and "-cfg-" in cfg[0]["id"])
    check("설정 폴더 ID 규칙(폰과 같음)", cfg[0]["id"] == ss.control_id(pol))
    check("경로를 안 주면 만들지 않음", not [p for p in sp.plan(pol, d, "pc", {}) if p["module"] == "control"])
    plan = {"tiers": [{"files": ["a.md", ".resources/x.png"]}, {"files": ["b.md", ".resources/y.png", ".resources/z.png"]}]}
    check("총수를 적음(글 2·그림 3)", ss.write_totals(d, plan) and json.load(open(os.path.join(d, ss.TOTALS_FILE))) == {"notesAll": 2, "mediaAll": 3})
    check("같으면 다시 쓰지 않음", ss.write_totals(d, plan) is False)
print("통과 %d / %d" % (TOTAL - fails, TOTAL) if fails == 0 else "실패 %d" % fails)
sys.exit(1 if fails else 0)
