"""복원 지점: 어느 시점의 모든 노트(.md)를 기억해 두었다가 그 상태로 되돌린다(윈도의 복원 지점처럼).

노트 내용은 내용 해시(sha1)로 한 번만 압축 보관하고(<볼트>/.snapshots/objects), 복원 지점은 "경로 → 해시" 목록
(<볼트>/.snapshots/points/<번호>.json.gz)만 가진다. 그래서 두 번째 지점부터는 그 사이 바뀐 노트만 공간을 차지한다.
그림·첨부(리소스 폴더)는 용량이 커서 넣지 않는다. 화면 코드가 없는 순수 로직이다."""
import gzip
import hashlib
import json
import os
import secrets
import time
import zlib

SNAP_DIR = ".snapshots"
KEEP_COUNT = 30     # 기본 보관: 최근 30개 이거나
KEEP_DAYS = 30      # 30일 안의 것(둘 중 하나라도 해당하면 보관)


class Snapshots:
    def __init__(self, store):
        self.store = store

    @property
    def base(self):
        return os.path.join(self.store.root, SNAP_DIR)

    @property
    def points_dir(self):
        return os.path.join(self.base, "points")

    @property
    def objects_dir(self):
        return os.path.join(self.base, "objects")

    # ---- 노트 파일 훑기
    def walk(self):
        """볼트 안 모든 노트 파일 → {상대 경로: 절대 경로}. 점으로 시작하는 폴더(.history .trash .snapshots .resources)와 _resources 는 뺀다"""
        root, out = self.store.root, {}
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if not d.startswith(".") and d != "_resources"]
            for f in fn:
                if f.lower().endswith(".md"):
                    p = os.path.join(dp, f)
                    out[os.path.relpath(p, root).replace("\\", "/")] = p
        return out

    def _obj(self, h):
        return os.path.join(self.objects_dir, h[:2], h[2:])

    def _put(self, h, raw):
        path = self._obj(h)
        if os.path.exists(path):
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(zlib.compress(raw, 6))
        os.replace(tmp, path)

    def _get(self, h):
        with open(self._obj(h), "rb") as f:
            return zlib.decompress(f.read())

    # ---- 복원 지점 목록
    def points(self):
        """[{id, created, label, count}] 최근 것부터"""
        out = []
        try:
            names = os.listdir(self.points_dir)
        except OSError:
            return out
        for name in names:
            if not name.endswith(".json.gz"):
                continue
            try:
                m = self.load(name[:-8], files=False)
                out.append({"id": name[:-8], "created": m["created"], "label": m.get("label", ""), "count": m.get("count", 0)})
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
    def scan(self, prev=None, progress=None, cancelled=lambda: False, store_objects=True):
        """지금 노트들의 {상대 경로: [해시, 크기, mtime_ns]}. 크기·수정 시각이 이전 지점과 같으면 다시 읽지 않는다."""
        prev_files = (prev or {}).get("files", {})
        cur, paths = {}, self.walk()
        total = len(paths)
        for i, (rel, path) in enumerate(paths.items()):
            if cancelled():
                return None
            if progress and i % 200 == 0:
                progress(i, total)
            try:
                st = os.stat(path)
                old = prev_files.get(rel)
                if old and old[1] == st.st_size and old[2] == st.st_mtime_ns and (not store_objects or os.path.exists(self._obj(old[0]))):
                    cur[rel] = old
                    continue
                with open(path, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            h = hashlib.sha1(raw).hexdigest()
            if store_objects:
                self._put(h, raw)
            cur[rel] = [h, st.st_size, st.st_mtime_ns]
        return cur

    def create(self, label="", progress=None, cancelled=lambda: False, force=False):
        """복원 지점을 만든다 → 지점 id (바뀐 게 없고 force 가 아니면 가장 최근 지점의 id)"""
        pts = self.points()
        prev = self.load(pts[0]["id"]) if pts else None
        files = self.scan(prev, progress, cancelled)
        if files is None:
            return None
        if prev and not force and {k: v[0] for k, v in files.items()} == {k: v[0] for k, v in prev["files"].items()}:
            return pts[0]["id"]
        pid = "%d-%s" % (int(time.time() * 1000), secrets.token_hex(2))
        os.makedirs(self.points_dir, exist_ok=True)
        self.store.hide_dir(self.base)
        tmp = os.path.join(self.points_dir, pid + ".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump({"created": time.time(), "label": label, "files": files}, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(self.points_dir, pid + ".json.gz"))
        return pid

    # ---- 비교·복원
    def diff(self, pid, progress=None, cancelled=lambda: False):
        """그 지점으로 되돌리면 어떻게 되는지 → {"change": [고쳐질 노트], "add": [되살릴 노트], "remove": [휴지통으로 갈 노트]} (상대 경로)"""
        m = self.load(pid)
        latest = self.points()
        base = self.load(latest[0]["id"]) if latest else None
        cur = self.scan(base, progress, cancelled, store_objects=False)
        if cur is None:
            return None
        pf = m["files"]
        return {"change": sorted(k for k in pf if k in cur and cur[k][0] != pf[k][0]),
                "add": sorted(k for k in pf if k not in cur),
                "remove": sorted(k for k in cur if k not in pf)}

    def restore(self, pid, progress=None, cancelled=lambda: False):
        """그 지점의 상태로 되돌린다(호출하는 쪽이 먼저 지금 상태의 지점을 만들어 둔다). → (되돌린 수, 되살린 수, 휴지통으로 보낸 수)"""
        m = self.load(pid)
        d = self.diff(pid, progress, cancelled)
        if d is None:
            return None
        root = self.store.root
        todo = d["change"] + d["add"]
        for i, rel in enumerate(todo):
            if progress and i % 100 == 0:
                progress(i, len(todo))
            h, size, mtime_ns = m["files"][rel]
            raw = self._get(h)
            path = os.path.join(root, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".restore.tmp"
            with open(tmp, "wb") as f:
                f.write(raw)
            os.replace(tmp, path)
            try:
                os.utime(path, ns=(mtime_ns, mtime_ns))
            except OSError:
                pass
        gone = [os.path.join(root, rel.replace("/", os.sep)) for rel in d["remove"]]
        if gone:
            self.store.trash_files(gone, root, label="복원 지점 뒤에 생긴 노트")   # 지점 뒤에 생긴 노트는 휴지통 항목 하나로(복원 가능)
        return len(d["change"]), len(d["add"]), len(gone)

    # ---- 지우기·정리
    def delete(self, pid):
        try:
            os.remove(os.path.join(self.points_dir, pid + ".json.gz"))
        except OSError:
            pass
        self.gc()

    def prune(self, count=KEEP_COUNT, days=KEEP_DAYS):
        """최근 count 개이거나 days 일 안인 지점만 남기고 지운다 → 지운 개수"""
        pts = self.points()
        limit = time.time() - days * 86400
        gone = [p for i, p in enumerate(pts) if i >= count and p["created"] < limit]
        for p in gone:
            try:
                os.remove(os.path.join(self.points_dir, p["id"] + ".json.gz"))
            except OSError:
                pass
        if gone:
            self.gc()
        return len(gone)

    def gc(self):
        """어느 지점에서도 쓰지 않는 보관 내용을 지운다 → 지운 개수"""
        used = set()
        for p in self.points():
            try:
                used.update(v[0] for v in self.load(p["id"])["files"].values())
            except (OSError, ValueError, KeyError):
                continue
        n = 0
        try:
            subs = os.listdir(self.objects_dir)
        except OSError:
            return 0
        for sub in subs:
            d = os.path.join(self.objects_dir, sub)
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
