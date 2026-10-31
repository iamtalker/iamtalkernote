"""즐겨찾기(favorites.py) 시험: py -3 -I -X utf8 tools/test_favorites.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import favorites as fv

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


check("경로: 노트 폴더 기준 슬래시", fv.rel_of(os.path.join("C:\\", "v"), os.path.join("C:\\", "v", "ScrapBook", "a.md")) == "ScrapBook/a.md")
check("합치기: 더 최근 것이 이김", fv.merge({"a": [1, 10]}, {"a": [0, 20]}) == {"a": False} and fv.merge({"a": [1, 30]}, {"a": [0, 20]}) == {"a": True})
check("합치기: 깨진 항목은 건너뜀", fv.merge({"a": "x", "b": [1]}, {"c": [1, 5]}) == {"c": True})
with tempfile.TemporaryDirectory() as d:
    f = fv.Favorites(d)
    check("처음엔 비어 있음", f.all() == [] and not f.is_fav("a.md"))
    f.set("a.md", True, now=100)
    check("켜면 즐겨찾기", f.is_fav("a.md") and f.all() == ["a.md"])
    check("내 파일에만 적음", os.path.exists(os.path.join(d, fv.OWN)) and not os.path.exists(os.path.join(d, fv.OTHER)))
    json.dump({"items": {"a.md": [0, 200], "b/c.md": [1, 150]}}, open(os.path.join(d, fv.OTHER), "w"))
    f.invalidate()
    check("폰이 더 나중에 끄면 꺼짐, 폰이 켠 것도 보임", not f.is_fav("a.md") and f.is_fav("b/c.md") and f.all() == ["b/c.md"])
    f.set("a.md", True, now=300)
    check("내가 더 나중에 다시 켜면 켜짐", f.is_fav("a.md"))
    check("토글", f.toggle("b/c.md") is False and not f.is_fav("b/c.md") and f.toggle("b/c.md") is True)
    f2 = fv.Favorites(d)
    check("다른 객체(앱 다시 시작)에서도 같은 상태", f2.is_fav("a.md") and f2.is_fav("b/c.md"))
    with open(os.path.join(d, fv.OTHER), "w") as fh:
        fh.write("{깨짐")
    check("상대 파일이 깨져도 내 것은 유지", fv.Favorites(d).is_fav("a.md"))
    check("한글 경로", (f.set("노트/한글 제목.md", True) or f.is_fav("노트/한글 제목.md")))
print("통과" if not fails else "실패 %d" % fails)
sys.exit(1 if fails else 0)
