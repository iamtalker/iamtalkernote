"""단계별 받기 계산(app/stages.py) 시험 — 임시 볼트만 쓴다."""
import os, shutil, sys, tempfile, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import stages

DAY = 86400
now = time.mktime((2026, 10, 31, 12, 0, 0, 0, 0, -1))
tmp = tempfile.mkdtemp(prefix="stagetest-")
ok = []


def check(desc, cond):
    ok.append(bool(cond)); print(("  ✔ " if cond else "  ✘ ") + desc)


def iso(days_ago):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now - days_ago * DAY))


def note(rel, body, updated=None, created=None):
    p = os.path.join(tmp, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    fm = ""
    if updated is not None or created is not None:
        fm = "---\n" + (f"updated: {iso(updated)}\n" if updated is not None else "") + (f"created: {iso(created)}\n" if created is not None else "") + "---\n\n"
    open(p, "w", encoding="utf-8").write(fm + body)


def res(name, size=10, days_ago=None):
    p = os.path.join(tmp, ".resources", name); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(b"x" * size)
    if days_ago is not None:
        t = now - days_ago * DAY; os.utime(p, (t, t))


try:
    note("a/new.md", "![](../.resources/shared.png) ![](:/aaa.jpg)", updated=3, created=900)           # 최근에 고침
    note("a/born.md", "text", updated=2000, created=10)                                                    # 최근에 만듦(updated 가 더 옛날)
    note("b/mid.md", "![x](../.resources/shared.png) ![](<../.resources/with space.png>)", updated=100)  # 6개월
    note("b/old.md", "![](../.resources/old.gif)", updated=1500)                                           # 3년 이전
    note("b/nodate.md", "no front matter")                                                                  # 날짜 없음 → 1단계
    note(".history/h.md", "x", updated=1)                                                                   # 이력은 제외
    res("shared.png"); res("aaa.jpg"); res("with space.png"); res("old.gif"); res("orphan.bin", days_ago=400)
    OLD = [("최근 1개월", 30), ("최근 6개월", 183), ("최근 1년", 365), ("최근 3년", 3 * 365), ("그 이전", None)]
    plan = stages.build(tmp, now, OLD)
    weekly = stages.build(tmp, now)
    wn = [x["name"] for x in weekly["tiers"]]
    check("기본 단계는 주 단위로 시작하고 빈 단계는 뺀다", wn[0] == "1주 이내" and all(x["files"] for x in weekly["tiers"][1:]) and len(wn) <= 15)
    check("주 단위에서도 모든 파일이 한 번씩", sorted(f for x in weekly["tiers"] for f in x["files"]) == sorted(f for x in plan["tiers"] for f in x["files"]))
    t = {x["name"]: x["files"] for x in plan["tiers"]}
    names = [x["name"] for x in plan["tiers"]]
    check("단계 이름(빈 단계는 빠짐)", names[0] == "최근 1개월" and 1 <= len(names) <= 5)
    check("최근에 고친 노트·최근에 만든 노트·날짜 없는 노트는 1단계", {"a/new.md", "a/born.md", "b/nodate.md"} <= set(t["최근 1개월"]))
    check("그림은 쓰는 노트 중 가장 최근 단계(shared.png 는 1단계)", ".resources/shared.png" in t["최근 1개월"] and ".resources/aaa.jpg" in t["최근 1개월"])
    check("6개월 노트와 띄어쓰기 든 그림", "b/mid.md" in t["최근 6개월"] and ".resources/with space.png" in t["최근 6개월"])
    check("오래된 노트와 그 그림은 '그 이전'", "b/old.md" in t["그 이전"] and ".resources/old.gif" in t["그 이전"])
    check("아무도 안 쓰는 그림은 파일 시각으로(400일 → 3년)", ".resources/orphan.bin" in t["최근 3년"])
    allf = [f for x in plan["tiers"] for f in x["files"]]
    check("한 파일은 한 단계에만", len(allf) == len(set(allf)))
    check("이력 폴더는 목록에 없음", not any(f.startswith(".history") for f in allf))
    ig = stages.ignore_lines(plan, 1)
    check("1단계만 열면 나머지가 무시 목록에", "/b/mid.md" in ig and "/b/old.md" in ig and "/a/new.md" not in ig)
    check("전부 열면 무시 목록 비어 있음", stages.ignore_lines(plan, 5) == [])
    path = stages.save(tmp, plan)
    check("목록 파일 저장(.sync/stages.json)", os.path.isfile(path))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("통과 %d / %d" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
