"""본문이 pdf 링크 하나뿐인 노트는 pdf 뷰어로 보이고, 그 밖의 노트는 그대로인지 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_pdf_note.py"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import pdflink  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


tmp = tempfile.mkdtemp(prefix="pdfnote-")
vault = os.path.join(tmp, "v")
res = os.path.join(vault, ".resources")
os.makedirs(res)
os.makedirs(os.path.join(vault, "업무"))
PDF = (b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
with open(os.path.join(res, "보고서 1.pdf"), "wb") as f:
    f.write(PDF)
with open(os.path.join(res, "그림.png"), "wb") as f:
    f.write(b"x")


def note(rel, text):
    path = os.path.join(vault, rel)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


a_path = note("보고서.md", "[보고서](.resources/보고서%201.pdf)\n")
b_path = note("머리말.md", "---\ntags: [a]\n---\n# 보고서\n\n![](.resources/보고서%201.pdf)\n\n태그: #회계 #2024\n")
c_path = note("설명 있음.md", "이 보고서를 보세요.\n\n[보고서](.resources/보고서%201.pdf)\n")
d_path = note("링크 둘.md", "[a](.resources/보고서%201.pdf)\n[b](.resources/보고서%201.pdf)\n")
e_path = note("없는 파일.md", "[x](.resources/없음.pdf)\n")
f_path = note("그림만.md", "[x](.resources/그림.png)\n")
g_path = note("웹.md", "[x](https://example.com/a.pdf)\n")
h_path = note("업무/하위.md", "[보고서](../.resources/보고서%201.pdf)\n")
pdf = os.path.normpath(os.path.join(res, "보고서 1.pdf"))

t = lambda p: pdflink.pdf_target(open(p, encoding="utf-8").read(), p)  # noqa: E731
check("본문이 pdf 링크 하나뿐이면 그 pdf 경로를 돌려준다(%20 풀어서)", t(a_path) == pdf)
check("머리말·제목 줄·그림 문법·태그 줄이 있어도 링크 하나뿐이면 된다", t(b_path) == pdf)
check("다른 글이 있으면 돌려주지 않는다", t(c_path) is None)
check("링크가 둘이면 돌려주지 않는다", t(d_path) is None)
check("파일이 없으면 돌려주지 않는다", t(e_path) is None)
check("pdf 가 아니면 돌려주지 않는다", t(f_path) is None)
check("웹 주소면 돌려주지 않는다", t(g_path) is None)
check("하위 노트북의 상대 경로(..)도 맞게 푼다", t(h_path) == pdf)

# 앱: 실제 윈도 미리보기 처리기가 있을 때만
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.environ["IAT_NO_SINGLE"] = "1"
import notes  # noqa: E402
import winpreview  # noqa: E402

app = notes.App()


def pump(n=30):
    for _ in range(n):
        app.root.update()
        time.sleep(0.02)


pump(60)
app.reload_notes()
pump(20)
pick = lambda title: next(x for x in app.all_notes if x["title"] == title)  # noqa: E731
if not winpreview.available("pdf"):
    print("  (이 컴퓨터에는 pdf 미리보기 처리기가 없어 앱 시험은 건너뜁니다)")
else:
    app.open_note(pick("보고서"))
    pump(40)
    check("pdf 링크 노트를 열면 pdf 뷰어로 보인다", app.pv_active and app.pdf_note == pdf)
    check("머리줄에 '노트 글로 보기' 단추가 있다", app.doc_toggle.winfo_ismapped() and "노트 글" in app.doc_toggle.label.cget("text"))
    app.toggle_doc_view()
    pump(20)
    check("단추를 누르면 노트 글(마크다운)로 바뀐다", not app.pv_active and app.doc_toggle.label.cget("text") == "PDF 로 보기")
    app.toggle_doc_view()
    pump(40)
    check("다시 누르면 pdf 뷰어로 돌아온다", app.pv_active)
    app.open_note(pick("설명 있음"))
    pump(20)
    check("다른 노트를 열면 pdf 뷰어가 닫히고 단추도 사라진다", not app.pv_active and app.pdf_note is None and not app.doc_toggle.winfo_ismapped())
    app.open_note(pick("보고서"))
    pump(40)
    app.close_note()
    pump(10)
    check("노트를 닫으면 pdf 뷰어도 닫힌다", not app.pv_active and app.pdf_note is None)
app.root.destroy()
sys.exit(1 if fails else 0)
