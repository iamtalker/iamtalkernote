"""노트 저장소: 노트북 = 폴더, 노트 = .md 파일(제목 = 파일 이름). 위키나루의 md_name / md_title 규칙을 그대로 쓴다."""
import base64
import calendar
import hashlib
import json
import os
import threading
import re
import secrets
import sqlite3
import shutil
import sys
import time
from urllib.parse import unquote

from wikiconv.markdown import md_name, md_title

APP_NAME = "iamtalkernote"
HISTORY_DIR = ".history"   # 노트별 이전 버전(숨김 폴더라 노트북으로 보이지 않는다)
MEDIA_DIR = ".resources"   # 볼트 안의 숨김 첨부 폴더(노트북으로 보이지 않는다)
TRASH_DIR = ".trash"   # 앱 안의 휴지통(숨김 폴더). 지운 노트는 여기서 TRASH_DAYS 일 보관 뒤 완전히 지워진다
TRASH_DAYS = 30
LEGACY_MEDIA_DIR ="_resources"   # 조플린 마크다운 내보내기·이전 버전의 폴더 이름. 이전 전까지는 그대로 읽는다
ROOT_ID = "__root__"   # 클리퍼가 '기본'(저장 폴더 바로 아래)을 가리키는 이름


def config_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")


def read_config():
    """파일이 없으면 빈 설정. 다른 쓰레드가 바꿔치기하는 찰나에 잠겨 있으면 잠깐 기다렸다 다시 읽는다(빈 설정으로 잘못 읽고 그 위에 덮어쓰지 않게)"""
    for i in range(8):
        try:
            with open(config_path(), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            if i < 7:
                time.sleep(0.02)
    return {}


_cfg_lock = threading.RLock()   # 화면·동기화 시작 같은 여러 쓰레드가 동시에 설정을 쓰면 파일이 깨졌다


def write_config(**patch):
    """읽고 고쳐 쓰는 동안 잠그고, 임시 파일에 쓴 뒤 바꿔치기해서 읽는 쪽이 반쯤 쓴 파일을 보지 않게 한다"""
    with _cfg_lock:
        c = read_config()
        c.update(patch)
        path = config_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False)
        for i in range(10):   # 다른 곳이 읽는 중이면 윈도가 바꿔치기를 잠깐 거절한다
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if i == 9:
                    raise
                time.sleep(0.03)


def version_settings():
    """노트 버전 설정: keep = 노트당 보관 개수(0 이면 끔), minutes = 이 시간 안에 또 저장하면 새 버전을 만들지 않음"""
    v = read_config().get("versions", {})
    try:
        keep = max(0, min(200, int(v.get("keep", 10))))
    except (TypeError, ValueError):
        keep = 10
    try:
        minutes = max(0.0, float(v.get("minutes", 1)))
    except (TypeError, ValueError):
        minutes = 1.0
    if not v.get("enabled", True):
        keep = 0
    return {"keep": keep, "minutes": minutes, "enabled": bool(v.get("enabled", True)), "count": max(1, int(v.get("keep", 10) or 10))}


def clipper_token():
    t = read_config().get("clipToken")
    if not t:
        t = secrets.token_hex(24)
        write_config(clipToken=t)
    return t


def default_root():
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs if os.path.isdir(docs) else os.path.expanduser("~"), APP_NAME)


def recycle(path):
    """윈도 휴지통으로 보낸다(안 되면 삭제하지 않고 예외)."""
    if sys.platform != "win32":
        raise OSError("휴지통을 지원하지 않는 운영체제입니다")
    import ctypes
    from ctypes import wintypes

    class OP(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
    # FO_DELETE, FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    op = OP(None, 3, os.path.abspath(path) + "\0", None, 0x40 | 0x10 | 0x4 | 0x400, False, None, None)
    if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0 or os.path.exists(path):
        raise OSError("휴지통으로 보내지 못했습니다")


def decode(data):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return data.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace").replace("\r\n", "\n")


FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
TIME_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?")


def parse_time(s):
    """'2026-10-16 14:46:17Z' · '2026-10-16T14:46:17.000Z' · '2026-10-16 14:46' → epoch(초).
    Z/시차가 없으면 이 PC의 시각대로 읽는다. 읽지 못하면 None"""
    m = TIME_RE.search(s or "")
    if not m:
        return None
    y, mo, d, hh, mi, ss, tz = m.groups()
    parts = (int(y), int(mo), int(d), int(hh or 0), int(mi or 0), int(ss or 0))
    try:
        if tz:
            t = calendar.timegm(parts + (0, 0, 0))
            if tz != "Z":
                digits = tz[1:].replace(":", "")
                t -= (1 if tz[0] == "+" else -1) * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
            return float(t)
        return time.mktime(parts + (0, 0, -1))
    except (ValueError, OverflowError):
        return None


def parse_meta(body):
    """조플린 'Markdown + Front Matter' 내보내기의 머리말에서 날짜·URL·작성자·태그를 읽는다. 머리말이 없으면 빈 값.
    파일 날짜는 내보낸 시각으로 바뀌어 있어도, 머리말에는 원래 만든·고친 시각이 남아 있다."""
    out = {"created": None, "updated": None, "source": "", "author": "", "tags": [], "fm": False}
    if not body.startswith("---"):
        return out
    m = FM_RE.match(body)
    if not m:
        return out
    out["fm"] = True
    in_tags = False
    lines = m.group(1).split("\n")
    for i, line in enumerate(lines):
        line = line.rstrip("\r")
        mm = re.match(r"^([A-Za-z_]+):[ \t]*(.*)$", line)
        if mm:
            key, val = mm.group(1).lower(), mm.group(2).strip().strip("\"'")
            if re.fullmatch(r"[>|][+-]?", val):   # 긴 값은 다음 줄에 들여써 이어진다(source: >-)
                rest = []
                for nxt in lines[i + 1:]:
                    if nxt[:1] in (" ", "\t"):
                        rest.append(nxt.strip())
                    else:
                        break
                val = " ".join(rest).strip().strip("\"'")
            in_tags = key == "tags" and not val
            if key in ("created", "updated"):
                out[key] = parse_time(val)
            elif key in ("source", "author"):
                out[key] = val
            elif key == "tags" and val:
                out["tags"] = [t.strip().strip("\"'") for t in val.strip("[]").split(",") if t.strip()]
        elif in_tags:
            li = re.match(r"^\s*-\s*(.+)$", line)
            if li:
                out["tags"].append(li.group(1).strip().strip("\"'"))
    return out


def fm_edit_tags(body, fn):
    """머리말 tags 의 태그마다 fn(이름) 을 불러 이름을 바꾸거나(새 이름) 지운다(None 이나 빈 문자열) → (새 본문, 바뀐 태그 수)
    목록(`- 이름`)과 한 줄(`tags: [a, b]`) 두 모양을 다루고, 바꾼 결과가 같은 이름이 둘이 되면 뒤의 것은 뺀다.
    머리말의 다른 줄과 본문은 건드리지 않는다."""
    if not body.startswith("---"):
        return body, 0
    m = FM_RE.match(body)
    if not m:
        return body, 0
    changed, seen, in_tags, out = [0], set(), False, []

    def apply(name):
        new = fn(name.strip())
        if new != name.strip():
            changed[0] += 1
        return new

    for line in m.group(1).split("\n"):
        raw = line.rstrip("\r")
        eol = line[len(raw):]
        mm = re.match(r"^([A-Za-z_]+):([ \t]*)(.*)$", raw)
        if mm:
            key, sp, val = mm.groups()
            in_tags = key.lower() == "tags" and not val.strip()
            if key.lower() == "tags" and val.strip():
                v = val.strip()
                wrapped = v.startswith("[") and v.endswith("]")
                parts = []
                for it in (v[1:-1] if wrapped else v).split(","):
                    pm = re.match(r"^(\s*[\"']?)(.*?)([\"']?\s*)$", it)
                    if not (pm and pm.group(2)):
                        parts.append(it)
                        continue
                    new = apply(pm.group(2))
                    if new and new not in seen:
                        seen.add(new)
                        parts.append(pm.group(1) + new + pm.group(3))
                joined = ",".join(parts)
                line = f"{key}:{sp}" + (f"[{joined}]" if wrapped else joined) + eol
        elif in_tags:
            li = re.match(r"^(\s*-\s*[\"']?)(.+?)([\"']?\s*)$", raw)
            if li:
                new = apply(li.group(2))
                if not new or new in seen:   # 지우거나, 바꾸고 보니 이미 있는 태그면 줄을 뺀다
                    continue
                seen.add(new)
                line = li.group(1) + new + li.group(3) + eol
        out.append(line)
    if not changed[0]:
        return body, 0
    return body[:m.start(1)] + "\n".join(out) + body[m.end(1):], changed[0]


def format_like(epoch, sample):
    """머리말에 이미 있던 값과 같은 모양(UTC 'Z' / 'T' 구분 / 현지 시각)으로 시각을 적는다"""
    sample = sample.strip().strip("\"'")
    sep = "T" if re.match(r"\d{4}-\d{2}-\d{2}T", sample) else " "
    if sample.endswith("Z"):
        return time.strftime(f"%Y-%m-%d{sep}%H:%M:%S", time.gmtime(epoch)) + "Z"
    return time.strftime(f"%Y-%m-%d{sep}%H:%M:%S", time.localtime(epoch))


def fm_set(body, key, epoch):
    """머리말의 key(updated/created) 줄을 epoch 로 바꾼다 → (새 본문, 바꿨는가)"""
    if not body.startswith("---"):
        return body, False
    m = FM_RE.match(body)
    if not m:
        return body, False
    fm = m.group(1)
    mm = re.search(r"(?m)^" + key + r":[ \t]*(.*)$", fm)
    if not mm:
        return body, False
    new_fm = fm[:mm.start(1)] + format_like(epoch, mm.group(1)) + fm[mm.end(1):]
    return body[:m.start(1)] + new_fm + body[m.end(1):], True


def touch_updated(body):
    """저장할 때 머리말에 updated 가 있으면 지금 시각으로 갱신(조플린과 같은 동작)"""
    return fm_set(body, "updated", time.time())[0]


def note_source(body, meta=None):
    """노트의 원본 주소: 머리말 source, 없으면 클리퍼가 맨 위에 적는 '원본: <주소>'"""
    meta = meta or parse_meta(body)
    if meta["source"]:
        return meta["source"]
    m = re.search(r"(?m)^원본:\s*<?(https?://[^\s>]+)", body[:2000])
    return m.group(1) if m else ""


INDEX_VERSION = 6   # 색인 DB 의 판(태그·색인 방식이 바뀌면 올리면 새로 만든다)


class Note(dict):
    """노트 한 개의 요약(제목·위치·날짜·태그). 본문은 처음 쓸 때 파일에서 읽는다(n["body"]).
    n.read() 는 읽기만 하고 기억하지 않는다(여러 개를 훑을 때 메모리가 불어나지 않게)."""

    def __missing__(self, key):
        if key == "body":
            self["body"] = self.read()
            return self["body"]
        raise KeyError(key)

    def read(self):
        try:
            with open(self["path"], "rb") as fh:
                return decode(fh.read())
        except OSError:
            return ""


def _sql_cond(node, params):
    """검색식(AND/OR/NOT)을 SQL 조건으로 바꾼다. 본문은 소문자 UTF-8 덩어리로 색인해 두고 instr 로 찾는다."""
    if node[0] == "WORD":
        params.append(node[1].encode("utf-8"))
        return "instr(hay, ?) > 0"
    left, right = _sql_cond(node[1], params), _sql_cond(node[2], params)
    if node[0] == "AND":
        return f"({left} AND {right})"
    if node[0] == "OR":
        return f"({left} OR {right})"
    return f"({left} AND NOT {right})"   # NOT


IMG_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg"}
DATA_IMG = re.compile(r"data:image/[a-z+.\-]+;base64,[A-Za-z0-9+/=]+", re.I)


def embedded_images(body):
    """본문에 통째로 박힌(base64) 그림의 (개수, 글자 수)"""
    found = DATA_IMG.findall(body)
    return len(found), sum(len(x) for x in found)


def folder_name(title):
    """노트북 이름 → 폴더 이름 (md_name 에서 .md 를 뗀 것)"""
    return md_name(title)[:-3]


class Store:
    tagger = None   # 앱이 정해 준다: tagger(본문) -> 태그 집합

    def __init__(self, root=None):
        root = root or read_config().get("root")
        if not root or not os.path.isdir(root):
            root = default_root()
        os.makedirs(root, exist_ok=True)
        self.root = os.path.abspath(root)
        self._jlast = {}   # 변경 이력에 노트별로 마지막으로 적은 시각
        self.hide_system_dirs()

    def before_change(self, path):
        """노트 파일(또는 폴더)을 바꾸거나 지우거나 옮기기 직전에 부른다: 복원 지점이 그 바뀌기 전 내용을 보관해 둔다(on_change)"""
        cb = getattr(self, "on_change", None)
        if cb:
            cb(path)

    def set_root(self, root):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)
        write_config(root=self.root)
        self.hide_system_dirs()

    def hide_system_dirs(self):
        """볼트 안의 앱 전용 폴더(.history .snapshots .trash .resources)에 윈도 '숨김' 속성을 준다(이미 있는 것만)"""
        for name in (HISTORY_DIR, ".snapshots", TRASH_DIR, MEDIA_DIR):
            p = os.path.join(self.root, name)
            if os.path.isdir(p):
                self.hide_dir(p)

    @property
    def root_name(self):
        """저장 폴더 자신의 이름(노트북 목록에서 '기본' 대신 보여 준다). 드라이브 루트처럼 이름이 없으면 '기본'"""
        return os.path.basename(self.root.rstrip(os.sep + "/")) or "기본"

    def nb_dir(self, nb):
        p = os.path.abspath(os.path.join(self.root, nb))
        if p != self.root and not p.startswith(self.root + os.sep):
            raise ValueError("잘못된 경로")
        return p

    # ---- 노트북 (하위 노트북 = 하위 폴더. 경로는 항상 "a/b" 모양)
    def notebooks(self):
        """모든 노트북의 상대 경로(부모 바로 뒤에 자식이 오는 순서)"""
        out = []
        media = os.path.normcase(self.media_dir)

        def walk(rel):
            try:
                names = sorted(os.listdir(self.nb_dir(rel)), key=str.lower)
            except OSError:
                return
            for name in names:
                if name.startswith(".") or name == LEGACY_MEDIA_DIR:
                    continue
                path = f"{rel}/{name}" if rel else name
                if os.path.normcase(self.nb_dir(path)) == media:
                    continue
                if os.path.isdir(self.nb_dir(path)):
                    out.append(path)
                    walk(path)
        walk("")
        return out

    def create_notebook(self, name, parent=""):
        name = (name or "").strip()
        if not name:
            return None
        folder = folder_name(name)
        rel = f"{parent}/{folder}" if parent else folder
        os.makedirs(self.nb_dir(rel), exist_ok=True)
        return rel

    def delete_notebook(self, nb):
        self.to_trash(self.nb_dir(nb))

    # ---- 전체 변경 이력(저널): <볼트>/.history/journal.jsonl 에 한 줄씩. 노트별 버전과 달리 모든 노트의 변경을 시간순으로 본다.
    @property
    def journal_path(self):
        return os.path.join(self.root, HISTORY_DIR, "journal.jsonl")

    def journal(self, ev, path, to=None, detail=""):
        """ev: edit create delete restore rename move cleanup … path/to 는 볼트 기준 상대 경로. 실패해도 본 작업을 막지 않는다."""
        try:
            rel = os.path.relpath(path, self.root).replace("\\", "/") if os.path.isabs(path) else path
            if ev == "edit":   # 자동 저장은 자주 일어나므로 같은 노트는 1분에 한 번만 적는다
                last = self._jlast.get(rel, 0)
                if time.time() - last < 60:
                    return
                self._jlast[rel] = time.time()
            rec = {"t": round(time.time(), 1), "ev": ev, "path": rel}
            if to:
                rec["to"] = os.path.relpath(to, self.root).replace("\\", "/") if os.path.isabs(to) else to
            if detail:
                rec["d"] = detail
            os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)
            self.hide_dir(os.path.join(self.root, HISTORY_DIR))
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if os.path.getsize(self.journal_path) > 4_000_000:   # 너무 커지면 최근 2만 줄만 남긴다
                with open(self.journal_path, encoding="utf-8") as f:
                    lines = f.readlines()[-20000:]
                with open(self.journal_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
        except OSError:
            pass

    def journal_read(self, limit=5000):
        """최근 것부터 [{t, ev, path, to?, d?}]"""
        out = []
        try:
            with open(self.journal_path, encoding="utf-8") as f:
                for line in f.readlines()[-limit:]:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            pass
        out.reverse()
        return out

    def undo_event(self, rec):
        """변경 이력 한 줄(journal_read 의 항목)을 되돌린다 → 한 일을 설명하는 글. 못 하면 OSError(이유).
        수정: 그 저장 직전 버전(저널과 10초 안)으로 / 새 노트: 휴지통으로 / 삭제: 휴지통에서 복원 / 이름 바꿈·이동: 원래 이름·노트북으로"""
        ev, rel = rec["ev"], rec["path"]
        full = os.path.join(self.root, rel.replace("/", os.sep))
        if ev == "edit":
            if not os.path.isfile(full):
                raise OSError("이 노트는 지금 없습니다(삭제되었거나 이름이 바뀌었습니다).")
            near = [v for v in self.versions(full) if abs(v[0] - rec["t"]) <= 10]
            if not near:
                raise OSError("이 저장 직전의 버전이 없습니다(같은 노트의 잦은 저장은 버전을 간격을 두고 남기거나, 버전 기록이 꺼져 있었을 수 있습니다).")
            ts, _, fp = min(near, key=lambda v: abs(v[0] - rec["t"]))
            body = self.read_version(fp)
            self.snapshot(full, body, max(1, version_settings()["keep"]), 0)   # 지금 내용은 새 버전으로 남겨 다시 돌아올 수 있게
            self.save(full, body, versioned=False, ev="restore")
            return "%s 저장 직전의 내용으로 되돌렸습니다." % time.strftime("%H:%M:%S", time.localtime(ts))
        if ev == "create":
            if not os.path.isfile(full):
                raise OSError("이 노트는 지금 없습니다.")
            self.to_trash(full)
            return "새로 만든 노트를 휴지통으로 보냈습니다."
        if ev == "delete":
            if rel == ".":
                raise OSError("여러 파일을 한꺼번에 지운 항목은 파일 → 휴지통에서 복원하세요.")
            cands = [x for x in self.trash_items() if x["rel"] == rel and abs(x["deleted"] - rec["t"]) <= 10]
            if not cands:
                raise OSError("휴지통에 없습니다(이미 복원했거나 비웠습니다).")
            return "휴지통에서 복원했습니다: " + os.path.relpath(self.restore_trash(cands[0]["id"]), self.root)
        if ev in ("rename", "move") and rec.get("to"):
            cur = os.path.join(self.root, rec["to"].replace("/", os.sep))
            if not os.path.isfile(cur):
                raise OSError("바뀐 뒤의 노트가 지금 없습니다.")
            if ev == "rename":
                if os.path.exists(full):
                    raise OSError("원래 이름의 노트가 이미 있습니다.")
                _, new = self.rename(cur, md_title(os.path.basename(full)))
            else:
                new = self.move(cur, os.path.dirname(rel))
            return "원래대로 되돌렸습니다: " + os.path.relpath(new, self.root)
        raise OSError("이 종류의 변경은 이력에서 되돌릴 수 없습니다.")

    # ---- 휴지통: <볼트>/.trash/<번호>/{item, meta.json}. 지운 지 TRASH_DAYS 일이 지나면 시작할 때 완전히 지운다.
    @property
    def trash_dir(self):
        return os.path.join(self.root, TRASH_DIR)

    @property
    def trash_days(self):
        try:
            return max(0, int(read_config().get("trash_days", TRASH_DAYS)))
        except (TypeError, ValueError):
            return TRASH_DAYS

    def to_trash(self, path):
        """노트(파일)나 노트북(폴더)을 휴지통 폴더로 옮긴다. 원래 위치를 기억해 두어 복원할 수 있다."""
        path = os.path.abspath(path)
        rel = os.path.relpath(path, self.root).replace("\\", "/")
        if rel.startswith("..") or rel == ".":
            raise OSError("볼트 밖의 항목은 휴지통으로 보낼 수 없습니다")
        tid = "%d-%s" % (int(time.time() * 1000), secrets.token_hex(3))
        d = os.path.join(self.trash_dir, tid)
        os.makedirs(d)
        self.hide_dir(self.trash_dir)
        try:
            self.before_change(path)
            shutil.move(path, os.path.join(d, "item"))
            with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"rel": rel, "deleted": time.time(), "dir": os.path.isdir(os.path.join(d, "item"))}, f)
        except OSError:
            shutil.rmtree(d, ignore_errors=True)
            raise
        self.journal("delete", rel, detail="휴지통")

    def trash_files(self, paths, into, label=None):
        """여러 파일(예: 안 쓰는 그림)을 휴지통 항목 하나로 옮긴다. 복원하면 into 폴더 안으로 돌아간다 → 옮긴 개수"""
        paths = [p for p in paths if os.path.isfile(p)]
        if not paths:
            return 0
        into = os.path.abspath(into)
        tid = "%d-%s" % (int(time.time() * 1000), secrets.token_hex(3))
        d = os.path.join(self.trash_dir, tid)
        os.makedirs(os.path.join(d, "item"))
        self.hide_dir(self.trash_dir)
        moved = []
        try:
            for p in paths:
                rel = os.path.relpath(p, into)
                dst = os.path.join(d, "item", rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                self.before_change(p)
                shutil.move(p, dst)
                moved.append((p, dst))
            with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"rel": (label or "안 쓰는 미디어 파일") + " %d개" % len(moved), "deleted": time.time(), "dir": True, "into": into}, f)
            self.journal("delete", ".", detail=(label or "안 쓰는 미디어 파일") + " %d개" % len(moved))
        except OSError:
            for p, dst in moved:
                shutil.move(dst, p)
            shutil.rmtree(d, ignore_errors=True)
            raise
        return len(moved)

    def trash_items(self):
        """[{id, name, rel, deleted, dir, path}] 최근에 지운 것부터"""
        out = []
        try:
            ids = os.listdir(self.trash_dir)
        except OSError:
            return out
        for tid in ids:
            d = os.path.join(self.trash_dir, tid)
            try:
                with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                    m = json.load(f)
                out.append({"id": tid, "root": bool(m.get("root")), "rel": m["rel"] if m["rel"] != "." else "(저장 폴더 전체)", "name": md_title(os.path.basename(m["rel"])) if not m.get("dir") else os.path.basename(m["rel"]),
                            "deleted": float(m["deleted"]), "dir": bool(m.get("dir")), "into": m.get("into"), "path": os.path.join(d, "item")})
            except (OSError, ValueError, KeyError):
                continue
        out.sort(key=lambda x: -x["deleted"])
        return out

    def restore_trash(self, tid):
        """원래 자리로 되돌린다(같은 이름이 있으면 ' (복원)' 을 붙인다) → 복원된 경로"""
        it = next((x for x in self.trash_items() if x["id"] == tid), None)
        if not it:
            raise OSError("휴지통에 없는 항목입니다")
        if it["into"]:   # 파일 묶음: 원래 폴더 구조대로 되돌린다(같은 이름이 이미 있으면 그대로 둔다)
            for dp, _, fn in os.walk(it["path"]):
                for f in fn:
                    src = os.path.join(dp, f)
                    dst = os.path.join(it["into"], os.path.relpath(src, it["path"]))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.exists(dst):
                        shutil.move(src, dst)
            shutil.rmtree(os.path.join(self.trash_dir, tid), ignore_errors=True)
            return it["into"]
        if it["root"]:   # 저장 폴더 전체: 내용을 하나씩 되돌리고, 같은 이름이 이미 있으면 ' (복원)' 을 붙인다
            for x in os.listdir(it["path"]):
                dst = os.path.join(self.root, x)
                base, ext = os.path.splitext(dst)
                i = 0
                while os.path.exists(dst):
                    i += 1
                    dst = f"{base} (복원{'' if i == 1 else i}){ext}"
                shutil.move(os.path.join(it["path"], x), dst)
            shutil.rmtree(os.path.join(self.trash_dir, tid), ignore_errors=True)
            return self.root
        target = self.nb_dir(it["rel"]) if not it["dir"] else os.path.join(self.root, it["rel"].replace("/", os.sep))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        base, ext = os.path.splitext(target)
        i = 0
        while os.path.exists(target):
            i += 1
            target = f"{base} (복원{'' if i == 1 else i}){ext}"
        shutil.move(it["path"], target)
        shutil.rmtree(os.path.join(self.trash_dir, tid), ignore_errors=True)
        self.journal("restore", target, detail="휴지통에서")
        return target

    def delete_trash(self, tid):
        shutil.rmtree(os.path.join(self.trash_dir, tid), ignore_errors=True)

    def empty_trash(self):
        n = len(self.trash_items())
        shutil.rmtree(self.trash_dir, ignore_errors=True)
        return n

    def purge_trash(self):
        """보관 기간이 지난 항목을 완전히 지운다 → 지운 개수 (trash_days 가 0 이면 자동으로 지우지 않는다)"""
        days = self.trash_days
        if not days:
            return 0
        limit, n = time.time() - days * 86400, 0
        for it in self.trash_items():
            if it["deleted"] < limit:
                self.delete_trash(it["id"])
                n += 1
        return n

    def delete_root(self):
        """저장 폴더 전체를 휴지통으로 보내고 같은 이름의 빈 폴더를 다시 만든다.
        드라이브 루트나 사용자 폴더·문서·바탕화면·다운로드 자체는 실수로 지우지 않게 막는다."""
        p = os.path.abspath(self.root)
        home = os.path.expanduser("~")
        protected = {os.path.normcase(x) for x in (home, *(os.path.join(home, d) for d in ("Documents", "Desktop", "Downloads")))}
        if os.path.dirname(p) == p or os.path.normcase(p) in protected:
            raise ValueError("드라이브 루트나 사용자·문서·바탕화면·다운로드 폴더 자체는 통째로 삭제할 수 없습니다.\n"
                             "먼저 설정 > 폴더 설정에서 노트 전용 폴더로 바꾸세요.")
        # 폴더 자신은 그대로 두고 안의 내용(휴지통 폴더만 빼고)을 휴지통 항목 하나로 옮긴다
        names = [x for x in os.listdir(p) if x != TRASH_DIR]
        if not names:
            return
        tid = "%d-%s" % (int(time.time() * 1000), secrets.token_hex(3))
        d = os.path.join(self.trash_dir, tid)
        os.makedirs(os.path.join(d, "item"))
        self.hide_dir(self.trash_dir)
        moved = []
        try:
            for x in names:
                self.before_change(os.path.join(p, x))
                shutil.move(os.path.join(p, x), os.path.join(d, "item", x))
                moved.append(x)
            with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"rel": ".", "deleted": time.time(), "dir": True, "root": True}, f)
            self.journal("delete", ".", detail="저장 폴더 전체")
        except OSError:
            for x in moved:   # 도중에 실패하면 제자리로
                shutil.move(os.path.join(d, "item", x), os.path.join(p, x))
            shutil.rmtree(d, ignore_errors=True)
            raise

    # ---- 노트
    # ---- 색인 DB (SQLite). 노트 파일(.md)이 원본이고, DB 는 언제든 다시 만들 수 있는 요약·검색용 사본이다.
    @property
    def index_path(self):
        key = hashlib.sha1(os.path.normcase(self.root).encode("utf-8")).hexdigest()[:12]
        return os.path.join(os.path.dirname(config_path()), f"index-{key}.db")

    def _db(self):
        conn = sqlite3.connect(self.index_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        ver = conn.execute("SELECT v FROM meta WHERE k='version'").fetchone()
        if not ver or ver[0] != str(INDEX_VERSION):
            conn.execute("DROP TABLE IF EXISTS notes")
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (str(INDEX_VERSION),))
        conn.execute("CREATE TABLE IF NOT EXISTS notes (path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, "
                     "updated REAL, created REAL, tags TEXT, hay BLOB)")
        conn.commit()
        return conn

    def key_of(self, path):
        return os.path.relpath(path, self.root).replace("\\", "/")

    def _index_row(self, key, stt, body, title):
        meta = parse_meta(body)
        tags = sorted(self.tagger(body)) if self.tagger else sorted(meta["tags"])
        text = DATA_IMG.sub(" ", body) if "base64," in body else body   # 그림 데이터는 검색 대상이 아니다
        hay = (title + "\n" + text).lower().encode("utf-8", "ignore")
        return (key, stt.st_size, stt.st_mtime_ns, meta["updated"], meta["created"], json.dumps(tags, ensure_ascii=False), hay)

    def index_one(self, path, body=None):
        """노트 하나의 색인을 지금 파일 상태로 갱신한다(저장 직후)"""
        try:
            stt = os.stat(path)
            if body is None:
                with open(path, "rb") as fh:
                    body = decode(fh.read())
            row = self._index_row(self.key_of(path), stt, body, md_title(os.path.basename(path)))
            conn = self._db()
            try:
                conn.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?,?,?)", row)
                conn.commit()
            finally:
                conn.close()
        except (OSError, sqlite3.Error):
            pass   # 색인 갱신 실패가 저장을 막지 않게(다음에 목록을 읽을 때 다시 맞춘다)

    def query_hits(self, node, words, scoring=False):
        """검색식에 맞는 노트를 DB 안에서 찾는다 → {경로키: 점수}. scoring=True 면 관련도(글자 수 대비 단어 밀도)도 계산"""
        params = []
        cond = _sql_cond(node, params)
        conn = self._db()
        try:
            if not scoring:
                return {k: 0.0 for (k,) in conn.execute(f"SELECT path FROM notes WHERE {cond}", params)}
            ws = [w for w in words if w]
            hits = {}
            for k, hay in conn.execute(f"SELECT path, hay FROM notes WHERE {cond}", params):
                text = bytes(hay).decode("utf-8", "ignore")
                hits[k] = 1000 * sum(text.count(w) for w in ws) / max(1, len(text))
            return hits
        finally:
            conn.close()

    def list_notes(self, nb, tagger=None, progress=None):
        """nb == '*' 이면 모든 노트, '' 이면 저장 폴더 바로 아래, 그 밖은 그 노트북과 하위 노트북의 노트.
        본문은 읽지 않는다. 전체 목록('*')은 색인 DB 와 비교해서, 크기·수정 시각이 그대로인 파일은 다시 읽지 않고
        바뀌었거나 새로 생긴 파일만 읽어 색인한다(노트가 수만 개여도 시작이 빠르다).
        progress(읽은 수, 읽을 총 수) 는 처음 색인을 만들 때 진행 상황을 알린다."""
        books = self.notebooks()
        if nb == "*":
            scopes = [""] + books
        elif nb == "":
            scopes = [""]
        else:
            scopes = [nb] + [b for b in books if b.startswith(nb + "/")]
        tagger = tagger or self.tagger
        full = nb == "*"
        entries = []
        for s in scopes:
            try:
                it = os.scandir(self.nb_dir(s))
            except OSError:
                continue
            with it:
                for e in it:
                    if not e.name.lower().endswith(".md"):
                        continue
                    try:
                        if not e.is_file():
                            continue
                        entries.append((f"{s}/{e.name}" if s else e.name, s, e.name, e.path, e.stat()))
                    except OSError:
                        continue
        info, conn = {}, None
        if full:
            conn = self._db()
            try:
                cached = {k: (sz, mt, u, c, tg) for k, sz, mt, u, c, tg in
                          conn.execute("SELECT path, size, mtime_ns, updated, created, tags FROM notes")}
                misses = []
                for key, s, name, path, stt in entries:
                    ent = cached.get(key)
                    if ent and ent[0] == stt.st_size and ent[1] == stt.st_mtime_ns:
                        info[key] = (ent[2], ent[3], set(json.loads(ent[4])))
                    else:
                        misses.append((key, name, path, stt))
                batch = []
                for i, (key, name, path, stt) in enumerate(misses, 1):
                    try:
                        with open(path, "rb") as fh:
                            body = decode(fh.read())
                    except OSError:
                        continue
                    row = self._index_row(key, stt, body, md_title(name))
                    batch.append(row)
                    info[key] = (row[3], row[4], set(json.loads(row[5])))
                    if len(batch) >= 200:
                        conn.executemany("INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?,?,?)", batch)
                        conn.commit()
                        batch = []
                    if progress and (i % 50 == 0 or i == len(misses)):
                        progress(i, len(misses))
                if batch:
                    conn.executemany("INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?,?,?)", batch)
                stale = set(cached) - {x[0] for x in entries}
                if cached:   # 처음 색인이 아닐 때: 앱이 모르는 사이 바뀐 노트를 기록한다(앱이 저장·이동한 건 색인에 그때그때 반영되어 여기 걸리지 않는다)
                    self.note_external([m for m in misses if m[0] in cached], stale)
                if stale:
                    conn.executemany("DELETE FROM notes WHERE path=?", [(k,) for k in stale])
                conn.commit()
            finally:
                conn.close()
        out = []
        for key, s, name, path, stt in entries:
            if full and key not in info:
                continue   # 읽지 못한 파일
            upd, cre, tags = info.get(key, (None, None, set()))
            out.append(Note(nb=s, key=key, title=md_title(name), path=path, size=stt.st_size, file_mtime=stt.st_mtime,
                            mtime=upd or stt.st_mtime,                                  # 수정 시각: 머리말 updated, 없으면 파일
                            ctime=cre or getattr(stt, "st_birthtime", stt.st_ctime),    # 생성 시각: 머리말 created, 없으면 파일
                            tags=tags))
        return out

    def note_external(self, changed, gone):
        """앱 밖에서(다른 편집기·동기화 도구) 고친 노트와 사라진 노트를 변경 이력에 적는다. 바뀌기 전 내용은 앱이 볼 기회가 없어 되돌릴 수 없지만,
        고친 뒤의 내용은 노트 버전으로 남겨 두어서(200개까지) 이후에 앱에서 고쳐도 그 상태로 돌아올 수 있게 한다."""
        last, moved = {}, set()   # 앱이 직접 한 일은 이력에 있으므로 거른다: 노트별 마지막 기록 시각 / 앱이 지우거나 옮긴 노트
        for r in reversed(self.journal_read(20000)):
            last[r["path"]] = r["t"]
            if r["ev"] in ("delete", "rename", "move"):
                moved.add(r["path"])
        changed = [m for m in changed if m[3].st_mtime > last.get(m[0], 0) + 5]
        gone = [k for k in gone if k not in moved]
        if len(changed) > 200:   # 동기화 도구가 한꺼번에 바꾼 경우: 개수만 적는다
            self.journal("external", ".", detail="앱 밖에서 노트 %d개 수정" % len(changed))
        else:
            v = version_settings()
            for key, name, path, stt in changed:
                self.journal("external", key, detail="앱 밖에서 수정")
                if v["keep"] > 0:
                    try:
                        self.snapshot(path, "", v["keep"], 0)   # 지금 파일 내용을 버전으로
                    except OSError:
                        pass
        if len(gone) > 200:
            self.journal("external", ".", detail="앱 밖에서 노트 %d개 사라짐" % len(gone))
        else:
            for key in sorted(gone):
                self.journal("external", key, detail="앱 밖에서 사라짐(지우기·이름 바꿈·이동)")

    def create_note(self, nb, title="제목 없음", body=""):
        d = self.nb_dir(nb)
        os.makedirs(d, exist_ok=True)
        name, i = title, 2
        while os.path.exists(os.path.join(d, md_name(name))):
            name = f"{title} ({i})"
            i += 1
        p = os.path.join(d, md_name(name))
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        self.journal("create", p)
        return {"nb": nb, "title": name, "path": p}

    def save(self, path, body, versioned=True, force=False, touch=True, ev="edit"):
        """저장. 버전 기능이 켜져 있으면 덮어쓰기 전의 내용을 이전 버전으로 남긴다.
        force=True 면 간격과 상관없이 남긴다(노트를 연 뒤 처음 고칠 때)."""
        v = version_settings()
        if touch:
            body = touch_updated(body)   # 머리말에 updated 가 있으면 지금 시각으로
        if versioned and v["keep"] > 0:
            try:
                self.snapshot(path, body, v["keep"], 0 if force else v["minutes"])
            except OSError:
                pass   # 버전 기록 실패가 저장을 막지 않게
        self.before_change(path)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        self.index_one(path, body)
        self.journal(ev, path)
        return body

    def set_dates(self, path, updated=None, created=None):
        """노트의 수정·생성 시각을 직접 바꾼다. 머리말에 그 줄이 있어야 파일 안에 남는다."""
        with open(path, "rb") as fh:
            body = decode(fh.read())
        new = body
        if updated is not None:
            new, _ = fm_set(new, "updated", updated)
        if created is not None:
            new, ok = fm_set(new, "created", created)
            if not ok:
                raise ValueError("이 노트에는 생성 시각을 적어 둘 머리말(created)이 없어서 바꿀 수 없습니다.")
        if new != body:
            self.before_change(path)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
        if updated is not None:
            os.utime(path, (updated, updated))
        self.index_one(path)

    def rename(self, path, new_title):
        """새 제목으로 파일 이름을 바꾼다 → (새 제목, 새 경로)"""
        d = os.path.dirname(path)
        base = (new_title or "").strip() or "제목 없음"
        target = os.path.join(d, md_name(base))
        if os.path.normcase(target) == os.path.normcase(path):
            return md_title(os.path.basename(path)), path
        n, i = base, 2
        while os.path.exists(os.path.join(d, md_name(n))):
            n = f"{base} ({i})"
            i += 1
        target = os.path.join(d, md_name(n))
        self.before_change(path)
        os.rename(path, target)
        self.move_history(path, target)
        self.journal("rename", path, to=target)
        return md_title(os.path.basename(target)), target

    def depth(self, nb):
        return len(nb.split("/")) if nb else 0

    def move(self, path, nb):
        """노트를 다른 노트북(폴더)으로 옮긴다 → 새 경로. 같은 이름이 있으면 (2) 를 붙이고, 그림 링크(_resources)를 새 위치에 맞춘다."""
        d = self.nb_dir(nb)
        os.makedirs(d, exist_ok=True)
        name = os.path.basename(path)
        base, i = md_title(name), 2
        target = os.path.join(d, name)
        if os.path.normcase(os.path.dirname(path)) == os.path.normcase(d):
            return path
        while os.path.exists(target):
            target = os.path.join(d, md_name(f"{base} ({i})"))
            i += 1
        self.before_change(path)
        os.rename(path, target)
        self.move_history(path, target)
        self.journal("move", path, to=target)
        try:   # 깊이가 달라졌으면 ../_resources/ 의 ../ 개수를 맞춘다
            with open(target, "rb") as fh:
                body = decode(fh.read())
            prefix = self.media_rel(d)
            name = re.escape(os.path.basename(self.media_dir))
            fixed = re.sub(r"(?<![\w/.])(?:\.\./)*" + name + "/", lambda m: prefix, body)
            if fixed != body:
                with open(target, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(fixed)
        except OSError:
            pass
        return target

    def extract_images(self, md, nb):
        """본문에 박힌 base64 그림을 <저장 폴더>/_resources/ 파일로 빼고 상대 경로로 바꾼다 → (새 본문, 옮긴 개수)"""
        res = self.media_dir
        rel = self.media_rel(self.nb_dir(nb))
        count = [0]

        def save(mime, b64):
            buf = base64.b64decode(b64)
            name = hashlib.sha1(buf).hexdigest()[:16] + "." + IMG_EXT.get(mime.lower(), "bin")
            self.ensure_media()
            with open(os.path.join(res, name), "wb") as f:
                f.write(buf)
            count[0] += 1
            return rel + name

        md = re.sub(r"(!\[[^\]]*\]\()data:(image/[a-z+.\-]+);base64,([A-Za-z0-9+/=]+)(\))",
                    lambda m: m.group(1) + save(m.group(2), m.group(3)) + m.group(4), md, flags=re.I)
        md = re.sub(r'(<img\b[^>]*?\bsrc=")data:(image/[a-z+.\-]+);base64,([A-Za-z0-9+/=]+)(")',
                    lambda m: m.group(1) + save(m.group(2), m.group(3)) + m.group(4), md, flags=re.I)
        return md, count[0]

    def delete_note(self, path):
        self.to_trash(path)

    # ---- 리소스(미디어) 폴더: 기본은 노트 폴더 안의 _resources, 노트 폴더와 같은 위치나 직접 지정도 가능
    def media_dir_for(self, mode, path=None):
        """mode: 'vault' = 볼트 안 .resources, 'default' = vault 이되 아직 이전 안 한 _resources 가 있으면 그것,
        'sibling'/'custom' = 예전 설정(이전 기능으로 vault 로 옮길 수 있다)"""
        if mode == "sibling":
            return os.path.join(os.path.dirname(self.root), LEGACY_MEDIA_DIR)
        if mode == "custom" and path:
            return os.path.abspath(path)
        new, old = os.path.join(self.root, MEDIA_DIR), os.path.join(self.root, LEGACY_MEDIA_DIR)
        if mode == "default" and not os.path.isdir(new) and os.path.isdir(old):
            return old
        return new

    @property
    def media_is_vault(self):
        return os.path.normcase(os.path.abspath(self.media_dir)) == os.path.normcase(os.path.join(self.root, MEDIA_DIR))

    def hide_dir(self, path):
        """윈도에서 폴더에 '숨김' 속성을 준다(탐색기에서 안 보이게)"""
        if sys.platform == "win32":
            try:
                import ctypes
                attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
                if attrs != -1:
                    ctypes.windll.kernel32.SetFileAttributesW(path, attrs | 2)
            except Exception:  # noqa: BLE001
                pass

    def ensure_media(self):
        res = self.media_dir
        os.makedirs(res, exist_ok=True)
        if os.path.basename(res) == MEDIA_DIR:
            self.hide_dir(res)
        return res

    @property
    def media_mode(self):
        return read_config().get("media", {}).get("mode", "default")

    @property
    def media_dir(self):
        m = read_config().get("media", {})
        return self.media_dir_for(m.get("mode", "default"), m.get("path"))

    def media_rel(self, note_dir):
        """노트가 있는 폴더에서 리소스 폴더까지의 상대 경로(끝에 /). 드라이브가 다르면 file:/// 주소"""
        res = self.media_dir
        try:
            return os.path.relpath(res, note_dir).replace("\\", "/") + "/"
        except ValueError:
            return "file:///" + res.replace("\\", "/") + "/"

    def count_media(self):
        try:
            return len(os.listdir(self.media_dir))
        except OSError:
            return 0

    def relink(self, old_dir, new_dir, progress=None, rename=None, dry=False, keep_md=False):
        """모든 노트에서 old_dir 안의 파일을 가리키는 그림·링크를 new_dir 쪽으로 고친다 → 고친 노트 수
        progress(읽은 노트 수, 전체 노트 수, 단계 이름) 으로 진행을 알린다.
        rename = {소문자 이전 이름: 새 이름} (옮기다 이름이 바뀐 최상위 항목), dry=True 면 파일은 건드리지 않고 고칠 노트 수만 센다."""
        old_n = os.path.normcase(os.path.abspath(old_dir))
        pat = re.compile(r'(\]\(|\bsrc=")([^)"\s]+)')
        changed = 0
        notes = self.list_notes("*")
        for i, n in enumerate(notes):
            if progress and i % 50 == 0:
                progress(i, len(notes), "2/2단계 — 노트의 그림 링크 고치는 중…")
            d = os.path.dirname(n["path"])

            def fix(m):
                target = m.group(2)
                if target.lower().startswith("file:///"):
                    cand = os.path.normpath(unquote(target[8:]))
                elif re.match(r"(?i)^[a-z][a-z0-9+.-]*:", target) and not re.match(r"^[A-Za-z]:[\\/]", target):
                    return m.group(0)   # http: 등 바깥 주소
                else:
                    cand = os.path.normpath(os.path.join(d, unquote(target)))
                nc = os.path.normcase(cand)
                if nc != old_n and not nc.startswith(old_n + os.sep):
                    return m.group(0)
                if keep_md and nc.endswith(".md"):
                    return m.group(0)   # 옮기지 않은 노트 파일을 가리키는 링크
                inner = os.path.relpath(cand, old_dir)
                if rename:
                    parts = inner.split(os.sep)
                    parts[0] = rename.get(parts[0].lower(), parts[0])
                    inner = os.sep.join(parts)
                new_path = os.path.join(new_dir, inner)
                try:
                    rel = os.path.relpath(new_path, d).replace("\\", "/")
                except ValueError:
                    rel = "file:///" + new_path.replace("\\", "/")
                return m.group(1) + rel
            text = n.read()
            body = pat.sub(fix, text)
            if body != text:
                if not dry:
                    self.before_change(n["path"])
                    with open(n["path"], "w", encoding="utf-8", newline="\n") as f:
                        f.write(body)
                changed += 1
        return changed

    def check_media_folder(self, old):
        """옮길 폴더로 쓸 수 있는지 검사한다 → 이유(문자열) 또는 None"""
        o, r, m = (os.path.normcase(os.path.abspath(x)) for x in (old, self.root, os.path.join(self.root, MEDIA_DIR)))
        if not os.path.isdir(old):
            return "폴더가 없습니다."
        if o == m:
            return "이미 .resources 폴더입니다."
        if o == r or r.startswith(o + os.sep):
            return "노트 폴더 전체이거나 그것을 품은 폴더는 고를 수 없습니다."
        if o.startswith(m + os.sep) or m.startswith(o + os.sep):
            return ".resources 와 서로 안에 들어 있는 폴더는 고를 수 없습니다."
        return None

    def preview_media_folder(self, old, progress=None):
        """폴더를 .resources 로 옮기면 → (옮길 항목 수, 링크가 바뀔 노트 수). 아무것도 바꾸지 않는다."""
        items = [e for e in os.listdir(old) if not e.lower().endswith(".md")]
        return len(items), self.relink(old, os.path.join(self.root, MEDIA_DIR), progress, dry=True, keep_md=True)

    def move_media_folder(self, old, progress=None):
        """임의의 폴더(이름은 사람마다 다르다)의 내용을 볼트의 .resources 로 옮기고 모든 노트의 링크를 고친 뒤,
        앞으로 저장할 리소스 폴더도 .resources 로 정한다. .md 노트는 옮기지 않고, 이름이 겹치면 번호를 붙인다. → (옮긴 항목 수, 고친 노트 수)"""
        why = self.check_media_folder(old)
        if why:
            raise ValueError(why)
        new = os.path.join(self.root, MEDIA_DIR)
        os.makedirs(new, exist_ok=True)
        self.hide_dir(new)
        entries = [e for e in os.listdir(old) if not e.lower().endswith(".md")]
        rename, moved = {}, 0
        for i, entry in enumerate(entries):
            if progress and i % 50 == 0:
                progress(i, len(entries), "1/2단계 — 파일 옮기는 중…")
            dst, stem, ext, k = os.path.join(new, entry), *os.path.splitext(entry), 1
            while os.path.exists(dst):
                dst = os.path.join(new, f"{stem}-{k}{ext}")
                k += 1
            if os.path.basename(dst) != entry:
                rename[entry.lower()] = os.path.basename(dst)
            shutil.move(os.path.join(old, entry), dst)
            moved += 1
        relinked = self.relink(old, new, progress, rename=rename, keep_md=True)
        write_config(media={"mode": "vault", "path": ""})
        try:
            os.rmdir(old)
        except OSError:
            pass
        return moved, relinked

    def set_media(self, mode, path=None, migrate=False, progress=None):
        """리소스 폴더를 바꾼다. migrate=True 면 기존 파일을 새 폴더로 옮기고 노트의 링크도 고친다 → (옮긴 파일 수, 고친 노트 수)"""
        old = self.media_dir
        new = self.media_dir_for(mode, path)
        on, nn = os.path.normcase(os.path.abspath(old)), os.path.normcase(os.path.abspath(new))
        if migrate and on != nn and (nn.startswith(on + os.sep) or on.startswith(nn + os.sep)):
            raise ValueError("새 폴더와 기존 리소스 폴더가 서로 안에 들어 있어 옮길 수 없습니다.")
        write_config(media={"mode": mode, "path": path or ""})
        moved = relinked = 0
        if migrate and on != nn and os.path.isdir(old):
            os.makedirs(new, exist_ok=True)
            if os.path.basename(new) == MEDIA_DIR:
                self.hide_dir(new)
            entries = os.listdir(old)
            for i, entry in enumerate(entries):
                if progress and i % 50 == 0:
                    progress(i, len(entries), "1/2단계 — 리소스 파일 옮기는 중…")
                dst = os.path.join(new, entry)
                if not os.path.exists(dst):
                    shutil.move(os.path.join(old, entry), dst)
                    moved += 1
            relinked = self.relink(old, new, progress)
            try:
                os.rmdir(old)
            except OSError:
                pass
        return moved, relinked

    # ---- 노트 버전(이전 내용). <저장 폴더>/.history/<노트 경로의 해시>/<밀리초>.md
    def hist_dir(self, path):
        rel = os.path.relpath(path, self.root).replace("\\", "/").lower()
        return os.path.join(self.root, HISTORY_DIR, hashlib.sha1(rel.encode("utf-8")).hexdigest()[:20])

    def versions(self, path):
        """[(시각(초), 글자 수, 파일 경로)] 최신순"""
        d = self.hist_dir(path)
        out = []
        try:
            names = os.listdir(d)
        except OSError:
            return out
        for f in names:
            if f.endswith(".md") and f[:-3].isdigit():
                fp = os.path.join(d, f)
                try:
                    out.append((int(f[:-3]) / 1000, os.path.getsize(fp), fp))
                except OSError:
                    pass
        return sorted(out, reverse=True)

    def read_version(self, fp):
        with open(fp, "rb") as fh:
            return decode(fh.read())

    def delete_version(self, fp):
        os.remove(fp)

    def prune(self, path, keep):
        for _, _, fp in self.versions(path)[max(keep, 0):]:
            try:
                os.remove(fp)
            except OSError:
                pass

    def snapshot(self, path, new_body, keep, minutes):
        """지금 파일에 있는 내용(= 덮어쓰기 전)을 새 내용과 다르면 버전으로 남긴다. 마지막 버전이 minutes 분 안이면 건너뛴다."""
        try:
            with open(path, "rb") as fh:
                old = decode(fh.read())
        except OSError:
            return False
        if old == new_body or not old.strip():
            return False
        existing = self.versions(path)
        if existing and minutes > 0 and time.time() - existing[0][0] < minutes * 60:
            return False
        d = self.hist_dir(path)
        os.makedirs(d, exist_ok=True)
        self.hide_dir(os.path.join(self.root, HISTORY_DIR))
        with open(os.path.join(d, f"{int(time.time() * 1000)}.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(old)
        self.prune(path, keep)
        return True

    def move_history(self, old_path, new_path):
        """노트 이름이 바뀌거나 옮겨지면 버전 기록도 따라간다."""
        a, b = self.hist_dir(old_path), self.hist_dir(new_path)
        if a != b and os.path.isdir(a) and not os.path.exists(b):
            try:
                os.rename(a, b)
            except OSError:
                pass
