"""노트 목록(불러오기·검색·그리기)의 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class NoteListMixin:
    # ------------------------------------------------------------ 목록: 불러오기·검색·그리기
    def reload_notes(self, background=False, keep_scroll=False):
        """저장 폴더의 노트를 다시 읽는다. background=True 면 창을 먼저 보이고 뒤에서 읽는다(노트가 많을 때 시작이 느려지지 않게)."""
        self.load_gen += 1
        gen = self.load_gen
        if not background:
            return self.apply_loaded(self.read_all_notes(), keep_scroll)
        self.count.config(text=tr("노트를 불러오는 중…"))
        q = queue.Queue()

        def work():
            try:
                q.put(("ok", self.read_all_notes()))
            except Exception as ex:  # noqa: BLE001
                q.put(("err", str(ex)))
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                d, t = self.load_prog
                if t:
                    self.count.config(text=tr('처음 한 번 색인을 만드는 중… {0:,} / {1:,}').format(d, t))
                return self.root.after(80, poll)
            if gen != self.load_gen:
                return    # 그 사이에 다른 읽기가 있었으면 버린다
            if kind == "ok":
                self.apply_loaded(val)
            else:
                self.count.config(text=tr("노트를 불러오지 못했습니다: ") + val)
        self.root.after(80, poll)

    def refresh_all(self, e=None):
        """전체 새로 고침(F5·⟳): 탐색기 등 앱 밖에서 노트북·노트를 지우거나 옮겼을 때, 껐다 켜지 않고 노트·노트북·태그·즐겨찾기·달력·가져온 문서를 다시 읽는다"""
        self.flush()
        for fn in (self.fav.invalidate, self.planner.sync):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
        self.reload_notes(keep_scroll=True)
        if self.docs.folders():
            self.rescan_docs_bg()
        self.status.config(text=tr("새로 고쳤습니다"))
        return "break"

    def read_all_notes(self):
        self.load_prog = (0, 0)
        return self.store.list_notes(ALL, tagger=note_tags, progress=lambda d, t: setattr(self, "load_prog", (d, t)))

    def apply_loaded(self, loaded, keep_scroll=False):
        keep = self.cur["path"] if self.cur else None
        self.all_notes = loaded
        if self.nb.startswith("@doc"):   # 가져온 폴더를 골랐으면 목록은 노트가 아니라 가져온 문서
            fid = self.doc_key_parts(self.nb)[0] if self.nb.startswith("@doc:") else None
            self.notes = self.docs.list_docs(fid)
            if fid:
                root = self.doc_root(fid)
                rel = self.doc_key_parts(self.nb)[1]
                if root:
                    cur = self.dnorm(os.path.join(root, *rel.split("/"))) if rel else self.dnorm(root)
                    self.notes = [n for n in self.notes if self.dnorm(os.path.dirname(n["path"])) == cur
                                  or self.dnorm(os.path.dirname(n["path"])).startswith(cur + os.sep)]
                else:
                    self.notes = []
        elif self.nb == CAL:             # 달력·할일: 노트 목록에는 달력 마크다운 파일들(달마다 한 개, 눌러서 열 수 있다)
            self.notes = [n for n in self.all_notes if n["nb"] == pm.MD_DIR]
        elif self.nb == TRASH:           # 휴지통: 지운 노트를 다른 노트북과 같은 목록으로(삭제까지 남은 날 표시)
            self.notes = self.store.trash_notes()
        elif self.scope_all():           # 모든 파일(저장된 검색 포함) = 내 노트 + 가져온 문서
            self.notes = list(self.all_notes) + self.docs.list_docs()
        else:
            self.notes = [n for n in self.all_notes if self.in_nb(n)]
        self.cur = next((n for n in self.notes if n["path"] == keep), None) if keep else None
        if keep and self.cur is None and self.doc_open:   # 보던 가져온 문서가 목록에서 사라졌으면 미리보기도 닫는다
            self.close_note()
        seen = getattr(self.store, "books_seen", None)
        self._books_once = seen[1] if seen and seen[0] is loaded else None   # 방금 이 목록과 함께 훑은 노트북들(다른 목록의 것이면 쓰지 않는다)
        try:
            self.reload_notebooks()
        finally:
            self._books_once = None
        self.reload_tags()
        self.refresh(keep_page=keep_scroll)

    def search_now(self, e=None):
        """검색 단추·Enter: 기다리지 않고 지금 검색(날짜 칸이 덜 쓰인 채여도 읽히는 만큼으로)"""
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.refresh()
        self.search_entry.focus_set()

    def open_advanced_search(self):
        top = tk.Toplevel(self.root)
        top.title(tr("고급 검색"))
        top.configure(bg=C["bg"])
        top.transient(self.root)
        top.resizable(False, False)
        top.geometry(f"700x310+{self.root.winfo_x() + 100}+{self.root.winfo_y() + 80}")
        tk.Label(top, text=tr("조건을 고르고 AND·OR·NOT으로 결합합니다. NOT은 앞 조건에 이어 제외합니다."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")

        old = {c.get("field"): c for c in self.adv_conditions if isinstance(c, dict)}
        known_tags = {t for n in self.all_notes for t in n["tags"]}
        known_tags.update(self.docs.tag_counts())
        no_tag_label = "◌ " + tr("태그 없음")
        tag_options = [no_tag_label] + ["#" + t for t in sorted(known_tags, key=str.lower)]
        folders = self.docs.folders()
        folder_labels = [f'{f.get("name") or f["path"]} ({f["path"]})' for f in folders]
        folder_by_label = dict(zip(folder_labels, (f["id"] for f in folders)))
        extensions = sorted({"md"} | {str(x).lower().lstrip(".") for x in self.docs.cfg().get("exts", []) if x})

        body = tk.Frame(top, bg=C["bg"], padx=16)
        body.pack(fill="both", expand=True)
        rows = []

        def add_row(field, label, value):
            previous = old.get(field, {})
            row = tk.Frame(body, bg=C["bg"])
            row.pack(fill="x", pady=3)
            enabled = tk.BooleanVar(value=field in old)
            tk.Checkbutton(row, text=tr(label), variable=enabled, bg=C["bg"], fg=C["text"], activebackground=C["bg"],
                           selectcolor=C["bg"], font=(self.ui, 9), width=15, anchor="w").pack(side="left")
            op = tk.StringVar(value=previous.get("op", "AND"))
            combo = ttk.Combobox(row, textvariable=op, values=("AND", "OR", "NOT"), width=6, state="readonly")
            combo.pack(side="left", padx=(0, 8))
            entry = None
            if field == "date":
                start = tk.StringVar(value=previous.get("from", ""))
                end = tk.StringVar(value=previous.get("to", ""))
                tk.Label(row, text=tr("시작"), bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
                tk.Entry(row, textvariable=start, width=13).pack(side="left", padx=(4, 10))
                tk.Label(row, text=tr("끝"), bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
                tk.Entry(row, textvariable=end, width=13).pack(side="left", padx=(4, 0))
                entry = (start, end)
            else:
                options = {"tag": tag_options, "folder": folder_labels, "extension": extensions}[field]
                entry = tk.StringVar()
                if field == "tag":
                    entry.set(no_tag_label if previous.get("untagged") else "#" + previous.get("value", "") if previous else "")
                elif field == "folder":
                    entry.set(next((name for name, fid in folder_by_label.items() if fid == previous.get("value")), ""))
                else:
                    entry.set(previous.get("value", ""))
                ttk.Combobox(row, textvariable=entry, values=options, width=42, state="readonly").pack(side="left", fill="x", expand=True)
            rows.append((field, enabled, op, entry))

        add_row("date", "기간", None)
        add_row("tag", "태그", None)
        add_row("folder", "가져온 폴더", None)
        add_row("extension", "확장자", None)

        def apply():
            conditions = []
            for field, enabled, op, value in rows:
                if not enabled.get():
                    continue
                cond = {"field": field}
                if field == "date":
                    start, end = (v.get().strip() for v in value)
                    if not start and not end:
                        return messagebox.showinfo(APP, tr("기간을 하나 이상 입력하세요."), parent=top)
                    if (start and search.parse_date(start) is None) or (end and search.parse_date(end, True) is None):
                        return messagebox.showerror(APP, tr("날짜 형식을 확인하세요. 예: 20240131"), parent=top)
                    cond.update({"from": start, "to": end})
                elif field == "tag":
                    selected = value.get()
                    if not selected:
                        return messagebox.showinfo(APP, tr("태그를 선택하세요."), parent=top)
                    if selected == no_tag_label:
                        cond["untagged"] = True
                    else:
                        cond["value"] = selected[1:] if selected.startswith("#") else selected
                elif field == "folder":
                    selected = value.get()
                    if selected not in folder_by_label:
                        return messagebox.showinfo(APP, tr("가져온 폴더를 선택하세요."), parent=top)
                    cond["value"] = folder_by_label[selected]
                else:
                    selected = value.get().strip().lower().lstrip(".")
                    if not selected:
                        return messagebox.showinfo(APP, tr("확장자를 선택하세요."), parent=top)
                    cond["value"] = selected
                cond["op"] = op.get()
                conditions.append(cond)
            self.adv_conditions = conditions
            top.destroy()
            self.refresh()

        buttons = tk.Frame(top, bg=C["bg"], padx=16, pady=12)
        buttons.pack(fill="x")
        Btn(buttons, tr("취소"), top.destroy, padx=14).pack(side="right", padx=(6, 0))
        Btn(buttons, tr("검색 적용"), apply, kind="primary", padx=14).pack(side="right")
        top.bind("<Escape>", lambda _e: top.destroy())
        top.grab_set()

    def schedule_search(self):
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.search_gen = getattr(self, "search_gen", 0) + 1   # 뒤에서 돌고 있는 이전 검색의 결과는 버린다
        self.search_job = self.root.after(180, self.search_bg)

    def search_index(self, pool):
        """지금 범위에서 검색에 쓸 색인(휴지통은 None: 메모리의 본문으로 찾는다)"""
        if self.nb == TRASH:
            return None
        if self.nb.startswith("@doc"):
            return self.docs
        # '문서 내부 검색'을 끄면 노트도 제목·태그에서만 찾는다(본문은 체크를 켰을 때만)
        notes_index = self.store if self.docs.content_search else search.TitleIndex([n for n in pool if not isinstance(n, docidx.Doc)])
        return docidx.Combined(notes_index, self.docs) if self.scope_all() else notes_index

    def hits_key(self, qtext):
        """색인 DB 를 훑는 검색(본문 검색)인지, 그렇다면 찾은 결과를 다시 써도 되는지 가리는 열쇠 → (검색식, 점수 여부, 범위 종류, 노트 목록).
        검색어가 없거나 색인을 훑지 않는 검색(휴지통, 제목만 찾기)이면 None"""
        q = search.split_date(qtext.strip())[0]
        node = search.parse(q) if q else None
        if node is None or self.nb == TRASH or not self.docs.content_search:
            return None
        kind = "docs" if self.nb.startswith("@doc") else "all" if self.scope_all() else "notes"
        return node, self.sort == "relevance", kind, id(self.all_notes)

    def search_bg(self):
        """입력 중 검색: 색인 훑기(본문 사본 전체를 읽어 0.2~0.5초 걸린다)를 뒤 쓰레드에서 하고, 끝나면 그 결과로 목록을 그린다.
        그동안 화면이 멈추지 않아 글자가 끊기지 않는다. 색인을 훑지 않는 검색은 바로 그린다."""
        self.search_job = None
        key = self.hits_key(self.q.get() + ime.composing())
        if key is None:
            return self.refresh()
        index = self.search_index(())
        node, scoring = key[0], key[1]
        words = search.positive_words(node)
        self.search_gen = gen = getattr(self, "search_gen", 0) + 1
        box = queue.Queue()

        def work():
            try:
                box.put(index.query_hits(node, words, scoring=scoring))
            except Exception:  # noqa: BLE001  (못 찾으면 화면 쓰레드에서 예전처럼 다시 찾는다)
                box.put(None)
        threading.Thread(target=work, daemon=True).start()

        def poll():
            if gen != self.search_gen:
                return                                # 그 사이 검색어가 바뀌었거나 다른 곳에서 목록을 다시 그렸다
            try:
                hits = box.get_nowait()
            except queue.Empty:
                return self.root.after(15, poll)
            self._hits_ready = (key, hits) if hits is not None else None
            try:
                self.refresh()
            finally:
                self._hits_ready = None
        self.root.after(15, poll)

    def refresh_saved(self):
        """자동 저장 뒤의 목록 갱신. 본문 검색 중이면 색인을 다시 훑지 않고 직전 검색 결과에서 방금 저장한 노트만 다시 맞춰 본다
        (저장할 때마다 본문 사본 전체를 훑으면 글을 쓰는 동안 화면이 계속 멈춘다)."""
        key = self.hits_key(self.q.get() + ime.composing())
        last = getattr(self, "_last_hits", None)
        n = self.cur
        if key is not None and last and last[0] == key and n and "key" in n and not isinstance(n, docidx.Doc):
            node, scoring, hits = key[0], key[1], last[1]
            body = n["body"]
            hay = (n["title"] + "\n" + (st.DATA_IMG.sub(" ", body) if "base64," in body else body)).lower()   # 색인에 넣는 글과 같은 모양
            if search.match(node, hay, n.get("tags", ())):
                ws = [w for w in search.positive_words(node) if w]
                hits[n["key"]] = 1000 * sum(hay.count(w) for w in ws) / max(1, len(hay)) if scoring else 0.0
            else:
                hits.pop(n["key"], None)
            self._hits_ready = (key, hits)
        try:
            self.refresh(keep_page=True)
        finally:
            self._hits_ready = None

    def refresh(self, keep_page=False):
        """검색·정렬을 다시 하고 목록을 그린다. keep_page=True 는 자동 저장 때처럼 보던 자리를 유지"""
        self.search_job = None
        self.search_gen = getattr(self, "search_gen", 0) + 1   # 뒤에서 돌고 있는 검색이 있으면 그 결과는 버린다
        if self.tag_none:
            pool = [n for n in self.notes if not n["tags"]]
        elif self.tag:
            pool = [n for n in self.notes if self.tag in n["tags"]]
        else:
            pool = self.notes
        if self.nb.startswith("@doc:"):
            fid, rel = self.doc_key_parts(self.nb)
            root = self.doc_root(fid)
            if root:
                cur = self.dnorm(os.path.join(root, *rel.split("/"))) if rel else self.dnorm(root)
                searching_docs = bool(self.q.get().strip() or self.d_from.get().strip() or self.d_to.get().strip()
                                      or self.tag or self.tag_none or self.adv_conditions)
                if searching_docs:
                    pool = [n for n in pool if self.dnorm(os.path.dirname(n["path"])) == cur
                            or self.dnorm(os.path.dirname(n["path"])).startswith(cur + os.sep)]
                else:
                    pool = [n for n in pool if self.dnorm(os.path.dirname(n["path"])) == cur]
        qtext = self.q.get() + ime.composing()   # 한글 입력기가 아직 확정하지 않은 마지막 글자도 검색에 넣는다(예: '로타' 의 '타')
        self.bad_dates = search.bad_dates(qtext, self.d_from.get(), self.d_to.get()) + search.bad_advanced_dates(self.adv_conditions)
        if self.bad_dates:   # 날짜를 읽을 수 없으면 기간 없이 찾지 말고 비워서 알린다
            self.results, self.words = [], []
        else:
            index = self.search_index(pool)
            key = self.hits_key(qtext) if index is not None else None
            if key is not None:   # 색인을 훑는 검색: 미리 찾아 둔 결과가 이 검색의 것이면 그것을 쓰고, 아니면 지금 찾아서 기억한다
                ready = getattr(self, "_hits_ready", None)
                index = search.HitsOnce(index, ready[1] if ready and ready[0] == key else None)
            self.results, self.words = search.run(pool, qtext, self.sort, self.asc, self.d_from.get(), self.d_to.get(), index=index)
            self._last_hits = (key, index.hits) if key is not None and index.hits is not None else None
            if self.adv_conditions:
                self.results = [n for n in self.results if search.advanced_match(n, self.adv_conditions, self.sort)]
        self.draw_list(keep_scroll=keep_page)

    @staticmethod
    def dnorm(path):
        return os.path.normcase(os.path.normpath(path))

    @staticmethod
    def doc_key_parts(key):
        """가져온 폴더 노드 키 → (등록 폴더 ID, 상대 하위 폴더 경로)."""
        fid, _, rel = key[5:].partition("/")
        return fid, rel

    def doc_root(self, fid):
        folder = next((f for f in self.docs.folders() if f["id"] == fid), None)
        return os.path.normpath(folder["path"]) if folder else None

    def update_folder_rows(self):
        """고른 노트북 바로 아래의 하위 노트북을 노트 목록 맨 위에 폴더 줄로 보인다(저장 폴더를 고르면 ScrapBook 같은 노트북들)"""
        box = self.folder_box
        kids = []
        if self.nb == "" or (self.nb and not self.nb.startswith("@") and self.nb != ALL):
            depth = self.nb.count("/") + 1 if self.nb else 0
            kids = [k for k in self.nb_keys if k and not k.startswith("@") and k != ALL and k.count("/") == depth
                    and (not self.nb or k.startswith(self.nb + "/")) and not (self.feat["outl"] and (k == OUTL or k.startswith(OUTL + "/")))]
        sig = (self.nb, tuple(kids), tuple(self.nb_direct.get(k, 0) for k in kids))
        if getattr(self, "_folder_sig", None) == sig:
            return
        self._folder_sig = sig
        for w in box.winfo_children():
            w.destroy()
        if not kids:
            box.pack_forget()
            return
        box.pack(fill="x", before=self.list_body, pady=(4, 2))
        for k in kids[:12]:
            n = sum(c for kk, c in self.nb_direct.items() if kk == k or kk.startswith(k + "/"))
            lb = tk.Label(box, text=f"📁  {self.nb_short(k)}", anchor="w", bg=C["bg"], fg=C["accent"], font=(self.ui, 10), padx=18, pady=3, cursor="hand2")
            lb.pack(fill="x", side="top")
            tk.Label(lb, text=f"{n:,}", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="right", padx=14)
            lb.bind("<Button-1>", lambda e, k=k: self.go_nb(k))
            lb.bind("<Enter>", lambda e, lb=lb: lb.config(bg=C["soft"]))
            lb.bind("<Leave>", lambda e, lb=lb: lb.config(bg=C["bg"]))
        if len(kids) > 12:
            tk.Label(box, text=tr('… 외 폴더 {0}개 (왼쪽 노트북 목록에서 고르세요)').format(len(kids) - 12), anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=18).pack(fill="x")

    def draw_list(self, keep_scroll=False):
        self.update_folder_rows()
        total = len(self.results)
        searching = self.q.get().strip() or self.d_from.get().strip() or self.d_to.get().strip() or self.tag or self.tag_none or self.adv_conditions
        unit = i18n.unit("파일") if self.scope_all() or self.nb.startswith("@doc") else i18n.unit("노트")
        text = tr('{0:,}개 중 {1:,}개 찾음').format(len(self.notes), total) if searching else tr('{0:,}개의 {1}').format(total, unit)
        if getattr(self, "bad_dates", None):
            text = tr("날짜를 읽을 수 없습니다: ") + ", ".join(self.bad_dates) + tr("  (예: date:20200202-20221231)")
        if self.tag:
            text += f"  ·  # {self.tag}"
        elif self.tag_none:
            text += "  ·  " + tr("태그 없음")
        if self.adv_conditions:
            text += "  ·  " + tr("고급 검색")
        self.count.config(text=text)
        L = self.lst
        if not keep_scroll:
            self.multi.clear()
        top = L.yview()[0] if keep_scroll else 0.0   # 자동 저장·삭제 때만 스크롤을 유지하고, 정렬·검색·노트북을 바꾸면 맨 위부터
        top_line = L.index("@0,0") if keep_scroll else None   # 목록이 줄어도 같은 자리에 머물도록 맨 위 줄로 되돌린다
        want = max(LIST_CHUNK, self.rendered) if keep_scroll else LIST_CHUNK
        self.sb_frozen = True
        L.config(state="normal")
        L.delete("1.0", "end")
        L.config(state="disabled")
        self.cards, self.card_starts, self.rendered, self.next_line = [], [], 0, 1
        self.append_cards(want)
        L.tk.call(L._w, "sync")   # Tk 가 줄 높이를 다 잰 뒤에 막대를 맞춘다(안 그러면 추정값으로 그렸다가 잠시 뒤 크기가 바뀌어 막대가 출렁인다)
        L.yview_moveto(top)
        if top_line:
            L.yview(top_line)
        self.sb_frozen = False
        self.lst_scroll(*L.yview())
        self.mark_selected()
        self.update_star()   # 폰에서 바꾼 즐겨찾기도 편집기의 별에 반영
        for k, b in self.sort_btns.items():
            arrow = ""
            if self.sort == k:   # 제목순은 기본이 가나다(오름차순)라서 화살표 뜻이 반대
                arrow = " ↑" if (self.asc != (k == "title")) else " ↓"
            b.config(text=self.sort_names[k] + arrow)
            b.set_on(self.sort == k)

    def append_cards(self, count=LIST_CHUNK):
        """검색 결과의 다음 count 개를 목록 아래에 이어 붙인다"""
        chunk = self.results[self.rendered:self.rendered + count]
        if not chunk:
            return
        L = self.lst
        first_line = self.next_line
        L.config(state="normal")
        for n in chunk:
            a = self.next_line
            L.insert("end", n["title"] + "\n", "title")
            shown_t = n.get("ctime", n["mtime"]) if self.sort == "ctime" else n["mtime"]   # 생성순이면 생성 시각을 보여 준다
            meta = time.strftime("%Y.%m.%d %H:%M", time.localtime(shown_t))
            if self.sort == "ctime" and n.get("created_known") is False:
                meta += " " + tr("(기준일)")
            if n.get("trash"):
                meta += "   " + (tr("삭제까지 %d일") % n["left"] if n["left"] is not None else tr("자동 삭제 안 함")) + "   ← " + n["orig"]
            elif self.scope_all() or n["nb"] != self.nb:   # 모든 노트이거나 하위 노트북의 노트면 어느 노트북인지 보여 준다
                meta += "   " + self.nb_label(n["nb"])
            if self.words:   # 검색 중일 때만 일치한 부분을 보여 준다
                L.insert("end", meta + "\n", "meta")
                if isinstance(n, docidx.Doc) and not self.docs.content_search:   # 본문을 찾지 않았으니 글 대신 경로를 보여 준다
                    L.insert("end", n["path"] + "\n", "snip")
                else:
                    snip, wkey = n.get("_snip"), tuple(self.words)
                    if not snip or snip[0] != wkey:   # 같은 검색어로 다시 그릴 때(자동 저장·이어 그리기) 파일을 또 읽지 않는다
                        snip = n["_snip"] = (wkey, search.snippet(n.read(), self.words))
                    L.insert("end", snip[1] + "\n", "snip")
                lines = 3
            else:            # 평소에는 제목과 날짜만
                L.insert("end", meta + "\n", ("meta", "pad"))
                lines = 2
            L.insert("end", "\n", "sep")
            b = a + lines - 1
            self.cards.append((a, b, n))
            self.card_starts.append(a)
            self.next_line = b + 2
        self.rendered += len(chunk)
        for w in self.words:   # 방금 붙인 부분에서만 검색어를 강조
            if not w:
                continue
            pos = f"{first_line}.0"
            while True:
                pos = L.search(w, pos, "end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(w)}c"
                L.tag_add("hl", pos, end)
                pos = end
        L.config(state="disabled")

    def more_cards(self):
        """스크롤이 목록 끝에 가까워지면 다음 노트들을 이어서 그린다"""
        L = self.lst
        grew = False
        for _ in range(20):   # 아래에 남은 글이 MORE_SCREENS 화면보다 적으면 그만큼 채울 때까지 이어 그린다
            lo, hi = L.yview()
            if self.rendered >= len(self.results) or (1 - hi) >= MORE_SCREENS * (hi - lo):
                break
            # 지금까지 그린 만큼을 한 번에 더 붙여서(핸들이 적어도 중간까지 올라오게), 검색 중에는 본문을 읽으니 적게
            self.append_cards(max(LIST_CHUNK * 2, min(self.rendered, MORE_MAX_SEARCH if self.words else MORE_MAX)))
            grew = True
            L.update_idletasks()   # 늘어난 길이로 스크롤 위치(yview)를 다시 계산
        if grew:
            self.mark_selected()

    def mark_selected(self):
        L = self.lst
        L.tag_remove("selcard", "1.0", "end")
        if self.multi:   # 여러 개를 골랐으면 고른 것 모두
            for a, b, n in self.cards:
                if n["path"] in self.multi:
                    L.tag_add("selcard", f"{a}.0", f"{b + 1}.0")
        elif self.cur:
            for a, b, n in self.cards:
                if n["path"] == self.cur["path"]:
                    L.tag_add("selcard", f"{a}.0", f"{b + 1}.0")
                    break

    def clear_multi(self):
        if self.multi:
            self.multi.clear()
            self.mark_selected()
            self.status.config(text="")

    def pick_multi(self, items):
        """items: 고른 노트들. 한 개 이하면 다중 선택을 끝낸다. 가져온 문서는 이동·삭제 대상이 아니라서 뺀다"""
        items = [n for n in items if not isinstance(n, docidx.Doc)]
        self.multi = {n["path"]: n for n in items} if len(items) > 1 else {}
        self.mark_selected()
        self.status.config(text=tr('노트 {0}개 선택됨 (우클릭: 휴지통·이동, Esc: 해제)').format(len(self.multi)) if self.multi else "")

    def select_range(self, n):
        """Shift+클릭: 시작 노트(anchor)부터 클릭한 노트까지 모두 고른다"""
        start = self.anchor or (self.cur["path"] if self.cur else None)
        order = [c[2] for c in self.cards]
        paths = [x["path"] for x in order]
        if start not in paths:
            self.anchor = n["path"]
            return self.pick_multi([n])
        i, j = paths.index(start), paths.index(n["path"])
        self.pick_multi(order[min(i, j):max(i, j) + 1])

    def toggle_multi(self, n):
        """Ctrl+클릭: 이 노트를 고른 목록에 넣거나 뺀다"""
        cur = dict(self.multi) if self.multi else ({self.cur["path"]: self.cur} if self.cur else {})
        if n["path"] in cur:
            del cur[n["path"]]
        else:
            cur[n["path"]] = n
        self.anchor = n["path"]
        self.pick_multi(list(cur.values()))

    def trash_multi(self):
        items = list(self.multi.values())
        if not items or not messagebox.askyesno(APP, tr('고른 노트 {0}개를 휴지통으로 보낼까요?\n({1}일 동안 보관하며 복원할 수 있습니다)').format(len(items), self.store.trash_days), parent=self.root):
            return
        self.multi.clear()
        self.trash_notes([n["path"] for n in items])

    def move_multi(self, nb):
        items = list(self.multi.values())
        self.flush()
        cur_path = self.cur["path"] if self.cur else None
        fail = 0
        for n in items:
            try:
                self.fav_move(n["path"], self.store.move(n["path"], nb))
            except OSError:
                fail += 1
        self.multi.clear()
        if cur_path in {n["path"] for n in items}:
            self.cur = None
        self.reload_notes()
        if fail:
            messagebox.showerror(APP, tr('{0}개 노트를 옮기지 못했습니다.').format(fail), parent=self.root)

    def card_at(self, e):
        line = int(self.lst.index(f"@{e.x},{e.y}").split(".")[0])
        i = bisect.bisect_right(self.card_starts, line) - 1
        if i >= 0 and line <= self.cards[i][1]:
            return self.cards[i][2]
        return None

    def on_list_click(self, e):
        n = self.card_at(e)
        if n and self.nb == CAL and self.feat["cal"] and not self.cur and self.planner_view is not None:
            m = pm.MONTH_RE.match(os.path.basename(n["path"]))
            if m:                                   # 달력·할일에는 마크다운·좌우 분할 보기가 없다: 달력만 그 달로 간다
                self.planner_view.goto_month(int(m.group(1)), int(m.group(2)))
            return "break"
        if isinstance(n, docidx.Doc):   # 가져온 파일은 여러 개 고르기·이동·삭제가 없다: 그냥 연다
            self.anchor = n["path"]
            self.clear_multi()
            self.open_note(n)
        elif n and e.state & 0x1:       # Shift+클릭: 범위 선택(노트는 열지 않는다)
            self.select_range(n)
        elif n and e.state & 0x4:     # Ctrl+클릭: 하나씩 넣고 빼기
            self.toggle_multi(n)
        elif n:
            self.anchor = n["path"]
            self.clear_multi()
            self.open_note(n)
        # 클릭하면 키보드(PageUp/PageDown)가 목록에 먹히게. 노트를 여는 동안 옮겨 간 포커스를 되찾는다.
        self.lst.focus_set()
        self.root.after_idle(self.lst.focus_set)
        return "break"

    def on_list_double(self, e):
        """가져온 파일을 더블클릭하면 그 파일의 기본 프로그램으로 연다(노트는 Text 의 기본 글자 선택을 막기만 한다)"""
        n = self.card_at(e)
        if isinstance(n, docidx.Doc):
            self.open_doc_file(n)
        return "break"

    def open_with_program(self, ext):
        """확장자에 지정해 둔 연결 프로그램 경로(없거나 파일이 없어졌으면 None). 옵션에 따로 두지 않고 우클릭으로 지정한다."""
        exe = (st.read_config().get("openWith") or {}).get(ext.lower().lstrip("."))
        return exe if isinstance(exe, str) and os.path.isfile(exe) else None

    def set_open_with(self, ext, exe):
        table = dict(st.read_config().get("openWith") or {})
        key = ext.lower().lstrip(".")
        if exe:
            table[key] = exe
        else:
            table.pop(key, None)
        st.write_config(openWith=table)

    def pick_open_with(self, n):
        ext = n["ext"]
        exe = filedialog.askopenfilename(parent=self.root, title=tr('.{0} 파일을 열 프로그램 고르기').format(ext),
                                         filetypes=[(tr("프로그램"), "*.exe"), (tr("모든 파일"), "*.*")])
        if exe:
            self.set_open_with(ext, os.path.normpath(exe))

    def open_doc_file(self, n):
        exe = self.open_with_program(n["ext"])
        try:
            if exe:   # 사용자가 이 확장자에 지정한 프로그램(예: zip → 만화 뷰어). 셸을 거치지 않고 경로를 인자로만 넘긴다
                paths = [os.path.normpath(n["path"])]
                # WaterView/NeeView 같은 미디어 뷰어는 여러 경로를 한 번에
                # 넘기면 재생목록으로 연다. 가져온 파일을 한 곡씩 여는 대신
                # 같은 폴더의 오디오·동영상만 모아 현재 파일부터 재생한다.
                media_exts = set(docidx.AUDIO_EXT) | {"mp4", "webm", "ogv", "mov", "avi", "mkv"}
                if n.get("ext", "").lower() in media_exts:
                    folder = os.path.dirname(os.path.normpath(n["path"]))
                    try:
                        siblings = []
                        for item in os.scandir(folder):
                            if item.is_file() and os.path.splitext(item.name)[1].lower().lstrip(".") in media_exts:
                                siblings.append(os.path.normpath(item.path))
                        current = paths[0].casefold()
                        paths += sorted((p for p in siblings if p.casefold() != current), key=str.casefold)
                    except OSError:
                        pass
                # WaterView/NeeView는 --slideshow on으로 파일 종료 후 다음
                # 항목으로 자동 진행한다. 다른 연결 프로그램에는 옵션을
                # 넘기지 않는다.
                viewer = os.path.basename(exe).lower()
                launch = [exe]
                if viewer in {"waterview.exe", "neeview.exe"} and len(paths) > 1:
                    launch += ["--slideshow", "on"]
                subprocess.Popen([*launch, *paths])
            else:
                os.startfile(n["path"])
        except OSError as ex:
            messagebox.showerror(APP, tr('파일을 열지 못했습니다.\n{0}').format(ex), parent=self.root)

    def doc_menu(self, e, n):
        self.open_note(n)
        lm = self.listmenu
        lm.delete(0, "end")
        lm.add_command(label=tr("연결 프로그램으로 열기") if self.open_with_program(n["ext"]) else tr("기본 프로그램으로 열기"), command=lambda: self.open_doc_file(n))
        lm.add_command(label=tr('.{0} 파일을 열 프로그램 지정…').format(n["ext"]), command=lambda: self.pick_open_with(n))
        if self.open_with_program(n["ext"]):
            lm.add_command(label=tr('.{0} 연결 해제 (윈도 기본 프로그램으로)').format(n["ext"]), command=lambda: self.set_open_with(n["ext"], None))
        lm.add_command(label=tr("태그 추가·고치기…"), command=self.edit_tags)
        lm.add_command(label=tr("메모…"), command=self.edit_memo)
        lm.add_separator()
        lm.add_command(label=tr("파일 위치 열기"), command=lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(n["path"])]))
        lm.add_command(label=tr("경로 복사"), command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(n["path"])))
        lm.tk_popup(e.x_root, e.y_root)
        return "break"
