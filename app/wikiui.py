"""위키 링크(켜짐 확인·[[ 자동완성·연결된 노트 보기): App 에서 그대로 옮겨 온 메서드 묶음(동작 변경 없음).
App 이 WikiUIMixin 을 물려받아 self.메서드() 처럼 그대로 부른다."""
from notes_shared import *  # noqa: F401,F403


class WikiUIMixin:
    def wiki_on(self):
        return st.wiki_enabled()

    def wiki_index(self):
        """제목(정규화) → 가장 최근 노트. 노트 목록이 바뀔 때만 다시 만든다"""
        key = (id(self.all_notes), len(self.all_notes))
        if getattr(self, "_wiki_key", None) != key:
            self._wiki_key, self._wiki_idx = key, wikilinks.index(self.all_notes)
        return self._wiki_idx

    # ---- [[ 제목 자동완성
    def wiki_typed(self, e=None):
        if e is not None and e.keysym in ("Up", "Down", "Return", "Tab", "Escape", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        if not self.wiki_on() or self.doc_open or not self.cur:
            return self.wiki_close()
        t = self.text
        tok = wikilinks.open_token(t.get("insert linestart", "insert") + ime.composing())
        if tok is None:
            return self.wiki_close()
        items = wikilinks.suggest([n for n in self.all_notes if n["path"] != self.cur["path"]], tok[1])
        if not items or (len(items) == 1 and wikilinks.norm(items[0]) == wikilinks.norm(tok[1])):
            return self.wiki_close()
        if self.wiki_pop is None:
            lb = tk.Listbox(t, activestyle="none", exportselection=False, height=8, font=(self.ui, 10), relief="solid", bd=1,
                            bg=C["bg"], fg=C["text"], selectbackground=C["accent"], selectforeground="#ffffff")
            lb.bind("<ButtonRelease-1>", lambda ev: (self.wiki_pick(lb.nearest(ev.y)), "break")[1])
            self.wiki_pop = lb
        lb = self.wiki_pop
        lb.delete(0, "end")
        for x in items:
            lb.insert("end", x)
        lb.selection_set(0)
        lb.config(height=len(items), width=max(14, min(48, max(len(x) for x in items) + 2)))
        bb = t.bbox("insert")
        if bb:
            lb.place(x=max(0, min(bb[0], t.winfo_width() - 260)), y=bb[1] + bb[3] + 2)
            lb.lift()

    def wiki_close(self, escape=False):
        if self.wiki_pop is None:
            return None
        self.wiki_pop.destroy()
        self.wiki_pop = None
        return "break" if escape else None

    def wiki_move(self, d):
        lb = self.wiki_pop
        if lb is None:
            return None
        cur = (lb.curselection() or (0,))[0]
        lb.selection_clear(0, "end")
        lb.selection_set(max(0, min(lb.size() - 1, cur + d)))
        lb.see(lb.curselection()[0])
        return "break"

    def wiki_pick(self, idx=None):
        lb = self.wiki_pop
        if lb is None:
            return None
        if idx is None:
            idx = (lb.curselection() or (0,))[0]
        title = lb.get(idx)
        self.wiki_close()
        t = self.text
        tok = wikilinks.open_token(t.get("insert linestart", "insert"))
        if tok:
            line = t.index("insert").split(".")[0]
            a = f"{line}.{tok[0]}"
            t.edit_separator()
            t.delete(a, "insert")
            t.insert(a, title + ("" if t.get("insert", "insert +2c") == "]]" else "]]"))
            t.mark_set("insert", t.search("]]", a, "end") + "+2c" if t.search("]]", a, "end") else "insert")
            t.edit_separator()
        t.focus_set()
        return "break"

    # ---- 연결된 노트
    def show_links(self, n=None):
        n = n or self.cur
        if not n or isinstance(n, docidx.Doc):
            return
        self.flush()
        top = tk.Toplevel(self.root)
        top.title(tr('연결된 노트 — {0}').format(n['title']))
        top.configure(bg=C["bg"])
        top.geometry("460x420")
        top.transient(self.root)
        info = tk.Label(top, text=tr("찾는 중…"), bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=14, pady=6)
        info.pack(fill="x")
        lists = []
        for head in (tr("이 노트를 가리키는 노트"), tr("이 노트가 가리키는 노트")):
            tk.Label(top, text=head, bg=C["bg"], fg=C["text"], font=(self.ui, 10, "bold"), anchor="w", padx=14).pack(fill="x", pady=(6, 2))
            lb = tk.Listbox(top, activestyle="none", exportselection=False, font=(self.ui, 10), relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                            selectbackground=C["accent"], selectforeground="#ffffff", highlightthickness=0)
            lb.pack(fill="both", expand=True, padx=14, pady=(0, 4))
            lists.append(lb)
        rows = [[], []]

        def open_row(which):
            sel = lists[which].curselection()
            if not sel:
                return
            path = rows[which][sel[0]]
            top.destroy()
            self.follow_path(path)
        for i, lb in enumerate(lists):
            lb.bind("<Double-Button-1>", lambda e, i=i: open_row(i))
            lb.bind("<Return>", lambda e, i=i: open_row(i))
        top.bind("<Escape>", lambda e: top.destroy())
        q = queue.Queue()
        threading.Thread(target=lambda: q.put(self.store.wiki_links()), daemon=True).start()

        def done(link_map):
            if not top.winfo_exists():
                return
            idx = self.wiki_index()
            by_key = {self.store.key_of(x["path"]): x for x in self.all_notes}
            mine = self.store.key_of(n["path"])
            back = [k for k in wikilinks.backlinks(link_map, n["title"]) if k != mine and k in by_key]
            out = []
            if self.cur and n["path"] == self.cur["path"]:
                body = self.text.get("1.0", "end-1c")
            else:
                try:
                    with open(n["path"], "rb") as fh:
                        body = st.decode(fh.read())
                except OSError:
                    body = ""
            for title, _, _ in wikilinks.links_in(body):
                tgt = idx.get(wikilinks.norm(title))
                if tgt and tgt["path"] != n["path"] and tgt["path"] not in out:
                    out.append(tgt["path"])
            for which, paths in ((0, [by_key[k]["path"] for k in back]), (1, out)):
                rows[which] = paths
                for p in paths:
                    nn = next((x for x in self.all_notes if x["path"] == p), None)
                    lists[which].insert("end", nn["title"] if nn else p)
            info.config(text=tr('가리키는 노트 {0}개 · 가리킨 노트 {1}개 (두 번 누르면 열림)').format(len(back), len(out)))

        def poll():
            try:
                done(q.get_nowait())
            except queue.Empty:
                if top.winfo_exists():
                    top.after(80, poll)
        poll()
