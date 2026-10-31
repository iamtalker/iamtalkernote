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
import threading
import time
import zlib
import zipfile
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
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
PDF_SECONDS = 120               # PDF 한 개를 읽는 데 쓸 시간 상한(넘으면 읽은 데까지만)
STUCK_SECONDS = PDF_SECONDS + 60   # 이 시간이 넘도록 끝나지 않는 파일은 멈춘 것으로 보고 그 작업 프로세스를 죽인다
HEAVY_EXT = ("pdf", *OFFICE_EXT)   # 오래 걸려서 다른 프로세스에서 나눠 읽는 형식
DOC_VERSION = 1
EXPORT_DIR = ".imported"       # 노트 폴더 안 숨김 폴더: 가져온 문서의 요약을 내보내는 곳(폰 앱이 읽는다)
EXPORT_TEXT_CHARS = 20000      # 문서마다 내보내는 글의 길이(앞부분만)
EXPORT_VERSION = 1


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
    out, total, deadline = [], 0, time.time() + PDF_SECONDS
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001  (깨진 쪽은 건너뛴다)
            continue
        out.append(t)
        total += len(t)
        if total > MAX_CHARS or time.time() > deadline:   # 너무 큰·느린 PDF 는 읽은 데까지만 색인
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


def extract_job(path, ext, size):
    """작업 프로세스에서 도는 함수(최상위여야 다른 프로세스가 부를 수 있다)"""
    return extract(path, ext, size)


def _kill(pool):
    for proc in list((getattr(pool, "_processes", None) or {}).values()):
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
    pool.shutdown(wait=False, cancel_futures=True)


def heavy_results(jobs, cancelled=None, name_of=None, progress=None):
    """[(경로, 확장자, 크기)] 를 여러 프로세스로 나눠 읽으며 끝나는 대로 (경로, 글) 을 낸다.
    한 파일이 PDF_SECONDS+60 초가 넘게 멈춰 있으면 그 작업 프로세스를 죽이고 그 파일은 이름만 색인한 뒤 나머지를 이어서 읽는다.
    프로세스를 못 만드는 환경이면 같은 프로세스에서 하나씩 읽는다."""
    todo = list(jobs)
    workers = max(1, min(4, (os.cpu_count() or 2) - 1))
    while todo:
        if cancelled and cancelled():
            return
        try:
            pool = ProcessPoolExecutor(max_workers=workers)
            futs = {pool.submit(extract_job, p, ext, size): (p, ext, size) for p, ext, size in todo}
        except Exception:  # noqa: BLE001  (프로세스를 못 만드는 환경)
            for p, ext, size in todo:
                if cancelled and cancelled():
                    return
                if progress and name_of:
                    progress(name_of(p))
                yield p, extract(p, ext, size)
            return
        finished, started, stuck = set(), {}, None
        pending = set(futs)
        while pending and stuck is None:
            if cancelled and cancelled():
                _kill(pool)
                return
            done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
            for f in done:
                p = futs[f][0]
                finished.add(p)
                try:
                    text = f.result()
                except Exception:  # noqa: BLE001
                    text = ""
                if progress and name_of:
                    progress(name_of(p))
                yield p, text
            now = time.time()
            for f in pending:
                if f.running():
                    started.setdefault(f, now)
                    if now - started[f] > STUCK_SECONDS:
                        stuck = f
                        break
        if stuck is None:
            pool.shutdown()
            return
        _kill(pool)                       # 멈춘 파일: 이름만 색인하고 나머지는 새 프로세스로 이어서
        finished.add(futs[stuck][0])
        yield futs[stuck][0], ""
        todo = [t for t in todo if t[0] not in finished]


def sql_cond(node, params):
    if node[0] == "WORD":
        params.append(node[1].encode("utf-8"))
        return "instr(hay, ?) > 0"
    left, right = sql_cond(node[1], params), sql_cond(node[2], params)
    return f"({left} {'AND' if node[0] in ('AND', 'NOT') else 'OR'}{' NOT' if node[0] == 'NOT' else ''} {right})"


class Combined:
    """노트 색인과 문서 색인을 하나처럼 검색한다('모든 파일'): query_hits 결과를 합친다(노트 키는 상대 경로, 문서 키는 절대 경로라 겹치지 않는다)"""

    def __init__(self, *indexes):
        self.indexes = indexes

    def query_hits(self, node, words, scoring=False):
        hits = {}
        for ix in self.indexes:
            hits.update(ix.query_hits(node, words, scoring))
        return hits


class Doc(dict):
    """가져온 문서 한 개의 요약. 목록에는 노트처럼 나오고, 글은 DB 에서 읽는다"""
    is_doc = True

    def read(self):
        return self["_index"].body(self["path"])


class DocIndex:
    """가져온 폴더 목록(설정)과 문서 색인(DB). 앱을 껐다 켜도 남고, 바뀐 파일만 다시 읽는다."""

    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(st.config_path()), "docs-index.db")
        self.content_search = bool(st.read_config().get("docContentSearch", False))   # 검색창의 '문서 안 글 포함' 체크

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
        conn = self._db()
        try:   # 예전에 뺐다가 다시 넣는 폴더면, 그때 만든 색인을 그대로 되살린다(다시 읽을 필요 없이 바뀐 파일만 읽는다)
            if conn.execute("SELECT 1 FROM docs_old WHERE folder=? LIMIT 1", (self.fid(path),)).fetchone():
                conn.execute("INSERT OR REPLACE INTO docs SELECT * FROM docs_old WHERE folder=?", (self.fid(path),))
                conn.execute("DELETE FROM docs_old WHERE folder=?", (self.fid(path),))
                conn.commit()
        finally:
            conn.close()
        return True

    def remove_folder(self, fid):
        c = self.cfg()
        c["folders"] = [f for f in c["folders"] if self.fid(f["path"]) != fid]
        self.save_cfg(c)
        conn = self._db()
        try:   # 목록에서만 빼고 색인은 보관해 둔다(같은 폴더를 다시 넣으면 되살림)
            conn.execute("INSERT OR REPLACE INTO docs_old SELECT * FROM docs WHERE folder=?", (fid,))
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
            conn.execute("DROP TABLE IF EXISTS docs_old")
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (str(DOC_VERSION),))
        conn.execute("CREATE TABLE IF NOT EXISTS docs (path TEXT PRIMARY KEY, folder TEXT, ext TEXT, size INTEGER, mtime_ns INTEGER, "
                     "mtime REAL, ctime REAL, title TEXT, hay BLOB, body BLOB, content INTEGER, nhay BLOB)")
        conn.execute("CREATE INDEX IF NOT EXISTS docs_folder ON docs(folder)")
        conn.execute("CREATE TABLE IF NOT EXISTS docs_old (path TEXT PRIMARY KEY, folder TEXT, ext TEXT, size INTEGER, mtime_ns INTEGER, "
                     "mtime REAL, ctime REAL, title TEXT, hay BLOB, body BLOB, content INTEGER, nhay BLOB)")   # 목록에서 뺀 폴더의 색인 보관
        if "nhay" not in [r[1] for r in conn.execute("PRAGMA table_info(docs)")]:
            # 이름·경로·태그·메모만의 검색용 사본('문서 안 글' 검색을 끈 채 찾을 때 쓴다). 이미 읽어 둔 색인은 파일을 다시 읽지 않고 DB 안의 값으로 채운다
            conn.execute("ALTER TABLE docs ADD COLUMN nhay BLOB")
            roots = {self.fid(f["path"]): f["path"] for f in self.cfg()["folders"]}
            ann = {p: (json.loads(t or "[]"), m or "") for p, t, m in conn.execute("SELECT path, tags, memo FROM annot")}
            rows = []
            for p, folder, title in conn.execute("SELECT path, folder, title FROM docs").fetchall():
                tags, memo = ann.get(p, ([], ""))
                rel = os.path.relpath(p, roots[folder]) if folder in roots else os.path.basename(p)
                rows.append((self.make_hay(title, rel, "", tags, memo), p))
            conn.executemany("UPDATE docs SET nhay=? WHERE path=?", rows)
        # 내가 붙인 태그·메모. 원본 파일은 건드리지 않고 여기에만 적으며, docs 표를 다시 만들어도(색인 판이 바뀌어도) 남는다
        conn.execute("CREATE TABLE IF NOT EXISTS annot (path TEXT PRIMARY KEY, tags TEXT, memo TEXT)")
        conn.commit()
        return conn

    # ---- 태그·메모
    def annots(self):
        """{경로: (태그 목록, 메모)}"""
        conn = self._db()
        try:
            return {p: (json.loads(t or "[]"), m or "") for p, t, m in conn.execute("SELECT path, tags, memo FROM annot")}
        finally:
            conn.close()

    @staticmethod
    def make_hay(title, rel, text, tags, memo):
        """검색용 사본: 이름·경로·본문에 내가 붙인 태그와 메모도 넣어서 함께 찾아지게"""
        extra = " ".join("#" + t for t in tags) + "\n" + memo if (tags or memo) else ""
        return (title + "\n" + rel + "\n" + text + ("\n" + extra if extra else "")).lower().encode("utf-8", "ignore")

    def set_annot(self, path, tags=None, memo=None):
        """태그나 메모를 바꾼다(None 이면 그대로). 검색용 사본도 새로 만든다. 둘 다 비면 기록을 지운다"""
        roots = {self.fid(f["path"]): f["path"] for f in self.cfg()["folders"]}
        conn = self._db()
        try:
            row = conn.execute("SELECT folder, title, body FROM docs WHERE path=?", (path,)).fetchone()
            if not row or row[0] not in roots:
                return False
            old = conn.execute("SELECT tags, memo FROM annot WHERE path=?", (path,)).fetchone()
            cur_tags = json.loads(old[0] or "[]") if old else []
            cur_memo = (old[1] or "") if old else ""
            tags = cur_tags if tags is None else list(dict.fromkeys(tags))
            memo = cur_memo if memo is None else memo.strip()
            if tags or memo:
                conn.execute("INSERT OR REPLACE INTO annot VALUES (?,?,?)", (path, json.dumps(tags, ensure_ascii=False), memo))
            else:
                conn.execute("DELETE FROM annot WHERE path=?", (path,))
            text = zlib.decompress(row[2]).decode("utf-8", "ignore") if row[2] else ""
            rel = os.path.relpath(path, roots[row[0]])
            conn.execute("UPDATE docs SET hay=?, nhay=? WHERE path=?",
                         (self.make_hay(row[1], rel, text, tags, memo), self.make_hay(row[1], rel, "", tags, memo), path))
            conn.commit()
            self.export_soon()
            return True
        finally:
            conn.close()

    def tag_counts(self):
        """가져온 문서에 붙인 태그별 개수"""
        out = {}
        conn = self._db()
        try:
            for (t,) in conn.execute("SELECT annot.tags FROM annot JOIN docs ON docs.path = annot.path"):
                for tag in json.loads(t or "[]"):
                    out[tag] = out.get(tag, 0) + 1
        finally:
            conn.close()
        return out

    def rename_tags(self, olds, new):
        """olds 의 태그를 모두 new 로 바꾼다(None 이면 지운다) → 바뀐 문서 수"""
        olds = set(olds)
        changed = 0
        for path, (tags, memo) in self.annots().items():
            if not olds & set(tags):
                continue
            moved = [t for t in tags if t not in olds]
            if new and new not in moved:
                moved.append(new)
            if self.set_annot(path, tags=moved):
                changed += 1
        return changed

    def tag_use_count(self, tags):
        """tags 중 하나라도 붙은 가져온 문서 수"""
        want = set(tags)
        return sum(1 for tg, _m in self.annots().values() if want & set(tg))

    def scan(self, progress=None, cancelled=None, only=None):
        """가져온 폴더를 훑어 새로 생기거나 바뀐 파일만 읽고, 사라진 파일은 색인에서 뺀다 → (읽은 수, 뺀 수, 총 수)
        content=False(문서 안 검색 끔)면 글은 뽑지 않고 파일 이름만 색인한다.
        pdf·Office 는 오래 걸리고 멈출 수도 있어서 다른 프로세스에서 나눠 읽는다(앱 화면이 얼지 않는다)."""
        cfg = self.cfg()
        exts = {e.lower().lstrip(".") for e in cfg["exts"]}
        content = cfg["content"]
        conn = self._db()
        count = {"done": 0, "removed": 0, "total": 0}
        try:
            for f in cfg["folders"]:
                fid = self.fid(f["path"])
                if only and fid != only:
                    continue
                cached = {p: (sz, mt, ct) for p, sz, mt, ct in conn.execute(
                    "SELECT path, size, mtime_ns, content FROM docs WHERE folder=?", (fid,))}
                seen, todo = set(), {}
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
                        todo[p] = (name, ext, stt)
                count["total"] += len(seen)
                ann = self.annots() if todo else {}
                batch, n = [], [0]

                def add(p, text):
                    name, ext, stt = todo[p]
                    title = os.path.splitext(name)[0]
                    tags, memo = ann.get(p, ([], ""))   # 내가 붙인 태그·메모도 검색 대상에 넣는다
                    rel = os.path.relpath(p, f["path"])
                    batch.append((p, fid, ext, stt.st_size, stt.st_mtime_ns, stt.st_mtime, getattr(stt, "st_birthtime", stt.st_ctime),
                                  title, self.make_hay(title, rel, text, tags, memo), zlib.compress(text.encode("utf-8", "ignore"), 3),
                                  1 if content else 0, self.make_hay(title, rel, "", tags, memo)))
                    count["done"] += 1
                    n[0] += 1
                    if len(batch) >= 40:
                        conn.executemany("INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
                        conn.commit()
                        batch.clear()
                    if progress:
                        progress(n[0], len(todo), f"읽는 중 — {name}  ")
                light = [p for p, (name, ext, stt) in todo.items() if not (content and ext in HEAVY_EXT)]
                heavy = [(p, todo[p][1], todo[p][2].st_size) for p in todo if content and todo[p][1] in HEAVY_EXT]
                for p in light:
                    if cancelled and cancelled():
                        break
                    add(p, extract(p, todo[p][1], todo[p][2].st_size) if content else "")
                if heavy and not (cancelled and cancelled()):
                    for p, text in heavy_results(heavy, cancelled, name_of=lambda q: todo[q][0],
                                                 progress=(lambda name: progress(n[0], len(todo), f"읽는 중 — {name}  ")) if progress else None):
                        add(p, text)
                if batch:
                    conn.executemany("INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
                gone = [(p,) for p in cached if p not in seen]
                if gone and not (cancelled and cancelled()):
                    conn.executemany("DELETE FROM docs WHERE path=?", gone)
                    count["removed"] += len(gone)
                conn.commit()
        finally:
            conn.close()
        if count["done"] or count["removed"] or only is None:
            try:
                self.export()
            except Exception:  # noqa: BLE001
                pass
        return count["done"], count["removed"], count["total"]

    # ---- 폰으로 내보내기: <노트 폴더>/.imported/docs.jsonl — 문서마다 한 줄(이름·폴더·태그·메모·글 앞부분). 원본 파일은 담지 않는다.
    # 노트 폴더를 동기화하면 폰 앱이 이 파일을 읽어 가져온 파일을 목록·검색·보기로 쓴다(폰에서는 읽기 전용).
    def export_enabled(self):
        return bool(st.read_config().get("imports", {}).get("export", True))

    def export(self, root=None):
        """가져온 문서 요약을 내보낸다 → 내보낸 문서 수(끄거나 폴더가 없으면 0). 실패해도 본 작업을 막지 않게 호출하는 쪽에서 try 한다"""
        root = root or st.read_config().get("root") or st.default_root()
        if not self.export_enabled() or not os.path.isdir(root):
            return 0
        names = {self.fid(f["path"]): f for f in self.cfg()["folders"]}
        if not names:
            return 0
        conn = self._db()
        try:
            rows = conn.execute("SELECT path, folder, ext, size, mtime, title, body FROM docs").fetchall()
            ann = {p: (json.loads(t or "[]"), m or "") for p, t, m in conn.execute("SELECT path, tags, memo FROM annot")}
        finally:
            conn.close()
        lines = []
        for path, folder, ext, size, mt, title, body in rows:
            if folder not in names:
                continue
            text = zlib.decompress(body).decode("utf-8", "ignore") if body else ""
            tags, memo = ann.get(path, ([], ""))
            rel = os.path.relpath(path, names[folder]["path"]).replace("\\", "/")
            lines.append(json.dumps({"id": hashlib.sha1(path.encode("utf-8")).hexdigest()[:16], "folder": names[folder].get("name") or folder,
                                     "rel": rel, "ext": ext, "size": size, "mtime": round(mt, 1), "title": title, "tags": tags, "memo": memo,
                                     "text": text[:EXPORT_TEXT_CHARS]}, ensure_ascii=False))
        d = os.path.join(root, EXPORT_DIR)
        os.makedirs(d, exist_ok=True)
        if os.name == "nt":
            try:
                import ctypes
                ctypes.WinDLL("kernel32").SetFileAttributesW(d, 0x2)   # 숨김 폴더
            except Exception:  # noqa: BLE001
                pass
        for name, data in (("docs.jsonl", "\n".join(lines) + ("\n" if lines else "")),
                           ("meta.json", json.dumps({"version": EXPORT_VERSION, "generated": time.time(), "count": len(lines), "textChars": EXPORT_TEXT_CHARS}))):
            tmp = os.path.join(d, name + ".tmp")
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(data)
            os.replace(tmp, os.path.join(d, name))
        return len(lines)

    _export_timer = None

    def export_soon(self, delay=4.0):
        """태그·메모를 고친 직후처럼 자주 불릴 때 한 번만 내보내도록 잠깐 기다린다"""
        if self._export_timer is not None:
            self._export_timer.cancel()

        def run():
            try:
                self.export()
            except Exception:  # noqa: BLE001
                pass
        t = threading.Timer(delay, run)
        t.daemon = True
        self._export_timer = t
        t.start()

    # ---- 목록·검색
    def list_docs(self, fid=None):
        """색인된 문서 목록(글은 읽지 않는다). fid=None 이면 가져온 모든 폴더"""
        names = {self.fid(f["path"]): f for f in self.cfg()["folders"]}
        conn = self._db()
        try:
            q = "SELECT path, folder, ext, size, mtime, ctime, title FROM docs" + (" WHERE folder=?" if fid else "")
            rows = conn.execute(q, (fid,) if fid else ()).fetchall()
            ann = {p: (json.loads(t or "[]"), m or "") for p, t, m in conn.execute("SELECT path, tags, memo FROM annot")}
        finally:
            conn.close()
        out = []
        for p, folder, ext, size, mt, ct, title in rows:
            if folder not in names:
                continue
            tags, memo = ann.get(p, ([], ""))
            out.append(Doc(nb="@doc:" + folder, key=p, path=p, title=title + "." + ext, size=size, mtime=mt, ctime=ct, file_mtime=mt,
                           tags=set(tags), memo=memo, ext=ext, root=names[folder]["path"], _index=self))
        return out

    def kept_counts(self):
        """목록에서 뺐지만 색인을 보관 중인 폴더별 개수"""
        conn = self._db()
        try:
            return dict(conn.execute("SELECT folder, COUNT(*) FROM docs_old GROUP BY folder"))
        finally:
            conn.close()

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
        col = "hay" if self.content_search else "nhay"   # 문서 안 글까지 찾을지, 이름·경로·태그·메모만 찾을지
        cond = cond.replace("instr(hay,", f"instr({col},")
        conn = self._db()
        try:
            if not scoring:
                return {k: 0.0 for (k,) in conn.execute(f"SELECT path FROM docs WHERE {cond}", params)}
            ws = [w for w in words if w]
            hits = {}
            for k, hay in conn.execute(f"SELECT path, {col} FROM docs WHERE {cond}", params):
                text = bytes(hay).decode("utf-8", "ignore")
                hits[k] = 1000 * sum(text.count(w) for w in ws) / max(1, len(text))
            return hits
        finally:
            conn.close()
