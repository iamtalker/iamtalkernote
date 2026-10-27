"""공통 구조(AST).

문서 = Doc(blocks, cats, redirect)
블록(리스트, 첫 칸이 종류):
  ["h", 단계1~6, 인라인들]            ["p", 인라인들]
  ["list", 번호있음?, [항목(블록들), ...]]
  ["code", 언어, 글]                  ["pre", 글]            ["math", 수식]
  ["quote", 블록들]                   ["hr"]                 ["toc"]    ["refs"]
  ["table", 줄들, 제목인라인들]  줄 = [칸, ...], 칸 = {"h": 머리칸?, "cs": 가로합침, "rs": 세로합침, "al": 정렬, "c": 인라인들}
  ["fold", 요약인라인들, 블록들]
  ["tpl", 이름, [[키 또는 None, 값글], ...]]
  ["raw", 형식, 원문]
인라인:
  ["t", 글]  ["b"|"i"|"u"|"s"|"sup"|"sub", 인라인들]  ["code", 글]  ["br"]  ["math", 수식]
  ["link", 문서, 인라인들 또는 None, 앵커]   ["url", 주소, 인라인들 또는 None]
  ["img", 파일 또는 주소, 설명]   ["video", 서비스, 영상ID]   ["fn", 이름, 인라인들]   ["tpl", 이름, 인자]   ["raw", 형식, 원문]
문서 제목의 이름공간은 공통으로 '분류:' 와 '틀:' 을 쓴다(각 형식이 읽고 쓸 때 바꾼다).
"""


class Doc:
    __slots__ = ("blocks", "cats", "redirect")

    def __init__(self, blocks=None, cats=None, redirect=None):
        self.blocks = blocks or []
        self.cats = cats or []
        self.redirect = redirect

    def __repr__(self):
        return f"Doc({self.blocks!r}, cats={self.cats!r}, redirect={self.redirect!r})"


CAT = "분류:"
TPL = "틀:"


# 영상 끼워 넣기: 서비스 이름 → (표시 이름, 주소 틀). 끼워 넣기가 없는 형식은 '▶ 표시 이름에서 보기' 링크로 쓴다.
VIDEOS = {"youtube": ("유튜브", "https://www.youtube.com/watch?v={}"),
          "nicovideo": ("니코니코 동화", "https://www.nicovideo.jp/watch/{}"),
          "vimeo": ("비메오", "https://vimeo.com/{}"),
          "kakaotv": ("카카오TV", "https://tv.kakao.com/v/{}"),
          "navertv": ("네이버TV", "https://tv.naver.com/v/{}")}


def video_url(service, vid):
    return VIDEOS[service][1].format(vid)


def youtube_id(url):
    """유튜브 영상 주소(youtu.be/ID · watch?v=ID · embed/ID · shorts/ID)에서 ID. 아니면 None."""
    import re
    m = re.match(r"(?i)https?://(?:youtu\.be/|(?:www\.|m\.)?youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|embed/|shorts/))([\w-]+)", url.strip())
    return m.group(1) if m else None


def video_label(service):
    return f"▶ {VIDEOS[service][0]}에서 보기"


def video_from_link(url, label):
    """['video', 서비스, ID] 를 링크로 쓴 것(주소와 '▶ …에서 보기' 글이 맞을 때)을 영상으로 되돌린다. 아니면 None."""
    for svc, (name, fmt) in VIDEOS.items():
        head, tail = fmt.split("{}")
        if label == video_label(svc) and url.startswith(head) and url.endswith(tail) and len(url) > len(head) + len(tail):
            return ["video", svc, url[len(head):len(url) - len(tail) if tail else None]]
    return None


def text_of(inl):
    """인라인들의 글자만."""
    out = []
    for n in inl or []:
        k = n[0]
        if k == "t" or k == "code" or k == "math":
            out.append(n[1])
        elif k in ("b", "i", "u", "s", "sup", "sub"):
            out.append(text_of(n[1]))
        elif k == "link":
            out.append(text_of(n[2]) if n[2] else n[1])
        elif k == "url":
            out.append(text_of(n[2]) if n[2] else n[1])
        elif k == "br":
            out.append(" ")
        elif k == "video":
            out.append(video_label(n[1]))
    return "".join(out)


def merge_text(inl):
    """이웃한 글자 조각을 합친다."""
    out = []
    for n in inl:
        if n[0] == "t" and out and out[-1][0] == "t":
            out[-1] = ["t", out[-1][1] + n[1]]
        elif n[0] != "t" or n[1]:
            out.append(n)
    return out


class InlineScanner:
    """문법별 인라인 해석을 돕는 틀: rules = [(정규식, 함수(m) → 노드 또는 노드들)] 를 앞에서부터 가장 먼저 맞는 것으로."""

    def __init__(self, rules):
        import re
        self.rules = rules
        def scoped(rx):  # 규칙마다 준 대소문자 무시·여러 줄 옵션을 합친 식 안에서도 지키게
            f = ("i" if rx.flags & re.I else "") + ("s" if rx.flags & re.S else "") + ("m" if rx.flags & re.M else "")
            return f"(?{f}:{rx.pattern})" if f else rx.pattern
        self.master = re.compile("|".join(f"(?P<r{i}>{scoped(rx)})" for i, (rx, _) in enumerate(rules)))
        self.groups = [f"r{i}" for i in range(len(rules))]

    def scan(self, s):
        out, pos = [], 0
        for m in self.master.finditer(s):
            if m.start() < pos:
                continue
            idx = next(i for i, g in enumerate(self.groups) if m.group(g) is not None)
            rx, fn = self.rules[idx]
            sub = rx.match(s, m.start())
            if not sub or sub.end() != m.end():
                sub = rx.fullmatch(m.group(0))
            if sub is None:
                continue
            res = fn(sub)
            if res is None:
                continue
            if m.start() > pos:
                out.append(["t", s[pos:m.start()]])
            if res and isinstance(res[0], list):
                out.extend(res)
            elif res:
                out.append(res)
            pos = m.end()
        if pos < len(s):
            out.append(["t", s[pos:]])
        return merge_text(out)


def build_lists(items, para):
    """[(깊이, 번호있음?, 글)] → 목록 블록들. 같은 깊이에서 번호 여부가 바뀌면 새 목록을 시작한다.
    para(글) → 항목 첫 블록."""
    out, k = [], 0

    def build(k, depth):
        lst = ["list", items[k][1], []]
        while k < len(items) and items[k][0] >= depth:
            d, ordered, body = items[k][:3]
            if d > depth:
                subs = []
                while k < len(items) and items[k][0] > depth:
                    sub, k = build(k, items[k][0])
                    subs.append(sub)
                if not lst[2]:
                    lst[2].append([])
                lst[2][-1].extend(subs)
                continue
            if ordered != lst[1]:
                break
            lst[2].append([para(body)])
            k += 1
        return lst, k

    while k < len(items):
        lst, k = build(k, items[k][0])
        out.append(lst)
    return out


def tidy(doc):
    """읽은 뒤 공통 정리: 문단 앞뒤 빈칸·줄바꿈을 걷어 내고, 빈 문단은 뺀다(형식마다 빈칸 처리가 달라 왕복이 흔들리지 않게)."""
    def trim(inl):
        inl = [list(n) for n in inl]
        while inl and (inl[0][0] == "br" or (inl[0][0] == "t" and not inl[0][1].strip())):
            inl.pop(0)
        while inl and (inl[-1][0] == "br" or (inl[-1][0] == "t" and not inl[-1][1].strip())):
            inl.pop()
        if inl and inl[0][0] == "t":
            inl[0][1] = inl[0][1].lstrip()
        if inl and inl[-1][0] == "t":
            inl[-1][1] = inl[-1][1].rstrip()
        return inl

    def blocks(bs):
        out = []
        for b in bs:
            k = b[0]
            if k == "p":
                inl = trim(b[1])
                if len(inl) == 1 and inl[0][0] == "tpl":  # 틀 하나만 있는 문단은 틀 블록으로(형식마다 같게)
                    out.append(["tpl", inl[0][1], inl[0][2]])
                elif inl:
                    out.append(["p", inl])
                continue
            if k == "h":
                b = ["h", b[1], trim(b[2])]
            elif k == "list":
                b = ["list", b[1], [blocks(item) for item in b[2]]]
            elif k == "quote":
                b = ["quote", blocks(b[1])]
            elif k == "fold":
                b = ["fold", trim(b[1]), blocks(b[2])]
            elif k == "table":
                for r in b[1]:
                    for c in r:
                        c["c"] = trim(c["c"])
                        if c.get("b"):
                            c["b"] = blocks(c["b"])
                b = ["table", b[1], trim(b[2])]
            out.append(b)
        return out
    doc.blocks = blocks(doc.blocks)
    return doc


def raw_fallback(src):
    """다른 형식의 원문 보존 조각을 이 형식에서 보여 줄 때: HTML 이면 글자만, 아니면 None(코드로 보여 줌)."""
    import html as _h
    import re as _re
    s = src
    m = _re.match(r"\{\{\{#!html\s?(.*)\}\}\}$", s, _re.S)
    if m:
        s = m.group(1)
    elif not _re.search(r"<[a-zA-Z][^>]*>", s):
        return None
    s = _re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=_re.S | _re.I)
    s = _re.sub(r"<br\s*/?>", " ", s, flags=_re.I)
    return _h.unescape(_re.sub(r"<[^>]+>", "", s)).strip()


def flatten_blocks(blocks):
    """블록들 → 줄 안 노드(줄바꿈으로 이음). 칸 안에 블록을 담을 수 없는 형식에서 쓴다."""
    out = []

    def add(inl):
        if out:
            out.append(["br"])
        out.extend(inl)

    def walk(bs):
        for b in bs:
            k = b[0]
            if k == "p":
                add(b[1])
            elif k == "h":
                add([["b", b[2]]])
            elif k == "list":
                for item in b[2]:
                    walk(item)
            elif k in ("quote",):
                walk(b[1])
            elif k == "fold":
                add([["b", b[1]]])
                walk(b[2])
            elif k == "table":
                for r in b[1]:
                    add([n for c in r for n in (cell_inline(c) + [["t", " "]])])
            elif k in ("code", "pre"):
                add([["code", b[-1]]])
            elif k == "tpl":
                add([["tpl", b[1], b[2]]])
    walk(blocks)
    return merge_text(out)


def cell_inline(c):
    return c["c"] if not c.get("b") else flatten_blocks(c["b"])
