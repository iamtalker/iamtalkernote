"""폴더검색(folder-search)의 검색 엔진 이식.
AND / OR / NOT + 괄호, & | ! 기호, "정확한 구절", 관련도(밀도)순·최신순, 수정일 기간, 일치 단어 강조."""
import calendar
import re
import time

TOKEN_RE = re.compile(r'"([^"]*)"|\(|\)|&+|\|+|!+|\bAND\b|\bOR\b|\bNOT\b|[^\s&|]+')


def tokenize(q):
    tokens, depth = [], 0
    for m in TOKEN_RE.finditer(q):
        t = m.group(0)
        if t == "(":
            tokens.append(("(", None))
            depth += 1
        elif t == ")":
            tokens.append((")", None))
            depth = max(0, depth - 1)
        elif t == "AND" or t[0] == "&":
            tokens.append(("AND", None))
        elif t == "OR" or t[0] == "|":
            tokens.append(("OR", None))
        elif t == "NOT" or t[0] == "!":
            tokens.append(("NOT", None))
        elif m.group(1) is not None:
            tokens.append(("WORD", m.group(1)))
        else:
            stripped = t.rstrip(")")
            close = min(depth, len(t) - len(stripped))
            if close:
                core = t[:len(t) - close]
                if core:
                    tokens.append(("WORD", core))
                tokens.extend([(")", None)] * close)
                depth -= close
            else:
                tokens.append(("WORD", t))
    return tokens


def parse(q):
    tokens, pos = tokenize(q), [0]

    def peek():
        return tokens[pos[0]][0] if pos[0] < len(tokens) else None

    def nxt():
        pos[0] += 1
        return tokens[pos[0] - 1]

    def p_or():
        node = p_and()
        while peek() == "OR":
            nxt()
            node = ("OR", node, p_and())
        return node

    def p_and():
        node = p_factor()
        while peek() in ("AND", "NOT", "WORD", "("):
            op = "AND"
            if peek() in ("AND", "NOT"):
                op = nxt()[0]
            if op == "AND" and peek() == "NOT":
                op = nxt()[0]
            right = p_factor()
            if right is None:
                break
            node = (op, node, right)
        return node

    def p_factor():
        k = peek()
        if k is None:
            return None
        if k == "(":
            nxt()
            node = p_or()
            if peek() == ")":
                nxt()
            return node
        if k == "WORD":
            return ("WORD", nxt()[1].lower())
        return None

    return p_or() if tokens else None


def match(node, hay):
    if node is None:
        return True
    op = node[0]
    if op == "WORD":
        return node[1] in hay
    if op == "AND":
        return match(node[1], hay) and match(node[2], hay)
    if op == "OR":
        return match(node[1], hay) or match(node[2], hay)
    if op == "NOT":
        return match(node[1], hay) and not match(node[2], hay)
    return True


def positive_words(node, out=None):
    out = [] if out is None else out
    if node is None:
        return out
    if node[0] == "WORD":
        out.append(node[1])
    elif node[0] == "NOT":
        positive_words(node[1], out)
    else:
        positive_words(node[1], out)
        positive_words(node[2], out)
    return out


def score(hay, title, words, raw_query):
    """글자 수 대비 밀도(긴 글이 단어 수만으로 이기지 않게) + 제목 일치 가산점"""
    raw = sum(hay.count(w) for w in words if w)
    s = 1000 * raw / max(1, len(hay))
    t, q = title.lower(), raw_query.strip().lower()
    if q and t == q:
        s += 1000
    elif q and q in t:
        s += 50
    return s


def snippet(body, words, radius=70):
    flat = re.sub(r"\s+", " ", body)
    low = flat.lower()
    idx = -1
    for w in words:
        idx = low.find(w)
        if idx != -1:
            break
    if idx == -1:
        return flat[:radius * 2]
    a, b = max(0, idx - radius), min(len(flat), idx + radius)
    return ("…" if a > 0 else "") + flat[a:b] + ("…" if b < len(flat) else "")


DATE_RE = re.compile(r"^(\d{4})(?:[.\-/]?(\d{1,2})(?:[.\-/]?(\d{1,2}))?)?$")
DATE_TOKEN = re.compile(r"(?<!\S)(?:date|날짜|기간):(\S*)", re.I)


def parse_date(s, end=False):
    """'2021.01.01' / '2021-1-1' / '2021/1/1' / '20210101' / '202101'(그 달) / '2021'(그 해) → 그 날의 시작·끝 (epoch 초). 안 읽히면 None"""
    m = DATE_RE.match((s or "").strip())
    if not m:
        return None
    y = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else (12 if end else 1)
    if m.group(3):
        d = int(m.group(3))
    else:
        d = calendar.monthrange(y, mo)[1] if end and 1 <= mo <= 12 else 1
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    try:
        return time.mktime((y, mo, d, 23 if end else 0, 59 if end else 0, 59 if end else 0, 0, 0, -1))
    except (OverflowError, ValueError):
        return None


def bad_dates(query, date_from="", date_to=""):
    """읽을 수 없는 날짜(없는 달·날, 모양이 틀린 것)가 든 조각들. 조용히 무시하면 기간이 안 걸려 엉뚱한 결과가 나오므로 알려 준다"""
    bad = []
    for m in DATE_TOKEN.finditer(query):
        tok = m.group(1)
        if re.fullmatch(r"\d{8}(-\d{8})?|\d{8}-|-\d{8}", tok):
            parts = [x for x in tok.split("-") if x] if tok.count("-") <= 1 else [tok]
        else:
            parts = [tok]
        if not parts or any(parse_date(x) is None for x in parts):
            bad.append("date:" + tok)
    for label, v in (("기간 시작", date_from), ("기간 끝", date_to)):
        v = (v or "").strip()
        if re.fullmatch(r"\d{8}|\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", v) and parse_date(v) is None:   # 다 쓴 날짜만 검사(치는 중인 글은 건드리지 않는다)
            bad.append(f"{label} {v}")
    return bad


def split_date(query):
    """검색식 속의 'date:20101011-20240104' (또는 date:20240101 · date:20240101- · date:-20240104, 날짜:·기간: 도 같음)를 떼어 낸다
    → (남은 검색식, 시작 epoch 또는 None, 끝 epoch 또는 None). 날짜 형식은 parse_date 와 같다"""
    f = t = None
    for m in DATE_TOKEN.finditer(query):
        a, sep, b = m.group(1).partition("-") if re.fullmatch(r"\d{8}(-\d{8})?|\d{8}-|-\d{8}", m.group(1)) else (m.group(1), "", "")
        if not sep:                                   # 하나만 쓰면 그 날(달·해)
            lo, hi = parse_date(a), parse_date(a, True)
        else:
            lo, hi = (parse_date(a) if a else None), (parse_date(b, True) if b else None)
        f = lo if f is None else (f if lo is None else max(f, lo))
        t = hi if t is None else (t if hi is None else min(t, hi))
    return DATE_TOKEN.sub(" ", query).strip(), f, t


def title_bonus(title, q):
    t, q = title.lower(), q.strip().lower()
    if q and t == q:
        return 1000
    if q and q in t:
        return 50
    return 0


def run(notes, query="", sort="relevance", asc=False, date_from="", date_to="", index=None):
    """notes: [{title, mtime, ...}] → (정렬된 일치 목록, 강조할 단어들).
    index(색인 DB, store.Store)가 있으면 본문 검색을 DB 안에서 하고, 없으면 메모리의 본문으로 한다."""
    q, qf, qt = split_date(query.strip())             # 검색식 속의 date:기간
    node = parse(q) if q else None
    words = positive_words(node)
    f, t = parse_date(date_from), parse_date(date_to, True)
    f = qf if f is None else (f if qf is None else max(f, qf))
    t = qt if t is None else (t if qt is None else min(t, qt))
    dkey = "ctime" if sort == "ctime" else "mtime"   # 기간 필터는 지금 정렬 기준의 날짜에 건다
    hits = None
    if node is not None and index is not None:
        hits = index.query_hits(node, words, scoring=(sort == "relevance"))
    out = []
    for n in notes:
        if f is not None and n.get(dkey, n["mtime"]) < f:
            continue
        if t is not None and n.get(dkey, n["mtime"]) > t:
            continue
        if node is not None:
            if hits is not None and "key" in n:
                if n["key"] not in hits:
                    continue
            else:
                if "_hay" not in n:
                    n["_hay"] = (n["title"] + "\n" + (n.read() if hasattr(n, "read") else n["body"])).lower()
                if not match(node, n["_hay"]):
                    continue
        out.append(n)
    if sort == "relevance" and q:
        for n in out:
            if hits is not None and "key" in n:
                n["_score"] = hits[n["key"]] + title_bonus(n["title"], q)
            else:
                n["_score"] = score(n["_hay"], n["title"], words, q)
        out.sort(key=lambda n: n["_score"], reverse=not asc)
    elif sort == "ctime":
        out.sort(key=lambda n: n.get("ctime", n["mtime"]), reverse=not asc)
    elif sort == "title":
        out.sort(key=lambda n: n["title"].lower(), reverse=asc)   # 기본은 가나다순
    else:
        out.sort(key=lambda n: n["mtime"], reverse=not asc)
    return out, words
