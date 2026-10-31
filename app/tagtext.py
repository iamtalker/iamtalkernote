"""노트 본문 속 태그를 읽고 고치는 순수 함수들(화면 없음): #해시태그·'태그:' 줄·머리말 tags.
notes.py 에서 그대로 옮겨 왔다(동작 변경 없음)."""
import re

import store as st

TAG_LINE = re.compile(r"^[ \t]*(?:태그|tags?)[ \t]*[:：][ \t]*(.+)$", re.I | re.M)
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


HASH_FAST = re.compile(r"#([A-Za-z_가-힣][\w가-힣\-]*)")
BAD_PREV = set("#&/(=-.:[?")   # 이런 글자 바로 뒤의 #는 태그가 아니다(주소의 #앵커, 제목 등)
URL_RE = re.compile(r"(?:https?|ftp)://[^\s<>\]\)]+|file:///[^\s<>\]\)]+", re.I)   # 주소 속의 #(앵커·댓글 번호 …)는 태그가 아니다


def hashtags(text):
    """본문 속 #태그. '#' 가 있는 자리만 훑어서 빠르다."""
    out = []
    for m in HASH_FAST.finditer(text):
        i = m.start()
        if i:
            p = text[i - 1]
            if p.isalnum() or p == "_" or p in BAD_PREV:
                continue
        out.append(m.group(1))
    return out


def line_tags(body):
    """'태그: a, b' 줄에 적힌 태그들(줄 순서대로). 링크·괄호·긴 조각은 태그가 아니다(블로그의 'Tags: [블로그](주소)' 같은 줄)"""
    out = []
    if "태그" in body or "tag" in body or "Tag" in body or "TAG" in body:
        for m in TAG_LINE.finditer(body):
            for t in re.split(r"[,\s]+", m.group(1)):
                t = t.strip().lstrip("#")
                if t and len(t) <= 30 and not re.search(r"[\[\]()/<>]", t) and t not in out:
                    out.append(t)
    return out


def mask_protected(text):
    """코드·그림·주소 덩어리를 같은 길이의 공백으로 가린다(줄바꿈은 그대로): 그 속의 #는 태그가 아니라서 건너뛰되, 글자 위치는 그대로라
    찾은 자리를 원문에서 그대로 바꿀 수 있다('#태그http://…' 처럼 주소가 붙어 있어도 '#태그' 만 잡힌다)."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))   # noqa: E731
    return URL_RE.sub(blank, CODE_RE.sub(blank, st.DATA_IMG.sub(blank, text)))


def body_after_fm(body):
    """머리말(--- … ---)을 뺀 본문. 머리말의 title 등에 든 #는 태그가 아니고 이름 변경·삭제로 고칠 수도 없어서 태그를 찾을 때 뺀다"""
    m = st.FM_RE.match(body)
    return body[m.end():] if m else body


def note_tags(body):
    """태그: 머리말 tags, '태그: a, b' 줄, 본문 속 #해시태그(코드·주소·제목 제외).
    대부분의 노트에는 태그가 없으므로, 필요할 때만 무거운 처리를 한다."""
    tags = set(st.parse_meta(body)["tags"])
    rest = body_after_fm(body)
    tags.update(line_tags(rest))
    if "#" in rest and hashtags(rest):
        tags.update(hashtags(mask_protected(rest)))   # 후보가 있을 때만 코드·그림·주소를 가리고 다시 확인
    return tags


TAG_OK = re.compile(r"^[A-Za-z_가-힣][\w가-힣\-]*$")   # 본문에 '#이름' 으로 쓸 수 있는 이름


def clean_tag_name(name):
    """입력한 태그 이름을 정리한다: 앞의 # 를 떼고 공백은 _ 로. 쓸 수 없으면 ''"""
    t = re.sub(r"\s+", "_", (name or "").strip().lstrip("#").strip())
    return t if t and len(t) <= 30 and not re.search(r"[\[\]()/<>,]", t) else ""


def edit_tag(body, old, new):
    """노트 본문에서 태그 old 를 new 로 바꾼다(new 가 None 이면 지운다) → (새 본문, 센 수)
    태그는 세 군데에서 온다: 머리말 tags('fm'), 글 아래의 '태그: #a #b' 줄('line'), 본문 속 #해시태그('inline').
    코드·주소 속의 #는 태그가 아니라서 건드리지 않고, 본문에 못 쓰는 이름(공백·기호가 든 것)으로는 본문 #태그를 못 바꿔서 'stuck' 으로 센다."""
    counts = {"fm": 0, "line": 0, "inline": 0, "stuck": 0}
    body, counts["fm"] = st.fm_edit_tags(body, lambda t: (new if new else None) if t == old else t)
    m = st.FM_RE.match(body)
    head, rest = (body[:m.end()], body[m.end():]) if m else ("", body)
    for m in reversed(list(TAG_LINE.finditer(rest))):   # 글 아래의 '태그: …' 줄
        toks = re.findall(r"[^,\s]+", m.group(1))
        if not any(t.lstrip("#") == old and len(t) <= 31 for t in toks):
            continue
        out = []
        for t in toks:
            if t.lstrip("#") == old:
                t = ("#" if t.startswith("#") else "") + new if new else None
            if t and t.lstrip("#") not in [x.lstrip("#") for x in out]:
                out.append(t)
        counts["line"] += 1
        if out:
            rest = rest[:m.start()] + rest[m.start():m.start(1)] + " ".join(out) + rest[m.end():]
        else:   # 줄에 태그가 하나도 안 남으면 줄째로 지운다
            end = m.end() + 1 if rest[m.end():m.end() + 1] == "\n" else m.end()
            rest = rest[:m.start()] + rest[end:]
    if "#" in rest:   # 본문 속 #해시태그(note_tags 와 같은 방법으로 찾는다: 코드·주소 속 #는 건너뛴다)
        masked = mask_protected(rest)
        out, pos = [], 0
        for mm in HASH_FAST.finditer(masked):
            i = mm.start()
            if mm.group(1) != old or (i and (masked[i - 1].isalnum() or masked[i - 1] == "_" or masked[i - 1] in BAD_PREV)):
                continue
            if new is None:   # 지우기: '#이름' 과 바로 뒤의 공백 하나
                end = mm.end() + 1 if rest[mm.end():mm.end() + 1] == " " else mm.end()
                out.append(rest[pos:i])
                pos = end
            elif TAG_OK.match(new):
                out.append(rest[pos:i] + "#" + new)
                pos = mm.end()
            else:
                counts["stuck"] += 1
                continue
            counts["inline"] += 1
        rest = "".join(out) + rest[pos:]
    return head + rest, counts


def add_tag(body, tag):
    """노트에 태그를 더한다 → (새 본문, 더했는가). 이미 있으면 그대로. 글 아래의 '태그:' 줄 끝에 붙이고, 줄이 없으면 만든다."""
    if tag in note_tags(body):
        return body, False
    m = st.FM_RE.match(body)
    head, rest = (body[:m.end()], body[m.end():]) if m else ("", body)
    ms = list(TAG_LINE.finditer(rest))
    if ms:
        rest = rest[:ms[0].end()] + " #" + tag + rest[ms[0].end():]
    else:
        tail = "" if rest.endswith("\n\n") else ("\n" if rest.endswith("\n") else "\n\n")
        rest += f"{tail}태그: #{tag}\n"
    return head + rest, True
