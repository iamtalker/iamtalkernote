"""위키 링크 [[노트 제목]] 규칙 (화면과 상관없는 순수 계산)

- 제목 비교는 대소문자·앞뒤/연속 공백을 무시한다.
- 같은 제목 노트가 여럿이면 가장 최근(mtime) 노트로 연결한다.
- 위키가 켜져 있으면 같은 제목은 만들지 못하게 한다(`taken`, `free_title`).
"""
import re

from i18n import tr

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


# ---- 노트북 범위: 최상위 노트북 하나가 위키 공간 하나(도쿠위키의 네임스페이스 묶음처럼). 옵션이 켜져 있을 때만 쓴다
def space(nb):
    """노트북 경로('A/B') → 위키 공간(최상위 노트북 'A'). 노트북 밖(저장 폴더 바로 아래)은 ''"""
    return (nb or "").split("/")[0]


def multi(notes):
    """제목(정규화) → 그 제목의 모든 노트 [노트]. 범위를 가를 때 쓴다"""
    out = {}
    for n in notes:
        out.setdefault(norm(n["title"]), []).append(n)
    return out


def pick(cands, nb, restrict):
    """같은 제목 후보 중 연결할 노트. restrict 이면 nb 와 같은 위키 공간만 보고, 같은 노트북(폴더)이 먼저, 그다음 가장 최근 노트"""
    if restrict:
        sp = space(nb)
        cands = [n for n in cands if space(n["nb"]) == sp]
        cands = [n for n in cands if n["nb"] == nb] or cands
    if not cands:
        return None
    return max(cands, key=lambda n: (n.get("mtime") or 0, n["path"]))


def in_space(notes, nb, restrict):
    """restrict 이면 nb 와 같은 위키 공간의 노트만"""
    if not restrict:
        return list(notes)
    sp = space(nb)
    return [n for n in notes if space(n["nb"]) == sp]


# ---- 포함(include): 줄에 ![[제목]] / ![[제목#절]] 만 있으면 그 노트의 내용을 그 자리에 보여 준다(옵시디언과 같은 문법)
_EMBED = re.compile(r"(?m)^[ \t]*!\[\[([^\[\]\n]+?)\]\][ \t]*$")
_FM = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.S)
_HEAD = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t#]*$")


def strip_meta(body):
    """맨 위 머리말(--- … ---)을 뺀 본문"""
    return _FM.sub("", body or "", count=1).lstrip("\n")


def section_of(body, section):
    """본문에서 제목이 section 인 절(그 제목 줄부터 같거나 높은 단계의 다음 제목 앞까지). 없으면 None. 코드 안의 # 줄은 제목이 아니다"""
    body = body or ""
    masked = _FENCE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), body).split("\n")
    lines = body.split("\n")
    want = norm(section)
    start = level = None
    for i, ln in enumerate(masked):
        m = _HEAD.match(ln)
        if not m:
            continue
        if start is None:
            if norm(m.group(2)) == want:
                start, level = i, len(m.group(1))
        elif len(m.group(1)) <= level:
            return "\n".join(lines[start:i]).rstrip("\n")
    return None if start is None else "\n".join(lines[start:]).rstrip("\n")


EMBED_DEPTH = 6        # 포함 속 포함의 최대 단계(순환은 따로 막는다)
EMBED_BUDGET = 150_000  # 한 번 그릴 때 펼치는 글자 수의 상한: 문서 하나가 수십만 글자로 펼쳐지면 화면이 십수 초 멈춘다


def expand_embeds(text, fetch, nb="", depth=EMBED_DEPTH, seen=(), budget=EMBED_BUDGET):
    """text 의 한 줄짜리 ![[제목]]·![[제목#절]] 을 그 노트의 내용(인용 블록, 맨 위 줄은 원본 노트 링크)으로 바꾼다.
    fetch(제목, 지금 노트북) → {"key","title","body","nb"} 또는 None. 같은 노트를 다시 품는 순환과 depth 단계보다 깊은 포함은 막는다.
    budget(글자 수)을 이 글 속 포함들이 똑같이 나눠 가지며, 몫보다 긴 문서는 앞부분만 보이고 '위 링크를 누르면 전체' 안내가 붙는다(그 속의 포함은 남은 몫만큼).
    코드 블록 안의 것은 건드리지 않는다"""
    if "![[" not in (text or ""):
        return text
    code = [(m.start(), m.end()) for m in _FENCE.finditer(text)]
    live = [m for m in _EMBED.finditer(text) if not any(a <= m.start() < b for a, b in code)]
    share = budget // max(1, len(live))
    more = tr("…(길어서 여기까지만 보입니다. 위 링크를 누르면 전체가 열립니다)")

    def one(m):
        if any(a <= m.start() < b for a, b in code):
            return m.group(0)
        title, section, _label = split_target(m.group(1))
        if not title:
            return m.group(0)
        if depth <= 0:
            return tr("> ⚠ 너무 깊이 포함됨: ") + title
        hit = fetch(title, nb)
        if hit is None:
            return tr("> ⚠ 없는 노트: ") + title
        if hit["key"] in seen:
            return tr("> ⚠ 서로 포함함(순환): ") + hit["title"]
        body = strip_meta(hit["body"])
        if not section:    # 문서 맨 위 제목이 노트 제목과 같으면 맨 위 [[링크]] 줄과 겹치므로 뺀다
            first = body.split("\n", 1)
            h = _HEAD.match(first[0])
            if h and norm(h.group(2)) == norm(hit["title"]):
                body = first[1].lstrip("\n") if len(first) > 1 else ""
        if section:
            body = section_of(body, section)
            if body is None:
                return tr("> ⚠ 없는 절: ") + hit["title"] + "#" + section
        if share <= 0:
            body = more
        elif len(body) > share:     # 몫보다 길면 줄 경계에서 자른다
            cut = body[:share]
            body = (cut[:cut.rfind("\n")] if "\n" in cut else cut).rstrip() + "\n\n" + more
        body = expand_embeds(body, fetch, hit["nb"], depth - 1, seen + (hit["key"],), share - len(body))
        lines = ["[[" + hit["title"] + "]]", ""] + body.strip("\n").split("\n")
        return "\n".join(("> " + ln) if ln.strip() else ">" for ln in lines)
    return _EMBED.sub(one, text)
