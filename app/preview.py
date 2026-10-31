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


def pad(s, n, al=""):
    """칸 너비 n 에 맞춰 채운다. al: 'right' 는 오른쪽 맞춤, 'center' 는 가운데, 그 밖은 왼쪽"""
    gap = max(0, n - width(s))
    if al == "right":
        return " " * gap + s
    if al == "center":
        return " " * (gap // 2) + s + " " * (gap - gap // 2)
    return s + " " * gap


def wrap_cell(s, w):
    """표 칸의 글을 표시 너비 w 안에서 줄바꿈한 줄들(영문은 낱말 경계, 낱말이 w 보다 길거나 한글은 글자 단위). 빈 글은 ['']"""
    lines, cur = [], ""
    for word in s.split(" "):
        sep = " " if cur else ""
        if width(cur) + len(sep) + width(word) <= w:
            cur += sep + word
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while width(word) > w:          # 낱말 하나가 칸보다 길면 글자 단위로 자른다
            head, k = "", 0
            while k < len(word) and width(head + word[k]) <= w:
                head += word[k]
                k += 1
            head = head or word[0]
            lines.append(head)
            word = word[len(head):]
        cur = word
    lines.append(cur)
    return lines


def fit_columns(w, avail):
    """열 너비 w 의 합이 avail 보다 크면, 좁은 열은 그대로 두고 남은 칸을 넓은 열이 똑같이 나눠 갖게 줄인다(열마다 최소 2칸)"""
    if sum(w) <= avail:
        return list(w)
    out = [0] * len(w)
    free = list(range(len(w)))
    rest = max(avail, 2 * len(w))
    while free:
        share = max(2, rest // len(free))
        small = [i for i in free if w[i] <= share]
        if not small:
            for i in free:
                out[i] = share
            break
        for i in small:
            out[i] = w[i]
            rest -= w[i]
            free.remove(i)
    return out


def wrap_px(s, w, ms):
    """wrap_cell 의 픽셀판: 칸 너비 w(픽셀) 안에서 줄바꿈한 줄들. ms(글) = 글꼴에서 차지하는 픽셀 너비. 영문은 낱말 경계, 긴 낱말·한글은 글자 단위"""
    lines, cur = [], ""
    for word in s.split(" "):
        sep = " " if cur else ""
        if ms(cur + sep + word) <= w:
            cur += sep + word
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while ms(word) > w:
            head = ""
            for ch in word:
                if ms(head + ch) > w and head:
                    break
                head += ch
            lines.append(head)
            word = word[len(head):]
        cur = word
    lines.append(cur)
    return lines


def fit_px(w, avail, minw):
    """열 너비(픽셀) w 의 합이 avail 보다 크면 fit_columns 처럼 줄인다(열마다 최소 minw)"""
    if sum(w) <= avail:
        return list(w)
    out = [0] * len(w)
    free = list(range(len(w)))
    rest = max(avail, minw * len(w))
    while free:
        share = max(minw, rest // len(free))
        small = [i for i in free if w[i] <= share]
        if not small:
            for i in free:
                out[i] = share
            break
        for i in small:
            out[i] = w[i]
            rest -= w[i]
            free.remove(i)
    return out


def tab_tag(stops):
    """표의 탭 정지점 [(픽셀, 'l'|'r'|'c')] → 태그 이름('T:14l;150r;…'). 화면(notes.py)이 이 이름을 읽어 Text 태그의 tabs 로 만든다"""
    return "T:" + ";".join("%d%s" % (x, s) for x, s in stops)


class Layout:
    def __init__(self, cols=None, avail=None, measure=None):
        self.cols = cols            # 렌더링 칸에 들어가는 고정폭 글자 수(None 이면 줄이지 않는다). avail·measure 가 있으면 쓰지 않는다
        self.avail = avail          # 렌더링 칸에 들어가는 픽셀 너비
        self.measure = measure      # 표 글꼴로 글의 픽셀 너비를 재는 함수. avail·measure 가 있으면 표를 탭 정지점으로 맞춘다(한글·영문 폭이 달라도 열이 어긋나지 않음)
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
        rows, aligns = [], {}
        for r in b[1]:
            row = []
            for c in r:
                if c.get("al") and len(row) not in aligns:
                    aligns[len(row)] = c["al"]      # 칸 정렬(:--  --:  :-:)은 그 열의 첫 지정을 따른다
                row.append(text_of(cell_inline(c)).replace("\n", " "))
                row.extend([""] * (c.get("cs", 1) - 1))
            rows.append(row)
        if b[2]:
            self.emit(text_of(b[2]) + "\n", m + ("b",))
        if not rows:
            return
        if self.avail and self.measure:
            return self.table_px(rows, aligns, m)
        cols = max(len(r) for r in rows)
        w = [max([width(r[i]) for r in rows if i < len(r)] + [1]) for i in range(cols)]
        wrapped = False
        if self.cols and len(rows) > 1 and self.cols - (3 * cols + 1) < 4 * cols:
            # 칸이 너무 좁아 열마다 4칸도 못 쓰면 상자 대신 행마다 '머리글: 값' 으로 풀어 보여 준다
            for r in rows[1:]:
                for i, c in enumerate(r):
                    if not c.strip():
                        continue
                    label = rows[0][i].strip() if i < len(rows[0]) else ""
                    if label:
                        self.emit(label + ": ", m + ("b",))
                    self.emit(c + "\n", m)
                self.emit("\n", m)
            return
        if self.cols:       # 칸이 좁으면 열 너비를 줄이고 칸 안의 글을 줄바꿈한다(안 그러면 줄이 꺾여 상자가 깨진다)
            fit = fit_columns(w, self.cols - (3 * cols + 1))
            wrapped, w = fit != w, fit
        for ri, r in enumerate(rows):
            cells = [r[i] if i < len(r) else "" for i in range(cols)]
            pieces = [wrap_cell(c, w[i]) if wrapped else [c] for i, c in enumerate(cells)]
            for li in range(max(len(p) for p in pieces)):
                line = [pad(p[li] if li < len(p) else "", w[i], aligns.get(i, "") if ri else "left") for i, p in enumerate(pieces)]   # 머리행은 왼쪽 맞춤
                self.emit("│ " + " │ ".join(line) + " │\n", m + ("code",))
            if ri == 0:
                self.emit("├─" + "─┼─".join("─" * x for x in w) + "─┤\n", m + ("code",))
        self.emit("\n", m)

    def table_px(self, rows, aligns, m):
        """표를 픽셀 단위로 그린다. 줄마다 '<탭>글<탭>글<탭>…' 이고 탭 정지점(왼쪽·오른쪽·가운데)이 열 위치와 정렬을 맡으므로
        글꼴이 고정폭이 아니어도(한글·영문 폭이 달라도) 열이 정확히 맞는다. 머리행은 굵게 + 아래 가로줄 하나(세로줄 없음).
        칸이 좁으면 열을 줄이고 글을 줄바꿈하며, 열마다 4글자도 못 쓰면 행마다 '머리글: 값' 카드."""
        ms = self.measure
        cw = max(1, ms("0"))
        n = max(len(r) for r in rows)
        rows = [r + [""] * (n - len(r)) for r in rows]
        W = [max([ms(r[i]) for r in rows] + [cw]) for i in range(n)]
        room = self.avail - 3 * cw * n                       # 칸마다 왼쪽 여백 1글자 + 오른쪽 여백 2글자를 뺀, 글이 쓸 수 있는 너비
        if sum(W) > room:
            if len(rows) > 1 and room < 4 * cw * n:
                for r in rows[1:]:      # 표 대신 행마다 '머리글: 값'
                    for i, c in enumerate(r):
                        if not c.strip():
                            continue
                        if rows[0][i].strip():
                            self.emit(rows[0][i].strip() + ": ", m + ("b",))
                        self.emit(c + "\n", m)
                    self.emit("\n", m)
                return
            W = fit_px(W, room, 2 * cw)
        wrapped = [[wrap_px(r[i], W[i], ms) if ms(r[i]) > W[i] else [r[i]] for i in range(n)] for r in rows]
        body, x = [], 0
        for j in range(n):
            left = x + cw                                    # 이 열의 글이 시작하는 곳
            al = aligns.get(j, "")
            body.append((left + W[j], "r") if al == "right" else (left + W[j] // 2, "c") if al == "center" else (left, "l"))
            x += 3 * cw + W[j]
            body.append((x, "l"))
        tb = tab_tag(body)                                   # 머리행도 그 열의 정렬을 따른다(GFM 과 같음)
        # 칸마다 태그를 달아 Text 의 태그 테두리로 격자선을 그린다. 같은 태그가 이어지면 바깥 테두리 하나만 생기므로
        # 이웃한 칸의 태그 이름을 달리한다(행·열 홀짝 4종: tb00 tb01 tb10 tb11, 머리행 th0 th1). 한 칸의 줄바꿈된 줄들은 같은 태그라 한 칸으로 묶인다.
        for ri, r in enumerate(wrapped):
            for li in range(max(len(p) for p in r)):
                for j, p in enumerate(r):
                    cell = ("th%d" % (j % 2)) if ri == 0 else ("tb%d%d" % ((ri - 1) % 2, j % 2))
                    self.emit("\t" + (p[li] if li < len(p) else "") + "\t", m + (cell, tb))
                self.emit("\n", m + (tb,))
        self.emit("\n", m)


def layout(doc, title="", cols=None, avail=None, measure=None):
    """Doc → [(글, 태그들, 덧붙임)]. 목차와 각주를 채워 돌려준다. 표를 칸 폭에 맞추려면 avail(픽셀)+measure(글→픽셀) 또는 cols(글자 수)"""
    lay = Layout(cols, avail, measure)
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
