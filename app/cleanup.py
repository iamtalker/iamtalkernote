"""노트 정리 도구: 중복 노트 찾기, 스크랩한 글의 군더더기(사이트 메뉴·"맨위로" 같은 줄) 찾기.
화면 코드가 없는 순수 로직이라 notes.py 가 대화상자를 만들어 쓴다."""
import hashlib
import re
from collections import Counter
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import store as st

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


MIN_BODY = 100          # 군더더기를 뺀 본문이 이보다 짧으면 비교하지 않는다(짧은 노트는 같은지 판단할 수 없다)
MAX_BUCKET = 60         # 같은 제목이 이보다 많은 노트에 붙어 있으면 비슷한 정도는 비교하지 않는다(똑같은 본문만 찾는다)
SUFFIX = re.compile(r"(\s*\(\d+\)|-\d+)$")   # 같은 이름이 있을 때 앱·클리퍼가 붙이는 번호: "제목-1", "제목 (2)"


def title_key(title):
    """제목이 같은지 볼 때 쓰는 키: 소문자로, 끝에 붙은 중복 번호("-1", " (2)")는 뗀다"""
    t = title.strip().lower()
    return SUFFIX.sub("", t).strip() or t


def find_duplicates(notes, progress=None, cancelled=lambda: False):
    """notes(store.list_notes 결과) → [(이유들, [노트, …])] 묶음 목록. 묶음 안은 수정 시각이 최근인 것부터.
    ① 제목이 같은 노트끼리 모으고(끝의 "-1" 같은 번호는 무시) ② 그 안에서 내용이 같거나(군더더기를 뺀 본문)
    아주 비슷한 것만 중복으로 본다. 제목이 다르면 내용이 같아도 묶지 않는다.
    이유: 본문이 같음 / 본문이 비슷함"""
    by_path = {n["path"]: n for n in notes}
    by_title, raw_hash = {}, {}
    n_of, df = Counter(), {}
    total = len(notes)
    for i, n in enumerate(notes):   # 1단계: 제목별로 모으고, 사이트별 공통 줄(메뉴 등)도 센다
        if cancelled():
            return []
        if progress and i % 200 == 0:
            progress(i, total * 2)
        by_title.setdefault(title_key(n["title"]), []).append(n["path"])
    groups = {k: g for k, g in by_title.items() if len(g) >= 2}
    cand = {p for g in groups.values() for p in g}
    if not cand:
        return []
    for i, p in enumerate(cand):    # 2단계: 후보 노트만 읽는다(다른 사이트의 공통 줄을 알아야 하므로 같은 사이트 노트도 세어 둔다)
        if cancelled():
            return []
        if progress and i % 100 == 0:
            progress(total + i, total + len(cand))
        body = by_path[p].read()
        site = site_of(body)
        if site:
            n_of[site] += 1
            df.setdefault(site, Counter()).update(doc_keys(body))
        raw_hash[p] = (body, site)
    sites = {}
    for site, c in df.items():
        if n_of[site] >= SITE_MIN_NOTES:
            need = max(SITE_MIN_DOCS, SITE_RATIO * n_of[site])
            lines = frozenset(k for k, v in c.items() if v >= need)
            if lines:
                sites[site] = lines
    uf, why_of, members = _Union(), {}, {}
    links = []
    for group in groups.values():
        text, sh = {}, {}
        for p in group:
            body, site = raw_hash[p]
            t = norm_body(clean_body(body, sites.get(site, frozenset()))[0])
            if len(t) >= MIN_BODY:
                text[p] = t
        same = {}
        for p, t in text.items():
            same.setdefault(hashlib.sha1(t.encode("utf-8")).hexdigest(), []).append(p)
        for ps in same.values():
            for x in ps[1:]:
                links.append((ps[0], x, "본문이 같음"))
        if len(group) <= MAX_BUCKET:
            firsts = [ps[0] for ps in same.values()]
            for p in firsts:
                sh[p] = shingles(text[p])
            for a in range(len(firsts)):
                for b in range(a + 1, len(firsts)):
                    if jaccard(sh[firsts[a]], sh[firsts[b]]) >= SIMILAR:
                        links.append((firsts[a], firsts[b], "본문이 비슷함"))
    for a, b, why in links:
        uf.join(a, b)
    for a, b, why in links:
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

# 조플린 클리퍼 플러스(content.js)의 글 기준 규칙을 저장된 마크다운에 맞게 옮긴 것.
# (클리퍼의 사이트별 CSS 선택자는 HTML 에만 걸 수 있어서, 이미 마크다운이 된 노트에는 쓸 수 없다)
BOARD_NAV = re.compile(r"^(이전\s*\S*글?|다음\s*\S*글?|목록|랜덤\s*\S*|list|prev(ious)?|next|편집|토론|역사)$", re.I)
WIRE_MARK = re.compile(r"^\[.{1,20}(주요\s*뉴스|헤드라인)\]$")
WIRE_COPY = re.compile(r"ⓒ\s*.+(무단\s*전재|재배포|AI\s*학습)")
WIKI_ATTR = re.compile(r"이\s*문서의\s*내용\s*중\s*전체\s*또는\s*일부는.*?판에서\s*가져왔습니다")
VIEWS_DATE = re.compile(r"조회\s*\d+")
DATE = re.compile(r"\d{4}[.\-]\s?\d{1,2}[.\-]\s?\d{1,2}")


def clipper_rule(line, plain):
    """클리퍼에서 가져온 줄 단위 규칙에 걸리면 이유(문자열), 아니면 None"""
    if len(plain) <= 60:
        parts = [x for x in re.split(r"\s*[|·/]\s*|\s{2,}", plain) if x]
        if parts and all(BOARD_NAV.match(x) for x in parts) and ("](" in line or len(parts) > 1 or BOARD_NAV.match(plain)):
            return "게시판 이전/다음/목록"
    if len(plain) < 80 and VIEWS_DATE.search(plain) and DATE.search(plain):
        return "조회수·날짜 줄"
    if WIRE_COPY.search(plain):
        return "저작권(무단전재) 줄"
    if WIKI_ATTR.search(plain) and len(plain) < 300:
        return "위키 가져옴 안내"
    if len(plain) < 60 and re.match(r"^최근\s*수정\s*시각\s*[:：]", plain):
        return "위키 수정 시각 줄"
    return None


SITE_MIN_NOTES = 6      # 같은 사이트에서 스크랩한 노트가 이만큼은 있어야 "사이트 공통 줄"을 찾는다
SITE_RATIO = 0.30       # 그중 이 비율 이상의 노트에 똑같이 나오는 줄이 사이트 공통(메뉴·머리글·바닥글)
SITE_MIN_DOCS = 4       # 그리고 최소 이만큼의 노트에 나와야 한다
NAV_RUN = 5             # 글 맨 위·맨 아래에 짧은 링크/목록 줄이 이만큼 이어지면 메뉴 덩어리로 본다
NAV_EDGE = 25           # 맨 위/아래 몇 줄 안쪽을 가장자리로 볼지


def _plain(line):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)          # 그림 문법 제거
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)          # [글](주소) → 글
    s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)
    s = re.sub(r"^[\s>*+\-•·|#]+", "", s)
    s = re.sub(r"[\s*_`|:·•]+$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def site_of(body):
    """노트의 원본 사이트(호스트). 원본 주소가 없으면 ''"""
    src = st.note_source(body)
    try:
        h = urlsplit(src).netloc.lower() if src else ""
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def line_key(line):
    """사이트 공통 줄을 세기 위한 키(비교할 만한 글줄이면 그 글, 아니면 None). 제목·숫자뿐인 줄·기호뿐인 줄은 제외"""
    if line.lstrip().startswith("#"):
        return None
    if re.search(r"\]\([^)]*(youtube\.com|youtu\.be)", line):   # 영상 링크·썸네일은 본문이다
        return None
    plain = _plain(line)
    if not (2 <= len(plain) <= 120) or re.fullmatch(r"[\d\W_]+", plain):
        return None
    return plain


def _split(body):
    m = st.FM_RE.match(body)
    return (body[:m.end()], body[m.end():]) if m else ("", body)


def doc_keys(body):
    """한 노트가 가진 (코드 블록 밖) 글줄 키 집합"""
    keys, fence = set(), False
    for line in _split(body)[1].split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence:
            k = line_key(line)
            if k:
                keys.add(k)
    return keys


def _navlike(line):
    plain = _plain(line)
    if not plain or len(plain) > 24:
        return False
    return "](" in line   # 링크가 든 짧은 줄만(링크 없는 짧은 목록 항목은 본문일 수 있다)


def nav_lines(lines):
    """글 맨 위/맨 아래 가장자리에서 짧은 링크·목록 줄이 NAV_RUN 줄 이상 이어지는 덩어리의 줄 번호 집합(0부터)"""
    idx = [i for i, l in enumerate(lines) if l.strip()]
    edge = set(idx[:NAV_EDGE]) | set(idx[-NAV_EDGE:])
    marked, run = set(), []
    for i in idx + [None]:
        if i is not None and i in edge and _navlike(lines[i]):
            run.append(i)
            continue
        if len(run) >= NAV_RUN:
            marked.update(run)
        run = []
    return marked


def clean_body(body, site_lines=frozenset()):
    """군더더기 줄을 뺀 본문과 뺀 줄 목록을 돌려준다 → (새 본문, [(줄 번호, 줄, 이유)])
    이유: 사이트 공통 / 메뉴 덩어리 / 흔한 군더더기"""
    head, rest = _split(body)
    lines = rest.split("\n")
    base = head.count("\n")
    nav = nav_lines(lines)
    out, removed, fence = [], [], False
    # 통신사 기사 꼬리: "[OO 주요뉴스]" 줄부터 끝까지(글 뒤쪽 절반에서만)
    wire_from = next((i for i, l in enumerate(lines) if WIRE_MARK.match(_plain(l)) and i >= len(lines) * 0.5), None)
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and not line.lstrip().startswith("#"):   # 제목 줄은 건드리지 않는다
            plain = _plain(line)
            why = None
            if wire_from is not None and i >= wire_from:
                why = "통신사 관련뉴스 꼬리"
            elif plain and (cr := clipper_rule(line, plain)):
                why = cr
            elif plain and line_key(line) in site_lines:
                why = "사이트 공통"
            elif i in nav and not re.search(r"(youtube\.com|youtu\.be)", line):
                why = "메뉴 덩어리"
            elif plain and len(plain) <= 40 and JUNK_RE.match(plain):
                why = "흔한 군더더기"
            if why:
                removed.append((base + i + 1, line, why))
                continue
        out.append(line)
    if not removed:
        return body, []
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return head + text, removed


def site_boilerplate(notes, progress=None, cancelled=lambda: False):
    """사이트별로 노트 여러 개에 똑같이 반복되는 줄을 찾는다 → {사이트: 줄 집합}"""
    n_of, df = Counter(), {}
    for i, n in enumerate(notes):
        if cancelled():
            return {}
        if progress and i % 200 == 0:
            progress(i, len(notes) * 2)
        body = n.read()
        site = site_of(body)
        if not site:
            continue
        n_of[site] += 1
        df.setdefault(site, Counter()).update(doc_keys(body))
    out = {}
    for site, c in df.items():
        total = n_of[site]
        if total < SITE_MIN_NOTES:
            continue
        need = max(SITE_MIN_DOCS, SITE_RATIO * total)
        lines = frozenset(k for k, v in c.items() if v >= need)
        if lines:
            out[site] = lines
    return out


def scan_junk(notes, progress=None, cancelled=lambda: False):
    """[(노트, 새 본문, 뺀 줄들)] — 뺄 게 있는 노트만. 1단계: 사이트별 공통 줄 찾기, 2단계: 노트마다 적용"""
    sites = site_boilerplate(notes, progress, cancelled)
    out, total = [], len(notes)
    for i, n in enumerate(notes):
        if cancelled():
            break
        if progress and i % 200 == 0:
            progress(total + i, total * 2)
        body = n.read()
        new, removed = clean_body(body, sites.get(site_of(body), frozenset()))
        if removed:
            out.append((n, new, removed))
    return out


# ------------------------------------------------------------------ 안 쓰는 미디어 파일
def unused_media(store, notes, progress=None, cancelled=lambda: False):
    """리소스 폴더 안에서 어떤 노트도 가리키지 않는 파일 → [(경로, 크기)] 큰 것부터.
    노트(휴지통 안의 노트 포함)의 링크·그림 주소에서 파일 이름을 찾아 비교한다. 조플린 ':/아이디' 주소도 인식."""
    import os
    from urllib.parse import unquote
    media = store.media_dir
    files = {}
    for dp, _, fn in os.walk(media):
        for f in fn:
            files.setdefault(f.lower(), []).append(os.path.join(dp, f))
    if not files:
        return []
    stems = {}
    for name in files:
        stems.setdefault(os.path.splitext(name)[0], name)
    spaced = [n for n in files if " " in n]          # 띄어쓰기가 든 이름은 낱말로 쪼개면 못 찾으니 따로
    used = set()
    tok = re.compile(r"[^\s()\[\]<>\"'`|]+")
    sources = [n["path"] for n in notes]
    for it in store.trash_items():                   # 휴지통의 노트를 복원해도 그림이 살아 있게
        base = it["path"]
        if it["dir"]:
            for dp, dn, fn in os.walk(base):
                sources += [os.path.join(dp, f) for f in fn if f.lower().endswith(".md")]
        elif base.lower().endswith(".md") or True:
            sources.append(base)
    total = len(sources)
    for i, path in enumerate(sources):
        if cancelled():
            return []
        if progress and i % 200 == 0:
            progress(i, total)
        try:
            with open(path, "rb") as fh:
                text = st.decode(fh.read()).lower()
        except OSError:
            continue
        for t in set(tok.findall(text)):
            t = unquote(t.split("#")[0].split("?")[0]).replace("\\", "/")
            base = t.rsplit("/", 1)[-1]
            if base in files:
                used.add(base)
            elif base in stems and re.fullmatch(r"[0-9a-f]{32}", base):
                used.add(stems[base])
        for n in spaced:
            if n not in used and n in text:
                used.add(n)
    out = []
    for name, paths in files.items():
        if name in used:
            continue
        for p in paths:
            try:
                out.append((p, os.path.getsize(p)))
            except OSError:
                pass
    out.sort(key=lambda x: -x[1])
    return out
