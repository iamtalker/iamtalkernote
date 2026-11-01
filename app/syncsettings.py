"""컴퓨터와 폰의 동기화 규칙이 같은지 맞춰 본다: 방향·함께 보낼 것이 양쪽이 같아야 그 폴더를 동기화하고, 다르면 멈춘다.

설정만 담는 작은 폴더(항상 양방향, 종류 cfg)로 각자 자기 파일만 쓴다(서로 덮어쓰지 않는다 → '누가 더 나중에 바꿨나' 를 가릴 일이 없다).
 - pc-config.json    (컴퓨터가 씀) 컴퓨터의 지금 규칙 {"notes": {"direction": 방향, "include": {media: 참/거짓 …}}, "ext": {폴더 ID: 방향}}
 - phone-config.json (폰이 씀)   폰이 컴퓨터와 다르게 정한 것만 같은 모양으로(없는 항목은 컴퓨터를 따른다)
Syncthing 을 전혀 모르는 순수 계산이라 폰 앱 SyncSettings.kt 와 같은 규칙을 쓴다."""
import hashlib
import json
import os

import syncpolicy as sp
from i18n import tr

OWN_FILE = "pc-config.json"
PEER_FILE = "phone-config.json"


def control_dir():
    """이 컴퓨터의 설정 폴더(노트 폴더 밖, 앱 설정 옆)"""
    import store as st
    d = os.path.join(os.path.dirname(st.config_path()), "sync-control")
    os.makedirs(d, exist_ok=True)
    return d


def control_id(policy):
    """설정 폴더의 Syncthing ID(폰도 같은 규칙으로 알아본다: 종류 부분이 cfg)"""
    return "%s%s-cfg-%s" % (sp.ID_PREFIX, policy["vault"], hashlib.sha1(b"control").hexdigest()[:8])


def own(policy):
    """컴퓨터의 지금 규칙. 옛 방식 정책(모듈마다 방향)이면 None(맞춰 볼 것이 없다)"""
    if not sp.is_simple(policy):
        return None
    sm = policy["simple"]
    return {"notes": {"direction": sm.get("direction", sp.BOTH),
                      "include": {k: bool(sm.get("include", {}).get(k)) for k, _, _, _ in sp.SIMPLE_OPTIONS}},
            "ext": {sp.folder_id(policy, mid): m.get("direction", sp.OFF)
                    for mid, m in policy["modules"].items() if m.get("kind") == "external"}}


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


def write_own(directory, policy):
    """컴퓨터의 규칙을 설정 폴더에 적는다(내용이 같으면 다시 쓰지 않는다). 적었으면 True"""
    cur = own(policy)
    if cur is None:
        return False
    path = os.path.join(directory, OWN_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            if json.load(fh) == cur:
                return False
    except (OSError, ValueError):
        pass
    _dump(path, cur)
    return True


def read_peer(directory):
    """폰이 컴퓨터와 다르게 정한 것. 파일이 없거나 깨졌으면 {}(전부 컴퓨터를 따른다 = 옛 폰 앱도 멈추지 않는다)"""
    try:
        with open(os.path.join(directory, PEER_FILE), encoding="utf-8") as fh:
            s = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(s, dict):
        return {}
    out = {}
    notes = s.get("notes")
    if isinstance(notes, dict):
        n = {}
        if notes.get("direction") in sp.DIRECTIONS:
            n["direction"] = notes["direction"]
        if isinstance(notes.get("include"), dict):
            n["include"] = {k: bool(v) for k, v in notes["include"].items() if k in {o[0] for o in sp.SIMPLE_OPTIONS}}
        if n:
            out["notes"] = n
    if isinstance(s.get("ext"), dict):
        e = {k: v for k, v in s["ext"].items() if v in sp.DIRECTIONS}
        if e:
            out["ext"] = e
    return out


def mismatches(policy, peer):
    """컴퓨터와 폰의 규칙이 다른 모듈 {모듈 id: [어디가 어떻게 다른지 글 …]}. 노트 폴더는 'markdown', 외부 폴더는 'ext:…'.
    폰이 따로 정한 것이 없는 항목은 컴퓨터를 따르므로 같은 것으로 본다"""
    mine = own(policy)
    out = {}
    if mine is None or not peer:
        return out
    pn = peer.get("notes") or {}
    diffs = []
    if pn.get("direction") and pn["direction"] != mine["notes"]["direction"]:
        diffs.append(tr("방향(컴퓨터 / 폰): {0} / {1}").format(sp.LABELS[mine["notes"]["direction"]], sp.LABELS[pn["direction"]]))
    for key, label, _, _ in sp.SIMPLE_OPTIONS:
        if key in (pn.get("include") or {}) and pn["include"][key] != mine["notes"]["include"][key]:
            onoff = lambda v: tr("켬") if v else tr("끔")   # noqa: E731
            diffs.append(tr("{0}(컴퓨터 / 폰): {1} / {2}").format(label, onoff(mine["notes"]["include"][key]), onoff(pn["include"][key])))
    if diffs:
        out["markdown"] = diffs
    for mid, m in policy["modules"].items():
        if m.get("kind") != "external":
            continue
        theirs = (peer.get("ext") or {}).get(sp.folder_id(policy, mid))
        if theirs and theirs != m.get("direction", sp.OFF):
            out[mid] = [tr("방향(컴퓨터 / 폰): {0} / {1}").format(sp.LABELS[m.get("direction", sp.OFF)], sp.LABELS[theirs])]
    return out


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
    _dump(os.path.join(directory, TOTALS_FILE), new)
    return True
