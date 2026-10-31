"""최근부터 단계별로 보내기: 아직 열지 않은 단계의 파일을 컴퓨터 쪽 무시 목록으로 가려서 폰이 받지 못하게 하고,
폰이 지금 단계를 다 받으면 다음 단계를 연다. (폰이 긴 무시 목록을 처리하다 멈추던 문제를 피하려고 가림을 컴퓨터가 맡는다)
단계 목록은 stages.py 가 만든 .sync/stages.json. 열린 단계 수는 이 컴퓨터의 설정(config.json)에만 둔다."""
import json
import os
import time
import urllib.parse

import stages
import store as st
import syncpolicy as sp

HOLD = 20        # '다 받음'이 이만큼(초) 이어져야 다음 단계를 연다
COOLDOWN = 60    # 방금 연 뒤에는 이만큼(초) 기다린다(폰이 새 목록을 반영하기 전의 낡은 '다 받음'에 속지 않게)

_cache = {"path": None, "mtime": None, "plan": None}


def load_plan(root):
    path = os.path.join(root, ".sync", "stages.json")
    try:
        m = os.path.getmtime(path)
    except OSError:
        return None
    if _cache["path"] == path and _cache["mtime"] == m:
        return _cache["plan"]
    try:
        with open(path, encoding="utf-8") as fh:
            plan = json.load(fh)
    except (OSError, ValueError):
        return None
    _cache.update(path=path, mtime=m, plan=plan)
    return plan


def enabled(policy):
    return sp.is_simple(policy) and policy.get("simple", {}).get("staged", True)


def released():
    return max(1, int(st.read_config().get("stagesReleased", 1)))


def extra_ignore(root, policy):
    """열지 않은 단계의 파일을 가리는 무시 줄들(없으면 [])"""
    if not enabled(policy):
        return []
    plan = load_plan(root)
    return stages.ignore_lines(plan, released()) if plan else []


def apply_plans(plans, root, policy):
    """sp.plan 의 결과 중 노트 폴더 항목의 무시 목록에 가림 줄을 더한다(원래 목록은 바꾸지 않고 복사본을 돌려준다)"""
    extra = extra_ignore(root, policy)
    if not extra:
        return plans
    return [dict(p, ignore=list(p["ignore"]) + extra) if p.get("module") == "markdown" else p for p in plans]


def decide(r, total, done, since, last, now):
    """다음 단계로 갈지 정하는 순수 계산 → (열린 단계 수, 새 since, 새 last)"""
    if r >= total or not done:
        return r, 0, last
    if now - last < COOLDOWN:
        return r, 0, last
    if since == 0:
        return r, now, last
    if now - since >= HOLD:
        return r + 1, 0, now
    return r, since, last


def peers_done(eng, folder_id):
    """연결된 기기가 하나 이상이고, 연결된 모든 기기가 이 폴더를 다 받았는가"""
    conns = (eng.api("/rest/system/connections") or {}).get("connections", {})
    me = eng.my_id()
    ids = [d["deviceID"] for d in eng.api("/rest/config")["devices"] if d["deviceID"] != me and conns.get(d["deviceID"], {}).get("connected")]
    if not ids:
        return False
    for i in ids:
        x = eng.api("/rest/db/completion?folder=%s&device=%s" % (urllib.parse.quote(folder_id), i), timeout=8) or {}
        if x.get("needItems", 1) != 0 or x.get("completion", 0) < 100:
            return False
    return True


def tick(eng, root, policy, plans_fn):
    """5초마다 한 번. 다음 단계를 열었으면 True(무시 목록을 다시 적용한 뒤)"""
    if not enabled(policy):
        return False
    plan = load_plan(root)
    if not plan:
        return False
    cfg = st.read_config()
    r = released()
    new_r, since, last = decide(r, len(plan["tiers"]), peers_done(eng, sp.folder_id(policy, "markdown")),
                                float(cfg.get("stagesSince", 0)), float(cfg.get("stagesLast", 0)), time.time())
    if new_r != r:
        st.write_config(stagesReleased=new_r, stagesSince=0, stagesLast=last)
        eng.apply(plans_fn())
        return True
    if since != float(cfg.get("stagesSince", 0)):
        st.write_config(stagesSince=since)
    return False
