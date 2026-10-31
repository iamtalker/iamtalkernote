"""위키 링크 [[노트 제목]] 규칙 (화면과 상관없는 순수 계산)

- 제목 비교는 대소문자·앞뒤/연속 공백을 무시한다.
- 같은 제목 노트가 여럿이면 가장 최근(mtime) 노트로 연결한다.
- 위키가 켜져 있으면 같은 제목은 만들지 못하게 한다(`taken`, `free_title`).
"""
import re

_FENCE = re.compile(r"(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$|`[^`\n]*`")
_LINK = re.compile(r"(?<!\\)\[\[([^\[\]\n]+?)\]\]")


def norm(title):
    return re.sub(r"\s+", " ", (title or "").strip()).casefold()


def split_target(raw):
    """'제목#절|표시글' → (제목, 절, 표시글). 없는 부분은 빈 글자"""
    target, _, label = (raw or "").partition("|")
    title, _, section = target.partition("#")
    return title.strip(), section.strip(), label.strip()


def links_in(text):
    """본문에 든 위키 링크 [(제목, 절, 표시글)] (코드 안은 건너뜀)"""
    out = []
    for m in _LINK.finditer(_FENCE.sub(lambda m: " " * len(m.group(0)), text or "")):
        title, section, label = split_target(m.group(1))
        if title:
            out.append((title, section, label))
    return out


def index(notes):
    """제목(정규화) → 그 제목 중 가장 최근 노트. notes 는 title·mtime·path 가 있는 dict"""
    best = {}
    for n in notes:
        k = norm(n["title"])
        cur = best.get(k)
        if cur is None or (n.get("mtime") or 0, n["path"]) > (cur.get("mtime") or 0, cur["path"]):
            best[k] = n
    return best


def latest(notes, title):
    return index(n for n in notes if norm(n["title"]) == norm(title)).get(norm(title))


def taken(title, titles, own=None):
    """그 제목이 이미 쓰이는가. titles = [(제목, 경로)] , own = 지금 고치는 노트의 경로(자기 자신은 제외)"""
    k = norm(title)
    return any(norm(t) == k and p != own for t, p in titles)


def free_title(base, titles, own=None):
    """겹치지 않는 제목: base, 겹치면 'base (2)', 'base (3)' …"""
    name, i = base, 2
    while taken(name, titles, own):
        name = f"{base} ({i})"
        i += 1
    return name


def open_token(before):
    """커서 앞의 글(그 줄)에서 아직 닫히지 않은 '[[' 뒤에 치던 글 → (시작 위치, 치던 글). 없으면 None"""
    i = before.rfind("[[")
    if i < 0:
        return None
    rest = before[i + 2:]
    if any(c in rest for c in "[]|#"):
        return None
    return i + 2, rest


def suggest(notes, prefix, limit=8):
    """제목 후보: 앞부분이 같은 것 → 글자가 들어 있는 것, 각각 최근 노트 순. 제목마다 하나만"""
    key = norm(prefix)
    pool = sorted(index(notes).values(), key=lambda n: -(n.get("mtime") or 0))
    first = [n["title"] for n in pool if norm(n["title"]).startswith(key)]
    rest = [n["title"] for n in pool if key in norm(n["title"]) and not norm(n["title"]).startswith(key)]
    return (first + rest)[:limit]


def backlinks(link_map, title):
    """link_map {경로: [링크 제목들]} 에서 title 을 가리키는 경로들"""
    k = norm(title)
    return sorted(p for p, ts in link_map.items() if any(norm(t) == k for t in ts))


def title_table(notes, min_len=2):
    """글 속 단어 자동 연결용: ({정규화한 제목: 가장 최근 노트의 제목}, 제목 길이들). 너무 짧은 제목은 뺀다"""
    best = index(notes)
    table = {k: n["title"] for k, n in best.items() if len(k) >= min_len}
    return table, sorted({len(k) for k in table}, reverse=True)


def _word_char(c):
    return c.isascii() and c.isalnum()


def auto_links(text, table, lengths, own=""):
    """text 에서 다른 노트 제목과 같은 낱말을 찾아 [(조각, 연결할 제목 또는 None)] 으로 쪼갠다(가장 긴 제목 먼저, 겹치지 않게).
    영문·숫자 제목은 낱말 경계에서만 맞추고, 한글은 조사가 붙으므로 경계를 보지 않는다. own = 이 노트의 제목(자기 자신은 잇지 않는다)"""
    low = text.lower()
    own = norm(own)
    out, i, last, n = [], 0, 0, len(text)
    while i < n:
        hit = None
        for ln in lengths:
            if i + ln > n:
                continue
            key = low[i:i + ln]
            if key in table and key != own:
                a, b = key[0], key[-1]
                if (_word_char(a) and i > 0 and _word_char(low[i - 1])) or (_word_char(b) and i + ln < n and _word_char(low[i + ln])):
                    continue
                hit = (ln, table[key])
                break
        if hit:
            if i > last:
                out.append((text[last:i], None))
            out.append((text[i:i + hit[0]], hit[1]))
            i += hit[0]
            last = i
        else:
            i += 1
    if last < n:
        out.append((text[last:], None))
    return out or [(text, None)]
