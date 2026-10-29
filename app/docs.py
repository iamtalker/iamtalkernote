"""가져온 폴더(노트 폴더 밖의 pdf·txt·mp3 …)를 읽어 검색 색인에 넣는다.

노트(.md)와는 따로 둔 문서 색인이다: 원본 파일은 그 자리에 두고(읽기만 한다), 글만 뽑아 DB 에 적어 둔다.
확장자마다 글을 뽑는 도구(EXTRACTORS)가 달라서, 새 형식은 함수 하나를 더하면 된다.
  - 글 파일(txt md csv …): 그대로 읽는다
  - pdf: pypdf (BSD-3-Clause)
  - docx pptx xlsx: zip 안의 xml 에서 글만 (표준 라이브러리)
  - mp3 flac m4a ogg wav …: 파일 이름 + ID3 등 태그 — tinytag (MIT)
"""
import hashlib
import json
import os
import re
import sqlite3
import time
import zlib
import zipfile
from xml.etree import ElementTree

import store as st

TEXT_EXT = ("txt", "md", "markdown", "csv", "tsv", "log", "json", "xml", "html", "htm", "ini", "yaml", "yml", "rtf")
OFFICE_EXT = ("docx", "pptx", "xlsx")
AUDIO_EXT = ("mp3", "flac", "m4a", "ogg", "wav", "wma", "opus")
DEFAULT_EXTS = ["pdf", "txt", "md", "mp3"]
KNOWN_EXTS = ["pdf", *TEXT_EXT, *OFFICE_EXT, *AUDIO_EXT]
MAX_TEXT_BYTES = 30_000_000     # 이보다 큰 글 파일은 이름만 색인
MAX_PDF_BYTES = 300_000_000
MAX_CHARS = 3_000_000           # 파일 하나에서 색인할 글자 수 상한
DOC_VERSION = 1


def _squash(text):
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _read_text(path, size):
    if size > MAX_TEXT_BYTES:
        return ""
    with open(path, "rb") as fh:
        text = st.decode(fh.read())
    return re.sub(r"<[^>]+>", " ", text) if path.lower().endswith((".html", ".htm", ".xml")) else text


def _read_pdf(path, size):
    if size > MAX_PDF_BYTES:
        return ""
    from pypdf import PdfReader
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            return ""
    out, total = [], 0
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001  (깨진 쪽은 건너뛴다)
            continue
        out.append(t)
        total += len(t)
        if total > MAX_CHARS:
            break
    return "\n\n".join(out)


def _read_office(path, size):
    ext = path.lower().rsplit(".", 1)[-1]
    parts = {"docx": ("word/document.xml",), "pptx": None, "xlsx": ("xl/sharedStrings.xml",)}[ext]
    out = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if parts is None:   # pptx: 슬라이드 순서대로
            parts = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
        for name in parts:
            if name not in names:
                continue
            root = ElementTree.fromstring(z.read(name))
            for el in root.iter():
                tag = el.tag.rsplit("}", 1)[-1]
                if tag in ("t",) and el.text:
                    out.append(el.text)
                elif tag in ("p", "si", "br"):
                    out.append("\n")
    return "".join(out)


def _read_audio(path, size):
    """소리는 글이 없으니 태그(제목·가수·앨범·연도·장르·가사·댓글)를 글로 만든다"""
    from tinytag import TinyTag
    tag = TinyTag.get(path)
    rows = [("제목", tag.title), ("가수", tag.artist), ("앨범", tag.album), ("앨범 가수", tag.albumartist), ("작곡", tag.composer),
            ("연도", tag.year), ("장르", tag.genre), ("트랙", tag.track), ("댓글", tag.comment)]
    extra = getattr(tag, "extra", None) or {}
    lyrics = extra.get("lyrics") or extra.get("lyrics-eng") or extra.get("unsynced_lyrics") or ""
    if isinstance(lyrics, list):
        lyrics = "\n".join(map(str, lyrics))
    text = "\n".join(f"{k}: {v}" for k, v in rows if v)
    if tag.duration:
        text += f"\n길이: {int(tag.duration // 60)}분 {int(tag.duration % 60)}초"
    return text + ("\n\n" + str(lyrics) if lyrics else "")


def extractor(ext):
    """확장자 → 글을 뽑는 함수(path, size) → str. 못 읽는 형식이면 None"""
    if ext == "pdf":
        return _read_pdf
    if ext in OFFICE_EXT:
        return _read_office
    if ext in AUDIO_EXT:
        return _read_audio
    if ext in TEXT_EXT:
        return _read_text
    return None


def available():
    """쓸 수 있는 읽기 도구(없는 라이브러리는 빼고) → {확장자: 설명}"""
    info = {e: "글 파일" for e in TEXT_EXT}
    info.update({e: "Office 문서" for e in OFFICE_EXT})
    try:
        import pypdf  # noqa: F401
        info["pdf"] = "PDF (pypdf)"
    except ImportError:
        pass
    try:
        import tinytag  # noqa: F401
        info.update({e: "소리 태그 (tinytag)" for e in AUDIO_EXT})
    except ImportError:
        pass
    return info


def extract(path, ext, size):
    """파일 하나의 검색용 글. 읽다가 실패해도 이름은 색인되도록 빈 글을 돌려준다"""
    fn = extractor(ext)
    if not fn:
        return ""
    try:
        return _squash(fn(path, size))[:MAX_CHARS]
    except Exception:  # noqa: BLE001  (깨진 pdf 등)
        return ""


def sql_cond(node, params):
    if node[0] == "WORD":
        params.append(node[1].encode("utf-8"))
        return "instr(hay, ?) > 0"
    left, right = sql_cond(node[1], params), sql_cond(node[2], params)
    return f"({left} {'AND' if node[0] in ('AND', 'NOT') else 'OR'}{' NOT' if node[0] == 'NOT' else ''} {right})"


class Doc(dict):
    """가져온 문서 한 개의 요약. 목록에는 노트처럼 나오고, 글은 DB 에서 읽는다"""
    is_doc = True

    def read(self):
        return self["_index"].body(self["path"])


class DocIndex:
    """가져온 폴더 목록(설정)과 문서 색인(DB). 앱을 껐다 켜도 남고, 바뀐 파일만 다시 읽는다."""

    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(st.config_path()), "docs-index.db")

    # ---- 설정 (config.json 의 "imports")
    def cfg(self):
        c = st.read_config().get("imports", {})
        folders = [f for f in c.get("folders", []) if isinstance(f, dict) and f.get("path")]
        exts = [e for e in c.get("exts", DEFAULT_EXTS) if isinstance(e, str)]
        return {"folders": folders, "exts": exts or list(DEFAULT_EXTS), "content": bool(c.get("content", True))}

    def save_cfg(self, c):
        st.write_config(imports=c)

    @staticmethod
    def fid(path):
        return hashlib.sha1(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()[:10]

    def folders(self):
        return [dict(f, id=self.fid(f["path"])) for f in self.cfg()["folders"]]

    def add_folder(self, path):
        c = self.cfg()
        path = os.path.abspath(path)
        if any(os.path.normcase(f["path"]) == os.path.normcase(path) for f in c["folders"]):
            return False
        c["folders"].append({"path": path, "name": os.path.basename(path.rstrip("\\/")) or path})
        self.save_cfg(c)
        return True

    def remove_folder(self, fid):
        c = self.cfg()
        c["folders"] = [f for f in c["folders"] if self.fid(f["path"]) != fid]
        self.save_cfg(c)
        conn = self._db()
        try:
            conn.execute("DELETE FROM docs WHERE folder=?", (fid,))
            conn.commit()
        finally:
            conn.close()

    # ---- DB
    def _db(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        ver = conn.execute("SELECT v FROM meta WHERE k='version'").fetchone()
        if not ver or ver[0] != str(DOC_VERSION):
            conn.execute("DROP TABLE IF EXISTS docs")
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (str(DOC_VERSION),))
        conn.execute("CREATE TABLE IF NOT EXISTS docs (path TEXT PRIMARY KEY, folder TEXT, ext TEXT, size INTEGER, mtime_ns INTEGER, "
                     "mtime REAL, ctime REAL, title TEXT, hay BLOB, body BLOB, content INTEGER)")
        conn.execute("CREATE INDEX IF NOT EXISTS docs_folder ON docs(folder)")
        conn.commit()
        return conn

    def scan(self, progress=None, cancelled=None, only=None):
        """가져온 폴더를 훑어 새로 생기거나 바뀐 파일만 읽고, 사라진 파일은 색인에서 뺀다 → (읽은 수, 뺀 수, 총 수)
        content=False(문서 안 검색 끔)면 글은 뽑지 않고 파일 이름만 색인한다."""
        cfg = self.cfg()
        exts = {e.lower().lstrip(".") for e in cfg["exts"]}
        content = cfg["content"]
        conn = self._db()
        done = removed = total = 0
        try:
            for f in cfg["folders"]:
                fid = self.fid(f["path"])
                if only and fid != only:
                    continue
                cached = {p: (sz, mt, ct) for p, sz, mt, ct in conn.execute(
                    "SELECT path, size, mtime_ns, content FROM docs WHERE folder=?", (fid,))}
                seen, todo = set(), []
                for dirpath, dirs, files in os.walk(f["path"]):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ("$recycle.bin", "system volume information")]
                    for name in files:
                        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                        if ext not in exts or name.startswith("~$"):
                            continue
                        p = os.path.join(dirpath, name)
                        try:
                            stt = os.stat(p)
                        except OSError:
                            continue
                        seen.add(p)
                        ent = cached.get(p)
                        if ent and ent[0] == stt.st_size and ent[1] == stt.st_mtime_ns and bool(ent[2]) == content:
                            continue
                        todo.append((p, name, ext, stt))
                total += len(seen)
                batch = []
                for i, (p, name, ext, stt) in enumerate(todo, 1):
                    if cancelled and cancelled():
                        break
                    text = extract(p, ext, stt.st_size) if content else ""
                    title = os.path.splitext(name)[0]
                    hay = (title + "\n" + os.path.relpath(p, f["path"]) + "\n" + text).lower().encode("utf-8", "ignore")
                    body = zlib.compress(text.encode("utf-8", "ignore"), 3)
                    batch.append((p, fid, ext, stt.st_size, stt.st_mtime_ns, stt.st_mtime, getattr(stt, "st_birthtime", stt.st_ctime),
                                  title, hay, body, 1 if content else 0))
                    done += 1
                    if len(batch) >= 40:
                        conn.executemany("INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch)
                        conn.commit()
                        batch = []
                    if progress and (i % 5 == 0 or i == len(todo)):
                        progress(i, len(todo), f"{f.get('name') or f['path']} 읽는 중…")
                if batch:
                    conn.executemany("INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch)
                gone = [(p,) for p in cached if p not in seen]
                if gone and not (cancelled and cancelled()):
                    conn.executemany("DELETE FROM docs WHERE path=?", gone)
                    removed += len(gone)
                conn.commit()
        finally:
            conn.close()
        return done, removed, total

    # ---- 목록·검색
    def list_docs(self, fid=None):
        """색인된 문서 목록(글은 읽지 않는다). fid=None 이면 가져온 모든 폴더"""
        names = {self.fid(f["path"]): f for f in self.cfg()["folders"]}
        conn = self._db()
        try:
            q = "SELECT path, folder, ext, size, mtime, ctime, title FROM docs" + (" WHERE folder=?" if fid else "")
            rows = conn.execute(q, (fid,) if fid else ()).fetchall()
        finally:
            conn.close()
        out = []
        for p, folder, ext, size, mt, ct, title in rows:
            if folder not in names:
                continue
            out.append(Doc(nb="@doc:" + folder, key=p, path=p, title=title + "." + ext, size=size, mtime=mt, ctime=ct, file_mtime=mt,
                           tags=set(), ext=ext, root=names[folder]["path"], _index=self))
        return out

    def counts(self):
        conn = self._db()
        try:
            return dict(conn.execute("SELECT folder, COUNT(*) FROM docs GROUP BY folder"))
        finally:
            conn.close()

    def body(self, path):
        conn = self._db()
        try:
            row = conn.execute("SELECT body FROM docs WHERE path=?", (path,)).fetchone()
        finally:
            conn.close()
        return zlib.decompress(row[0]).decode("utf-8", "ignore") if row and row[0] else ""

    def query_hits(self, node, words, scoring=False):
        """검색식에 맞는 문서 → {경로: 점수} (노트 색인(store.Store.query_hits)과 같은 모양이라 search.run 에 그대로 쓴다)"""
        params = []
        cond = sql_cond(node, params)
        conn = self._db()
        try:
            if not scoring:
                return {k: 0.0 for (k,) in conn.execute(f"SELECT path FROM docs WHERE {cond}", params)}
            ws = [w for w in words if w]
            hits = {}
            for k, hay in conn.execute(f"SELECT path, hay FROM docs WHERE {cond}", params):
                text = bytes(hay).decode("utf-8", "ignore")
                hits[k] = 1000 * sum(text.count(w) for w in ws) / max(1, len(text))
            return hits
        finally:
            conn.close()
