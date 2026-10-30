"""동기화 정책: 어떤 데이터(모듈)를 어느 방향으로 맞출지. 전송 엔진(Syncthing)을 전혀 모르는 순수 계산이라
엔진을 바꿔도 정책 파일과 사용자 설정은 그대로 쓸 수 있다. 설계는 docs/sync-design.md.

정책 파일은 노트 폴더 안 `.sync/policy.json` 에 둔다(마크다운 모듈로 함께 전달돼 두 기기가 같은 정책을 본다).
기기마다 다른 것(로컬 경로)은 정책에 넣지 않고 plan() 에 인자로 받는다."""
import hashlib
import json
import os
import secrets

POLICY_DIR = ".sync"
POLICY_FILE = "policy.json"
MEDIA_DIR = ".resources"
IMPORTED_DIR = ".imported"
HISTORY_DIR = ".history"
TRASH_DIR = ".trash"

BOTH, PC2MOBILE, MOBILE2PC, OFF = "both", "pc2mobile", "mobile2pc", "off"
DIRECTIONS = (BOTH, PC2MOBILE, MOBILE2PC, OFF)
LABELS = {BOTH: "양방향", PC2MOBILE: "PC → 모바일", MOBILE2PC: "모바일 → PC", OFF: "동기화 안 함"}

# 내장 모듈: id, 이름, 노트 폴더 안 위치(None=노트 폴더 전체), 기본 방향
BUILTIN = (
    ("markdown", "Markdown 노트 전체", None, BOTH),
    ("media", "미디어(그림·첨부)", MEDIA_DIR, BOTH),
    ("imported", "가져온 문서 요약(폰 앱이 읽는 파일)", IMPORTED_DIR, PC2MOBILE),
    # 이력·휴지통은 파일이 아주 많아 문서보다 먼저 전송되면 문서가 늦어진다 → 따로 두고 기본은 끈다(문서가 다 맞춰진 뒤에 켠다)
    ("history", "변경 이력(.history) — 문서를 다 맞춘 뒤에 켜기", HISTORY_DIR, OFF),
    ("trash", "휴지통(.trash) — 문서를 다 맞춘 뒤에 켜기", TRASH_DIR, OFF),
)

# 어느 폴더에서나 동기화하지 않는 파일
COMMON_IGNORE = ("(?d)Thumbs.db", "(?d)desktop.ini", "(?d).DS_Store", "~*.tmp")

ID_PREFIX = "inn-"   # 이 앱이 만든 Syncthing 폴더만 알아보고 고치게 하는 표시


def new_policy():
    mods = {}
    for mid, label, rel, direction in BUILTIN:
        mods[mid] = {"kind": mid, "label": label, "direction": direction}
        if rel:
            mods[mid]["path"] = rel
    return {"version": 1, "vault": secrets.token_hex(4), "modules": mods}


def path_of(root):
    return os.path.join(root, POLICY_DIR, POLICY_FILE)


def load(root):
    """정책 파일을 읽는다. 없거나 깨졌으면 기본 정책(저장하지는 않는다)"""
    try:
        with open(path_of(root), encoding="utf-8") as f:
            p = json.load(f)
        if isinstance(p, dict) and isinstance(p.get("modules"), dict) and p.get("vault"):
            for mid, label, rel, direction in BUILTIN:   # 내장 모듈이 빠졌으면 채운다
                if mid not in p["modules"]:
                    p["modules"][mid] = {"kind": mid, "label": label, "direction": OFF if mid != "markdown" else direction}
                    if rel:
                        p["modules"][mid]["path"] = rel
            return p
    except (OSError, ValueError):
        pass
    return new_policy()


def save(root, policy):
    d = os.path.join(root, POLICY_DIR)
    os.makedirs(d, exist_ok=True)
    tmp = path_of(root) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(policy, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path_of(root))


def exists(root):
    return os.path.isfile(path_of(root))


def set_direction(policy, mid, direction):
    if direction in DIRECTIONS and mid in policy["modules"]:
        policy["modules"][mid]["direction"] = direction


def add_notebook(policy, rel, direction=BOTH):
    rel = rel.replace("\\", "/").strip("/")
    if not rel:
        return None
    mid = "nb:" + rel
    policy["modules"][mid] = {"kind": "notebook", "label": "노트북 · " + rel, "path": rel, "direction": direction}
    return mid


def add_external(policy, ext_id, name, direction=BOTH):
    mid = "ext:" + ext_id
    policy["modules"][mid] = {"kind": "external", "label": "외부 폴더 · " + name, "direction": direction}
    return mid


def remove(policy, mid):
    if policy["modules"].get(mid, {}).get("kind") in ("notebook", "external"):
        policy["modules"].pop(mid)


def folder_id(policy, mid):
    """Syncthing 폴더 ID. 기기마다 경로가 달라도 같은 ID 라서 같은 동기화 대상으로 이어진다"""
    return "%s%s-%s-%s" % (ID_PREFIX, policy["vault"], policy["modules"][mid].get("kind", "x")[:3],
                           hashlib.sha1(mid.encode("utf-8")).hexdigest()[:8])


def folder_type(direction, role):
    """role: 'pc' 또는 'mobile' — 이 기기가 어느 쪽인지. Syncthing 폴더 종류를 돌려준다(없으면 None=만들지 않음)"""
    if direction == BOTH:
        return "sendreceive"
    if direction == PC2MOBILE:
        return "sendonly" if role == "pc" else "receiveonly"
    if direction == MOBILE2PC:
        return "receiveonly" if role == "pc" else "sendonly"
    return None


def _rel(policy, mid):
    m = policy["modules"][mid]
    if m["kind"] == "markdown":
        return ""
    return (m.get("path") or "").replace("\\", "/").strip("/")


def plan(policy, root, role="pc", external_paths=None):
    """이 기기에서 만들어야 할 Syncthing 폴더 목록. 각 항목: id, label, path, type, ignore(줄 목록), module.
    - 방향이 '안 함'인 노트북·미디어도 상위 폴더가 그 안을 건드리지 않도록 상위의 제외 목록에는 들어간다.
    - 노트 폴더 안의 하위 모듈(미디어·노트북 등)은 상위 폴더(마크다운 전체)가 `/<경로>` 로 제외하고 따로 동기화한다.
    - 외부 폴더는 이 기기의 로컬 경로(external_paths: ext id → 경로)가 있어야 한다."""
    external_paths = external_paths or {}
    root = os.path.abspath(root)
    inside = {}   # 모듈 id → 노트 폴더 안 상대 경로(노트 폴더 안에 있는 것들)
    for mid, m in policy["modules"].items():
        if m["kind"] != "external":
            inside[mid] = _rel(policy, mid)
    out = []
    for mid, m in policy["modules"].items():
        typ = folder_type(m.get("direction", OFF), role)
        if typ is None:
            continue
        if m["kind"] == "external":
            ext_id = mid.split(":", 1)[1]
            p = external_paths.get(ext_id)
            if not p:
                continue
            path, rel = os.path.abspath(p), None
        else:
            rel = inside[mid]
            path = os.path.normpath(os.path.join(root, *rel.split("/"))) if rel else root
        ign = []
        if rel is not None:
            # 이 모듈 안에 들어 있는 다른 모듈은 따로 맡으므로(또는 안 하므로) 이 폴더에서는 뺀다
            for other, orel in inside.items():
                if other != mid and orel and (not rel or orel.startswith(rel + "/")):
                    # 가장 가까운 상위 모듈만 제외 목록을 가진다(손자까지 중복으로 넣지 않는다)
                    parents = [r for o, r in inside.items() if o != other and r and orel.startswith(r + "/") and (not rel or r.startswith(rel + "/") or r == rel)]
                    nearest = max(parents, key=len) if parents else rel
                    if nearest == rel:
                        ign.append("/" + (orel[len(rel) + 1:] if rel else orel))
        if m["kind"] == "markdown":
            ign.append("/.snapshots")   # 복원 지점은 PC 전용(크고 폰은 쓰지 않는다)
        ign.extend(COMMON_IGNORE)
        out.append({"id": folder_id(policy, mid), "label": m.get("label", mid), "path": path, "type": typ, "ignore": ign, "module": mid})
    return out


def summary(policy):
    """화면에 보일 요약(모듈 id, 이름, 방향 이름)"""
    return [(mid, m.get("label", mid), LABELS.get(m.get("direction"), "?")) for mid, m in policy["modules"].items()]
