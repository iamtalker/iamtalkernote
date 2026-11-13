"""글 정리(줄 앞·끝 공백, 빈 줄, 여러 공백, 중복 줄, 줄 합치기·정렬): 화면 없는 함수들.
'고칠 곳'은 줄 목록을 받아 [(줄, 칸, 끝 줄, 끝 칸, 넣을 글)] 로 돌려준다(줄·칸은 0부터, 그 범위를 지우고 글을 넣는다).
실제로 고치는 일은 formattools.py 가 편집 칸에서 한다. 코드 블록(``` · ~~~ 울타리 안)은 건드리지 않는다."""
import re

SPACES = " \t　 "   # 반각 공백, 탭, 전각 공백, 줄 바꿈 없는 공백
_LIST = re.compile(r"^[ \t　 ]+(?:[-*+]|\d+[.)])[ \t]")   # 들여 쓴 목록 항목(하위 목록)
_GAP = re.compile(r"(?<=[^ \t　 ])[ \t　 ]{2,}(?=[^ \t　 ])")   # 글자 사이의 공백 2칸 이상


def fenced(lines):
    """줄마다 코드 블록 안(울타리 줄 포함)인지: [bool]"""
    out, mark = [], ""
    for ln in lines:
        s = ln.lstrip(SPACES)
        if mark:
            out.append(True)
            if s.startswith(mark) and not s.strip(mark + SPACES):
                mark = ""
        elif s.startswith("```") or s.startswith("~~~"):
            mark = s[:3]
            out.append(True)
        else:
            out.append(False)
    return out


def _hi(lines, hi):
    return len(lines) - 1 if hi is None else hi


def _drop_lines(lines, i, j):
    """i..j 줄을 줄 바꿈까지 통째로 지우는 '고칠 곳' 하나"""
    if j < len(lines) - 1:
        return (i, 0, j + 1, 0, "")
    if i > 0:
        return (i - 1, len(lines[i - 1]), j, len(lines[j]), "")
    return (i, 0, j, len(lines[j]), "")


def _blank_runs(lines, lo, hi):
    """빈 줄(공백만 있는 줄 포함)이 이어진 구간들: [(첫 줄, 끝 줄)]. 코드 블록 안은 뺀다."""
    code = fenced(lines)
    runs, i = [], lo
    while i <= hi:
        if lines[i].strip() or code[i]:
            i += 1
            continue
        j = i
        while j + 1 <= hi and not lines[j + 1].strip() and not code[j + 1]:
            j += 1
        runs.append((i, j))
        i = j + 1
    return runs


def leading_ops(lines, lo=0, hi=None):
    """줄 앞 공백 지우기: (고칠 곳, 그대로 둔 줄 수). 코드 블록 안의 줄과 들여 쓴 목록 항목(하위 목록)은 그대로 둔다."""
    code = fenced(lines)
    ops, kept = [], 0
    for i in range(lo, _hi(lines, hi) + 1):
        ln = lines[i]
        n = len(ln) - len(ln.lstrip(SPACES))
        if not n or not ln.strip():
            continue
        if code[i] or _LIST.match(ln):
            kept += 1
        else:
            ops.append((i, 0, i, n, ""))
    return ops, kept


def trailing_ops(lines, lo=0, hi=None):
    """줄 끝 공백 지우기(공백만 있는 줄은 빈 줄이 된다)"""
    code = fenced(lines)
    ops = []
    for i in range(lo, _hi(lines, hi) + 1):
        n = len(lines[i].rstrip(SPACES))
        if n < len(lines[i]) and not code[i]:
            ops.append((i, n, i, len(lines[i]), ""))
    return ops


def blank_ops(lines, lo=0, hi=None):
    """여러 빈 줄을 하나로: 빈 줄이 2줄 이상 이어진 곳을 빈 줄 하나로 줄인다"""
    return [(i, 0, j, len(lines[j]), "") for i, j in _blank_runs(lines, lo, _hi(lines, hi)) if j > i]


def noblank_ops(lines, lo=0, hi=None):
    """빈 줄 모두 지우기"""
    return [_drop_lines(lines, i, j) for i, j in _blank_runs(lines, lo, _hi(lines, hi))]


def spaces_ops(lines, lo=0, hi=None):
    """줄 안의 여러 공백을 하나로(줄 앞 들여쓰기와 줄 끝은 그대로)"""
    code = fenced(lines)
    ops = []
    for i in range(lo, _hi(lines, hi) + 1):
        if not code[i]:
            ops += [(i, m.start(), i, m.end(), " ") for m in _GAP.finditer(lines[i])]
    return ops


def dupe_ops(lines, lo=0, hi=None):
    """중복 줄 지우기: 같은 줄이 또 나오면 뒤의 것을 지운다(줄 끝 공백은 무시, 빈 줄·코드 블록은 그대로)"""
    code = fenced(lines)
    seen, ops = set(), []
    for i in range(lo, _hi(lines, hi) + 1):
        key = lines[i].rstrip(SPACES)
        if not key.strip() or code[i]:
            continue
        if key in seen:
            if ops and ops[-1][0] == "run" and ops[-1][2] == i - 1:
                ops[-1] = ("run", ops[-1][1], i)
            else:
                ops.append(("run", i, i))
        else:
            seen.add(key)
    # 맨 끝 줄들을 지울 때는 앞 줄의 줄 바꿈부터 지우므로, 이어진 줄은 한 덩어리로 묶어 둔다
    return [_drop_lines(lines, a, b) for _, a, b in ops]


OPS = {"lead": lambda *a: leading_ops(*a)[0], "trail": trailing_ops, "blank": blank_ops, "noblank": noblank_ops,
       "spaces": spaces_ops, "dupes": dupe_ops}


def apply(text, kind):
    """글 전체에 고칠 곳을 적용한 결과(시험·화면 없는 곳에서 쓰기)"""
    lines = text.split("\n")
    start, n = [], 0
    for ln in lines:
        start.append(n)
        n += len(ln) + 1
    for i, c, j, d, new in sorted(OPS[kind](lines), reverse=True):
        text = text[:start[i] + c] + new + text[start[j] + d:]
    return text


# ---- 고른 줄들을 통째로 바꾸는 것
_WS = r"[ \t　 ]"
_BLOCK = re.compile(r"^" + _WS + r"*(?:#{1,6}[ \t]|[-*+][ \t]|\d+[.)][ \t]|>|\||\[\^[^\]]+\]:|(?:[-*_][ \t]*){3,}$|={3,}[ \t]*$)")   # 제목·목록·인용·표·각주·가로줄
_ALONE = re.compile(r"^" + _WS + r"*(?:#{1,6}[ \t]|\||(?:[-*_][ \t]*){3,}$|={3,}[ \t]*$)")   # 뒤 줄을 붙이면 안 되는 줄: 제목·표·가로줄


def unwrap(lines, lo=0, hi=None):
    """문단 안 줄 바꿈 지우기: 빈 줄로 나뉜 문단마다 한 줄로 잇는다(lo..hi 줄을 바꾼 새 줄 목록).
    코드 블록, 제목·표·가로줄은 그대로 두고, 목록·인용 줄은 새 줄로 시작한다. 줄 끝이 공백 두 칸이나 역슬래시인 줄(일부러 넣은 줄 바꿈)도 그대로 둔다."""
    code = fenced(lines)
    out, glue = [], False   # glue: 바로 앞 줄에 이어 붙여도 되는가
    for i in range(lo, _hi(lines, hi) + 1):
        ln = lines[i]
        if code[i] or not ln.strip() or _ALONE.match(ln):
            out.append(ln)
            glue = False
            continue
        if glue and not _BLOCK.match(ln):
            out[-1] = out[-1].rstrip(SPACES) + " " + ln.strip(SPACES)
        else:
            out.append(ln)
        glue = not (ln.endswith("  ") or ln.endswith("\\"))
    return out


def join_lines(lines):
    """줄 합치기: 빈 줄은 빼고, 줄 앞뒤 공백을 떼어 공백 하나로 잇는다"""
    return " ".join(ln.strip() for ln in lines if ln.strip())


def sort_lines(lines, reverse=False):
    """줄 정렬(가나다·abc, 대소문자 구분 없이). 빈 줄은 뺀다."""
    return sorted((ln for ln in lines if ln.strip()), key=lambda s: (s.strip().casefold(), s), reverse=reverse)
