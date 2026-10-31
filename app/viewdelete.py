"""렌더링 화면에서 고른 글을 마크다운 원문에서 지우기(우클릭 → 삭제). 화면 글자와 원문은 서식 기호(**, #, 목록 기호 …)만큼 다르므로,
① 고른 글이 원문에 그대로 있으면 그 자리를 지우고 ② 아니면 줄마다 서식 기호를 뺀 글자와 맞춰 찾아 지운다. 정확히 못 찾으면 None(아무것도 안 지운다).
같은 글이 여러 곳에 있으면 화면에서 그 앞에 같은 글이 몇 번 나왔는지(before)로 몇 번째인지 정한다."""
import re

_MARK = re.compile(r"^(\s{0,3}#{1,6}\s+|\s*>+\s?|\s*[-*+]\s+(\[[ xX]\]\s+)?|\s*\d+[.)]\s+)")
_INLINE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)|\*\*|__|~~|`|\*|(?<![\w])_|_(?![\w])|\|")


def plain_map(line):
    """원문 한 줄 → (화면에 보이는 글, 그 글자가 원문 줄의 몇 번째인지 목록)"""
    pos = 0
    m = _MARK.match(line)
    if m:
        pos = m.end()
    chars, idx = [], []
    i = pos
    while i < len(line):
        t = _INLINE.match(line, i)
        if t:
            if t.group(1) is not None:           # [글](주소) → 글
                start = i + (2 if line[i] == "!" else 1)
                for k, ch in enumerate(t.group(1)):
                    chars.append(ch); idx.append(start + k)
            i = t.end()
            continue
        chars.append(line[i]); idx.append(i)
        i += 1
    return "".join(chars), idx


def _nth_positions(hay, needle):
    out, i = [], hay.find(needle)
    while i != -1:
        out.append(i)
        i = hay.find(needle, i + len(needle))
    return out


def _tidy(line):
    """지우고 남은 빈 서식(**** 등)을 정리한다"""
    for pat in (r"\*\*\*\*", r"____", r"~~~~", r"``", r"(?<!\*)\*\*(?!\*)\s*\*\*"):
        line = re.sub(pat, "", line)
    return line


def delete(src, sel, before=""):
    """src 에서 sel(렌더링 화면에서 고른 글)을 지운 새 글. 못 찾으면 None"""
    sel = sel.replace("\r", "")
    if not sel.strip():
        return None
    # ① 원문에 그대로 있을 때
    pos = _nth_positions(src, sel)
    if pos:
        k = before.count(sel) if before else 0
        p = pos[k] if k < len(pos) else pos[-1]
        out = src[:p] + src[p + len(sel):]
        a = out.rfind(chr(10), 0, p) + 1                 # 지운 자리가 든 줄만 빈 서식을 정리한다
        b = out.find(chr(10), p)
        b = len(out) if b < 0 else b
        return out[:a] + _tidy(out[a:b]) + out[b:]
    # ② 서식 기호가 낀 글: 줄 단위로 맞춘다
    frags = [f.strip() for f in sel.split("\n") if f.strip()]
    if not frags:
        return None
    lines = src.split("\n")
    maps = [plain_map(l) for l in lines]
    skip = 0                                   # 앞쪽에 같은 글이 몇 번 나왔는지(화면 기준) — 첫 조각에만 쓴다
    if before:
        skip = sum(1 for f in frags[:1] if before.count(f))
    cursor = 0
    edits = []                                  # (줄 번호, 지울 시작, 지울 끝 | None=줄 전체)
    for n, f in enumerate(frags):
        found = None
        seen = 0
        for li in range(cursor, len(lines)):
            plain, idx = maps[li]
            whole = plain.strip() == f
            if whole or (len(frags) == 1 and f in plain):
                if n == 0 and seen < skip:
                    seen += 1
                    continue
                if whole and (len(frags) > 1 or True):
                    found = (li, 0, None)
                else:
                    s = plain.find(f)
                    found = (li, idx[s], idx[s + len(f) - 1] + 1)
                break
        if found is None:
            return None
        edits.append(found)
        cursor = found[0] + 1
    out = list(lines)
    drop = set()
    for li, a, b in sorted(edits, reverse=True):
        if b is None:
            drop.add(li)
        else:
            out[li] = _tidy(out[li][:a] + out[li][b:])
    return "\n".join(l for i, l in enumerate(out) if i not in drop)


def minimal_change(old, new):
    """old → new 를 바꾸는 가장 작은 구간: (앞에서 같은 글자 수, 뒤에서 같은 글자 수). 앱이 그 구간만 지우고 넣어 되돌리기·커서가 덜 흔들리게 한다"""
    p = 0
    n = min(len(old), len(new))
    while p < n and old[p] == new[p]:
        p += 1
    s = 0
    while s < n - p and old[len(old) - 1 - s] == new[len(new) - 1 - s]:
        s += 1
    return p, s


# ---------------------------------------------------------------- 블록 단위(그림·표·목록·서식이 든 글)
_FENCE = re.compile(r"^[ \t]*(```|~~~)", re.M)
_IMG_MD = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_IMG_HTML = re.compile(r"<img\b[^>]*>", re.I)
_PLACEHOLDER = re.compile(r"\[그림: ([^\]]*)\]")


def split_blocks(src):
    """원문 → [(블록 글, 뒤의 빈 줄 구분)]. 빈 줄로 나누되 ``` 코드 블록 안의 빈 줄은 나누지 않는다"""
    parts = re.split(r"(\n[ \t]*\n+)", src)
    out, i = [], 0
    while i < len(parts):
        text = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        while len(_FENCE.findall(text)) % 2 == 1 and i + 2 < len(parts):   # 코드 블록이 열려 있으면 다음 조각과 합친다
            text += sep + parts[i + 2]
            sep = parts[i + 3] if i + 3 < len(parts) else ""
            i += 2
        out.append((text, sep))
        i += 2
    return out


def _drop_images(block, sub):
    """sub(화면 글) 속 '[그림: 설명]' 자리에 해당하는 그림 표기를 block 에서 지운다 → (새 block, 남은 sub)"""
    for alt in _PLACEHOLDER.findall(sub):
        hit = next((m for m in _IMG_MD.finditer(block) if m.group(1) == alt), None) or next(_IMG_MD.finditer(block), None) or next(_IMG_HTML.finditer(block), None)
        if hit:
            block = block[:hit.start()] + block[hit.end():]
    return block, _PLACEHOLDER.sub("", sub)


def delete_range(src, ss, se, render_flat):
    """렌더링 화면의 글 범위 [ss, se)(렌더링 글 기준 위치)를 원문에서 지운다. 렌더링 화면은 원문의 위치를 모르므로, 블록(빈 줄로 나눈 덩어리)마다
    따로 그려 본 글 길이로 '어느 블록이 화면의 어디에 해당하는지' 맞춘다. 블록 전체가 선택됐으면 그 블록을 통째로(그림·표·목록 줄), 일부만이면 그 조각만 지운다.
    render_flat(원문) → 렌더링 글 전체(문자열). 블록별 렌더링을 이어 붙인 것이 전체 렌더링과 다르면 맞출 수 없으니 None"""
    if se <= ss:
        return None
    blocks = split_blocks(src)
    texts = [render_flat(b + "\n") for b, _ in blocks]
    full = render_flat(src)
    if "".join(texts) != full:
        return None
    pos = 0
    edits = []                                    # (블록 번호, 새 글 또는 None=블록째 삭제)
    for i, ((b, _sep), t) in enumerate(zip(blocks, texts)):
        vis = len(t.rstrip("\n"))
        a, z = pos, pos + vis
        pos += len(t)
        lo, hi = max(ss, a), min(se, z)
        if lo >= hi:
            continue
        if ss <= a and se >= z:
            edits.append((i, None))
            continue
        sub, before = full[lo:hi], full[a:lo]
        nb, rest = _drop_images(b, sub)
        if rest.strip():
            nb = delete(nb, rest, before)
        if nb is None:
            return None
        edits.append((i, nb))
    if not edits:
        return None
    new = []
    changed = dict(edits)
    for i, (b, sep) in enumerate(blocks):
        if i in changed and changed[i] is None:
            continue
        new.append([changed.get(i, b), sep])
    # 지운 블록 때문에 구분 빈 줄이 겹치거나 끝에 남지 않게 정리
    if new and blocks and changed.get(len(blocks) - 1, "x") is None:
        new[-1][1] = blocks[-1][1]
    return "".join(b + s for b, s in new)
