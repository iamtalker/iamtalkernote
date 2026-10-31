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
