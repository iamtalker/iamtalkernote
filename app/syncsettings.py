"""설정 양방향 맞추기: 컴퓨터(옵션 → 동기화)와 폰(설정 → 동기화)에서 방향·함께 보낼 것을 고치면 '더 최근에 바꾼 쪽'이 이긴다.

노트 폴더의 방향이 '컴퓨터 → 폰'이면 폰이 쓴 파일은 올라가지 못하므로, 설정만 담는 작은 폴더(항상 양방향)를 따로 둔다.
그 폴더의 settings.json = {"updated": 바꾼 시각(ms), "direction": 방향, "include": {media: 참/거짓 …}}.
정책 파일(.sync/policy.json)의 simple.updated 가 컴퓨터 쪽 시각이다. Syncthing 을 전혀 모르는 순수 계산이라 폰 앱 SyncSettings.kt 와 같은 규칙을 쓴다."""
import hashlib
import json
import os
import time

import syncpolicy as sp

FILE = "settings.json"


def control_dir():
    """이 컴퓨터의 설정 폴더(노트 폴더 밖, 앱 설정 옆)"""
    import store as st
    d = os.path.join(os.path.dirname(st.config_path()), "sync-control")
    os.makedirs(d, exist_ok=True)
    return d


def control_id(policy):
    """설정 폴더의 Syncthing ID(폰도 같은 규칙으로 알아본다: 종류 부분이 cfg)"""
    return "%s%s-cfg-%s" % (sp.ID_PREFIX, policy["vault"], hashlib.sha1(b"control").hexdigest()[:8])


def now_ms():
    return int(time.time() * 1000)


def snapshot(policy):
    sm = policy["simple"]
    return {"updated": int(sm.get("updated", 0)), "direction": sm.get("direction", sp.BOTH),
            "include": {k: bool(sm.get("include", {}).get(k)) for k, _, _, _ in sp.SIMPLE_OPTIONS}}


def read(directory):
    try:
        with open(os.path.join(directory, FILE), encoding="utf-8") as fh:
            s = json.load(fh)
        if isinstance(s, dict) and isinstance(s.get("updated"), int) and s.get("direction") in sp.DIRECTIONS:
            return s
    except (OSError, ValueError):
        pass
    return None


def write(directory, snap):
    os.makedirs(directory, exist_ok=True)
    p = os.path.join(directory, FILE)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, p)


def decide(local, remote):
    """local/remote: 설정(없으면 None) → 'pull'(상대 것을 따른다) · 'push'(내 것을 적는다) · None(같다)"""
    if remote is None:
        return "push"
    if remote["updated"] > local["updated"]:
        return "pull"
    if remote["updated"] < local["updated"]:
        return "push"
    return None


def adopt(policy, remote):
    """상대의 설정을 정책에 받아들인다(시각도 상대 것 그대로)"""
    sm = policy["simple"]
    sp.set_simple(policy, direction=remote["direction"], stamp=False, **{k: bool(v) for k, v in (remote.get("include") or {}).items()})
    sm["updated"] = int(remote["updated"])


def reconcile(policy, directory):
    """정책(컴퓨터)과 설정 폴더를 맞춘다. 돌려주는 값: 'pull'(정책이 바뀌었으니 저장·적용해야 함) · 'push' · None"""
    if not sp.is_simple(policy):
        return None
    remote = read(directory)
    what = decide(snapshot(policy), remote)
    if what == "pull":
        adopt(policy, remote)
    elif what == "push":
        write(directory, snapshot(policy))
    return what


TOTALS_FILE = "totals.json"


def write_totals(directory, plan):
    """폰이 '전체 N개 중 M개'를 보이도록 글·그림 총수를 설정 폴더에 적는다(내용이 같으면 다시 쓰지 않는다). 적었으면 True"""
    notes = sum(1 for t in plan["tiers"] for f in t["files"] if f.endswith(".md"))
    media = sum(1 for t in plan["tiers"] for f in t["files"] if not f.endswith(".md"))
    new = {"notesAll": notes, "mediaAll": media}
    try:
        with open(os.path.join(directory, TOTALS_FILE), encoding="utf-8") as fh:
            if json.load(fh) == new:
                return False
    except (OSError, ValueError):
        pass
    os.makedirs(directory, exist_ok=True)
    tmp = os.path.join(directory, TOTALS_FILE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(new, fh)
    os.replace(tmp, os.path.join(directory, TOTALS_FILE))
    return True
