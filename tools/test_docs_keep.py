"""가져온 폴더 색인 삭제와 문서 주석 보존: py -3 -I -X utf8 tools/test_docs_keep.py"""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["APPDATA"] = tmp
os.makedirs(tmp + "/iamtalkernote")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import docs  # noqa: E402

ext = os.path.join(tmp, "ext")
os.makedirs(ext)
path = os.path.join(ext, "a.txt")
with open(path, "w", encoding="utf-8") as f:
    f.write("본문")
d = docs.DocIndex()
d.add_folder(ext)
fid = d.fid(os.path.abspath(ext))
d.scan()
d.set_annot(path, tags=["중요"], memo="다시 가져와도 남음")
ok = []
ok.append(d.counts() == {fid: 1})
d.remove_folder(fid)
ok.append(d.counts() == {} and d.annots()[path] == (["중요"], "다시 가져와도 남음"))
d.add_folder(ext)
ok.append(d.counts() == {})
d.scan()
ok.append(d.counts() == {fid: 1} and d.annots()[path] == (["중요"], "다시 가져와도 남음"))
c = d._db()
tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
c.close()
ok.append("docs_old" not in tables)
print("  ✔ 폴더 색인은 삭제하고 태그·메모는 보존" if all(ok) else "  ✘ %s" % ok)
sys.exit(0 if all(ok) else 1)
