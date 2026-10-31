"""즐겨찾기: 노트 파일은 건드리지 않고 설정 폴더(폰과 항상 양방향으로 맞추는 작은 폴더)의 작은 파일에 적는다.
충돌이 없도록 컴퓨터는 favorites-pc.json, 폰은 favorites-phone.json 만 자기가 쓰고, 읽을 때는 둘을 합쳐 노트마다 '더 최근에 바꾼 쪽'을 따른다.
형식: {"items": {"폴더/노트.md": [1 또는 0, 바꾼 시각(ms)]}}  (노트 경로는 노트 폴더 기준, 슬래시). 노트 이름을 바꾸거나 옮기면 그 노트의 즐겨찾기는 풀린다.
폰 앱 Favorites.kt 와 같은 규칙."""
import json
import os
import time

OWN = "favorites-pc.json"
OTHER = "favorites-phone.json"


def rel_of(root, path):
    """노트 파일 경로 → 노트 폴더 기준 상대 경로(슬래시)"""
    return os.path.relpath(path, root).replace(os.sep, "/")


def merge(*maps):
    """여러 {경로: [값, 시각]} 을 합친다: 경로마다 시각이 가장 늦은 것. 돌려주는 값: {경로: 값(bool)}"""
    best = {}
    for m in maps:
        for k, v in (m or {}).items():
            try:
                val, t = bool(v[0]), int(v[1])
            except (TypeError, ValueError, IndexError):
                continue
            if k not in best or t > best[k][1]:
                best[k] = (val, t)
    return {k: v for k, (v, _t) in best.items()}


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        items = d.get("items", {}) if isinstance(d, dict) else {}
        return items if isinstance(items, dict) else {}
    except (OSError, ValueError):
        return {}


class Favorites:
    """directory: 설정 폴더. 파일이 바뀌었을 때만 다시 읽는다(목록을 그릴 때마다 불리므로)"""

    def __init__(self, directory):
        self.dir = directory
        self._sig = None
        self._merged = {}

    def _signature(self):
        out = []
        for n in (OWN, OTHER):
            try:
                st = os.stat(os.path.join(self.dir, n))
                out.append((st.st_mtime_ns, st.st_size))
            except OSError:
                out.append(None)
        return tuple(out)

    def state(self):
        """{노트 경로: 즐겨찾기인가}"""
        sig = self._signature()
        if sig != self._sig:
            self._merged = merge(_read(os.path.join(self.dir, OWN)), _read(os.path.join(self.dir, OTHER)))
            self._sig = sig
        return self._merged

    def is_fav(self, rel):
        return bool(self.state().get(rel))

    def all(self):
        return sorted(k for k, v in self.state().items() if v)

    def set(self, rel, on, now=None):
        """즐겨찾기를 켜거나 끈다(내 파일에만 적는다)"""
        now = int(time.time() * 1000) if now is None else now
        os.makedirs(self.dir, exist_ok=True)
        own = os.path.join(self.dir, OWN)
        items = _read(own)
        items[rel] = [1 if on else 0, now]
        tmp = own + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"items": items}, fh, ensure_ascii=False)
        os.replace(tmp, own)
        self._sig = None

    def toggle(self, rel):
        on = not self.is_fav(rel)
        self.set(rel, on)
        return on
