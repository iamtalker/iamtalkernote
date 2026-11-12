"""빈 스크랩 다시 받기: 다시 받은 노트와 옛 빈 노트의 짝 찾기. py -3 -I -X utf8 tools/test_empty_scraps.py"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="empty-scraps-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")

import cleanup  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


def note(title, text):
    p = os.path.join(tmp, title + ".md")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return {"path": p, "title": title, "mtime": 0}


def fm(url, body=""):
    return f"---\nsource: {url}\n---\n\n{body}"


BODY = "다시 받은 본문입니다. 낱말이 충분히 많아서 빈 노트가 아닙니다.\n"
notes = [
    note("빈1 http", fm("http://web.example.com/board/read.html?table=pds&number=654964")),
    note("채움1 https", fm("https://web.example.com/board/read.html?table=pds&number=654964", BODY)),
    note("AA __ 전쟁 당시의 노점상들", fm("http://aa.example.com/aa/?idx=a71884")),
    note("전쟁 당시의 노점상들.jpg", fm("https://aa.example.com/issue/?idx=a71884", BODY)),
    note("트위터-1", fm("https://tw.example.com/alice/status/1143538773386416141?s=09")),
    note("남의 글 on Twitter", fm("https://tw.example.com/bob/status/786210954312679424?s=09", BODY)),
    note("게시판 글 하나", fm("http://bd.example.com/board/2097/1051027?no=555123")),
    note("전혀 다른 제목", fm("http://bd.example.com/other/9/9?no=555123", BODY)),
    note("카페 옛 글 제목", fm("https://cafe.example.com/nextrealm/")),
    note("카페의 다른 글", fm("http://cafe.example.com/nextrealm/", BODY)),
    note("11", fm("https://gall.example.com/board/view/?id=tw&no=322753&page=1")),
    note("제목이 완전히 다른 같은 글", fm("http://gall.example.com/board/view/?id=tw&no=322753&page=1", BODY)),
    note("빈3 www", fm("http://www.example.org/post/12/")),
    note("채움3 모바일", fm("https://m.example.org/post/12", BODY)),
    note("빈4 짝 없음", fm("http://none.example.com/a?id=1")),
    note("채움4 다른 글", fm("http://none.example.com/a?id=2", BODY)),
    note("빈5 긴 주소", "---\ntitle: x\nsource: >-\n  http://long.example.com/view?no=77\n---\n\n"),
    note("채움5 긴 주소", "---\nsource: >-\n  https://long.example.com/view?no=77\n---\n\n" + BODY),
    note("빈6 질의 없음", fm("http://path.example.com/a/1")),
    note("채움6 경로 다름", fm("http://path.example.com/b/1", BODY)),
    note("빈7 긴 주소 짝 없음", "---\nsource: >-\n  http://other.example.com/view?no=1\n---\n\n"),
    note("그림만", fm("http://img.example.com/1", "![](../.resources/a.jpg)\n")),
    note("출처 없음", "본문만 있는 노트\n"),
]
empties, repaired = cleanup.empty_scraps(notes)
empty_titles = {n["title"] for n, _u in empties}
pairs = {old["title"]: new["title"] for old, new in repaired}

check("빈 노트 11개를 찾는다", empty_titles == {"빈1 http", "AA __ 전쟁 당시의 노점상들", "트위터-1", "게시판 글 하나", "카페 옛 글 제목", "11", "빈3 www", "빈4 짝 없음", "빈5 긴 주소", "빈6 질의 없음", "빈7 긴 주소 짝 없음"})
check("그림만 있는 노트·출처 없는 노트는 빈 스크랩이 아니다", not ({"그림만", "출처 없음"} & empty_titles))
check("http → https 로 바뀐 주소도 짝", pairs.get("빈1 http") == "채움1 https")
check("경로만 바뀌고 글 번호(질의)가 같고 제목이 비슷하면 짝", pairs.get("AA __ 전쟁 당시의 노점상들") == "전쟁 당시의 노점상들.jpg")
check("질의가 꼬리표(?s=09)뿐이면 다른 글과 짝짓지 않는다", "트위터-1" not in pairs)
check("경로가 다르고 글 번호만 같은데 제목이 다르면 짝이 아니다", "게시판 글 하나" not in pairs)
check("글을 가리키지 않는 주소(카페 첫 화면)는 제목이 달라서 짝이 아니다", "카페 옛 글 제목" not in pairs)
check("주소가 글 번호까지 같으면 제목이 달라도 짝", pairs.get("11") == "제목이 완전히 다른 같은 글")
check("www. 와 m., 끝의 / 차이는 무시", pairs.get("빈3 www") == "채움3 모바일")
check("글 번호가 다르면 짝이 아니다", "빈4 짝 없음" not in pairs)
check("머리말의 긴 주소(source: >-)를 읽어 짝", pairs.get("빈5 긴 주소") == "채움5 긴 주소")
check("질의가 없는데 경로가 다르면 짝이 아니다", "빈6 질의 없음" not in pairs)
check("긴 주소끼리 서로 다른 글이면 짝이 아니다('>-' 글자로 잘못 묶지 않는다)", "빈7 긴 주소 짝 없음" not in pairs)
check("긴 주소는 주소 자체로 읽는다", dict((n["title"], u) for n, u in empties)["빈5 긴 주소"] == "http://long.example.com/view?no=77")
print("FAILS:", fails)
sys.exit(1 if fails else 0)
