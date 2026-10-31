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
