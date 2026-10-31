"""노트북 범위 제한(wikiScope)과 포함(![[노트]]) 시험.
순수 계산(wikilinks)과 앱 통합(임시 설정·임시 볼트): py -3 -I -X utf8 tools/test_wiki_scope_embed.py"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import wikilinks as w  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


# ---------------------------------------------------------------- 순수 계산
print("범위(space·pick)")
check("space: 최상위 노트북", w.space("Wiki/dev/x") == "Wiki" and w.space("Wiki") == "Wiki" and w.space("") == "")
N = [
    {"title": "시작", "nb": "Wiki", "path": "Wiki/시작.md", "mtime": 10},
    {"title": "시작", "nb": "Wiki/dev", "path": "Wiki/dev/시작.md", "mtime": 5},
    {"title": "시작", "nb": "Notes", "path": "Notes/시작.md", "mtime": 99},
]
c = w.multi(N)[w.norm("시작")]
check("제한 없음: 가장 최근", w.pick(c, "Wiki", False)["path"] == "Notes/시작.md")
check("제한: 같은 위키 공간만", w.pick(c, "Wiki/x", True)["path"] == "Wiki/시작.md")
check("제한: 같은 폴더가 먼저(더 오래돼도)", w.pick(c, "Wiki/dev", True)["path"] == "Wiki/dev/시작.md")
check("제한: 공간에 없으면 None", w.pick(c, "Other", True) is None)
check("in_space", [n["path"] for n in w.in_space(N, "Wiki/dev", True)] == ["Wiki/시작.md", "Wiki/dev/시작.md"] and len(w.in_space(N, "Wiki", False)) == 3)

print("절·머리말")
body = "---\ntags: a\n---\n# 소개\n내용\n## 하위\n하위내용\n# 다음\n끝\n```\n# 코드안\n```"
check("strip_meta", w.strip_meta(body).startswith("# 소개"))
check("절: 하위 포함, 다음 제목 앞까지", w.section_of(w.strip_meta(body), "소개") == "# 소개\n내용\n## 하위\n하위내용")
check("절: 하위 절만", w.section_of(w.strip_meta(body), "하위") == "## 하위\n하위내용")
check("절: 마지막 절은 끝까지(코드 안 # 은 제목 아님)", w.section_of(w.strip_meta(body), "다음").endswith("# 코드안\n```"))
check("절: 없으면 None", w.section_of(body, "없음") is None)

print("포함(expand_embeds)")
notes = {
    "A": {"key": "A.md", "title": "A", "nb": "w", "body": "---\nx: 1\n---\n# 소개\n내용A\n# 다음\n끝"},
    "B": {"key": "B.md", "title": "B", "nb": "w", "body": "B본문\n![[A]]"},
    "C": {"key": "C.md", "title": "C", "nb": "w", "body": "![[D]]"},
    "D": {"key": "D.md", "title": "D", "nb": "w", "body": "![[C]]"},
}
fetch = lambda t, nb: notes.get(t)  # noqa: E731
out = w.expand_embeds("앞\n![[A#소개]]\n뒤", fetch, seen=("cur.md",))
check("절 포함: 인용 블록·원본 링크", out == "앞\n> [[A]]\n>\n> # 소개\n> 내용A\n뒤")
check("전체 포함은 머리말 제외", "x: 1" not in w.expand_embeds("![[A]]", fetch, seen=("cur.md",)) and "끝" in w.expand_embeds("![[A]]", fetch, seen=("cur.md",)))
dup = {"D": {"key": "D.md", "title": "문서 D", "nb": "w", "body": "# 문서 D\n본문 D"}}
check("겹치는 첫 제목은 뺌", w.expand_embeds("![[D]]", lambda t, nb: dup["D"]) == "> [[문서 D]]\n>\n> 본문 D")
check("절 포함은 그 제목을 남김", "# 소개" in w.expand_embeds("![[A#소개]]", fetch))
check("없는 노트 표시", "없는 노트: 없음" in w.expand_embeds("![[없음]]", fetch))
check("없는 절 표시", "없는 절" in w.expand_embeds("![[A#없음]]", fetch))
check("코드 블록 안은 그대로", w.expand_embeds("```\n![[A]]\n```", fetch) == "```\n![[A]]\n```")
check("줄 안의 ![[A]] 는 건드리지 않음", w.expand_embeds("말 ![[A]] 말", fetch) == "말 ![[A]] 말")
check("중첩 포함(B 안의 A)", "> > [[A]]" in w.expand_embeds("![[B]]", fetch, seen=("cur.md",)))
cyc = w.expand_embeds("![[C]]", fetch, seen=("cur.md",))
check("순환 막음(C↔D)", "순환" in cyc and cyc.count("[[C]]") == 1)
check("자기 자신 포함 막음", "순환" in w.expand_embeds("![[A]]", fetch, seen=("A.md",)))
deep = {str(i): {"key": "%d.md" % i, "title": str(i), "nb": "w", "body": "![[%d]]" % (i + 1)} for i in range(10)}
check("깊이 제한", "너무 깊이" in w.expand_embeds("![[0]]", lambda t, nb: deep.get(t), seen=("cur.md",)))

# ---------------------------------------------------------------- 앱 통합
tmp = tempfile.mkdtemp(prefix="scope-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
vault = os.path.join(tmp, "vault")
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
for d in ("Wiki/dev", "Notes"):
    os.makedirs(os.path.join(vault, d))
json.dump({"root": vault}, open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w"))
import notes  # noqa: E402
import store as st  # noqa: E402


def put(rel, body, mtime):
    p = os.path.join(vault, rel)
    open(p, "w", encoding="utf-8").write(body)
    os.utime(p, (mtime, mtime))


now = time.time()
put("Wiki/시작.md", "# 시작\n위키 시작 본문", now - 100)
put("Notes/시작.md", "# 시작\n메모 시작 본문", now - 10)          # 더 최근
put("Wiki/dev/글.md", "[[시작]] 과 [[메모만]]\n\n![[시작]]\n\n![[시작#없는절]]", now - 50)
put("Notes/메모만.md", "메모만 있는 노트", now - 20)

app = notes.App()
for _ in range(60):
    app.root.update()
    time.sleep(0.05)
    if app.all_notes:
        break
for _ in range(20):
    app.root.update()

print("앱: 제한 꺼짐(기본)")
check("노트 불러옴", len(app.all_notes) == 4)
check("기본은 제한 꺼짐", not st.wiki_scoped())
g = next(x for x in app.all_notes if x["title"] == "글")
app.open_note(g)
app.mode = "view"
app.render()
for _ in range(10):
    app.root.update()
txt = app.view.get("1.0", "end")
check("꺼짐: [[시작]] 은 최근(Notes) 노트", app.wiki_find("시작")["path"].endswith(os.path.join("Notes", "시작.md")))
check("꺼짐: 포함에 메모 본문", "메모 시작 본문" in txt)
check("꺼짐: 없는 절 안내", "없는 절" in txt)

print("앱: 제한 켜짐")
st.write_config(wikiScope=True)
app.render()
for _ in range(10):
    app.root.update()
txt = app.view.get("1.0", "end")
check("켜짐: [[시작]] 은 같은 위키(Wiki)의 노트", app.wiki_find("시작")["path"].endswith(os.path.join("Wiki", "시작.md")))
check("켜짐: 포함에 위키 본문", "위키 시작 본문" in txt and "메모 시작 본문" not in txt)
check("켜짐: 다른 노트북에만 있는 [[메모만]] 은 없음(붉게)", app.wiki_find("메모만") is None)
miss = app.view.tag_ranges("linkmiss")
check("켜짐: 붉은 링크는 메모만", any(app.view.get(miss[i], miss[i + 1]) == "메모만" for i in range(0, len(miss), 2)))
check("블록 맞추기가 포함 때문에 깨지지 않음(None 이거나 목록)", app.block_map() is None or isinstance(app.block_map(), list))

s = app.store
a = s.create_note("Wiki", "시작")
b = s.create_note("Other", "시작")
check("켜짐: 같은 위키 안에는 같은 제목 못 만듦", a["title"] != "시작")
check("켜짐: 다른 노트북에는 같은 제목 만들 수 있음", b["title"] == "시작")
check("titles(space)", all(k.startswith("Wiki/") for _, k in s.titles("Wiki")) and any(k.startswith("Notes/") for _, k in s.titles("Notes"))
      and not any(k.startswith("Notes/") for _, k in s.titles("Wiki")))
for m in (a, b):
    os.remove(m["path"])

st.write_config(wikiScope=False)
st.write_config(wikiEnabled=False)
app.render()
for _ in range(5):
    app.root.update()
txt = app.view.get("1.0", "end")
check("위키를 끄면 포함은 펼치지 않음(기존 [[ ]] 처럼 글자만)", "위키 시작 본문" not in txt and "메모 시작 본문" not in txt and "시작" in txt)
app.root.destroy()

print("\n%s" % ("모두 통과" if not fails else "실패 %d" % fails))
sys.exit(1 if fails else 0)
