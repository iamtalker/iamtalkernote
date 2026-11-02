"""원문 편집 칸의 최소 서식 툴바와 그림 첨부(리소스 폴더로 복사)를 실제 창으로 시험. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_editor_tools.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="tool-")
vault = os.path.join(tmp, "v")
os.makedirs(os.path.join(vault, "업무"))
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
with open(os.path.join(vault, "업무", "회의.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("안녕 세상\n")
png = os.path.join(tmp, "다운로드 사진.png")   # 공백이 든 이름도 되는지
with open(png, "wb") as fh:
    fh.write(bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.environ["IAT_NO_SINGLE"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import notes  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


a = notes.App()


def pump(n=30):
    for _ in range(n):
        a.root.update()
        time.sleep(0.02)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


pump(60)
a.reload_notes()
pump(20)
n = next(x for x in a.all_notes if x["title"] == "회의")
a.open_note(n)
pump(20)
a.set_mode("edit")
pump(10)
labels = [w.label.cget("text") for w in walk(a.edit_tools) if w.__class__.__name__ == "Btn"]
check("원문만 보기에서도 툴바가 있다(되돌리기·다시 실행 + 서식 + 그림 첨부)",
      {"↶", "↷", "B", "I", "🖼", "🔗", "•", "☐"} <= set(labels))
check("원문만: 툴바가 편집 칸 위에 보인다", a.edit_tools.winfo_ismapped() and a.edit_tools.winfo_y() < a.text.winfo_rooty() - a.edit_frame.winfo_rooty())
check("태그 표시가 제목 아래 편집 영역 위쪽에 있다",
      a.tagbtn.master is a.tag_row and a.tag_row.winfo_y() < a.body.winfo_y())
a.edit_tags()
pump(5)
check("태그 편집 상자도 본문 위쪽에 열린다",
      a.tag_edit is not None and a.tag_edit.winfo_y() < a.body.winfo_y())
a.finish_tags(False)
pump(2)

# 실행 취소·다시 실행
a.text.edit_reset()
before_undo = a.text.get("1.0", "end-1c")
a.text.insert("end-1c", " 되돌리기 시험")
a.undo_btn.command()
pump(5)
check("툴바 실행 취소가 직전 입력을 되돌린다", a.text.get("1.0", "end-1c") == before_undo)
a.redo_btn.command()
pump(5)
check("툴바 다시 실행이 되돌린 입력을 복구한다", a.text.get("1.0", "end-1c") == before_undo + " 되돌리기 시험")

# 굵게
a.text.tag_add("sel", "1.0", "1.2")
bold = next(w for w in walk(a.edit_tools) if w.__class__.__name__ == "Btn" and w.label.cget("text") == "B")
bold.command()
pump(5)
check("굵게 단추가 고른 글을 **로 감싼다", a.text.get("1.0", "1.end").startswith("**안녕**"))

# 좌우 분할에서도 있다
a.set_mode("split")
pump(10)
check("좌우 분할에서도 툴바가 있다", a.edit_tools.winfo_ismapped())

# 그림 첨부: 리소스 폴더로 복사되고 노트에 상대 경로 링크가 들어간다
notes.filedialog.askopenfilenames = lambda **k: (png,)
a.text.mark_set("insert", "end-1c")
a.attach_files()
pump(10)
body = a.text.get("1.0", "end")
mdir = a.store.media_dir
files = os.listdir(mdir) if os.path.isdir(mdir) else []
check("그림이 리소스 폴더로 복사됐다", len(files) == 1 and files[0].endswith(".png"))
check("노트에 상대 경로 그림 링크가 들어갔다(이름은 원래 파일 이름)", "![다운로드 사진](../" in body and files[0] in body)
before = body
a.attach_files()
pump(10)
check("같은 그림을 또 넣어도 파일이 늘지 않는다(내용이 같으면 재사용)", len(os.listdir(mdir)) == 1 and a.text.get("1.0", "end").count(files[0]) == 2)
a.root.destroy()
sys.exit(1 if fails else 0)
