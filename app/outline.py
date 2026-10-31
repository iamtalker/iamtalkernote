"""아웃라이너 보기: 노트의 마크다운 목록(-, *, +, 1.)을 WorkFlowy 처럼 점(●)이 있는 계층 목록으로 보이게 하고,
점을 누르면 그 항목으로 줌인한다(그 항목이 맨 위 제목, 하위 항목만 보임). 원문은 그대로 두고 렌더링 화면에서만 바꾼다.
노트를 빈 줄로 나눈 블록으로 보아, 목록 블록은 아웃라이너로, 그 밖의 글(문단·제목·인용·표·코드·그림)은 '메모' 블록으로 따로 보인다.
항목과 메모 블록은 원문의 어느 구간인지(위치)를 알고 있어, 렌더링 화면에서 눌러 그 부분만 고칠 수 있다.
이 모듈은 화면을 모르는 순수 계산이다(블록·항목 나누기, 줌인 범위, 경로, 원문 위치)."""
import re

import viewdelete

LIST = re.compile(r"^(?P<ind>[ \t]*)(?P<mark>[-*+]|\d+[.)])[ \t]+(?P<text>.*?)[ \t]*$")
_FENCE = re.compile(r"^[ \t]*(```|~~~)")
_TASK = re.compile(r"^\[( |x|X)\][ \t]+")


def _width(ind):
    return len(ind.replace("\t", "    "))


def has_list(src):
    """목록 항목이 하나라도 있는가(코드 블록 속은 제외)"""
    fence = False
    for line in src.split("\n"):
        if _FENCE.match(line):
            fence = not fence
        elif not fence and LIST.match(line):
            return True
    return False


class Node:
    __slots__ = ("id", "depth", "text", "notes", "parent", "children", "mark", "done", "tstart", "tend")

    def __init__(self, id_, depth, text, parent, mark):
        self.id, self.depth, self.text, self.parent, self.mark = id_, depth, text, parent, mark
        self.notes = []          # 항목 바로 아래에 이어지는 글(그 항목의 메모)
        self.children = []
        self.done = None         # [ ] / [x] 체크박스 항목이면 False / True
        self.tstart = self.tend = 0     # 원문에서 이 항목의 글(마커·체크박스 뒤)이 있는 구간 [tstart, tend)


def parse(src):
    """원문 → (블록들, 항목들).
    블록: ('memo', 글, 시작, 끝) 또는 ('list', [최상위 Node…], 시작, 끝) — 시작·끝은 원문 위치.
    항목들은 위에서 아래 순서의 전체 목록(id = 위치)이고 각 항목의 tstart·tend 는 그 항목 글의 원문 구간."""
    nodes = []
    blocks = []
    pos = 0                                                         # 지금 블록이 원문의 어디서 시작하나
    for text, sep in viewdelete.split_blocks(src):
        base = pos
        pos += len(text) + len(sep)
        lines = text.split("\n")
        offs, o = [], 0
        for ln in lines:
            offs.append(o)
            o += len(ln) + 1
        memo, i = [], 0
        while i < len(lines) and not LIST.match(lines[i]):        # 목록이 시작되기 전의 글은 메모 블록
            memo.append(lines[i])
            i += 1
        if i == len(lines) or _FENCE.match(lines[0]):
            blocks.append(("memo", text, base, base + len(text)))
            continue
        if any(m.strip() for m in memo):
            mtext = "\n".join(memo)
            blocks.append(("memo", mtext, base, base + len(mtext)))
        stack = []                                                  # [(들여쓰기 폭, Node)]
        roots = []
        last = None
        fence = False
        for li in range(i, len(lines)):
            line = lines[li]
            if _FENCE.match(line):
                fence = not fence
            m = None if fence else LIST.match(line)
            if not m:
                if last is not None and line.strip():
                    last.notes.append(line.strip())                  # 목록 사이에 낀 글은 바로 앞 항목의 메모
                continue
            w = _width(m.group("ind"))
            while stack and stack[-1][0] >= w:
                stack.pop()
            parent = stack[-1][1] if stack else None
            txt = m.group("text")
            task = _TASK.match(txt)
            node = Node(len(nodes), len(stack), _TASK.sub("", txt) if task else txt, parent, m.group("mark"))
            node.tstart = base + offs[li] + m.start("text") + (task.end() if task else 0)
            node.tend = base + offs[li] + m.end("text")
            if task:
                node.done = task.group(1) in "xX"
            nodes.append(node)
            (parent.children if parent else roots).append(node)
            stack.append((w, node))
            last = node
        blocks.append(("list", roots, base + offs[i], base + len(text)))
    return blocks, nodes


def ancestors(node):
    """맨 위 항목부터 node 의 부모까지(자기 자신은 뺀다)"""
    out = []
    p = node.parent
    while p is not None:
        out.append(p)
        p = p.parent
    return out[::-1]


def walk(roots):
    """계층 순서(위에서 아래)로 (Node, 상대 깊이) 를 낸다"""
    def rec(ns, d):
        for n in ns:
            yield n, d
            yield from rec(n.children, d + 1)
    yield from rec(roots, 0)


# ---------------------------------------------------------------- 항목 편집(WorkFlowy 처럼): 원문 줄을 고쳐 (새 원문, 편집할 항목 글의 시작 위치) 를 돌려준다
def _subtree_end_line(src, node):
    """항목과 그 하위 항목·메모가 차지하는 마지막 줄 번호"""
    n = node
    while n.children:
        n = n.children[-1]
    return src.count("\n", 0, n.tstart) + len(n.notes)


def _prefix(src, node):
    """줄 맨 앞부터 항목 글 앞까지(들여쓰기+마커+체크박스)"""
    return src[src.rfind("\n", 0, node.tstart) + 1:node.tstart]


def _fresh(prefix):
    """새 항목 앞머리: 체크박스는 비우고 번호는 하나 올린다"""
    prefix = re.sub(r"\[[xX]\]", "[ ]", prefix)
    return re.sub(r"(\d+)([.)])", lambda m: str(int(m.group(1)) + 1) + m.group(2), prefix, count=1)


def _indent_of(prefix):
    return re.match(r"[ \t]*", prefix).group(0)


def _text_pos(lines, li):
    """lines[li] 가 목록 줄이면 그 항목 글이 시작하는 원문 위치"""
    m = LIST.match(lines[li])
    task = _TASK.match(m.group("text"))
    return sum(len(x) + 1 for x in lines[:li]) + m.start("text") + (task.end() if task else 0)


def _siblings(src, node):
    if node.parent:
        return node.parent.children
    for kind, data, _a, _z in parse(src)[0]:
        if kind == "list" and any(n.tstart == node.tstart for n in data):
            return data
    return []


def split_item(src, node, rest=""):
    """Enter: 항목 아래에 새 항목을 만든다(하위 항목이 있으면 그 맨 앞 자식으로). rest 는 새 항목에 넣을 글"""
    lines = src.split("\n")
    if node.children:
        pre = _fresh(_prefix(src, node.children[0]))
        pre = re.sub(r"\d+([.)])", r"1\1", pre, count=1)
    else:
        pre = _fresh(_prefix(src, node))
    at = src.count("\n", 0, node.tstart) + len(node.notes) + 1
    lines.insert(at, pre + rest)
    return "\n".join(lines), _text_pos(lines, at)


def indent_item(src, node):
    """Tab: 바로 앞 형제의 하위로 넣는다. 앞 형제가 없으면 None"""
    sibs = _siblings(src, node)
    if not sibs or sibs[0].tstart == node.tstart:
        return None
    unit = "\t" if "\t" in _indent_of(_prefix(src, node)) else "    "
    lines = src.split("\n")
    a = src.count("\n", 0, node.tstart)
    for i in range(a, _subtree_end_line(src, node) + 1):
        if lines[i].strip():
            lines[i] = unit + lines[i]
    return "\n".join(lines), _text_pos(lines, a)


def outdent_item(src, node):
    """Shift+Tab: 부모 바로 다음 형제로 올린다(뒤따르던 형제는 그대로 부모 아래에 남는다). 최상위면 None"""
    p = node.parent
    if p is None:
        return None

    def width(ws):
        return len(ws.replace("\t", "    "))
    delta = width(_indent_of(_prefix(src, node))) - width(_indent_of(_prefix(src, p)))
    lines = src.split("\n")
    a, z = src.count("\n", 0, node.tstart), _subtree_end_line(src, node)

    def dedent(line):
        n = used = 0
        while n < len(line) and used < delta and line[n] in " \t":
            used += 4 if line[n] == "\t" else 1
            n += 1
        return line[n:]
    chunk = [dedent(x) for x in lines[a:z + 1]]
    rest = lines[:a] + lines[z + 1:]
    at = _subtree_end_line(src, p) + 1 - len(chunk)   # 부모 쪽 줄은 모두 앞에 있으므로 빼낸 만큼만 당긴다
    rest[at:at] = chunk
    return "\n".join(rest), _text_pos(rest, at)


def delete_item(src, node):
    """빈 항목에서 Backspace: 하위 항목이 없으면 줄을 지운다 → 앞 줄 끝에서 이어 고치게 (새 원문, 위치). 하위가 있으면 None"""
    if node.children:
        return None
    lines = src.split("\n")
    a = src.count("\n", 0, node.tstart)
    del lines[a:a + len(node.notes) + 1]
    return "\n".join(lines), max(0, sum(len(x) + 1 for x in lines[:a]) - 1)
