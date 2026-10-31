"""아웃라이너 모델: 노트 원문(마크다운 목록) ↔ 항목의 평평한 목록(깊이 + 글). 화면을 모르는 순수 계산이라 따로 시험한다.
항목 목록은 위에서 아래 순서이고, 항목의 하위는 바로 뒤에 이어지는 더 깊은 항목들이다."""
import re

LIST = re.compile(r"^(?P<ind>[ \t]*)(?:[-*+]|\d+[.)])(?:[ \t]+(?P<text>.*?))?[ \t]*$")
UNIT = "    "


class Item:
    __slots__ = ("depth", "text", "collapsed")

    def __init__(self, depth, text, collapsed=False):
        self.depth, self.text, self.collapsed = depth, text, collapsed

    def __repr__(self):
        return f"Item({self.depth}, {self.text!r}{', collapsed' if self.collapsed else ''})"


def _width(ind):
    return len(ind.replace("\t", UNIT))


def parse(body):
    """원문 → [Item]. 목록이 아닌 줄은 바로 앞 항목과 같은 깊이의 항목으로 넣고, 빈 줄은 건너뛴다"""
    items, stack = [], []                         # stack: 들여쓰기 폭들
    for line in body.split("\n"):
        if not line.strip():
            continue
        m = LIST.match(line)
        if not m:
            items.append(Item(items[-1].depth if items else 0, line.strip()))
            continue
        w = _width(m.group("ind"))
        while stack and stack[-1] >= w:
            stack.pop()
        items.append(Item(len(stack), m.group("text") or ""))
        stack.append(w)
    normalize(items)
    return items


def dump(items):
    return "\n".join(UNIT * it.depth + "- " + it.text for it in items) + ("\n" if items else "")


def normalize(items):
    """첫 항목은 깊이 0, 그 뒤 항목은 앞 항목보다 한 단계보다 더 깊을 수 없다"""
    prev = -1
    for it in items:
        it.depth = max(0, min(it.depth, prev + 1))
        prev = it.depth


def end_of(items, i):
    """항목 i 의 하위까지 포함한 끝(그 다음 항목 번호)"""
    d = items[i].depth
    j = i + 1
    while j < len(items) and items[j].depth > d:
        j += 1
    return j


def has_children(items, i):
    return i + 1 < len(items) and items[i + 1].depth > items[i].depth


def visible(items, zoom=None):
    """화면에 보이는 항목 번호들: 접힌 항목의 하위는 숨기고, zoom 이 있으면 그 항목의 하위만"""
    if zoom is None:
        lo, hi = 0, len(items)
    else:
        lo, hi = zoom + 1, end_of(items, zoom)
    out, i = [], lo
    while i < hi:
        out.append(i)
        i = end_of(items, i) if items[i].collapsed else i + 1
    return out


def ancestors(items, i):
    """항목 i 의 부모들(맨 위부터)"""
    out, d = [], items[i].depth
    for j in range(i - 1, -1, -1):
        if items[j].depth < d:
            out.append(j)
            d = items[j].depth
    return out[::-1]


def split(items, i, col):
    """Enter: 항목 i 를 col 에서 나눈다. 하위가 보이면 첫 자식, 아니면 같은 깊이 다음 항목. 맨 앞에서 누르면 위에 빈 항목.
    → 커서가 갈 (항목 번호, 글자 위치)"""
    it = items[i]
    if col == 0 and it.text:
        items.insert(i, Item(it.depth, ""))
        return i + 1, 0
    before, after = it.text[:col], it.text[col:]
    it.text = before
    if has_children(items, i) and not it.collapsed:
        items.insert(i + 1, Item(it.depth + 1, after))
        return i + 1, 0
    at = end_of(items, i)
    items.insert(at, Item(it.depth, after))
    return at, 0


def indent(items, i, floor=0):
    """Tab: 항목과 그 하위를 한 단계 안으로. 앞 항목보다 깊을 수 없고, 줌인한 맨 위(floor) 아래로는 못 들어감. 했으면 True"""
    if i <= 0 or items[i].depth > items[i - 1].depth or items[i].depth < floor:
        return False
    for j in range(i, end_of(items, i)):
        items[j].depth += 1
    return True


def outdent(items, i, floor=0):
    """Shift+Tab: 한 단계 밖으로(뒤따르던 형제는 이 항목의 하위가 된다. WorkFlowy 와 같다). 했으면 True"""
    if items[i].depth <= floor:
        return False
    for j in range(i, end_of(items, i)):
        items[j].depth -= 1
    normalize(items)
    return True


def move(items, i, up, lo=0, hi=None):
    """항목(하위 포함)을 같은 깊이의 위/아래 형제와 맞바꾼다 → 옮겨진 항목 번호, 못 옮기면 None"""
    hi = len(items) if hi is None else hi
    end = end_of(items, i)
    d = items[i].depth
    if up:
        j = i - 1
        while j >= lo and items[j].depth > d:
            j -= 1
        if j < lo or items[j].depth != d:
            return None
        items[j:end] = items[i:end] + items[j:i]
        return j
    if end >= hi or items[end].depth != d:
        return None
    nend = end_of(items, end)
    items[i:nend] = items[end:nend] + items[i:end]
    return i + (nend - end)


def merge_prev(items, i, prev):
    """Backspace(맨 앞): 항목 i 의 글을 보이는 앞 항목 prev 의 끝에 붙인다. 하위는 앞 항목의 하위로 남는다 → (커서 항목, 글자 위치)"""
    col = len(items[prev].text)
    items[prev].text += items[i].text
    del items[i]
    normalize(items)
    return prev, col


def merge_next(items, i, nxt):
    """Delete(맨 끝): 보이는 다음 항목 nxt 의 글을 이 항목에 붙인다"""
    col = len(items[i].text)
    items[i].text += items[nxt].text
    del items[nxt]
    normalize(items)
    return i, col


def toggle_done(it):
    t = it.text
    if t.startswith("[x] ") or t.startswith("[X] "):
        it.text = "[ ] " + t[4:]
    elif t.startswith("[ ] "):
        it.text = "[x] " + t[4:]
    else:
        it.text = "[x] " + t


def is_done(it):
    return it.text[:4] in ("[x] ", "[X] ")
