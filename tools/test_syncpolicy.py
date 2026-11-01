"""동기화 정책(app/syncpolicy.py) 시험 — 엔진·화면 없이 순수 계산만 확인한다. 실행: py -3 tools/test_syncpolicy.py"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))
import syncpolicy as sp  # noqa: E402

root = tempfile.mkdtemp(prefix="sptest-")
try:
    # ---- 새 방식(기본): 폴더 하나, 양방향, 미디어·가져온 문서 요약만 함께
    p = sp.new_policy()
    assert sp.is_simple(p) and p["simple"]["direction"] == sp.BOTH
    plans = sp.plan(p, root, "pc")
    assert len(plans) == 1 and plans[0]["module"] == "markdown" and plans[0]["type"] == "sendreceive", plans
    ign = plans[0]["ignore"]
    assert "/.history" in ign and "/.trash" in ign and "/.snapshots" in ign, ign
    assert "/.resources" not in ign and "/.imported" in ign, ign          # 미디어는 함께 보내고, 예전 가져온 문서 요약(.imported)은 보내지 않는다
    assert plans[0]["path"] == os.path.abspath(root)
    # 두 기기가 같은 폴더 ID 를 쓴다
    assert sp.plan(p, root, "mobile")[0]["id"] == plans[0]["id"]

    # ---- 방향 하나로 바꾸기: PC→모바일, 모바일→PC, 안 함
    sp.set_simple(p, direction=sp.PC2MOBILE)
    assert sp.plan(p, root, "pc")[0]["type"] == "sendonly" and sp.plan(p, root, "mobile")[0]["type"] == "receiveonly"
    sp.set_simple(p, direction=sp.MOBILE2PC)
    assert sp.plan(p, root, "pc")[0]["type"] == "receiveonly" and sp.plan(p, root, "mobile")[0]["type"] == "sendonly"
    sp.set_simple(p, direction=sp.OFF)
    assert sp.plan(p, root, "pc") == []
    sp.set_simple(p, direction=sp.BOTH)

    # ---- 보낼 것 체크: 미디어를 빼면 제외 목록에 들어가고, 이력을 켜면 빠진다
    sp.set_simple(p, media=False, history=True)
    ign = sp.plan(p, root, "pc")[0]["ignore"]
    assert "/.resources" in ign and "/.history" not in ign and "/.trash" in ign, ign
    assert "/.snapshots" in sp.plan(p, root, "pc")[0]["ignore"]                # 복원 지점은 어떤 경우에도 제외
    sp.set_simple(p, media=True, history=False)

    # ---- 옛 폰 앱(1.3.x)이 읽는 modules 도 같은 뜻으로 채워진다
    assert p["modules"]["markdown"]["direction"] == sp.BOTH
    assert p["modules"]["media"]["direction"] == sp.BOTH and p["modules"]["history"]["direction"] == sp.OFF
    sp.set_simple(p, direction=sp.PC2MOBILE, media=False)
    assert p["modules"]["media"]["direction"] == sp.OFF and "imported" not in p["modules"]
    sp.set_simple(p, direction=sp.BOTH, media=True)

    # ---- 새 방식에서는 노트북을 따로 두지 못하고, 모듈별 방향 바꾸기는 무시된다
    assert sp.add_notebook(p, "업무", sp.MOBILE2PC) is None
    sp.set_direction(p, "media", sp.OFF)
    assert p["modules"]["media"]["direction"] == sp.BOTH and len(sp.plan(p, root, "pc")) == 1

    # ---- 외부 폴더는 새 방식에서도 따로(경로가 있어야 만든다)
    e = sp.add_external(p, "abc123", "자료", sp.PC2MOBILE)
    assert len(sp.plan(p, root, "pc")) == 1
    plans = {x["module"]: x for x in sp.plan(p, root, "pc", {"abc123": os.path.join(root, "x", "자료")})}
    assert plans[e]["type"] == "sendonly" and plans[e]["ignore"] == list(sp.COMMON_IGNORE) and plans["markdown"]["type"] == "sendreceive"
    sp.set_direction(p, e, sp.OFF)
    assert e not in {x["module"] for x in sp.plan(p, root, "pc", {"abc123": root})}

    # ---- 저장·읽기
    sp.save(root, p)
    q = sp.load(root)
    assert sp.is_simple(q) and q["vault"] == p["vault"] and q["simple"]["include"]["media"] is True
    # 깨진 파일 → 새 기본 정책(양방향)
    open(sp.path_of(root), "w").write("{broken")
    assert sp.load(root)["simple"]["direction"] == sp.BOTH

    # ---- 옛 정책은 그대로 읽히고 옛 방식으로 계산한다(전환 전에는 폴더가 바뀌지 않는다)
    old = sp.new_legacy_policy()
    sp.set_direction(old, "markdown", sp.PC2MOBILE)
    sp.set_direction(old, "media", sp.PC2MOBILE)
    sp.set_direction(old, "history", sp.PC2MOBILE)
    mid = sp.add_notebook(old, "업무", sp.MOBILE2PC)
    sp.save(root, old)
    old = sp.load(root)
    assert not sp.is_simple(old)
    ids = {x["module"] for x in sp.plan(old, root, "pc")}
    assert {"markdown", "media", "imported", "history", mid} <= ids and "trash" not in ids, ids
    before_ids = {x["module"]: x["id"] for x in sp.plan(old, root, "pc")}

    # ---- 전환: 지금의 방향을 그대로 이어받고, 사라지는 노트북을 알려 준다
    dropped = sp.to_simple(old)
    assert dropped == ["업무"] and not any(m["kind"] == "notebook" for m in old["modules"].values())
    assert old["simple"]["direction"] == sp.PC2MOBILE and old["simple"]["include"] == {"media": True, "history": True, "trash": False}
    plans = sp.plan(old, root, "pc")
    assert len(plans) == 1 and plans[0]["type"] == "sendonly" and plans[0]["id"] == before_ids["markdown"]   # 노트 폴더의 ID 는 그대로
    assert "/.trash" in plans[0]["ignore"] and "/.history" not in plans[0]["ignore"]
    sp.set_simple(old, direction=sp.BOTH)
    assert sp.plan(old, root, "pc")[0]["type"] == "sendreceive"
    # ---- 확정한 외부 폴더 방향 기억: 낡은 정책(옵션 창을 열 때 읽은 값)이 저장돼도 확정한 방향으로 되돌린다
    pe = sp.load(root)
    sp.add_external(pe, "x1", "이멋세", sp.PC2MOBILE)
    saved = sp.remembered_ext(pe)
    mid = [k for k, m in pe["modules"].items() if m["kind"] == "external"][0]
    assert saved == {mid: sp.PC2MOBILE}
    stale = json.loads(json.dumps(pe))
    stale["modules"][mid]["direction"] = sp.OFF
    assert sp.apply_remembered_ext(stale, saved) == 1 and stale["modules"][mid]["direction"] == sp.PC2MOBILE
    assert sp.apply_remembered_ext(stale, saved) == 0   # 이미 같으면 바꾸지 않음
    assert sp.apply_remembered_ext(stale, {"ext:없는것": sp.BOTH, mid: "엉터리"}) == 0   # 없는 모듈·잘못된 값은 무시
    assert sp.apply_remembered_ext(stale, None) == 0
    print("정책 시험 통과")
finally:
    shutil.rmtree(root, ignore_errors=True)
