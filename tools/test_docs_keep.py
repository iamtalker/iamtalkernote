"""가져온 폴더를 뺐다 다시 넣어도 색인이 남는지: py -3 -I -X utf8 tools/test_docs_keep.py"""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["APPDATA"] = tmp
os.makedirs(tmp + "/iamtalkernote")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import docs  # noqa: E402

ext = tmp + "/ext"
os.makedirs(ext)
d = docs.DocIndex()
d.add_folder(ext)
fid = d.fid(os.path.abspath(ext))
c = d._db()
c.execute("INSERT INTO docs(path,folder,ext,size,mtime_ns,mtime,ctime,title,hay,body,content,nhay) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
          (ext + "/a.txt", fid, ".txt", 1, 1, 1.0, 1.0, "a", b"h", b"b", 1, b"n"))
c.commit()
c.close()
ok = []
ok.append(d.counts() == {fid: 1})
d.remove_folder(fid)
ok.append(d.counts() == {} and d.kept_counts() == {fid: 1})
d.add_folder(ext)
ok.append(d.counts() == {fid: 1} and d.kept_counts() == {})
print("  ✔ 빼면 색인 보관, 다시 넣으면 되살림" if all(ok) else "  ✘ %s" % ok)
sys.exit(0 if all(ok) else 1)
