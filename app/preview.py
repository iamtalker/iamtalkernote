"""미리보기 배치: 공통 구조(Doc) → 글 조각들(Tk Text 위젯에 그대로 넣을 수 있는 모양). 화면 없이도 시험할 수 있게 따로 둔다.

조각 = (글, 태그들, 덧붙임)   덧붙임은 None 이거나 ("img", 원래 이름, 설명) · ("link", 종류, 대상)
태그: h1..h6 · b i u s sup sub · code codeblock math raw chip muted · link · quote · hr · M{n}(들여쓰기) B{n}(목록 첫 줄)
"""
import unicodedata

from wikiconv.tree import cell_inline, text_of, video_label, video_url

MAX_LEVEL = 8


def has_image(inl):
    """인라인들(안쪽 굵게·링크 포함)에 그림이 있는가"""
    for n in inl or []:
        if n[0] == "img":
            return True
        if n[0] in ("b", "i", "u", "s", "sup", "sub") and has_image(n[1]):
            return True
        if n[0] in ("link", "url") and len(n) > 2 and n[2] and has_image(n[2]):
            return True
    return False


def width(s):
    """고정폭 글꼴에서 차지하는 칸 수(한글·전각은 2칸)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - width(s))


class Layout:
    def __init__(self):
        self.out = []
        self.notes = []
        self.heads = []

    # ---------------- 줄 안
    def emit(self, text, tags=(), extra=None):
        if text:
            self.out.append((text, tuple(tags), extra))

    def inline(self, inl, tags=()):
        for n in inl or []:
            k = n[0]
            if k == "t":
                self.emit(n[1], tags)
            elif k in ("b", "i", "u", "s", "sup", "sub"):
                self.inline(n[1], tags + (k,))
            elif k == "code":
                self.emit(n[1], tags + ("code",))
            elif k == "br":
                self.emit("\n", tags)
            elif k == "math":
                self.emit(n[1], tags + ("math",))
            elif k == "link":
                anchor = n[3] if len(n) > 3 and n[3] else ""
                label = n[2] or [["t", n[1] + ("#" + anchor if anchor else "")]]
                start = len(self.out)
                self.inline(label, tags + ("link",))
                self.attach(start, ("link", "page", n[1]))
            elif k == "url":
                start = len(self.out)
                self.inline(n[2] or [["t", n[1]]], tags + ("link",))
                self.attach(start, ("link", "url", n[1]))
            elif k == "video":   # 창 안에서는 재생할 수 없어서, 유튜브는 썸네일 카드로 보이고 누르면 재생 창이 열린다
                start = len(self.out)
                if n[1] == "youtube":
                    self.emit("[▶ 유튜브 영상]", tags + ("chip",), ("img", f"https://i.ytimg.com/vi/{n[2]}/mqdefault.jpg", "", 0))
                    self.emit("\n", tags)
                self.emit(video_label(n[1]), tags + ("link",))
                self.attach(start, ("link", "url", video_url(n[1], n[2])))
            elif k == "img":
                label = n[2] or ("" if n[1][:5].lower() == "data:" else n[1])   # data: 주소(base64)를 글자로 찍지 않는다
                self.emit("[그림" + (": " + label if label else "") + "]", tags + ("chip",),
                          ("img", n[1], n[2] or "", n[3] if len(n) > 3 else 0))
            elif k == "fn":
                self.notes.append(n[2])
                self.emit(f"[{len(self.notes)}]", tags + ("sup", "fnref"))
            elif k == "tpl":
                self.emit(self.tpl_text(n), tags + ("chip",))
            elif k == "raw":
                self.emit(n[2], tags + ("raw",))

    def attach(self, start, extra):
        """start 번째 조각부터 지금까지를 같은 링크로 묶는다."""
        for i in range(start, len(self.out)):
            t, tg, ex = self.out[i]
            if ex and ex[0] == "img":
                ex = tuple(ex[:4]) + (extra[1], extra[2])   # 링크로 감싼 그림: 그림 정보 뒤에 링크 정보를 붙인다
            else:
                ex = ex or extra
            self.out[i] = (t, tg, ex)

    @staticmethod
    def tpl_text(n):
        if not n[2] and not n[1].startswith("틀:"):
            return f"⟦문서 끼워 넣기: {n[1]}⟧"
        args = ", ".join(f"{k}={v}" if k else v for k, v in n[2])
        return f"⟦{n[1]}{'(' + args + ')' if args else ''}⟧"

    # ---------------- 블록
    def blocks(self, blocks, lvl=0, tags=()):
        for b in blocks:
            self.block(b, lvl, tags)

    def block(self, b, lvl, tags):
        k = b[0]
        m = ("M%d" % min(lvl, MAX_LEVEL),) if lvl else ()
        if k == "h":
            self.heads.append((b[1], text_of(b[2])))
            self.inline(b[2], tags + m + ("h%d" % min(b[1], 6),))
            self.emit("\n\n", m + ("h%d" % min(b[1], 6),))
        elif k == "p":
            self.inline(b[1], tags + m)
            self.emit("\n\n", tags + m)
        elif k == "list":
            self.list(b, lvl + 1, tags)
            self.emit("\n", m)
        elif k in ("code", "pre"):
            lang, text = (b[1], b[2]) if k == "code" else ("", b[1])
            if lang:
                self.emit(lang + "\n", tags + m + ("muted",))
            self.emit(text + "\n\n", tags + m + ("codeblock",))
        elif k == "math":
            self.emit(b[1] + "\n\n", tags + m + ("math", "codeblock"))
        elif k == "quote":
            self.blocks(b[1], lvl + 1, tags + ("quote",))
        elif k == "hr":
            self.emit("─" * 40 + "\n\n", m + ("hr",))
        elif k == "toc":
            self.emit("목차\n", m + ("b",))
            for lv, text in self.toc_items():
                self.emit("  " * (lv - 1) + text + "\n", m + ("muted",))
            self.emit("\n", m)
        elif k == "table":
            self.table(b, m)
        elif k == "fold":
            self.emit("▸ ", tags + m + ("b",))
            self.inline(b[1], tags + m + ("b",))
            self.emit("\n", m)
            self.blocks(b[2], lvl + 1, tags)
        elif k == "tpl":
            self.emit(self.tpl_text(b) + "\n\n", tags + m + ("chip",))
        elif k == "raw":
            self.emit("⟦원문 보존⟧\n" + b[2] + "\n\n", tags + m + ("raw",))

    def toc_items(self):
        return getattr(self, "_toc", [])

    def list(self, b, lvl, tags):
        for n, item in enumerate(b[2], 1):
            mark = f"{n}. " if b[1] else "• "
            first = True
            for sub in item:
                if sub[0] == "list":
                    self.list(sub, lvl + 1, tags)
                    continue
                if first:
                    self.emit(mark, tags + ("B%d" % min(lvl, MAX_LEVEL),))
                    if sub[0] == "p":
                        self.inline(sub[1], tags + ("B%d" % min(lvl, MAX_LEVEL),))
                        self.emit("\n", tags + ("B%d" % min(lvl, MAX_LEVEL),))
                    else:
                        self.block(sub, lvl, tags)
                    first = False
                elif sub[0] == "p":
                    self.inline(sub[1], tags + ("M%d" % min(lvl, MAX_LEVEL),))
                    self.emit("\n", tags + ("M%d" % min(lvl, MAX_LEVEL),))
                else:
                    self.block(sub, lvl, tags)
            if first:
                self.emit(mark + "\n", tags + ("B%d" % min(lvl, MAX_LEVEL),))

    def table_with_images(self, b, m):
        """그림이 든 칸이 있는 표: 글자 상자표로는 그림을 담을 수 없어서, 칸의 내용(글·그림)을 가로로 늘어놓는다.
        글 칸만 있는 빈 머리행은 건너뛴다."""
        if b[2]:
            self.emit(text_of(b[2]) + "\n", m + ("b",))
        for ri, r in enumerate(b[1]):
            inls = [cell_inline(c) for c in r]
            if ri == 0 and all(not text_of(i).strip() and not has_image(i) for i in inls):
                continue   # 비어 있는 머리행
            first = True
            for inl in inls:
                if not first:
                    self.emit("   │   ", m + ("muted",))
                first = False
                self.inline(inl, m + (("b",) if ri == 0 else ()))
            self.emit("\n", m)
            if ri == 0:
                self.emit("─" * 30 + "\n", m + ("hr",))
        self.emit("\n", m)

    def table_single_column(self, b, m):
        """칸이 하나뿐인 표: 표가 아니라 글을 담는 상자로 쓰인 것(옛 스크랩에 많다)이라 상자 표로 그리지 않고
        칸의 내용을 보통 글처럼 풀어서 보여 준다(<br> 은 줄바꿈). 비어 있는 칸은 건너뛴다."""
        if b[2]:
            self.emit(text_of(b[2]) + "\n", m + ("b",))
        for r in b[1]:
            inl = cell_inline(r[0])
            if not text_of(inl).strip() and not has_image(inl):
                continue
            self.inline(inl, m)
            self.emit("\n\n", m)

    def table(self, b, m):
        if b[1] and all(len(r) == 1 and r[0].get("cs", 1) == 1 for r in b[1]):
            return self.table_single_column(b, m)
        if any(has_image(cell_inline(c)) for r in b[1] for c in r):
            return self.table_with_images(b, m)
        rows = []
        for r in b[1]:
            row = []
            for c in r:
                row.append(text_of(cell_inline(c)).replace("\n", " "))
                row.extend([""] * (c.get("cs", 1) - 1))
            rows.append(row)
        if b[2]:
            self.emit(text_of(b[2]) + "\n", m + ("b",))
        if not rows:
            return
        cols = max(len(r) for r in rows)
        w = [max([width(r[i]) for r in rows if i < len(r)] + [1]) for i in range(cols)]
        for ri, r in enumerate(rows):
            cells = [pad(r[i] if i < len(r) else "", w[i]) for i in range(cols)]
            self.emit("│ " + " │ ".join(cells) + " │\n", m + ("code",))
            if ri == 0:
                self.emit("├─" + "─┼─".join("─" * x for x in w) + "─┤\n", m + ("code",))
        self.emit("\n", m)


def layout(doc, title=""):
    """Doc → [(글, 태그들, 덧붙임)]. 목차와 각주를 채워 돌려준다."""
    lay = Layout()
    # 목차를 위해 제목을 먼저 모은다
    def collect(bs):
        for b in bs:
            if b[0] == "h":
                lay._toc = getattr(lay, "_toc", []) + [(b[1], text_of(b[2]))]
            elif b[0] in ("quote",):
                collect(b[1])
            elif b[0] == "fold":
                collect(b[2])
    collect(doc.blocks)
    lay.heads = []
    if doc.redirect:
        lay.emit(f"→ {doc.redirect} 문서로 넘겨줍니다\n\n", ("chip",), ("link", "page", doc.redirect.split("#")[0]))
    lay.blocks(doc.blocks)
    if lay.notes:
        lay.emit("─" * 40 + "\n", ("hr",))
        for i, note in enumerate(lay.notes, 1):
            lay.emit(f"{i}. ", ("muted",))
            lay.inline(note, ("muted",))
            lay.emit("\n", ("muted",))
    if doc.cats:
        lay.emit("\n분류: ", ("muted",))
        lay.emit(", ".join(doc.cats) + "\n", ("muted", "b"))
    return lay.out
