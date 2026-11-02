"""검색 자동완성은 입력한 글에 맞추고, 최근 검색은 별도 동작으로 연다."""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import searchbox


class SearchHarness(searchbox.SearchBoxMixin):
    def __init__(self, root):
        self.root = root
        self.ui = "Segoe UI"
        self.q = tk.StringVar()
        self.notes = [{"title": "회의록"}, {"title": "아이디어"}]
        self.listf = tk.Frame(root)
        self.listf.pack(fill="both", expand=True)
        self.search_entry = tk.Entry(root, textvariable=self.q)
        self.search_entry.pack(fill="x")
        self.ac_init()


searchbox.st.read_config = lambda: {"searchHist": ["지난 검색어", "회의록"]}
root = tk.Tk()
root.geometry("360x180")
app = SearchHarness(root)
app.search_entry.focus_force()
root.update()
app.search_entry.event_generate("<Button-1>")
root.after(150, root.quit)
root.mainloop()
checks = [not app.ac_visible()]
print(("  ✔ " if checks[-1] else "  ✘ ") + "빈 검색창을 눌러도 최근 검색을 열지 않음")

app.show_search_history()
root.update()
labels = list(app.ac_list.get(0, "end"))
checks.append(labels == ["지난 검색어", "회의록"] and all("최근" not in label for label in labels))
print(("  ✔ " if checks[-1] else "  ✘ ") + "최근 검색 버튼용 목록은 접두어 없이 검색어만 표시")

app.remember_search = lambda _query: None
app.ac_hide()
app.q.set("현재 검색어")
app.show_search_history()
root.update()
app.show_search_history()
root.update()
checks.append(app.q.get() == "지난 검색어" and not app.ac_visible())
print(("  ✔ " if checks[-1] else "  ✘ ") + "최근 검색 버튼을 다시 누르면 가장 최근 검색어를 입력")

app.q.set("회의")
app.ac_show()
root.update()
checks.append(bool(app.ac_items) and all(item[0] != "history" for item in app.ac_items)
              and any(item[1] == "회의록" for item in app.ac_items))
print(("  ✔ " if checks[-1] else "  ✘ ") + "입력한 글자에 맞는 제목 제안만 표시")
root.destroy()

if not all(checks):
    raise SystemExit(1)
