"""가져온 폴더 색인 3일 보관과 문서 주석 보존: py -3 -I -X utf8 tools/test_docs_keep.py"""
import os
import sys
import tempfile
import time

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
c = d._db()
expires = c.execute("SELECT expires FROM removed_folders WHERE folder=?", (fid,)).fetchone()[0]
ok.append(abs(expires - time.time() - 3 * 86400) < 5)
c.close()
ok.append(d.counts() == {} and d.annots()[path] == (["중요"], "다시 가져와도 남음"))
d.add_folder(ext)
ok.append(d.counts() == {fid: 1})
ok.append(d.scan()[0] == 0)
ok.append(d.counts() == {fid: 1} and d.annots()[path] == (["중요"], "다시 가져와도 남음"))
# 3일 경과 시 보관 색인만 지워진다. 다시 뺐을 때부터 새로 3일을 센다.
d.remove_folder(fid)
c = d._db()
ok.append(c.execute("SELECT COUNT(*) FROM docs_retained").fetchone()[0] == 1)
c.execute("UPDATE removed_folders SET expires=0")
c.commit(); c.close()
d = docs.DocIndex()  # 재시작 뒤에도 만료 처리
c = d._db()
ok.append(c.execute("SELECT COUNT(*) FROM docs_retained").fetchone()[0] == 0)
ok.append(c.execute("SELECT COUNT(*) FROM removed_folders").fetchone()[0] == 0)
c.close()
d.add_folder(ext)
ok.append(d.counts() == {} and d.annots()[path] == (["중요"], "다시 가져와도 남음"))
d.scan()
ok.append(d.counts() == {fid: 1})
c = d._db()
tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
c.close()
ok.append("docs_old" not in tables)
print("  ✔ 폴더 색인 3일 보관·재추가 취소·만료 삭제·태그 메모 보존" if all(ok) else "  ✘ %s" % ok)
sys.exit(0 if all(ok) else 1)
