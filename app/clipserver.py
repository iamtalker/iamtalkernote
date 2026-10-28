"""조플린 Web Clipper 호환 로컬 서버 (표준 라이브러리만).
가져온 'Joplin Clipper Plus' 확장(clipper/)이 조플린 대신 이 앱에 저장할 수 있게, 조플린 REST API 의
/ping · /folders · /notes 만 흉내 낸다. 127.0.0.1 에서만 열고, 토큰이 없으면 거절한다."""
import hmac
import json
import re
import threading
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urljoin, urlsplit

from store import ROOT_ID
from wikiconv.markdown import md_title

MAX_BODY = 200 * 1024 * 1024


# ---------------------------------------------------------------- HTML → 마크다운 (전체 페이지 클립용)
class _Md(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "head", "svg"}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.skip = base, [], 0
        self.lists, self.href, self.pre, self.cell_row = [], [], 0, None
        self.table, self.link_start = None, []

    def w(self, s):
        if self.table is not None and self.cell_row is not None:
            self.cell_row.append(s)
        else:
            self.out.append(s)

    def abs(self, u):
        return urljoin(self.base, u) if self.base and u else (u or "")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.w("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "section", "article", "header", "footer", "figure"):
            self.w("\n\n")
        elif tag == "br":
            self.w("  \n")
        elif tag == "hr":
            self.w("\n\n---\n\n")
        elif tag in ("strong", "b"):
            self.w("**")
        elif tag in ("em", "i"):
            self.w("*")
        elif tag in ("del", "s", "strike"):
            self.w("~~")
        elif tag == "code" and not self.pre:
            self.w("`")
        elif tag == "pre":
            self.pre += 1
            self.w("\n\n```\n")
        elif tag == "blockquote":
            self.w("\n\n> ")
        elif tag in ("ul", "ol"):
            self.lists.append([tag, 0])
            self.w("\n")
        elif tag == "li":
            depth = max(0, len(self.lists) - 1)
            mark = "- "
            if self.lists and self.lists[-1][0] == "ol":
                self.lists[-1][1] += 1
                mark = f"{self.lists[-1][1]}. "
            self.w("\n" + "  " * depth + mark)
        elif tag == "a":
            self.href.append(self.abs(a.get("href", "")))
            self.w("[")
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            if src:
                self.w(f"![{a.get('alt', '')}]({self.abs(src)})")
        elif tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.table.append([])
        elif tag in ("td", "th") and self.table is not None:
            self.cell_row = []

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "blockquote", "section", "article"):
            self.w("\n\n")
        elif tag in ("strong", "b"):
            self.w("**")
        elif tag in ("em", "i"):
            self.w("*")
        elif tag in ("del", "s", "strike"):
            self.w("~~")
        elif tag == "code" and not self.pre:
            self.w("`")
        elif tag == "pre":
            self.pre = max(0, self.pre - 1)
            self.w("\n```\n\n")
        elif tag in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
            self.w("\n")
        elif tag == "a" and self.href:
            self.w(f"]({self.href.pop()})")
        elif tag in ("td", "th") and self.table is not None and self.cell_row is not None:
            cell = re.sub(r"\s+", " ", "".join(self.cell_row)).strip().replace("|", "\\|")
            if self.table:
                self.table[-1].append(cell)
            self.cell_row = None
        elif tag == "table" and self.table is not None:
            rows, self.table = [r for r in self.table if r], None
            if rows:
                n = max(len(r) for r in rows)
                rows = [r + [""] * (n - len(r)) for r in rows]
                lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * n]
                lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                self.out.append("\n\n" + "\n".join(lines) + "\n\n")

    def handle_data(self, data):
        if self.skip:
            return
        self.w(data if self.pre else re.sub(r"\s+", " ", data))


def html_to_md(html, base=""):
    p = _Md(base)
    p.feed(html or "")
    p.close()
    md = "".join(p.out)
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


# ---------------------------------------------------------------- 서버
def start(store, get_token, on_saved):
    """서버를 열고 (서버, 포트) 를 돌려준다. 조플린(41184~41194)과 겹치지 않게 41200~41209 에서 빈 포트를 쓴다."""

    def extract_images(md, nb):
        return store.extract_images(md, nb)[0]

    def create_note(b):
        pid = b.get("parent_id") or ROOT_ID
        nb = "" if pid == ROOT_ID else pid
        if b.get("body_html") is not None:
            body = html_to_md(b["body_html"], b.get("base_url", ""))
        else:
            body = b.get("body") or ""
        body = extract_images(body, nb)
        tags = [t.strip() for t in (b.get("tags") or "").split(",") if t.strip()]
        text = ""
        if b.get("source_url"):   # 맨 위 머리말(front matter)에 둔다: 렌더링 화면에서는 숨겨지고 문서 정보의 URL 로 나온다
            text += f"---\nsource: {b['source_url']}\n---\n\n"
        text += body
        if tags:
            text += "\n\n태그: " + " ".join("#" + re.sub(r"\s+", "_", t) for t in tags) + "\n"
        note = store.create_note(nb, (b.get("title") or "").strip() or "제목 없음", text)
        on_saved()
        return {"id": (nb + "/" if nb else "") + note["title"], "title": note["title"], "parent_id": nb or ROOT_ID}

    def folders():
        items = [{"id": ROOT_ID, "title": store.root_name, "parent_id": ""}]
        for n in store.notebooks():   # 하위 노트북은 "업무 / 프로젝트" 처럼 경로를 이름에 넣어 구분한다(확장은 목록을 이름순으로만 보여 준다)
            parts = n.split("/")
            items.append({"id": n, "title": " / ".join(md_title(p) for p in parts), "parent_id": "/".join(parts[:-1])})
        return {"items": items, "has_more": False}

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def send(self, code, obj):
            data = obj.encode("utf-8") if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8" if isinstance(obj, str) else "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send(204, "")

        def authorized(self, q):
            tok = (q.get("token") or [""])[0]
            return hmac.compare_digest(tok.encode(), get_token().encode())

        def do_GET(self):
            u = urlsplit(self.path)
            if u.path == "/ping":
                return self.send(200, "JoplinClipperServer")
            if not self.authorized(parse_qs(u.query)):
                return self.send(403, {"error": "Invalid token"})
            if u.path == "/folders":
                return self.send(200, folders())
            self.send(404, {"error": "Not found"})

        def do_POST(self):
            u = urlsplit(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                self.close_connection = True
                return self.send(413, {"error": "Too large"})
            raw = self.rfile.read(n)
            if not self.authorized(parse_qs(u.query)):
                return self.send(403, {"error": "Invalid token"})
            if u.path != "/notes":
                return self.send(404, {"error": "Not found"})
            try:
                self.send(200, create_note(json.loads(raw.decode("utf-8"))))
            except Exception as e:  # noqa: BLE001
                self.send(500, {"error": str(e)})

    class Srv(ThreadingHTTPServer):
        allow_reuse_address = False   # 윈도에서는 켜면 다른 프로그램(조플린)이 쓰는 포트에도 겹쳐 열린다

    for port in range(41200, 41210):
        try:
            srv = Srv(("127.0.0.1", port), H)
        except OSError:
            continue
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv, port
    return None, None
