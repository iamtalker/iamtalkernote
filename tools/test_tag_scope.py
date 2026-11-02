"""사이드바 태그 범위와 태그 없는 노트 필터 회귀 시험."""
import os
import sys
import tempfile
from types import SimpleNamespace

tmp = tempfile.mkdtemp(prefix="tagscope-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import notes  # noqa: E402


class Tree:
    def __init__(self):
        self.rows = {}
        self.selected = ()
        self.clicked = "tg0"

    def delete(self, *_items):
        self.rows.clear()

    def get_children(self):
        return list(self.rows)

    def insert(self, _parent, _index, iid, text, values):
        self.rows[iid] = (text, values)

    def selection(self):
        return self.selected

    def selection_remove(self, *items):
        self.selected = tuple(i for i in self.selected if i not in items)

    def selection_set(self, *items):
        self.selected = items

    def identify_row(self, _y):
        return self.clicked


class Button:
    def config(self, **kw):
        self.text = kw.get("text", getattr(self, "text", ""))


app = notes.App.__new__(notes.App)
app.show = {"tags": True}
app.notes = [{"tags": {"local"}}, {"tags": set()}]
app.all_notes = [{"tags": {"alpha"}}, {"tags": set()}]
app.docs = SimpleNamespace(tag_counts=lambda: {"doc-tag": 2}, untagged_count=lambda: 3)
app.tag_global = False
app.tag = None
app.tag_none = False
app.adv_conditions = []
app.quiet = False
app.tagtree = Tree()
app.fit_count = lambda _tree, _values: None
app.reload_tags()
checks = [
    app.tag_keys == [None, "local"],
    app.tagtree.rows["tg0"] == ("  태그 없음   1", ("1",)),
]
print(("  ✔ " if checks[-1] else "  ✘ ") + "현재 범위의 태그 목록 맨 위에 태그 없음 표시")

saved = {}
old_write_config = notes.st.write_config
notes.st.write_config = lambda **kw: saved.update(kw)
app.tag_scope_btn = Button()
app.toggle_tag_scope()
checks.append(app.tag_global and saved.get("tagGlobal") is True
              and app.tag_keys == [None, "doc-tag", "alpha"]
              and app.tagtree.rows["tg0"][1] == ("4",))
print(("  ✔ " if checks[-1] else "  ✘ ") + "전체 범위에서 노트와 가져온 문서 태그를 합산")

app.tagtree.clicked = "tg0"
refresh = app.refresh
app.refresh = lambda: None
app.on_tag_click(SimpleNamespace(y=0, state=0))
checks.append(app.tag_none and app.tag is None)
print(("  ✔ " if checks[-1] else "  ✘ ") + "태그 없음 행을 선택하면 전용 필터 상태가 됨")

app.notes = [{"title": "with-tag", "tags": {"tag"}}, {"title": "without-tag", "tags": set()}]
app.search_job = None
app.results = app.words = []
app.q = SimpleNamespace(get=lambda: "")
app.d_from = SimpleNamespace(get=lambda: "")
app.d_to = SimpleNamespace(get=lambda: "")
app.doc_context = lambda: None
app.nb = "A"
app.sort, app.asc = "relevance", False
app.scope_all = lambda: False
app.store = object()
app.draw_list = lambda **_kw: None
old_search = notes.search.run
notes.search.run = lambda pool, *_args, **_kw: (list(pool), [])
app.refresh = refresh
app.refresh()
checks.append([n["title"] for n in app.results] == ["without-tag"])
print(("  ✔ " if checks[-1] else "  ✘ ") + "태그 없는 항목만 검색 결과로 남음")

notes.search.run = old_search
notes.st.write_config = old_write_config
raise SystemExit(0 if all(checks) else 1)
