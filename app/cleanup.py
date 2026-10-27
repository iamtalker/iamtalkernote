"""노트 정리 도구: 중복 노트 찾기, 스크랩한 글의 군더더기(메뉴·"맨위로" 같은 줄) 찾기.
화면 코드가 없는 순수 로직이라 notes.py 가 대화상자를 만들어 쓴다."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import store as st

MIN_LEN = 30        # 본문이 이보다 짧으면 본문 비교로는 중복으로 보지 않는다
SIMILAR = 0.85      # 같은 제목끼리 본문이 이만큼 비슷하면 중복 후보


# ------------------------------------------------------------------ 중복 노트
def norm_url(u):
    """같은 글인데 주소만 조금 다른 경우(추적 인자, www, 끝 슬래시, #조각)를 같게 만든다"""
    try:
        p = urlsplit(u.strip())
    except ValueError:
        return u.strip().lower()
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref")]
    return urlunsplit((p.scheme.lower(), host, p.path.rstrip("/"), urlencode(q), ""))


def norm_body(body):
    """머리말·기호·공백·대소문자 차이를 없앤 본문(비교용)"""
    m = st.FM_RE.match(body)
    if m:
        body = body[m.end():]
    body = re.sub(r"(?m)^원본:.*$", "", body, count=1)
    return re.sub(r"[\W_]+", "", body.lower())


def shingles(text, k=6):
    text = text[:20000]
    return {hash(text[i:i + k]) for i in range(0, max(1, len(text) - k + 1), 3)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class _Union:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def join(self, a, b):
        self.p[self.find(a)] = self.find(b)


def find_duplicates(notes, progress=None, cancelled=lambda: False):
    """notes(store.list_notes 결과) → [(이유들, [노트, …])] 묶음 목록. 묶음 안은 수정 시각이 최근인 것부터.
    이유: 같은 원본 주소 / 본문이 같음 / 같은 제목에 본문이 비슷함"""
    uf = _Union()
    reasons = {}                       # 대표 노트 경로 → 이유 집합 (묶은 뒤에 모은다)
    by_path = {n["path"]: n for n in notes}
    link = []                          # (a, b, 이유)
    src_seen, body_seen, title_seen = {}, {}, {}
    total = len(notes)
    for i, n in enumerate(notes):
        if cancelled():
            return []
        if progress and i % 200 == 0:
            progress(i, total)
        body = n.read()
        nb = norm_body(body)
        n["_len"] = len(nb)
        src = st.note_source(body)
        if src:
            k = norm_url(src)
            if k in src_seen:
                link.append((src_seen[k], n["path"], "같은 원본 주소"))
            else:
                src_seen[k] = n["path"]
        if len(nb) >= MIN_LEN:
            h = hashlib.sha1(nb.encode("utf-8")).hexdigest()
            if h in body_seen:
                link.append((body_seen[h], n["path"], "본문이 같음"))
            else:
                body_seen[h] = n["path"]
        title_seen.setdefault(n["title"].strip().lower(), []).append((n["path"], nb))
    for group in title_seen.values():
        if len(group) < 2:
            continue
        sh = [(p, shingles(nb)) for p, nb in group if len(nb) >= MIN_LEN]
        for a in range(len(sh)):
            for b in range(a + 1, len(sh)):
                if jaccard(sh[a][1], sh[b][1]) >= SIMILAR:
                    link.append((sh[a][0], sh[b][0], "같은 제목에 본문이 비슷함"))
    for a, b, why in link:
        uf.join(a, b)
    members, why_of = {}, {}
    for a, b, why in link:
        for x in (a, b):
            members.setdefault(uf.find(x), set()).add(x)
        why_of.setdefault(uf.find(a), set()).add(why)
    out = []
    for root, paths in members.items():
        group = sorted((by_path[p] for p in paths), key=lambda n: -n["mtime"])
        if len(group) > 1:
            out.append((sorted(why_of.get(uf.find(root), set())), group))
    out.sort(key=lambda g: (-len(g[1]), g[1][0]["title"].lower()))
    return out


# ------------------------------------------------------------------ 스크랩 군더더기
# 줄 전체가 이런 말뿐일 때만 지운다(문장 속에 섞여 있으면 건드리지 않는다)
JUNK = [
    r"맨\s*위로", r"위로\s*가기", r"top", r"▲", r"↑", r"scroll\s*to\s*top", r"back\s*to\s*top", r"skip\s*to\s*(main\s*)?content",
    r"목록(으로|보기)?", r"이전\s*글.*", r"다음\s*글.*", r"이전\s*기사.*", r"다음\s*기사.*", r"prev(ious)?", r"next",
    r"댓글\s*(쓰기|달기|보기|\d*\s*개?)?", r"공유(하기)?", r"스크랩(하기)?", r"인쇄(하기)?", r"print", r"share", r"shares?\s*\d*",
    r"구독(하기)?", r"좋아요\s*\d*", r"like\s*\d*", r"신고(하기)?", r"url\s*복사", r"링크\s*복사", r"주소\s*복사",
    r"글자\s*크기.*", r"가\s*가\s*가", r"광고", r"ad", r"ads", r"advertisement", r"sponsored", r"추천\s*글", r"관련\s*(기사|글).*",
    r"많이\s*본\s*(뉴스|기사|글)", r"로그인", r"회원\s*가입", r"login", r"sign\s*(in|up)", r"트위터", r"페이스북", r"카카오(톡|스토리)", r"네이버\s*(블로그|카페)?",
    r"twitter", r"facebook", r"kakao(talk)?", r"copyright.*", r"ⓒ.*", r"©.*", r"무단\s*(전재|복제).*", r"all\s*rights\s*reserved.*",
]
JUNK_RE = re.compile(r"^(?:" + "|".join(JUNK) + r")$", re.I)


def _plain(line):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)          # 그림 문법 제거
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)          # [글](주소) → 글
    s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)
    s = re.sub(r"^[\s>*+\-•·|#]+", "", s)
    s = re.sub(r"[\s*_`|:·•]+$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_body(body):
    """군더더기 줄을 뺀 본문과 뺀 줄 목록을 돌려준다 → (새 본문, [(줄 번호, 줄)])"""
    m = st.FM_RE.match(body)
    head, rest = (body[:m.end()], body[m.end():]) if m else ("", body)
    out, removed, fence = [], [], False
    base = head.count("\n")
    for i, line in enumerate(rest.split("\n")):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and not line.lstrip().startswith("#"):   # 제목 줄은 건드리지 않는다
            plain = _plain(line)
            if plain and len(plain) <= 40 and JUNK_RE.match(plain):
                removed.append((base + i + 1, line))
                continue
        out.append(line)
    if not removed:
        return body, []
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return head + text, removed


def scan_junk(notes, progress=None, cancelled=lambda: False):
    """[(노트, 새 본문, 뺀 줄들)] — 뺄 게 있는 노트만"""
    out = []
    for i, n in enumerate(notes):
        if cancelled():
            break
        if progress and i % 200 == 0:
            progress(i, len(notes))
        body = n.read()
        new, removed = clean_body(body)
        if removed:
            out.append((n, new, removed))
    return out
