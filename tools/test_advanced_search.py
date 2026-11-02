"""고급 검색의 기간·태그·가져온 폴더·확장자와 결합 연산자 시험."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import search


notes = [
    {"title": "report.pdf", "nb": "@doc:folder-a", "ext": "pdf", "tags": {"report"},
     "mtime": search.parse_date("20240115"), "ctime": search.parse_date("20230101")},
    {"title": "audio.mp3", "nb": "@doc:folder-b", "ext": "mp3", "tags": set(),
     "mtime": search.parse_date("20240215"), "ctime": search.parse_date("20240120")},
    {"title": "plain.md", "nb": "Notes", "tags": set(),
     "mtime": search.parse_date("20240315"), "ctime": search.parse_date("20240220")},
]


def matches(condition, note=notes[0], sort="relevance"):
    return search.advanced_match(note, condition, sort)


checks = [
    ("기간은 수정 시각으로 거른다", matches([{"field": "date", "from": "20240101", "to": "20240131"}])),
    ("생성순 정렬이면 생성 시각으로 거른다", not matches([{"field": "date", "from": "20240101", "to": "20240131"}], sort="ctime")),
    ("태그 일치", matches([{"field": "tag", "value": "report"}])),
    ("태그 없음", matches([{"field": "tag", "untagged": True}], notes[1])),
    ("가져온 폴더", matches([{"field": "folder", "value": "folder-a"}])),
    ("확장자", matches([{"field": "extension", "value": ".PDF"}])),
    ("AND", matches([{"field": "tag", "value": "report"}, {"field": "folder", "value": "folder-a", "op": "AND"}])),
    ("OR", matches([{"field": "tag", "value": "missing"}, {"field": "folder", "value": "folder-a", "op": "OR"}])),
    ("NOT", matches([{"field": "tag", "value": "report"}, {"field": "folder", "value": "folder-b", "op": "NOT"}])),
    ("첫 조건 NOT", matches([{"field": "tag", "value": "report", "op": "NOT"}], notes[1])),
    ("잘못된 고급 날짜를 보고", search.bad_advanced_dates([{"field": "date", "from": "20241301"}]) == ["조건 1 from 20241301"]),
]
for name, ok in checks:
    print(("  ✔ " if ok else "  ✘ ") + name)

raise SystemExit(0 if all(ok for _, ok in checks) else 1)
