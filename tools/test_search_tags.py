"""검색식의 #태그가 태그 메타데이터와 정확히 일치하는지 시험한다."""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.TemporaryDirectory(prefix="search-tags-")
os.environ["APPDATA"] = os.path.join(tmp.name, "appdata")
os.makedirs(os.environ["APPDATA"])
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import docs  # noqa: E402
import search  # noqa: E402
import store  # noqa: E402
import tagtext  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


now = time.time()
plain = [
    {"title": "정치 기사", "mtime": now, "body": "선거 공약", "tags": {"정치"}},
    {"title": "정치인 기사", "mtime": now, "body": "선거 공약", "tags": {"정치인"}},
    {"title": "본문에만 해시태그", "mtime": now, "body": "#정치 선거 공약", "tags": set()},
    {"title": "정치 메모", "mtime": now, "body": "국회 일정", "tags": {"정치"}},
]
found, words = search.run(plain, "#정치")
check("#태그는 본문 글자 대신 정확한 태그와 일치",
      {n["title"] for n in found} == {"정치 기사", "정치 메모"})
check("태그 검색어는 본문 강조 단어로 취급하지 않음", words == [])
found, _ = search.run(plain, "#정치 AND 선거")
check("태그와 일반 검색어 AND 조합", [n["title"] for n in found] == ["정치 기사"])
found, _ = search.run(plain, "#정치 OR #정치인")
check("태그 OR 조합", {n["title"] for n in found} == {"정치 기사", "정치인 기사", "정치 메모"})
found, _ = search.run(plain, "#정치 NOT 선거")
check("태그 NOT 조합", [n["title"] for n in found] == ["정치 메모"])

root = os.path.join(tmp.name, "vault")
os.makedirs(root)
indexed = store.Store(root)
indexed.tagger = tagtext.note_tags
indexed_notes = []
for i in range(10):
    path = os.path.join(root, f"정치-{i}.md")
    body = f"---\ntags: [정치]\n---\n선거 공약 {i}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    indexed.index_one(path, body)
    indexed_notes.append({"key": indexed.key_of(path), "title": f"정치-{i}", "mtime": now,
                          "body": body, "tags": {"정치"}})
path = os.path.join(root, "정치인.md")
body = "---\ntags: [정치인]\n---\n선거 공약\n"
with open(path, "w", encoding="utf-8") as f:
    f.write(body)
indexed.index_one(path, body)
indexed_notes.append({"key": indexed.key_of(path), "title": "정치인", "mtime": now,
                      "body": body, "tags": {"정치인"}})
found, _ = search.run(indexed_notes, "#정치", index=indexed)
check("색인 검색에서도 정확한 정치 태그만 반환", len(found) == 10)

doc_index = docs.DocIndex()
conn = doc_index._db()
try:
    for path, tag in (("doc-politics", "정치"), ("doc-politician", "정치인")):
        conn.execute("INSERT INTO docs (path, folder, ext, size, mtime_ns, mtime, ctime, title, hay, body, content, nhay) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (path, "folder", "txt", 0, 0, now, now, path, b"", b"", 0, b""))
        conn.execute("INSERT INTO annot VALUES (?, ?, ?)",
                     (path, json.dumps([tag], ensure_ascii=False), ""))
    conn.commit()
finally:
    conn.close()
doc_index.content_search = False
doc_hits = doc_index.query_hits(search.parse("#정치"), [])
check("가져온 문서의 태그도 정확히 검색", set(doc_hits) == {"doc-politics"})

tmp.cleanup()
print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
