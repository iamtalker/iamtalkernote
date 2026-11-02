"""가져온 파일의 확장자에 연결 프로그램을 지정하면(예: zip → 만화 뷰어) 그 프로그램으로 열리는지 시험. 프로그램은 실제로 띄우지 않고 가로채서 본다.
임시 APPDATA·임시 노트 폴더만 쓴다.   py -3 -X utf8 tools/test_open_with.py"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
tmp = tempfile.mkdtemp(prefix="openwith-")
vault = os.path.join(tmp, "v")
os.makedirs(vault)
fake_exe = os.path.join(tmp, "comicviewer.exe")
open(fake_exe, "wb").write(b"x")
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8").write(json.dumps({"root": vault}))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.environ["IAT_NO_SINGLE"] = "1"
import notes  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


a = notes.App()
for _ in range(40):
    a.root.update()
    time.sleep(0.02)

launched, started = [], []
notes.subprocess.Popen = lambda args, *k, **kw: launched.append(args)
notes.os.startfile = lambda p: started.append(p)
doc = {"ext": "zip", "path": os.path.join(tmp, "만화 1화.zip"), "title": "만화 1화"}

a.open_doc_file(doc)
check("연결이 없으면 윈도 기본 프로그램으로 연다", started == [doc["path"]] and not launched)
a.set_open_with("zip", fake_exe)
check("확장자는 .zip/ZIP 어느 쪽으로 물어도 같다", a.open_with_program(".ZIP") == fake_exe)
a.open_doc_file(doc)
check("연결하면 그 프로그램에 파일 경로를 인자로 넘겨 연다(셸 없이 목록으로)", launched == [[fake_exe, os.path.normpath(doc["path"])]])
check("다른 확장자는 영향이 없다", a.open_with_program("pdf") is None)
os.remove(fake_exe)
started.clear()
a.open_doc_file(doc)
check("프로그램 파일이 사라지면 윈도 기본 프로그램으로 돌아간다", started == [doc["path"]])
open(fake_exe, "wb").write(b"x")
a.set_open_with("zip", None)
check("연결 해제하면 설정에서 빠진다", a.open_with_program("zip") is None and "zip" not in (notes.st.read_config().get("openWith") or {}))
a.root.destroy()
sys.exit(1 if fails else 0)
