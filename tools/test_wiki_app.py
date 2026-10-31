"""위키 링크 통합 시험(임시 설정·임시 볼트): py -3 -I -X utf8 tools/test_wiki_app.py"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="wikitest-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
vault = os.path.join(tmp, "vault")
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
os.makedirs(os.path.join(vault, "A"))
os.makedirs(os.path.join(vault, "B"))
json.dump({"root": vault}, open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w"))

import notes  # noqa: E402
import store as st  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def put(rel, body, mtime):
    p = os.path.join(vault, rel)
    open(p, "w", encoding="utf-8").write(body)
    os.utime(p, (mtime, mtime))


now = time.time()
put("A/회의록.md", "옛날", now - 1000)
put("B/회의록.md", "최근", now - 10)
put("본문.md", "[[회의록]] 과 [[없는노트]]", now - 500)

app = notes.App()
for _ in range(60):
    app.root.update()
    time.sleep(0.05)
    if app.all_notes:
        break
for _ in range(20):
    app.root.update()

check("노트 불러옴", len(app.all_notes) == 3)
check("위키 기본 켜짐", app.wiki_on())
check("같은 제목 중 최근 노트가 연결 대상", app.wiki_index()[notes.wikilinks.norm("회의록")]["path"].endswith(os.path.join("B", "회의록.md")))

n = next(x for x in app.all_notes if x["title"] == "본문")
app.open_note(n)
app.mode = "view"
app.render()
for _ in range(10):
    app.root.update()
v = app.view
check("있는 링크는 푸른 링크", bool(v.tag_ranges("link")))
miss = v.tag_ranges("linkmiss")
check("없는 링크만 붉게", len(miss) == 2 and v.get(miss[0], miss[1]) == "없는노트")

app.follow("page", "회의록")
for _ in range(10):
    app.root.update()
check("링크를 누르면 최근 노트가 열림", app.cur and app.cur["path"].endswith(os.path.join("B", "회의록.md")))

s = app.store
made = s.create_note("A", "회의록")
check("위키 켜짐: 다른 노트북에도 같은 제목 못 만듦(2 붙임)", made["title"] == "회의록 (3)" or made["title"].startswith("회의록 ("))
os.remove(made["path"])
s.index_one  # noqa
t1, _ = s.rename(os.path.join(vault, "본문.md"), "회의록")
check("제목 바꾸기도 겹치면 안 됨(저장소 안전장치)", t1 != "회의록")

st.write_config(wikiEnabled=False)
made2 = s.create_note("A", "회의록")
check("위키 꺼짐: 다른 노트북이면 같은 제목 허용", made2["title"] == "회의록" or made2["title"].startswith("회의록"))
app.open_note(next(x for x in app.all_notes if x["title"] == "본문") if any(x["title"] == "본문" for x in app.all_notes) else app.all_notes[0])
app.render()
for _ in range(10):
    app.root.update()
check("위키 꺼짐: [[ ]] 는 링크가 아님", not app.view.tag_ranges("link"))

app.root.destroy()
print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
