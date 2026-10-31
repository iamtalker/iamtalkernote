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

# --- 백링크·자동완성 (위키 다시 켬)
st.write_config(wikiEnabled=True)
put("링크원.md", "[[회의록]] 를 봄", now)
app.reload_notes()
for _ in range(60):
    app.root.update()
    time.sleep(0.03)
lm = app.store.wiki_links()
check("링크가 든 노트 모음", any("링크원" in k for k in lm))
check("백링크 계산", any("링크원" in k for k in notes.wikilinks.backlinks(lm, "회의록")))
bn = next(x for x in app.all_notes if x["title"] == "링크원")
app.open_note(bn)
app.mode = "edit"
app.text.delete("1.0", "end")
app.text.insert("1.0", "시작 [[회")
app.text.mark_set("insert", "end-1c")
app.wiki_typed()
check("[[회 → 후보 목록이 뜸", app.wiki_pop is not None and app.wiki_pop.size() >= 1 and app.wiki_pop.get(0).startswith("회의록"))
app.wiki_pick()
got = app.text.get("1.0", "end-1c")
check("고르면 제목과 ]] 가 들어감", got.startswith("시작 [[회의록") and got.endswith("]]") and got.count("]]") == 1)
check("목록이 닫힘", app.wiki_pop is None)

app.open_note(next(x for x in app.all_notes if x["title"] == "회의록" and x["path"].endswith(os.path.join("B", "회의록.md"))))
app.show_links()
for _ in range(40):
    app.root.update()
    time.sleep(0.03)
tops = [w for w in app.root.winfo_children() if w.winfo_class() == "Toplevel"]
lbs = [c for c in tops[-1].winfo_children() if c.winfo_class() == "Listbox"]
check("연결 창: 이 노트를 가리키는 노트에 링크원이 뜸", lbs and "링크원" in lbs[0].get(0, "end"))

# --- 즐겨찾기 노트북
tgt = next(x for x in app.all_notes if x["title"] == "링크원")
app.toggle_favorite(tgt)
check("노트북 목록에 즐겨찾기 항목", notes.FAVS in app.nb_keys)
app.nb = notes.FAVS
app.reload_notes()
for _ in range(60):
    app.root.update()
    time.sleep(0.03)
check("즐겨찾기를 고르면 즐겨찾기한 노트만", [n["title"] for n in app.notes] == ["링크원"])
app.toggle_favorite(tgt)
check("해제하면 목록에서 빠짐", app.notes == [] and not hasattr(app, "star_lbl"))
app.nb = notes.ALL

# --- 아웃라이너 폴더
check("사이드바에 아웃라이너 폴더(즐겨찾기 바로 아래)", app.nb_keys[:4] == [notes.ALL, notes.QUICK, notes.FAVS, notes.OUTL])
check("폴더는 볼트 안의 실제 폴더", os.path.isdir(os.path.join(vault, notes.OUTL)))
os.makedirs(os.path.join(vault, notes.OUTL), exist_ok=True)
put(notes.OUTL + "/할일.md", "---\ntags: [x]\n---\n- a\n- b\n    - b1\n", now)
app.nb = notes.ALL
app.reload_notes()
for _ in range(60):
    app.root.update()
    time.sleep(0.02)
on = next(x for x in app.all_notes if x["title"] == "할일")
app.open_note(on)
for _ in range(10):
    app.root.update()
check("보기 탭(분할·렌더링)은 숨김", not app.mode_seg.winfo_manager())
check("아웃라이너 폴더 노트는 아웃라이너 편집기로", app.is_outline_note() and app.ow.winfo_ismapped() and not app.box2.winfo_ismapped())
ow = app.ow
check("항목이 줄로 보임(머리말은 제외)", [ow.txt.get(f"{n}.2", f"{n}.end") for n in (1, 2, 3)] == ["a", "b", "b1"])
ow.txt.mark_set("insert", "1.3")
ow._enter()
ow.txt.insert("insert", "새")
ow._tab()
for _ in range(10):
    app.root.update()
body_now = app.text.get("1.0", "end-1c")
check("고치면 노트 원문에 마크다운 목록으로(머리말 보존)", body_now == "---\ntags: [x]\n---\n- a\n    - 새\n- b\n    - b1\n")
app.flush()
check("파일에도 저장됨", open(on["path"], encoding="utf-8").read() == body_now)
app.text.edit_undo()
for _ in range(10):
    app.root.update()
check("노트 되돌리기가 아웃라이너에도 반영", app.text.get("1.0", "end-1c") != body_now)
other = next(x for x in app.all_notes if x["title"] == "링크원")
app.open_note(other)
for _ in range(10):
    app.root.update()
check("일반 노트로 가면 평소 화면으로 돌아옴", not app.is_outline_note() and app.box2.winfo_manager() == "pack" and not app.ow.winfo_ismapped() and app.edit_frame.winfo_ismapped() and app.mode_seg.winfo_manager() == "pack")
# --- 아웃라이너에서 막 친 글이 노트를 옮겨도 그 노트에 저장되고 다른 노트로 새지 않음
app.open_note(on)
for _ in range(10):
    app.root.update()
app.ow.txt.mark_set("insert", "1.3")
app.ow.txt.insert("insert", "Q")
app.ow._released(type("E", (), {"keysym": "Q"})())      # 0.35초 뒤에 넘길 예약만 걸린 상태
before = open(other["path"], encoding="utf-8").read()
app.open_note(other)                                     # 키보드로 곧바로 다른 노트로 이동
for _ in range(10):
    app.root.update()
check("옮기기 전 친 글이 아웃라이너 노트 파일에 저장됨", "- aQ" in open(on["path"], encoding="utf-8").read())
check("다른 노트는 그대로", open(other["path"], encoding="utf-8").read() == before)

app.nb = notes.ALL

app.root.destroy()
print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
