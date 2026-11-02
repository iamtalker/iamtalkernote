"""가져온 문서 검색식·제목 전용 모드와 대량 색인 회귀 시험: py -3 -I -X utf8 tools/test_docs_search.py"""
import os
import sys
import tempfile
import zlib

tmp = tempfile.mkdtemp(prefix="docsearch-")
appdata = os.path.join(tmp, "appdata")
os.makedirs(os.path.join(appdata, "iamtalkernote"))
os.environ["APPDATA"] = appdata
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import docs  # noqa: E402
import search  # noqa: E402

root = os.path.join(tmp, "imported")
os.makedirs(root)
index = docs.DocIndex()
index.add_folder(root)
fid = index.folders()[0]["id"]

rows = []
for i in range(12000):
    title = f"book-{i}"
    path = os.path.join(root, f"{title}.txt")
    body = "scale marker"
    rows.append((path, fid, "txt", 1, 1, 1.0, 1.0, title,
                 index.make_hay(title, os.path.basename(path), body, [], ""),
                 zlib.compress(body.encode()), 1, index.title_hay(title, "txt")))

fixtures = (
    ("and.txt", "alpha", "beta"),
    ("or.txt", "gamma", ""),
    ("not.txt", "alpha", "banned"),
    ("body-only.txt", "ordinary", "needle"),
)
for filename, title, body in fixtures:
    path = os.path.join(root, filename)
    rows.append((path, fid, "txt", 1, 1, 1.0, 1.0, title,
                 index.make_hay(title, filename, body, [], ""),
                 zlib.compress(body.encode()), 1, index.title_hay(title, "txt")))

conn = index._db()
conn.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
conn.commit()
conn.close()
index.set_annot(rows[0][0], tags=["document-tag"])

notes = index.list_docs()
def matched(query):
    return {n["path"] for n in search.run(notes, query, index=index)[0]}

index.content_search = True
expected = {
    "scale": {row[0] for row in rows[:12000]},
    "alpha AND beta": {os.path.join(root, "and.txt")},
    "alpha OR gamma": {os.path.join(root, "and.txt"), os.path.join(root, "or.txt"), os.path.join(root, "not.txt")},
    "alpha NOT banned": {os.path.join(root, "and.txt")},
}
checks = []
for query, paths in expected.items():
    checks.append((query, matched(query) == paths))

index.content_search = False
checks.append(("본문 검색 끄면 제목만 검색", not matched("needle")))
checks.append(("제목은 계속 검색", os.path.join(root, "body-only.txt") in matched("ordinary")))
checks.append(("경로만 일치하는 검색어는 제외", not matched("body-only")))
index.content_search = True
checks.append(("본문 검색 켜면 본문도 검색", os.path.join(root, "body-only.txt") in matched("needle")))
checks.append(("가져온 문서에서 태그 없는 수를 셈", index.untagged_count() == len(rows) - 1))

for name, ok in checks:
    print(("  ✔ " if ok else "  ✘ ") + name)
sys.exit(0 if all(ok for _, ok in checks) else 1)
