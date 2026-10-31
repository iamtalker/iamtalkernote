"""검색창 자동완성(최근 검색·파일 제목·태그)과 한글 입력기 글꼴 맞춤: App 에서 그대로 옮겨 온 메서드 묶음(동작 변경 없음).
App 이 SearchBoxMixin 을 물려받아 self.ac_init() 처럼 그대로 부른다."""
from notes_shared import *  # noqa: F401,F403


class SearchBoxMixin:
    def ac_init(self):
        old = getattr(self, "ac_top", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
        self.ac_top = self.ac_list = None
        self.ac_items, self.ac_job, self.ac_click, self.ac_sig = [], None, False, None
        self.ac_titles = (None, [])      # (캐시 열쇠, [(제목, 소문자 제목)])
        self.ac_tagc = (0.0, {})         # (만든 시각, {태그: 개수})
        e = self.search_entry
        e.bind("<Down>", self.ac_down)
        e.bind("<Up>", self.ac_up)
        e.bind("<Return>", self.ac_enter)
        e.bind("<Escape>", self.ac_esc)
        e.bind("<FocusOut>", self.ac_focus_out, add="+")
        e.bind("<Button-1>", lambda ev: self.root.after(30, self.ac_show), add="+")   # 비어 있는 칸을 누르면 최근 검색
        e.bind("<FocusIn>", lambda ev: None if self.ac_visible() else setattr(self, "ac_sig", self.ac_signature()), add="+")   # 칸에 들어간 것만으로는 후보를 띄우지 않는다
        self.ac_ready = True
        if not getattr(self, "ac_polling", False):
            self.ac_polling = True
            self.ac_poll()

    def ime_keep_font(self, ev):
        """입력기 조합 글꼴을 그 칸 글꼴에 맞춰 둔다. 조합이 시작되기 전(글쇠를 누를 때, 조합 글자가 없을 때)에 미리 맞춰야 첫 글자부터 제 크기로
        보인다(조합이 시작된 뒤에 맞추면 그 글자가 작게 보였다가 확정되며 커졌다). 조합 중에 새로 시작된 경우도 한 번 더 맞춘다"""
        comp = bool(ime.composing())
        if (not comp and str(ev.type) in ("2", "KeyPress")) or (comp and not getattr(self, "_ime_on", False)):
            self.match_ime_font(ev)
        self._ime_on = comp

    def ime_family(self, f):
        """입력기 조합 글자를 그릴 글꼴 이름. 칸 글꼴(Consolas 같은 영문 전용)에 한글이 없으면 Tk 는 한글을 대체 글꼴로 그리는데, 입력기는 다른 대체 글꼴을
        골라 한글이 작게 보였다 확정되면 커졌다. 그래서 한글이 칸에서 앱 글꼴(self.ui, 한글 글꼴)과 같은 폭으로 그려지면 입력기에도 앱 글꼴을 쓴다"""
        fam = f.actual("family")
        try:
            if fam != self.ui:
                ref = tkfont.Font(root=self.root, family=self.ui, size=f.actual("size"), weight=f.actual("weight"))
                if abs(f.measure("가") - ref.measure("가")) <= 2:
                    return self.ui
        except tk.TclError:
            pass
        return fam

    def match_ime_font(self, ev=None, widget=None):
        """한글 입력기의 조합 글꼴을 지금 칸(입력칸·편집 칸 …)의 글꼴과 같게 맞춘다 — 안 맞추면 치는 글자가 잠깐 더 크게 보인다"""
        w = widget or (ev.widget if ev is not None else None)
        try:
            f = tkfont.Font(root=self.root, font=w.cget("font"))
            size = f.actual("size")
            px = size if size < 0 else -round(size * float(self.root.tk.call("tk", "scaling")))   # 음수 = 글자 높이 픽셀
            return ime.set_font(self.ime_family(f), px, f.actual("weight") == "bold")
        except (tk.TclError, AttributeError):
            return False

    def ac_signature(self):
        """입력칸의 값 + 한글 입력기가 아직 확정하지 않은 조합 중인 글자. 이게 바뀌면 후보를 다시 띄운다"""
        return (self.q.get(), ime.composing())

    def ac_poll(self):
        """치는 즉시 후보를 띄운다. 한글은 마지막 글자가 확정되기 전에는 입력칸의 값(StringVar)에 안 들어가서, 값이 바뀔 때를 기다리면 방향키를 눌러야 뜬다 → 조합 중인 글자까지 보며 0.12초마다 확인"""
        self.root.after(120, self.ac_poll)
        if not getattr(self, "ac_ready", False):
            return
        try:
            if self.root.focus_get() is not self.search_entry:   # 후보 창이 뜨며 잠깐 포커스가 빠져도 기준값은 그대로 둔다(안 그러면 다음 변화를 한 번 놓친다)
                return
        except KeyError:
            return
        sig = self.ac_signature()
        if sig[1] and not getattr(self, "ime_font_set", False):   # 조합이 막 시작됐으면 그 글꼴을 입력칸에 맞춘다(한 조합에 한 번)
            self.ime_font_set = self.match_ime_font(widget=self.search_entry)
        elif not sig[1]:
            self.ime_font_set = False
        if self.ac_sig is None:
            self.ac_sig = sig
            return
        if sig != self.ac_sig:
            self.ac_sig = sig
            self.ac_show()

    def search_history(self):
        return [h for h in st.read_config().get("searchHist", []) if isinstance(h, str)]

    def remember_search(self, q):
        q = (q or "").strip()
        if not q:
            return
        hist = [h for h in self.search_history() if h != q and not q.lower().startswith(h.lower())]   # 치다 만 앞부분은 같이 쌓지 않는다
        st.write_config(searchHist=([q] + hist)[:30])

    AC_TAGS_TTL = 60   # 태그 개수를 다시 세는 간격(초)

    def ac_tags(self):
        """{태그: 개수} (노트 + 가져온 파일). 키를 칠 때마다 불리므로 **기다리지 않고** 마지막으로 센 값을 바로 돌려주고,
        오래됐으면 뒤에서(다른 쓰레드) 다시 센다. 가져온 문서(DB)까지 세는 데 오래 걸려 화면이 멈추고 친 글자가 한꺼번에 들어오던 문제가 있었다."""
        t0, counts = self.ac_tagc
        if time.time() - t0 > self.AC_TAGS_TTL and not getattr(self, "_ac_busy", False):
            self._ac_busy = True
            notes = list(self.all_notes)

            def work():
                try:
                    c = {}
                    for n in notes:
                        for t in list(n["tags"]):
                            c[t] = c.get(t, 0) + 1
                    for t, k in self.docs.tag_counts().items():
                        c[t] = c.get(t, 0) + k
                    self.ac_tagc = (time.time(), c)
                except Exception:  # noqa: BLE001  (센 도중 목록이 바뀌어도 다음에 다시 센다)
                    pass
                finally:
                    self._ac_busy = False
            threading.Thread(target=work, daemon=True).start()
        return counts

    def ac_candidates(self):
        """지금 커서 앞의 낱말에 맞는 후보 → [(종류, 보여 줄 글, 넣을 글, 바꿀 시작, 바꿀 끝)] (최대 8개)"""
        text = self.q.get() + ime.composing()   # 조합 중인 마지막 글자까지 (아직 입력칸 값에 안 들어 있다)
        pos = len(text)   # 커서 위치는 쓰지 않는다: 한글 입력기(IME)는 커서를 한 글자씩 늦게 옮겨서, 치는 낱말이 비어 보이거나 한 글자 전 글이 잡힌다
        m = re.search(r"\S*$", text)
        start, tok = m.start(), m.group(0)
        lead = re.match(r'^[(!&|"]+', tok)      # 괄호·부정·따옴표는 낱말 앞에서 떼어 둔다
        quoted = bool(lead and '"' in lead.group(0))
        if lead:
            start += lead.end()
            tok = tok[lead.end():]
        items = []
        hist = self.search_history()
        if not text.strip():        # 빈 칸: 최근 검색
            return [("최근", h, h, 0, len(text)) for h in hist[:8]]
        low = tok.lower()
        if low.startswith("#"):                   # 태그만: '#' 만 쳤을 때는 띄우지 않고, '#신' 처럼 한 글자라도 더 쳐야 그 글자로 시작하는 태그를 보여 준다
            key = low[1:]
            if not key:
                return []
            tags = sorted(self.ac_tags().items(), key=lambda kv: (-kv[1], kv[0].lower()))
            return [("태그", f"#{t}   ({c:,})", f"#{t}", start, pos) for t, c in tags if t.lower().startswith(key)][:8]
        if not tok:
            return []
        key = (id(self.notes), len(self.notes))   # 그냥 글자를 치면 제목만(태그는 # 를 눌렀을 때만, 최근 검색은 빈 칸일 때만)
        if self.ac_titles[0] != key:
            self.ac_titles = (key, [(n["title"], n["title"].lower()) for n in self.notes])
        seen, titles = set(), []
        for title, tl in self.ac_titles[1]:
            if low in tl and tl not in seen:
                seen.add(tl)
                titles.append((not tl.startswith(low), len(tl), title))
        for _p, _l, title in sorted(titles)[:8]:
            if len(items) >= 8:
                break
            plain = re.fullmatch(r"[^\s()\"&|!]+", title) is not None
            ins = title if plain and not quoted else (title + '"' if quoted else f'"{title}"')
            items.append(("제목", title, ins, start, pos))
        return items[:8]

    def ac_show(self):
        self.ac_job = None
        if self.root.focus_get() is not self.search_entry:
            return
        self.ac_items = self.ac_candidates()
        if not self.ac_items:
            return self.ac_hide()
        if self.ac_list is None:
            # 별도 창(Toplevel)이 아니라 목록 칸 위에 겹쳐 놓는 위젯이다: 별도 창은 뜰 때 입력칸의 키보드 포커스를 가져가서 계속 칠 수 없다
            lb = self.ac_list = self.ac_top = tk.Listbox(self.listf, relief="flat", bd=0, activestyle="none", exportselection=False, takefocus=0,
                                                         highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["line"],
                                                         bg=C["bg"], fg=C["text"], selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10))
            lb.bind("<ButtonPress-1>", lambda ev: (setattr(self, "ac_click", True), "break")[1])      # 눌러도 입력칸의 포커스가 옮겨 가지 않게
            lb.bind("<ButtonRelease-1>", lambda ev: self.ac_pick(lb.nearest(ev.y)))
            lb.bind("<Motion>", lambda ev: (lb.selection_clear(0, "end"), lb.selection_set(lb.nearest(ev.y))))
        lb = self.ac_list
        lb.delete(0, "end")
        for kind, label, _ins, _a, _b in self.ac_items:   # 제목·태그는 # 로 구분되니 표시를 달지 않고, 최근 검색만 '최근' 을 붙인다
            lb.insert("end", f"최근   {label}" if kind == "최근" else label)
        lb.config(height=len(self.ac_items))
        box = self.search_entry.master
        lb.place(in_=self.listf, x=box.winfo_rootx() - self.listf.winfo_rootx(),
                 y=box.winfo_rooty() - self.listf.winfo_rooty() + box.winfo_height() + 1, width=box.winfo_width())
        lb.lift()

    def ac_hide(self):
        if self.ac_job:
            self.root.after_cancel(self.ac_job)
            self.ac_job = None
        self.ac_click = False
        if self.ac_list is not None:
            self.ac_list.place_forget()
        self.ac_items = []

    def ac_visible(self):
        return self.ac_list is not None and bool(self.ac_items) and self.ac_list.winfo_ismapped()

    def ac_move(self, step):
        lb = self.ac_list
        cur = lb.curselection()
        i = (cur[0] + step) if cur else (0 if step > 0 else len(self.ac_items) - 1)
        i = max(0, min(len(self.ac_items) - 1, i))
        lb.selection_clear(0, "end")
        lb.selection_set(i)
        lb.see(i)

    def ac_down(self, ev=None):
        if not self.ac_visible():
            self.ac_show()
            return "break"
        self.ac_move(1)
        return "break"

    def ac_up(self, ev=None):
        if self.ac_visible():
            self.ac_move(-1)
            return "break"

    def ac_enter(self, ev=None):
        if self.ac_visible() and self.ac_list.curselection():
            self.ac_pick(self.ac_list.curselection()[0])
            return "break"
        self.ac_hide()
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.refresh()
        self.remember_search(self.q.get())
        return "break"

    def ac_esc(self, ev=None):
        if self.ac_visible():
            self.ac_hide()
            return "break"

    def ac_pick(self, i):
        """고른 후보를 검색어에 넣고 바로 찾는다"""
        if not (0 <= i < len(self.ac_items)):
            return self.ac_hide()
        _kind, _label, ins, a, b = self.ac_items[i]
        text = self.q.get()
        new = text[:a] + ins + text[b:]   # (조합 중이던 글자는 입력칸 값에 없으므로 자연히 빠진다)
        self.ac_hide()
        ime.cancel()                          # 조합 중이던 글자가 나중에 또 붙지 않게
        self.q.set(new)
        self.ac_sig = (new, "")               # 이 값 바꿈이 또 후보를 띄우지 않게
        self.search_entry.focus_set()
        self.search_entry.icursor(a + len(ins))
        self.remember_search(new)

    def ac_focus_out(self, ev=None):
        if self.ac_click:                     # 후보를 누르는 중이면 ButtonRelease 가 처리한다
            return
        self.root.after(150, self.ac_hide)
        if self.q.get().strip() and self.results:
            self.remember_search(self.q.get())

    def clear_search(self):
        """검색어를 지우고 전체 목록으로 돌아간다(기간 필터와 태그 거르기는 그대로)"""
        self.q.set("")
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.refresh()
        self.search_entry.focus_set()

    def update_placeholder(self):
        if self.q.get():
            self.clear_btn.place(relx=1.0, x=-8, rely=0.5, anchor="e")
        else:
            self.clear_btn.place_forget()
        if self.q.get() or self.root.focus_get() is self.search_entry:
            self.ph.place_forget()
        else:
            self.ph.place(x=10, rely=0.5, anchor="w")
