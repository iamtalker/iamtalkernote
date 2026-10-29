"""복원 지점: 어느 시점의 모든 노트(.md)를 기억해 두었다가 그 상태로 되돌린다(윈도의 복원 지점처럼).

복원 지점은 "경로 → 해시" 목록(<볼트>/.snapshots/points/<번호>.json.gz, 노트 만 4천 개에 1MB 안팎)만 가진다.
노트의 내용은 지점을 만들 때 복사하지 않고, 앱이 그 노트를 **바꾸거나 지우거나 옮기기 직전에** 바뀌기 전 내용만
<볼트>/.snapshots/blobs/ 에 그대로(압축 없이) 복사해 둔다(preserve). 안 바뀐 노트는 파일 자체가 그 시점의 내용이라
공간을 쓰지 않는다. 되돌릴 때는 지금 파일이 지점과 같은지 해시로 비교해서 다른 것만 보관본으로 되돌린다.
앱 밖에서 직접 고친 노트는 바뀌기 전 내용을 복사할 기회가 없어 되돌릴 수 없고, 그런 노트는 건드리지 않고 알려 준다.
그림·첨부(저장 폴더 안의 .resources · _resources)는 기본으로 넣지 않고, 옵션(snap_media)을 켠 뒤에 만든 지점에만 넣는다
(지점이 media 표시를 가지고, 비교·복원은 그 지점의 표시를 따른다). 화면 코드가 없는 순수 로직이다."""
import gzip
import hashlib
import json
import os
import secrets
import threading
import time
import zlib

from store import read_config

SNAP_DIR = ".snapshots"
KEEP_COUNT = 30     # 기본 보관: 최근 30개 이거나
KEEP_DAYS = 30      # 30일 안의 것(둘 중 하나라도 해당하면 보관)


class Snapshots:
    def __init__(self, store):
        self.store = store
        self._lock = threading.Lock()
        self._latest = None     # 가장 최근 지점의 {상대 경로: [해시, 크기, mtime_ns]} 캐시

    @property
    def base(self):
        return os.path.join(self.store.root, SNAP_DIR)

    @property
    def points_dir(self):
        return os.path.join(self.base, "points")

    @property
    def blobs_dir(self):
        return os.path.join(self.base, "blobs")

    @property
    def objects_dir(self):   # 0.3.0 에서 만든 압축 보관(있으면 그대로 읽는다)
        return os.path.join(self.base, "objects")

    # ---- 노트 파일 훑기
    @staticmethod
    def media_on():
        return bool(read_config().get("snap_media", False))

    def walk(self, media=False):
        """볼트 안 모든 노트 파일 → {상대 경로: 절대 경로}. 점으로 시작하는 폴더(.history .trash .snapshots)는 뺀다.
        .resources · _resources 는 media=True 일 때만 그 안의 모든 파일을 넣고, 아니면 뺀다."""
        root, out = self.store.root, {}
        for dp, dn, fn in os.walk(root):
            in_media = os.path.basename(dp) in (".resources", "_resources") or any(
                x in (".resources", "_resources") for x in os.path.relpath(dp, root).split(os.sep))
            if in_media and not media:
                dn[:] = []
                continue
            dn[:] = [d for d in dn if (not d.startswith(".") or (media and d == ".resources")) and (media or d != "_resources")]
            for f in fn:
                if in_media or f.lower().endswith(".md"):
                    p = os.path.join(dp, f)
                    out[os.path.relpath(p, root).replace("\\", "/")] = p
        return out

    # ---- 보관본(blob)
    def _blob(self, h):
        return os.path.join(self.blobs_dir, h[:2], h[2:])

    def _legacy(self, h):
        return os.path.join(self.objects_dir, h[:2], h[2:])

    def has(self, h):
        return os.path.exists(self._blob(h)) or os.path.exists(self._legacy(h))

    def _put(self, h, raw):
        path = self._blob(h)
        if os.path.exists(path):
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.store.hide_dir(self.base)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, path)

    def _get(self, h):
        try:
            with open(self._blob(h), "rb") as f:
                return f.read()
        except OSError:
            with open(self._legacy(h), "rb") as f:
                return zlib.decompress(f.read())

    # ---- 바뀌기 직전 보관
    def _latest_files(self):
        with self._lock:
            if self._latest is None:
                pts = self.points()
                try:
                    self._latest = self.load(pts[0]["id"])["files"] if pts else {}
                except (OSError, ValueError, KeyError):
                    self._latest = {}
            return self._latest

    def preserve(self, path):
        """노트 파일(또는 노트북 폴더)을 바꾸거나 지우거나 옮기기 직전에 부른다. 그 파일이 가장 최근 복원 지점 때와 같은 상태이고
        아직 보관본이 없으면 그 내용을 복사해 둔다. 이미 바뀐 파일이나 지점이 없을 때는 아무것도 하지 않는다(실패해도 본 작업을 막지 않는다)."""
        try:
            path = os.path.abspath(path)
            if os.path.isdir(path):
                for dp, dn, fn in os.walk(path):
                    dn[:] = [d for d in dn if not d.startswith(".")]
                    for f in fn:
                        self._preserve_file(os.path.join(dp, f))
            else:
                self._preserve_file(path)
        except Exception:  # noqa: BLE001
            pass

    def _preserve_file(self, path):
        rel = os.path.relpath(path, self.store.root).replace("\\", "/")
        if rel.startswith(".."):
            return
        e = self._latest_files().get(rel)
        if not e:
            return
        st = os.stat(path)
        if st.st_size != e[1] or st.st_mtime_ns != e[2] or self.has(e[0]):
            return
        with open(path, "rb") as f:
            raw = f.read()
        self._put(hashlib.sha1(raw).hexdigest(), raw)

    # ---- 복원 지점 목록
    @staticmethod
    def _created(pid):
        try:
            return int(pid.split("-")[0]) / 1000.0
        except ValueError:
            return 0.0

    def points(self):
        """[{id, created, label, count}] 최근 것부터(목록은 작은 .meta.json 에서 읽어서 빠르다)"""
        out = []
        try:
            names = os.listdir(self.points_dir)
        except OSError:
            return out
        for name in names:
            if not name.endswith(".json.gz"):
                continue
            pid = name[:-8]
            try:
                try:
                    with open(os.path.join(self.points_dir, pid + ".meta.json"), encoding="utf-8") as f:
                        m = json.load(f)
                except (OSError, ValueError):
                    m = self.load(pid, files=False)
                out.append({"id": pid, "created": m.get("created") or self._created(pid), "label": m.get("label", ""), "count": m.get("count", 0)})
            except (OSError, ValueError, KeyError):
                continue
        out.sort(key=lambda x: -x["created"])
        return out

    def load(self, pid, files=True):
        with gzip.open(os.path.join(self.points_dir, pid + ".json.gz"), "rt", encoding="utf-8") as f:
            m = json.load(f)
        if not files:
            m["count"] = len(m.get("files", {}))
            m.pop("files", None)
        return m

    # ---- 만들기
    def scan(self, prev=None, progress=None, cancelled=lambda: False, media=False):
        """지금 노트들의 {상대 경로: [해시, 크기, mtime_ns]}. 크기·수정 시각이 이전 지점과 같으면 다시 읽지 않는다."""
        prev_files = prev if prev is not None else {}
        cur, paths = {}, self.walk(media)
        total = len(paths)
        for i, (rel, path) in enumerate(paths.items()):
            if cancelled():
                return None
            if progress and i % 200 == 0:
                progress(i, total)
            try:
                st = os.stat(path)
                old = prev_files.get(rel)
                if old and old[1] == st.st_size and old[2] == st.st_mtime_ns:
                    cur[rel] = old
                    continue
                with open(path, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            cur[rel] = [hashlib.sha1(raw).hexdigest(), st.st_size, st.st_mtime_ns]
        return cur

    def create(self, label="", progress=None, cancelled=lambda: False, force=False):
        """복원 지점을 만든다(노트 내용은 복사하지 않고 목록만 적는다) → 지점 id (바뀐 게 없고 force 가 아니면 가장 최근 지점의 id)"""
        pts = self.points()
        last = self.load(pts[0]["id"]) if pts else None
        prev = last["files"] if last else None
        media = self.media_on()
        files = self.scan(prev, progress, cancelled, media)
        if files is None:
            return None
        if prev is not None and not force and bool(last.get("media")) == media and {k: v[0] for k, v in files.items()} == {k: v[0] for k, v in prev.items()}:
            return pts[0]["id"]
        now = time.time()
        pid = "%d-%s" % (int(now * 1000), secrets.token_hex(2))
        os.makedirs(self.points_dir, exist_ok=True)
        self.store.hide_dir(self.base)
        tmp = os.path.join(self.points_dir, pid + ".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump({"created": now, "label": label, "media": media, "files": files}, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(self.points_dir, pid + ".json.gz"))
        with open(os.path.join(self.points_dir, pid + ".meta.json"), "w", encoding="utf-8") as f:
            json.dump({"created": now, "label": label, "count": len(files)}, f, ensure_ascii=False)
        with self._lock:
            self._latest = files
        return pid

    # ---- 비교·복원
    def diff(self, pid, progress=None, cancelled=lambda: False):
        """그 지점으로 되돌리면 어떻게 되는지 → {"change": 내용을 되돌릴 노트, "add": 되살릴 노트, "remove": 휴지통으로 갈 노트,
        "lost": 되돌려야 하지만 보관본이 없어 되돌릴 수 없는 노트(앱 밖에서 고친 노트)} (상대 경로)"""
        pt = self.load(pid)
        pf, media = pt["files"], bool(pt.get("media"))
        pts = self.points()
        base = self.load(pts[0]["id"])["files"] if pts else None
        cur = self.scan(base, progress, cancelled, media)
        if cur is None:
            return None
        change = sorted(k for k in pf if k in cur and cur[k][0] != pf[k][0])
        add = sorted(k for k in pf if k not in cur)
        lost = sorted(k for k in change + add if not self.has(pf[k][0]))
        return {"change": change, "add": add, "remove": sorted(k for k in cur if k not in pf), "lost": lost}

    def restore(self, pid, progress=None, cancelled=lambda: False):
        """그 지점의 상태로 되돌린다(호출하는 쪽이 먼저 지금 상태의 지점을 만들어 둔다) → (되돌린 수, 되살린 수, 휴지통으로 보낸 수, 못 되돌린 수)"""
        pf = self.load(pid)["files"]
        d = self.diff(pid, progress, cancelled)
        if d is None:
            return None
        root, lost = self.store.root, set(d["lost"])
        todo = [k for k in d["change"] + d["add"] if k not in lost]
        done_change = done_add = 0
        for i, rel in enumerate(todo):
            if progress and i % 100 == 0:
                progress(i, len(todo))
            h, size, mtime_ns = pf[rel]
            raw = self._get(h)
            path = os.path.join(root, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            existed = os.path.exists(path)
            if existed:
                self.preserve(path)   # 덮어쓰기 전에 지금 내용도 보관(직전에 만든 지점으로 되돌아올 수 있게)
            tmp = path + ".restore.tmp"
            with open(tmp, "wb") as f:
                f.write(raw)
            os.replace(tmp, path)
            try:
                os.utime(path, ns=(mtime_ns, mtime_ns))
            except OSError:
                pass
            if existed:
                done_change += 1
            else:
                done_add += 1
        gone = [os.path.join(root, rel.replace("/", os.sep)) for rel in d["remove"]]
        if gone:
            self.store.trash_files(gone, root, label="복원 지점 뒤에 생긴 노트")   # 지점 뒤에 생긴 노트는 휴지통 항목 하나로(복원 가능)
        return done_change, done_add, len(gone), len(lost)

    # ---- 지우기·정리
    def delete(self, pid):
        for ext in (".json.gz", ".meta.json"):
            try:
                os.remove(os.path.join(self.points_dir, pid + ext))
            except OSError:
                pass
        with self._lock:
            self._latest = None
        self.gc()

    def prune(self, count=KEEP_COUNT, days=KEEP_DAYS):
        """최근 count 개이거나 days 일 안인 지점만 남기고 지운다 → 지운 개수"""
        pts = self.points()
        limit = time.time() - days * 86400
        gone = [p for i, p in enumerate(pts) if i >= count and p["created"] < limit]
        for p in gone:
            for ext in (".json.gz", ".meta.json"):
                try:
                    os.remove(os.path.join(self.points_dir, p["id"] + ext))
                except OSError:
                    pass
        if gone:
            with self._lock:
                self._latest = None
            self.gc()
        return len(gone)

    def gc(self):
        """어느 지점에서도 쓰지 않는 보관본을 지운다 → 지운 개수"""
        used = set()
        for p in self.points():
            try:
                used.update(v[0] for v in self.load(p["id"])["files"].values())
            except (OSError, ValueError, KeyError):
                continue
        n = 0
        for root in (self.blobs_dir, self.objects_dir):
            try:
                subs = os.listdir(root)
            except OSError:
                continue
            for sub in subs:
                d = os.path.join(root, sub)
                try:
                    names = os.listdir(d)
                except OSError:
                    continue
                for name in names:
                    if sub + name not in used:
                        try:
                            os.remove(os.path.join(d, name))
                            n += 1
                        except OSError:
                            pass
                try:
                    os.rmdir(d)   # 비었으면
                except OSError:
                    pass
        return n

    def usage(self):
        """보관 중인 내용의 전체 크기(바이트)"""
        total = 0
        for dp, _, fn in os.walk(self.base):
            for f in fn:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
        return total
