"""문서에서 찾기 막대(Ctrl+F): App 에서 그대로 옮겨 온 메서드 묶음(동작 변경 없음).
App 이 FindBarMixin 을 물려받아 self.메서드() 처럼 그대로 부른다."""
from notes_shared import *  # noqa: F401,F403


class FindBarMixin:
    # ------------------------------------------------------------ 보기 모드·렌더링 (위키나루)
    # ------------------------------------------------------------ 문서 안에서 찾기
    def find_target(self):
        """찾은 곳을 옮겨 다니는 칸: 렌더링만 볼 때는 렌더링 화면, 그 밖에는 편집 칸(둘 다 보이면 양쪽에 강조하고 편집 칸으로 옮긴다)"""
        return self.view if self.mode == "view" and not self.doc_open else self.text

    def show_find(self):
        if not self.cur:
            return
        if self.doc_open and self.pv_active:   # 윈도 미리보기 안에서는 앱이 찾을 수 없으니, 색인해 둔 글로 바꿔서 찾는다
            self.show_doc(self.cur, native=False)
        for w in (self.text, self.view):
            w.tag_configure("find", background=C["mark"], foreground=C["text"])
            w.tag_configure("findcur", background="#ff9f43", foreground="#000000")
        if not self.findbar.winfo_ismapped():
            self.findbar.pack(side="top", fill="x", before=self.body)
        try:   # 편집 칸에서 한 줄을 골라 둔 채 눌렀으면 그 글자로 바로 찾는다
            sel = self.text.get("sel.first", "sel.last") if self.focus_in_text() else ""
        except tk.TclError:
            sel = ""
        if sel and "\n" not in sel and len(sel) <= 80:
            self.find_var.set(sel)
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")
        self.find_run()

    def focus_in_text(self):
        return self.root.focus_get() is self.text

    def hide_find(self, focus=True):
        if not self.findbar.winfo_ismapped():
            return
        self.findbar.pack_forget()
        for w in (self.text, self.view):
            w.tag_remove("find", "1.0", "end")
            w.tag_remove("findcur", "1.0", "end")
        self.find_hits, self.find_i = [], -1
        if focus and self.cur:
            self.find_target().focus_set()

    def find_matches(self, w, needle, limit=5000):
        out, pos = [], "1.0"
        n = tk.IntVar()
        while len(out) < limit:
            pos = w.search(needle, pos, "end", nocase=True, count=n)
            if not pos:
                break
            n_chars = max(1, n.get())
            out.append((pos, f"{pos}+{n_chars}c"))
            pos = f"{pos}+{n_chars}c"
        return out

    def find_run(self, goto=True):
        """찾을 글자가 바뀌었거나 내용이 바뀌면 일치하는 곳을 모두 강조하고, 지금 위치 다음(없으면 처음)의 것으로 이동한다"""
        if not self.findbar.winfo_ismapped():
            return
        for w in (self.text, self.view):
            w.tag_remove("find", "1.0", "end")
            w.tag_remove("findcur", "1.0", "end")
        needle = self.find_var.get()
        prim = self.find_target()
        old_i = self.find_i
        self.find_hits, self.find_i = [], -1
        if not needle:
            return self.find_count.config(text="", fg=C["muted"])
        shown = [self.text] if self.mode == "edit" else ([self.view] if self.mode == "view" else [self.text, self.view])
        for w in shown:
            hits = self.find_matches(w, needle)
            for a, b in hits:
                w.tag_add("find", a, b)
            if w is prim:
                self.find_hits = hits
        if not self.find_hits:
            return self.find_count.config(text="없음", fg=C["danger"])
        if goto:   # 편집 칸이면 커서 다음의 것, 렌더링 화면이면 처음 것
            at = prim.index("insert") if prim is self.text else "1.0"
            i = next((k for k, (a, _) in enumerate(self.find_hits) if prim.compare(a, ">=", at)), 0)
        else:
            i = min(max(old_i, 0), len(self.find_hits) - 1)
        self.find_goto(i, move=goto)

    def find_goto(self, i, move=True):
        prim = self.find_target()
        self.find_i = i
        a, b = self.find_hits[i]
        prim.tag_remove("findcur", "1.0", "end")
        prim.tag_add("findcur", a, b)
        prim.tag_raise("findcur")
        if move:
            prim.see(a)
            if prim is self.text:
                prim.mark_set("insert", a)
        self.find_count.config(text=f"{i + 1} / {len(self.find_hits):,}", fg=C["muted"])

    def find_step(self, d):
        if not self.find_hits:
            return self.find_run()
        self.find_goto((self.find_i + d) % len(self.find_hits))

    def find_later(self):
        """내용이 바뀌는 중(타이핑)에는 잠시 뒤에 한 번만 다시 찾는다"""
        if not self.findbar.winfo_ismapped():
            return
        if self.find_job:
            self.root.after_cancel(self.find_job)
        self.find_job = self.root.after(300, lambda: self.find_run(goto=False))

    def on_ctrl_f(self, e=None):
        """Ctrl+F: 노트가 열려 있으면 그 문서에서 찾기, 아니면(또는 목록 검색칸에 있으면) 모든 노트에서 검색. 모든 노트 검색은 Ctrl+Shift+F"""
        if self.cur and self.root.focus_get() is not self.search_entry:
            return self.show_find()
        self.focus_search()
