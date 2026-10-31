"""최근부터 단계별로 받기: 노트를 머리말 날짜(updated, 없으면 created)로 시기별 단계로 나누고, 각 노트가 쓰는 그림을 같은 단계에 묶는다.

받는 폰은 이 목록(.sync/stages.json)을 보고 1단계(가장 최근)부터 열어 간다. 여러 노트가 같은 그림을 쓰면 가장 최근 단계에서 한 번만 받는다.
날짜를 못 읽은 노트는 방금 만든 것일 수 있으니 1단계로 둔다. 어떤 노트도 가리키지 않는 그림은 파일 수정 시각으로 나눈다.
Syncthing 의 newestFirst 는 파일 수정 시각 기준인데 가져온 노트는 모두 같은 시각이라 쓸 수 없어서 우리가 순서를 정한다."""
import json
import os
import re
import time
from urllib.parse import unquote

import store as st

VERSION = 1
DAY = 86400
# (이름, 지금부터 며칠 전까지) — 마지막은 나머지 전부
WINDOWS = [("최근 1개월", 30), ("최근 6개월", 183), ("최근 1년", 365), ("최근 3년", 3 * 365), ("그 이전", None)]
SKIP_DIRS = {".resources", ".history", ".snapshots", ".trash", ".imported", ".sync", ".syncthing"}
TOKEN = re.compile(r"[^\s()\[\]<>\"'`|]+")


def tier_of(t, now, windows=WINDOWS):
    """시각 t(epoch, 없으면 None) → 단계 번호(0부터). 없으면 0"""
    if t is None:
        return 0
    age = (now - t) / DAY
    for i, (_, days) in enumerate(windows):
        if days is None or age <= days:
            return i
    return len(windows) - 1


def note_date(path):
    """머리말의 updated·created 중 더 최근 것. 못 읽으면 None"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(4000).decode("utf-8", "replace")
    except OSError:
        return None
    if not head.startswith("---"):
        return None
    if "\n---" not in head[3:]:
        head += "\n---\n"
    m = st.parse_meta(head)
    ts = [t for t in (m["updated"], m["created"]) if t]
    return max(ts) if ts else None          # 최근에 고쳤거나 최근에 만든 것이 먼저


def build(vault, now=None, windows=WINDOWS, media=True):
    """볼트 → {"version", "made", "tiers": [{"name", "files": [상대경로…]}]}. 경로는 슬래시, 볼트 기준.
    노트(.md)와, 노트가 가리키는 .resources 파일을 단계에 넣는다(media=False 면 노트만)."""
    now = time.time() if now is None else now
    vault = os.path.normpath(vault)
    res_dir = os.path.join(vault, ".resources")
    files = {}                                   # 소문자 이름 → [상대경로…]
    if media and os.path.isdir(res_dir):
        for dp, _, fn in os.walk(res_dir):
            for f in fn:
                files.setdefault(f.lower(), []).append(os.path.relpath(os.path.join(dp, f), vault).replace(os.sep, "/"))
    stems = {}
    for n in files:
        stems.setdefault(os.path.splitext(n)[0], n)
    spaced = [n for n in files if " " in n]
    tiers = [[] for _ in windows]
    media_tier = {}                              # 이름 → 가장 이른(최근) 단계
    for dp, dn, fn in os.walk(vault):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".stfolder")]
        for f in fn:
            if not f.lower().endswith(".md"):
                continue
            full = os.path.join(dp, f)
            k = tier_of(note_date(full), now, windows)
            tiers[k].append(os.path.relpath(full, vault).replace(os.sep, "/"))
            if not files:
                continue
            try:
                with open(full, "rb") as fh:
                    text = fh.read().decode("utf-8", "replace").lower()
            except OSError:
                continue
            found = set()
            for t in set(TOKEN.findall(text)):
                t = unquote(t.split("#")[0].split("?")[0]).replace("\\", "/")
                b = t.rsplit("/", 1)[-1]
                if b in files:
                    found.add(b)
                elif b in stems:
                    found.add(stems[b])
            for n in spaced:
                if n in text:
                    found.add(n)
            for n in found:
                if n not in media_tier or k < media_tier[n]:
                    media_tier[n] = k
    for n, rels in files.items():
        if n in media_tier:
            k = media_tier[n]
            for r in rels:
                tiers[k].append(r)
        else:                                    # 어떤 노트도 안 쓰는 그림 → 파일 시각으로
            for r in rels:
                try:
                    t = os.path.getmtime(os.path.join(vault, r))
                except OSError:
                    t = None
                tiers[tier_of(t, now, windows) if t is not None else len(windows) - 1].append(r)
    return {"version": VERSION, "made": int(now),
            "tiers": [{"name": windows[i][0], "files": sorted(tiers[i])} for i in range(len(windows))]}


def sizes(vault, plan):
    """각 단계의 (파일 수, 바이트)"""
    out = []
    for t in plan["tiers"]:
        total = 0
        for r in t["files"]:
            try:
                total += os.path.getsize(os.path.join(vault, r))
            except OSError:
                pass
        out.append((len(t["files"]), total))
    return out


def save(vault, plan):
    d = os.path.join(vault, ".sync")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "stages.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)
    return p


def ignore_lines(plan, released):
    """폰이 아직 받지 않을 파일을 가리는 무시 목록: released 단계 수(1이면 1단계만 받음) 뒤의 단계 파일 전부.
    무시 패턴에서 뜻이 있는 글자(* ? [ ] { } 와 역슬래시)는 '아무 글자 하나'(?)로 바꾼다(윈도 Syncthing 은 역슬래시 이스케이프를 못 쓴다).
    폰 앱 Stages.kt 와 같은 규칙."""
    out = []
    for t in plan["tiers"][released:]:
        for r in t["files"]:
            out.append("/" + re.sub(r"[\\*?\[\]{}]", "?", r))
    return out
