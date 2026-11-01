"""가져오기: 폴더 안의 폴더를 목록에 폴더로 보이고(들어가기·위로), 글 파일은 색인이 비어 있어도 파일에서 바로 읽어 보이는지 시험.
임시 APPDATA·임시 노트 폴더·임시 가져오기 폴더만 쓴다.  py -3 -X utf8 tools/test_docs_folders.py"""
import json
import os
import sys
import tempfile
import time

tmp = tempfile.mkdtemp(prefix="docf-")
vault = os.path.join(tmp, "v")
src = os.path.join(tmp, "소설")
os.makedirs(vault)
os.makedirs(os.path.join(src, "A 소설"))
os.makedirs(os.path.join(src, "B 소설", "외전"))
for rel, text in (("루트.txt", "루트 글"), (os.path.join("A 소설", "a1.txt"), "에이 글 하나"), (os.path.join("A 소설", "a2.txt"), "에이 글 둘"),
                  (os.path.join("B 소설", "b1.txt"), "비 글"), (os.path.join("B 소설", "외전", "x.txt"), "외전 글")):
    with open(os.path.join(src, rel), "wb") as fh:
        fh.write(text.encode("cp949"))   # 한글 txt 는 cp949 가 흔하다
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault}))
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


def pump(n=40):
    for _ in range(n):
        a.root.update()
        time.sleep(0.02)


pump(60)
c = a.docs.cfg()
c["content"] = False                        # 문서 안 글 검색을 끈 상태(색인에는 파일 이름만 들어간다)
a.docs.save_cfg(c)
fid = a.docs.add_folder(src)
a.docs.scan()
fid = a.docs.folders()[0]["id"]
a.nb = "@doc:" + fid
a.reload_notes()
pump(30)


def titles():
    return sorted(n["title"] for n in a.results)


def rows():
    box = getattr(a, "docdir_box", None)
    if box is None or not box.winfo_manager():
        return []
    for w in box.winfo_children():
        for x in [w] + list(w.winfo_children()):
            if x.winfo_class() == "Listbox":
                return list(x.get(0, "end"))
    return []


check("맨 위 폴더에는 그 폴더 바로 아래 파일만 보인다", titles() == ["루트.txt"])
check("하위 폴더가 폴더 줄로 나온다(파일 수 포함)", any("A 소설" in r and "(2)" in r for r in rows()) and any("B 소설" in r and "(2)" in r for r in rows()))

a.doc_go(os.path.join(src, "A 소설"))
pump(20)
check("폴더에 들어가면 그 폴더의 파일만 보인다", titles() == ["a1.txt", "a2.txt"])
check("하위 폴더가 없으면 폴더 줄이 없다", rows() == [])

a.doc_go(os.path.join(src, "B 소설"))
pump(20)
check("한 단계 더 안쪽 폴더도 폴더 줄로 나온다", titles() == ["b1.txt"] and any("외전" in r for r in rows()))
a.doc_go(os.path.dirname(os.path.join(src, "B 소설")))
pump(20)
check("위로 나오면 처음 폴더", titles() == ["루트.txt"])

# 검색하면 하위 폴더까지 전부 찾는다
a.q.set("a1")
a.refresh()
pump(20)
check("검색 중에는 하위 폴더까지 찾는다", "a1.txt" in titles())
a.q.set("")
a.refresh()
pump(20)

# 색인에 글이 없어도(문서 안 글 검색 끔) 글 파일은 파일에서 바로 읽어 보인다
n = next(x for x in a.results if x["title"] == "루트.txt")
check("색인에는 글이 없다(전제)", n.read().strip() == "")
a.open_note(n)
pump(20)
shown = a.text.get("1.0", "end")
check("글 파일은 파일에서 바로 읽어(cp949 도) 보인다", "루트 글" in shown and "뽑은 글이 없습니다" not in shown)
# 예전 '가져온 문서 요약'(.imported)은 앱이 만든 파일만 있을 때 치우고, 다른 파일이 섞여 있으면 건드리지 않는다
import docs as docs_mod  # noqa: E402
old = os.path.join(vault, ".imported")
os.makedirs(os.path.join(old, ".stfolder.removed-1"))
for name in ("docs.jsonl", "meta.json"):
    open(os.path.join(old, name), "w").write("{}")
check("앱이 만든 파일만 든 .imported 는 지운다", docs_mod.remove_old_export(vault) is True and not os.path.exists(old))
os.makedirs(old)
open(os.path.join(old, "docs.jsonl"), "w").write("{}")
open(os.path.join(old, "내가 둔 파일.txt"), "w").write("보관")
check("다른 파일이 섞여 있으면 그대로 둔다", docs_mod.remove_old_export(vault) is False and os.path.exists(os.path.join(old, "내가 둔 파일.txt")))
check(".imported 가 없으면 아무 일도 없다", docs_mod.remove_old_export(os.path.join(tmp, "없는곳")) is False)
# 뒤에서 다시 읽는 동안 상태 줄에 진행(읽은 수 / 읽을 수 · 파일 이름)이 보인다
import threading as _th  # noqa: E402
def slow_scan(progress=None, cancelled=None, only=None):
    progress(3, 12, "읽는 중 — 홍엽만리.txt  ")
    time.sleep(1.6)
    return (12, 0, 12)
a.docs.scan = slow_scan
a.doc_scanning = False
a.rescan_docs_bg()
seen = []
end = time.time() + 3
while time.time() < end:
    a.root.update()
    seen.append(a.status.cget("text"))
    time.sleep(0.05)
check("뒤에서 읽는 동안 상태 줄에 진행이 보인다", any("3 / 12" in x and "홍엽만리.txt" in x for x in seen))
check("끝나면 진행 글이 사라진다", "3 / 12" not in a.status.cget("text") and a.doc_scanning is False)
a.root.destroy()
sys.exit(1 if fails else 0)
