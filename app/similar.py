"""비슷한 노트 찾기(DEVONthink 의 See Also 같은 것). 화면 코드가 없는 순수 로직이다.

열어 둔 노트에서 자주 나오면서 흔하지 않은 낱말(어간)을 뽑고, 색인 DB(store.index_path)에 있는 모든 노트의 본문 사본에서
그 낱말이 얼마나 나오는지 한 번 훑어 BM25 비슷하게 점수를 매긴다. 색인 DB 는 언제든 다시 만들 수 있는 캐시라서 여기서도 읽기만 한다.
한국어는 조사가 붙어 있어도 잡히도록 낱말의 끝 글자 하나를 뗀 앞부분(3글자 이상일 때)으로 센다."""
import math
import re
import sqlite3
from collections import Counter

TOKEN = re.compile(r"[0-9A-Za-z가-힣]{2,}")
HANGUL = re.compile(r"[가-힣]")
STOP = {"the", "and", "for", "that", "with", "this", "from", "are", "was", "not", "you", "have", "has", "http", "https", "www", "com", "png", "jpg",
        "resources", "image", "images", "source", "updated", "created", "tags"}
CANDIDATES = 16      # 점수에 쓸 낱말 수(후보 30개를 모두 세므로 노트 1.4만 개에서 몇 초 걸린다)
MIN_TERMS = 3        # 뽑힌 낱말이 이보다 적으면 비교할 만한 글이 아니다


def stems(text):
    """글에서 센 낱말(어간) → Counter"""
    c = Counter()
    for w in TOKEN.findall(text.lower()):
        if w in STOP or w.isdigit():
            continue
        if len(w) >= 3 and HANGUL.match(w[-1]):
            w = w[:-1]
        c[w] += 1
    return c


def find(store, key, body, limit=30, progress=None, cancelled=lambda: False):
    """body 와 비슷한 노트 → [(경로키, 겹친 낱말 수, 비교한 낱말 수)] 비슷한 순. key 는 자기 자신이라 뺀다. 색인이 없거나 비교할 낱말이 없으면 빈 목록"""
    tf = stems(body)
    if not tf:
        return []
    conn = store._db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        if total < 2:
            return []
        # 1단계: 자주 나오는 낱말 후보 30개의 문서 빈도를 센다 → 흔하지 않은 것 위주로 CANDIDATES 개 고른다
        cand = [w for w, _ in tf.most_common(30)]
        raw = [w.encode("utf-8") for w in cand]
        df = Counter()
        lens = []
        rows = []
        for i, (path, hay) in enumerate(conn.execute("SELECT path, hay FROM notes")):
            if cancelled():
                return []
            if progress and i % 500 == 0:
                progress(i, total, "비슷한 노트 찾는 중…")
            hay = bytes(hay)
            if path == key:
                continue
            counts = [hay.count(b) for b in raw]
            for j, c in enumerate(counts):
                if c:
                    df[j] += 1
            lens.append(len(hay))
            rows.append((path, counts, len(hay)))
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    n = max(1, len(rows))
    idf = {j: math.log(1 + (n - df[j] + 0.5) / (df[j] + 0.5)) for j in range(len(cand))}
    # 문서의 절반 넘게 나오는 낱말은 구별에 도움이 안 되니 뺀다
    usable = [j for j in range(len(cand)) if df[j] <= n * 0.5 and df[j] > 0]
    pick = sorted(usable, key=lambda j: -idf[j] * (1 + math.log(tf[cand[j]])))[:CANDIDATES]
    if len(pick) < MIN_TERMS:
        return []
    w = {j: idf[j] * (1 + math.log(tf[cand[j]])) for j in pick}
    avg = sum(lens) / n
    k = 1.2
    scored = []
    for path, counts, ln in rows:
        sc, hit = 0.0, 0
        norm = k * (0.5 + 0.5 * ln / avg)
        for j in pick:
            c = counts[j]
            if c:
                hit += 1
                sc += w[j] * (c * (k + 1)) / (c + norm)
        if hit >= 2:   # 낱말 하나만 겹치는 건 비슷하다고 보지 않는다
            scored.append((path, hit, sc))
    scored.sort(key=lambda x: -x[2])
    return [(p, hit, len(pick)) for p, hit, _ in scored[:limit]]
