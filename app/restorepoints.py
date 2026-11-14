"""복원 지점(노트 폴더의 복원 지점을 만들고 되돌리는) 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class RestorePointMixin:
    # ------------------------------------------------------------ 복원 지점
    def snap_cfg(self):
        c = st.read_config()
        return {"auto": bool(c.get("snap_auto", True)), "count": max(1, int(c.get("snap_count", sn.KEEP_COUNT))),
                "days": max(0, int(c.get("snap_days", sn.KEEP_DAYS)))}

    def checkpoint(self, label, then):
        """큰 작업 직전에 복원 지점을 만들고(바뀐 게 없으면 바로) then() 을 부른다. 취소하면 then 은 부르지 않는다."""
        self.run_task(tr("복원 지점 만드는 중"), lambda prog, cancel: self.snap.create(label, prog, cancel), lambda pid: then(),
                      text=tr('"{0}" 복원 지점을 만드는 중… (처음 한 번은 오래 걸립니다)').format(label))

    def auto_snapshot(self):
        """시작한 뒤 한참 있다가: 마지막 복원 지점이 하루 넘었으면 조용히 하나 만들고 오래된 것을 정리한다"""
        cfg = self.snap_cfg()
        if not cfg["auto"]:
            return
        pts = self.snap.points()
        if pts and time.time() - pts[0]["created"] < 20 * 3600:
            return
        q = queue.Queue()

        def job():
            try:
                self.snap.create(tr("자동"))
                self.snap.prune(cfg["count"], cfg["days"])
                q.put("ok")
            except Exception as ex:  # noqa: BLE001
                q.put("err")
        threading.Thread(target=job, daemon=True).start()

        def poll():
            try:
                r = q.get_nowait()
            except queue.Empty:
                return self.root.after(1000, poll)
            if r == "ok":
                self.status.config(text=tr("복원 지점을 만들었습니다."))
        poll()

    def trash_notes(self, paths):
        """휴지통으로 보내고 목록을 새로 읽는다 → 보낸 개수"""
        cur_path = self.cur["path"] if self.cur else None
        if cur_path in paths:
            if self.save_job:
                self.root.after_cancel(self.save_job)
                self.save_job = None
            self.dirty = False
            self.close_note()
        else:
            self.flush()
        done = 0
        for p in paths:
            try:
                self.store.delete_note(p)
                done += 1
            except OSError:
                pass
        self.multi.clear()
        self.reload_notes(keep_scroll=True)   # 지운 뒤에도 보던 자리를 유지
        return done

    def go_nb(self, key):
        """노트북 목록의 항목(휴지통 등)으로 옮겨 간다"""
        self.flush()
        self.nb = key
        self.close_note()
        self.reload_notes()

    def show_duplicates(self):
        """도구 > 중복 노트 찾기: 같은 원본 주소 · 같은 본문 · 같은 제목에 비슷한 본문을 묶어 보여 주고, 골라서 휴지통으로"""
        self.scan_notes(tr("중복 노트 찾기"), lambda notes, prog, cancel: cleanup.find_duplicates(notes, prog, cancel), self.duplicates_dialog)

    def show_similar(self):
        """편집 > 비슷한 노트 찾기: 열어 둔 노트와 쓰인 낱말이 비슷한 노트를 색인된 본문에서 찾아 보여 준다(See Also)"""
        if not self.cur or self.doc_open:
            return messagebox.showinfo(APP, tr("먼저 노트를 여세요.") if not self.cur else tr("가져온 파일은 아직 지원하지 않습니다(노트만)."), parent=self.root)
        self.flush()
        n = self.cur
        key, body = self.store.key_of(n["path"]), n["body"]

        def done(res):
            top = self.tool_window(tr("비슷한 노트 — ") + n["title"], "700x520")
            if not res:
                tk.Label(top, text=tr("비슷한 노트를 찾지 못했습니다(글이 너무 짧거나 흔한 낱말뿐일 수 있습니다)."), bg=C["bg"], fg=C["muted"],
                         font=(self.ui, 10), padx=16, pady=20).pack(fill="x")
                return
            tk.Label(top, text=tr("열어 둔 노트에서 자주 나오면서 흔하지 않은 낱말을 다른 노트 본문에서 찾은 결과입니다. 더블클릭하면 그 노트를 엽니다."),
                     bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")
            wrap = tk.Frame(top, bg=C["bg"])
            wrap.pack(fill="both", expand=True, padx=16, pady=(0, 12))
            tv = ttk.Treeview(wrap, columns=("title", "nb", "hit"), show="headings", selectmode="browse")
            for col, text, w, stretch in (("title", tr("노트"), 380, True), ("nb", tr("노트북"), 170, False), ("hit", tr("겹친 낱말"), 90, False)):
                tv.heading(col, text=text)
                tv.column(col, width=w, stretch=stretch, anchor="e" if col == "hit" else "w")
            sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
            tv.config(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            tv.pack(side="left", fill="both", expand=True)
            by_key = {x["key"]: x for x in self.all_notes}
            for k, hit, tot in res:
                m = by_key.get(k)
                if m:
                    tv.insert("", "end", iid=k, values=(m["title"], self.nb_label(m["nb"]), f"{hit}/{tot}"))

            def open_sel(e=None):
                sel = tv.selection()
                if sel and sel[0] in by_key:
                    self.open_note(by_key[sel[0]])
            tv.bind("<Double-1>", open_sel)
            tv.bind("<Return>", open_sel)
        self.run_task(tr("비슷한 노트 찾기"), lambda prog, cancel: similar.find(self.store, key, body, 40, prog, cancel), done, text=tr("비슷한 노트를 찾는 중…"))

    def show_unused_media(self):
        """도구 > 안 쓰는 미디어 파일 정리: 어떤 노트도 가리키지 않는 그림·첨부를 찾아 한꺼번에 휴지통으로"""
        self.scan_notes(tr("안 쓰는 미디어 파일 찾기"), lambda notes, prog, cancel: cleanup.unused_media(self.store, notes, prog, cancel), self.unused_media_dialog)

    def unused_media_dialog(self, found):
        if not found:
            return messagebox.showinfo(APP, tr("안 쓰는 미디어 파일이 없습니다."), parent=self.root)
        total = sum(s for _, s in found)
        top = self.tool_window(tr('안 쓰는 미디어 파일 — {0:,}개').format(len(found)), "760x520", native=True)

        def mb(n):
            return f"{n / 1048576:,.1f}MB" if n >= 1048576 else f"{n / 1024:,.0f}KB"
        tk.Label(top, text=tr('어떤 노트도 가리키지 않는 파일 {0:,}개 ({1}). 휴지통으로 보내면 {2}일 동안 복원할 수 있습니다.\n(노트의 이전 버전 기록이 가리키는 그림은 확인하지 않으므로, 오래된 버전으로 되돌릴 때 그림이 빠질 수 있습니다.)').format(len(found), mb(total), self.store.trash_days),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        lb = tk.Listbox(wrap, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", selectmode="extended",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=lb.xview)
        lb.config(yscrollcommand=autohide(sb, lb), xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        lb.pack(side="left", fill="both", expand=True)
        for p, s in found:
            lb.insert("end", f"{os.path.relpath(p, self.store.media_dir)}   {mb(s)}")

        def open_sel(e=None):
            sel = lb.curselection()
            if sel:
                self.reveal_file(found[sel[0]][0])

        def trash(items):
            if not items:
                return messagebox.showinfo(APP, tr("먼저 파일을 고르세요."), parent=top)
            if not messagebox.askyesno(APP, tr('{0:,}개 파일을 휴지통으로 보낼까요?').format(len(items)), parent=top):
                return
            try:
                n = self.store.trash_files([p for p, _ in items], self.store.media_dir)
            except OSError as ex:
                return messagebox.showerror(APP, str(ex), parent=top)
            top.destroy()
            messagebox.showinfo(APP, tr('{0:,}개 파일을 휴지통으로 보냈습니다. (파일 → 휴지통에서 복원)').format(n), parent=self.root)
        def open_one(e=None):   # 파일 하나를 누르면 그 파일을 연다(그림·영상 등 보는 파일만. 나머지는 폴더에서 위치만 보여 준다)
            sel = lb.curselection()
            if len(sel) != 1:
                return
            p = found[sel[0]][0]
            if sys.platform == "win32" and os.path.splitext(p)[1].lower() in VIEWABLE:
                os.startfile(p)
            else:
                self.reveal_file(p)
        lb.bind("<<ListboxSelect>>", open_one)
        Btn(btns, tr("모두 휴지통으로"), lambda: trash(list(found)), kind="danger", padx=12, pady=3).pack(side="right")

        menu = tk.Menu(top, tearoff=0)

        def on_menu(e):   # 우클릭: 누른 줄이 고른 줄 안이 아니면 그 줄만 고르고, 열기·위치 열기·휴지통 메뉴를 띄운다
            i = lb.nearest(e.y)
            if 0 <= i < lb.size() and i not in lb.curselection():
                lb.selection_clear(0, "end")
                lb.selection_set(i)
            sel = list(lb.curselection())
            one = len(sel) == 1
            menu.delete(0, "end")
            menu.add_command(label=tr("파일 열기"), command=open_one, state="normal" if one else "disabled")
            menu.add_command(label=tr("파일 위치 열기"), command=open_sel, state="normal" if sel else "disabled")
            menu.add_command(label=tr('휴지통으로 보내기 ({0}개)').format(len(sel)) if len(sel) > 1 else tr("휴지통으로 보내기"),
                             command=lambda: trash([found[k] for k in lb.curselection()]), state="normal" if sel else "disabled")
            menu.tk_popup(e.x_root, e.y_root)
        lb.bind("<Button-3>", on_menu)

    def show_cleanup(self):
        """도구 > 스크랩 군더더기 정리: 노트마다 지울 줄을 미리 보여 주고, 골라서 적용(적용 전 내용은 노트 버전으로 남는다)"""
        self.cleanup_options()

    def cleanup_cfg(self):
        c = st.read_config().get("cleanup", {})
        try:
            ratio = min(100, max(5, int(c.get("ratio", round(cleanup.DEFAULT_RATIO * 100)))))
            docs = min(200, max(2, int(c.get("min_docs", cleanup.DEFAULT_MIN_DOCS))))
        except (TypeError, ValueError):
            ratio, docs = round(cleanup.DEFAULT_RATIO * 100), cleanup.DEFAULT_MIN_DOCS
        return {"ratio": ratio, "min_docs": docs, "keep": [k for k in c.get("keep", []) if isinstance(k, str)]}

    def cleanup_options(self):
        """군더더기 찾기 전에 기준을 고른다: 사이트 공통 줄로 볼 비율·최소 노트 수, 지우지 않기로 한 줄 목록"""
        cfg = self.cleanup_cfg()
        top = self.tool_window(tr("스크랩 군더더기 정리 — 기준"), "560x470", native=True)
        tk.Label(top, text=tr("같은 사이트에서 스크랩한 노트 여럿에 똑같이 나오는 줄(메뉴·머리글·바닥글)을 군더더기로 봅니다. 기준을 높이면 덜 지우고, 낮추면 더 지웁니다.\n"
                           "찾은 뒤 미리 보기에서 지우기 싫은 줄을 오른쪽 클릭해 \"이 줄은 지우지 않기\" 를 고르면 아래 목록에 쌓입니다."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", wraplength=520, padx=16, pady=10).pack(fill="x")
        f = tk.Frame(top, bg=C["bg"])
        f.pack(fill="x", padx=16)
        ratio = tk.IntVar(value=cfg["ratio"])
        docs = tk.IntVar(value=cfg["min_docs"])
        tk.Label(f, text=tr("사이트 노트의"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=0, column=0, sticky="w")
        tk.Spinbox(f, from_=5, to=100, increment=5, width=4, textvariable=ratio, font=(self.ui, 10)).grid(row=0, column=1, padx=4)
        tk.Label(f, text=tr("% 이상에 나오는 줄 (기본 30)"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=0, column=2, sticky="w")
        tk.Label(f, text=tr("그리고 최소"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=1, column=0, sticky="w", pady=6)
        tk.Spinbox(f, from_=2, to=200, width=4, textvariable=docs, font=(self.ui, 10)).grid(row=1, column=1, padx=4)
        tk.Label(f, text=tr("개 노트에 나와야 함 (기본 4)"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=1, column=2, sticky="w")
        tk.Label(top, text=tr("지우지 않기로 한 줄"), bg=C["bg"], fg=C["text"], font=(self.ui, 10, "bold"), anchor="w", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["panel"])
        wrap.pack(fill="both", expand=True, padx=16)
        lb = tk.Listbox(wrap, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", selectmode="extended",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        lb.pack(fill="both", expand=True, padx=6, pady=6)
        keep = list(cfg["keep"])
        for k in keep:
            lb.insert("end", k)

        def drop():
            for i in reversed(lb.curselection()):
                lb.delete(i)
                del keep[i]

        def save():
            try:
                r, d = int(ratio.get()), int(docs.get())
            except (tk.TclError, ValueError):
                r, d = cfg["ratio"], cfg["min_docs"]
            c = {"ratio": min(100, max(5, r)), "min_docs": min(200, max(2, d)), "keep": keep}
            st.write_config(cleanup=c)
            return c

        def go():
            c = save()
            top.destroy()
            self.cleanup_scan(c)
        Btn(btns, tr("군더더기 찾기"), go, kind="primary", bold=True, padx=16).pack(side="right")
        Btn(btns, tr("닫기"), lambda: (save(), top.destroy()), padx=14).pack(side="right", padx=6)
        Btn(btns, tr("고른 줄 목록에서 빼기"), drop, padx=12).pack(side="left")

    def cleanup_scan(self, c):
        opts = {"ratio": c["ratio"] / 100, "min_docs": c["min_docs"], "keep": c["keep"]}
        self.scan_notes(tr("스크랩 군더더기 찾기"), lambda notes, prog, cancel: cleanup.scan_junk(notes, prog, cancel, opts), self.cleanup_dialog)

    def check_update(self):
        """GitHub 의 최신 릴리스를 확인하고, 새 버전이면 내려받아 exe 를 바꾸고 다시 시작한다(소스로 실행 중이면 릴리스 페이지만 안내)"""
        self.run_task(tr("업데이트 확인"), lambda prog, cancel: updater.latest(), self.update_found, text=tr("최신 버전을 확인하는 중…"))

    def update_found(self, rel):
        if not updater.is_newer(rel["tag"], VERSION):
            return messagebox.showinfo(APP, tr('최신 버전입니다.\n현재 {0}, 최신 릴리스 {1}').format(VERSION, rel['tag']), parent=self.root)
        news = updater.whats_new(rel["body"])
        head = tr('새 버전 {0} 이 나왔습니다. (현재 {1})\n\n{2}\n\n').format(rel['tag'], VERSION, news)
        if not (ed.FROZEN and rel["asset_url"] and rel["sha"]):   # 소스로 실행 중이거나 자동으로 바꿀 파일이 없으면 페이지만
            why = tr("소스로 실행 중이라 자동으로 바꾸지 않습니다. ") if not ed.FROZEN else ""
            if messagebox.askyesno(APP, head + why + tr("릴리스 페이지를 열까요?"), parent=self.root):
                webbrowser.open(rel["url"])
            return
        ans = messagebox.askyesnocancel(
            APP, head + tr("예: 지금 업데이트(내려받아 바꾸고 자동으로 다시 시작)\n아니오: 릴리스 페이지 열기\n취소: 나중에"), parent=self.root)
        if ans is None:
            return
        if not ans:
            return webbrowser.open(rel["url"])
        self.run_task(tr("업데이트 내려받기"), lambda prog, cancel: updater.download(rel, prog, cancel), self.update_downloaded,
                      text=tr('{0} 을 내려받는 중… (KB)').format(rel['tag']))

    def update_downloaded(self, path):
        if not path:
            return
        self.flush()
        try:
            updater.apply(path)
        except OSError as ex:
            return messagebox.showerror(APP, tr('업데이트를 시작하지 못했습니다.\n{0}').format(ex), parent=self.root)
        self.quit()   # 앱이 끝나야 실행 파일이 풀려서 바뀐다. 바뀐 뒤 새 버전이 자동으로 다시 시작된다.

    MANUAL_URL = "https://github.com/iamtalker/iamtalkernote/blob/main/docs/manual.md"

    ANDROID_URL = "https://github.com/iamtalker/iamtalkernote-android/releases/latest"   # 폰 앱(APK) 최신 릴리스
    BOOK_URL = "https://bookk.co.kr/bookStore/6af3769e04f230844ed9303c"   # 도움말 → 책 소개(작가의 책 페이지)

    def open_manual(self):
        """도움말 → 사용 설명서(F1): GitHub 의 설명서 문서를 기본 브라우저로 연다"""
        webbrowser.open(self.MANUAL_URL)

    def help_search(self):
        messagebox.showinfo(tr("검색 문법"), tr("공백 = AND\n회의록 AND (예산 OR 일정) NOT 취소\n\"정확한 구절\"\n"
                            "& | ! 기호도 AND OR NOT 으로 쓸 수 있습니다(대문자만 연산자로 인식).\n\n"
                            "기간: date:20101011-20240104 만화&아이유  → 그 기간에 고친(생성순이면 만든) 글 중 만화와 아이유가 함께 든 글\n"
                            "   date:20240101(그 날) · date:202401(그 달) · date:2024(그 해) · date:20240101-(그날부터) · date:-20240104(그날까지)\n"
                            "   날짜:·기간: 으로 써도 됩니다. 아래 '기간' 칸과 함께 쓰면 겹치는 부분만 찾습니다.\n\n"
                            "태그는 본문의 #태그, 또는 '태그: a, b' 줄에서 모읍니다."), parent=self.root)

    def text_do(self, name):
        try:
            getattr(self.text, name)()
        except tk.TclError:
            pass

    def focus_search(self):
        if not self.show["list"]:
            self.v["list"].set(True)
            self.on_view_toggle()
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def insert_datetime(self):
        if self.cur:
            self.text.insert("insert", time.strftime("%Y-%m-%d %H:%M"))
            self.text.focus_set()
