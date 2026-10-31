"""큰 대화창들(옵션·휴지통·복원 지점·변경 이력·속성·이전 버전·정리·중복 찾기): App 에서 그대로 옮겨 온 메서드 묶음(동작 변경 없음).
App 이 DialogsMixin 을 물려받아 self.show_options() 처럼 그대로 부른다."""
from notes_shared import *  # noqa: F401,F403


class DialogsMixin:
    def show_snapshots(self):
        """파일 > 복원 지점: 어느 시점의 모든 노트를 기억해 두었다가 그 상태로 되돌린다"""
        top = self.tool_window("복원 지점", "800x520")
        tk.Label(top, text="복원 지점은 그 시점의 노트 목록을 기억해 두고, 앱이 노트를 바꾸기 직전에 바뀌기 전 내용만 따로 보관합니다(그림·첨부는 아래 옵션을 켠 뒤에 만든 지점에만 넣습니다). 고르면 노트를 그 시점으로 되돌리고, 그 뒤에 새로 생긴 노트는 휴지통으로 보냅니다. 앱 밖에서 고친 노트는 되돌릴 수 없어 건드리지 않습니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", wraplength=760, padx=16, pady=10).pack(fill="x")
        cfgrow = tk.Frame(top, bg=C["bg"])
        cfgrow.pack(side="bottom", fill="x", padx=16, pady=(0, 6))
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=10)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        tv = ttk.Treeview(wrap, columns=("when", "label", "count"), show="headings", selectmode="browse")
        for col, text, w, anc in (("when", "시각", 170, "w"), ("label", "이름", 300, "w"), ("count", "노트 수", 90, "e")):
            tv.heading(col, text=text)
            tv.column(col, width=w, anchor=anc, stretch=col == "label")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        info = tk.Label(cfgrow, text="", bg=C["bg"], fg=C["muted"], font=(self.ui, 9))
        cfg = self.snap_cfg()
        auto_var, cnt_var, day_var = tk.BooleanVar(value=cfg["auto"]), tk.StringVar(value=str(cfg["count"])), tk.StringVar(value=str(cfg["days"]))

        def refresh():
            tv.delete(*tv.get_children())
            pts = self.snap.points()
            for p in pts:
                tv.insert("", "end", iid=p["id"], values=(time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(p["created"])), p["label"] or "수동", f"{p['count']:,}"))
            mb = self.snap.usage() / 1048576
            info.config(text=f"지점 {len(pts)}개 · 보관 중인 내용 {mb:,.1f}MB")

        media_var = tk.BooleanVar(value=bool(st.read_config().get("snap_media", False)))

        def save_cfg(*_):
            try:
                st.write_config(snap_media=media_var.get(), snap_auto=auto_var.get(), snap_count=max(1, int(cnt_var.get())), snap_days=max(0, int(day_var.get())))
            except ValueError:
                pass

        def make():
            self.run_task("복원 지점 만드는 중", lambda prog, cancel: self.snap.create("수동", prog, cancel, force=True),
                          lambda pid: refresh(), text="복원 지점을 만드는 중… (처음 한 번은 오래 걸립니다)")

        def restore():
            sel = tv.selection()
            if not sel:
                return messagebox.showinfo(APP, "되돌릴 복원 지점을 먼저 고르세요.", parent=top)
            pid = sel[0]

            def after_diff(d):
                if not (d["change"] or d["add"] or d["remove"] or d["lost"]):
                    return messagebox.showinfo(APP, "지금 노트가 이 복원 지점과 같습니다.", parent=top)
                if not messagebox.askyesno(APP, f"이 시점으로 되돌릴까요?\n\n  내용을 되돌릴 노트  {len(d['change']):,}개\n  지워졌던 것을 되살릴 노트  {len(d['add']):,}개\n"
                                                 f"  그 뒤에 생긴 노트(휴지통으로 보냄)  {len(d['remove']):,}개\n"
                                                 + (f"  앱 밖에서 고쳐서 되돌릴 수 없는 노트(그대로 둠)  {len(d['lost']):,}개\n" if d["lost"] else "")
                                                 + "\n되돌리기 직전 상태도 복원 지점으로 남기므로 다시 돌아올 수 있습니다.", parent=top):
                    return
                self.flush()

                def go():
                    def done(res):
                        self.close_note()
                        self.reload_notes()
                        refresh()
                        messagebox.showinfo(APP, "되돌렸습니다.\n" + f"내용 {res[0]:,}개 · 되살림 {res[1]:,}개 · 휴지통 {res[2]:,}개"
                                            + (f"\n되돌릴 수 없어 그대로 둔 노트 {res[3]:,}개" if res[3] else ""), parent=top)
                    self.run_task("복원 중", lambda prog, cancel: self.snap.restore(pid, prog, cancel), done, text="노트를 되돌리는 중…")
                self.checkpoint("복원 직전", go)
            self.run_task("비교 중", lambda prog, cancel: self.snap.diff(pid, prog, cancel), after_diff, text="지금 노트와 비교하는 중…")

        def delete():
            sel = tv.selection()
            if sel and messagebox.askyesno(APP, "이 복원 지점을 지울까요?", parent=top):
                self.snap.delete(sel[0])
                refresh()

        def prune():
            c = self.snap_cfg()
            n = self.snap.prune(c["count"], c["days"])
            refresh()
            messagebox.showinfo(APP, f"{n}개를 정리했습니다." if n else "정리할 지점이 없습니다.", parent=top)
        Btn(btns, "지금 복원 지점 만들기", make, padx=12, pady=3).pack(side="left")
        Btn(btns, "이 지점으로 되돌리기", restore, kind="primary", padx=12, pady=3).pack(side="left", padx=6)
        Btn(btns, "지우기", delete, kind="danger", padx=12, pady=3).pack(side="right")
        Btn(btns, "오래된 것 정리", prune, padx=12, pady=3).pack(side="right", padx=6)
        tk.Checkbutton(btns, text="그림·첨부도 포함(앞으로 만드는 지점부터. 용량이 커질 수 있음)", variable=media_var, command=save_cfg, bg=C["bg"], activebackground=C["bg"], font=(self.ui, 9)).pack(side="left", padx=10)
        tk.Checkbutton(cfgrow, text="하루에 한 번 자동으로 만들기", variable=auto_var, command=save_cfg, bg=C["bg"], activebackground=C["bg"], font=(self.ui, 9)).pack(side="left")
        for label, var, hi in (("  보관: 최근", cnt_var, 500), ("개 이거나", None, 0), ("", day_var, 3650)):
            if var is None:
                tk.Label(cfgrow, text=label, bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
                continue
            if label:
                tk.Label(cfgrow, text=label, bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
            sp = tk.Spinbox(cfgrow, from_=0, to=hi, textvariable=var, width=5, command=save_cfg, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                            highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 9), buttonbackground=C["panel"])
            sp.pack(side="left", ipady=1, padx=3)
            sp.bind("<FocusOut>", save_cfg)
        tk.Label(cfgrow, text="일 안의 것", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
        info.pack(side="right")
        refresh()

    def show_trash(self, parent=None):
        """휴지통: 지운 노트·노트북을 보관 기간(기본 30일) 동안 두고, 고르면 내용을 미리 보여 주며, 복원하거나 바로 지운다.
        parent 가 없으면 노트북 목록의 휴지통 항목으로 간다"""
        if parent is None:
            return self.go_nb(TRASH)
        top = parent
        head = tk.Frame(top, bg=C["bg"])
        head.pack(fill="x", padx=16, pady=(12, 6))
        info = tk.Label(head, text="", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left")
        info.pack(side="left")
        days_var = tk.StringVar(value=str(self.store.trash_days))
        tk.Label(head, text="일", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="right")

        def set_days(*_):
            try:
                st.write_config(trash_days=max(0, int(days_var.get())))
            except ValueError:
                pass
            refresh()
        sp = tk.Spinbox(head, from_=0, to=3650, textvariable=days_var, width=5, command=set_days, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                        highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 10), buttonbackground=C["panel"])
        sp.pack(side="right", ipady=2, padx=4)
        sp.bind("<FocusOut>", set_days)
        sp.bind("<Return>", set_days)
        tk.Label(head, text="보관 기간 (0 = 자동으로 지우지 않음)", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="right")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        pvw = tk.Frame(top, bg=C["bg"])
        pvw.pack(side="bottom", fill="x", padx=16)
        pv = tk.Text(pvw, height=11, wrap="word", font=self.fonts["base"], bg=C["panel"], fg=C["text"], relief="flat", bd=0, padx=10, pady=8,
                     highlightthickness=0, state="disabled")
        pv.pack(fill="x")
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        tv = ttk.Treeview(wrap, columns=("kind", "where", "deleted", "left"), selectmode="extended", show="headings")
        for col, text, w, anchor in (("kind", "종류", 70, "w"), ("where", "이름 · 원래 위치", 360, "w"), ("deleted", "지운 때", 130, "w"), ("left", "남은 기간", 90, "e")):
            tv.heading(col, text=text)
            tv.column(col, width=w, anchor=anchor, stretch=col == "where")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)

        def refresh():
            tv.delete(*tv.get_children())
            days = self.store.trash_days
            items = self.store.trash_items()
            for it in items:
                left = "-" if not days else "%d일" % max(0, math.ceil(days - (time.time() - it["deleted"]) / 86400))
                tv.insert("", "end", iid=it["id"], values=("저장 폴더" if it["root"] else "파일 묶음" if it["into"] else "노트북" if it["dir"] else "노트", it["rel"], time.strftime("%Y.%m.%d %H:%M", time.localtime(it["deleted"])), left))
            info.config(text=f"{len(items)}개 — 지운 지 {days}일이 지나면 완전히 지워집니다." if days else f"{len(items)}개 — 자동으로 지우지 않습니다.")
        refresh()

        def show_content(e=None):
            """고른 항목의 내용(노트면 본문, 노트북이면 안의 파일 이름들)을 아래에 보인다"""
            sel = tv.selection()
            it = next((x for x in self.store.trash_items() if sel and x["id"] == sel[0]), None)
            text = ""
            if it:
                try:
                    if it["dir"] or it["into"]:
                        names = []
                        for dp, _d, fn in os.walk(it["path"]):
                            names += [os.path.relpath(os.path.join(dp, f), it["path"]) for f in fn]
                        text = f"파일 {len(names):,}개\n" + "\n".join(names[:200])
                    else:
                        with open(it["path"], "rb") as fh:
                            text = st.decode(fh.read(40000))
                except OSError:
                    text = "(내용을 읽지 못했습니다)"
            pv.config(state="normal")
            pv.delete("1.0", "end")
            pv.insert("1.0", text)
            pv.config(state="disabled")
        tv.bind("<<TreeviewSelect>>", show_content)

        def restore():
            sel = tv.selection()
            if not sel:
                return messagebox.showinfo(APP, "복원할 항목을 먼저 고르세요.", parent=top)
            fail = 0
            for tid in sel:
                try:
                    self.store.restore_trash(tid)
                except OSError:
                    fail += 1
            self.reload_notes()
            refresh()
            if fail:
                messagebox.showerror(APP, f"{fail}개를 복원하지 못했습니다.", parent=top)

        def remove():
            sel = tv.selection()
            if sel and messagebox.askyesno(APP, f"고른 {len(sel)}개를 완전히 지울까요? 되돌릴 수 없습니다.", parent=top):
                for tid in sel:
                    self.store.delete_trash(tid)
                refresh()

        def empty():
            n = len(tv.get_children())
            if n and messagebox.askyesno(APP, f"휴지통의 {n}개를 모두 완전히 지울까요? 되돌릴 수 없습니다.", parent=top):
                self.store.empty_trash()
                refresh()
        Btn(btns, "복원", restore, kind="primary", padx=14, pady=3).pack(side="left")
        Btn(btns, "선택한 항목 완전히 삭제", remove, kind="danger", padx=12, pady=3).pack(side="left", padx=6)
        Btn(btns, "휴지통 비우기", empty, kind="danger", padx=12, pady=3).pack(side="right")

    def duplicates_dialog(self, groups):
        if not groups:
            return messagebox.showinfo(APP, "중복으로 보이는 노트가 없습니다.", parent=self.root)
        top = self.tool_window(f"중복 노트 — {len(groups):,}묶음", native=True)
        tk.Label(top, text="제목이 같은 노트 중 본문이 완전히 같은 것과 비슷한 것을 나눠 보여 줍니다. 노트를 하나 누르면 그 노트가 열립니다.\n"
                           "지울 노트는 Ctrl/Shift 로 여러 개 고른 뒤 휴지통으로 보내세요. 완전히 같은 것은 단추 하나로 최근 것만 남기고 정리할 수 있습니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        tv = ttk.Treeview(wrap, columns=("nb", "mtime", "size"), selectmode="extended")
        tv.heading("#0", text="제목")
        tv.heading("nb", text="노트북")
        tv.heading("mtime", text="수정")
        tv.heading("size", text="크기")
        tv.column("#0", width=380)
        tv.column("nb", width=140)
        tv.column("mtime", width=130, stretch=False)
        tv.column("size", width=80, anchor="e", stretch=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        path_of, kind_groups = {}, {"same": [], "similar": []}   # kind_groups: 종류 → 묶음 줄(iid) 목록
        quiet = {"on": False}   # 코드로 줄을 고를 때는 노트를 열지 않는다

        def is_same(why):
            return set(why) == {"본문이 같음"}

        def fill():
            tv.delete(*tv.get_children())
            path_of.clear()
            for v in kind_groups.values():
                v.clear()
            for key, label, pick in (("same", "본문이 완전히 같음", is_same), ("similar", "본문이 비슷함", lambda w: not is_same(w))):
                part = [(why, notes) for why, notes in groups if pick(why)]
                if not part:
                    continue
                cat = tv.insert("", "end", text=f"{label} — {len(part):,}묶음, 노트 {sum(len(n) for _, n in part):,}개", open=True)
                for why, notes in part:
                    g = tv.insert(cat, "end", text=f"{notes[0]['title']} — {len(notes)}개", open=True)
                    kind_groups[key].append(g)
                    for n in notes:
                        iid = tv.insert(g, "end", text=n["title"], values=(self.nb_label(n["nb"]), time.strftime("%Y.%m.%d %H:%M", time.localtime(n["mtime"])), f"{n['size']:,}B"))
                        path_of[iid] = n["path"]
        fill()

        def old_of(key):   # 묶음마다 가장 최근에 고친 것만 남기고 나머지
            sel = []
            for g in kind_groups[key]:
                sel += tv.get_children(g)[1:]
            return sel

        def pick_old(key):
            sel = old_of(key)
            if not sel:
                return messagebox.showinfo(APP, "해당하는 중복이 없습니다.", parent=top)
            quiet["on"] = True
            tv.selection_set(sel)
            tv.see(sel[0])
            top.after(50, lambda: quiet.update(on=False))

        def on_select(e=None):   # 노트 하나를 누르면 그 노트로 연결(여러 개를 고르는 중에는 열지 않는다)
            sel = tv.selection()
            if not quiet["on"] and len(sel) == 1 and sel[0] in path_of:
                self.open_path_note(path_of[sel[0]])

        def trash_same():
            sel = old_of("same")
            if not sel:
                return messagebox.showinfo(APP, "본문이 완전히 같은 노트가 없습니다.", parent=top)
            if not messagebox.askyesno(APP, f"본문이 완전히 같은 {len(kind_groups['same']):,}묶음에서 가장 최근에 고친 것만 남기고\n"
                                            f"나머지 {len(sel):,}개를 휴지통으로 보낼까요?\n({self.store.trash_days}일 동안 보관하며 복원할 수 있습니다)", parent=top):
                return
            trash([path_of[i] for i in sel], confirm=False)

        def trash(paths=None, confirm=True):
            if paths is None:
                paths = [path_of[i] for i in tv.selection() if i in path_of]
            if not paths:
                return messagebox.showinfo(APP, "지울 노트를 먼저 고르세요.", parent=top)
            if confirm and not messagebox.askyesno(APP, f"고른 노트 {len(paths)}개를 휴지통으로 보낼까요?", parent=top):
                return
            gone = set(paths)

            def go():
                self.trash_notes(paths)
                for k, (why, notes) in enumerate(list(groups)):
                    groups[k] = (why, [n for n in notes if n["path"] not in gone])
                groups[:] = [g for g in groups if len(g[1]) > 1]
                if not groups:
                    top.destroy()
                    return messagebox.showinfo(APP, "정리했습니다.", parent=self.root)
                fill()
            self.checkpoint("중복 노트 정리 전", go) if len(paths) >= 5 else go()
        tv.bind("<<TreeviewSelect>>", on_select)
        Btn(btns, "완전히 같은 것: 최근 것만 남기고 삭제", trash_same, kind="danger", padx=12, pady=3).pack(side="left")
        Btn(btns, "비슷한 것: 최근 것만 남기고 고르기", lambda: pick_old("similar"), padx=12, pady=3).pack(side="right")

        menu = tk.Menu(top, tearoff=0)

        def on_menu(e):   # 우클릭: 누른 줄이 고른 줄 안이 아니면 그 줄만 고르고, 열어 보기·휴지통 메뉴를 띄운다
            row = tv.identify_row(e.y)
            if row and row not in tv.selection():
                quiet["on"] = True
                tv.selection_set(row)
                top.after(50, lambda: quiet.update(on=False))
            sel = [i for i in tv.selection() if i in path_of]
            menu.delete(0, "end")
            menu.add_command(label="노트 열어 보기", command=lambda: self.open_path_note(path_of[sel[0]]), state="normal" if sel else "disabled")
            menu.add_command(label=f"휴지통으로 보내기 ({len(sel)}개)" if len(sel) > 1 else "휴지통으로 보내기", command=trash, state="normal" if sel else "disabled")
            menu.tk_popup(e.x_root, e.y_root)
        tv.bind("<Button-3>", on_menu)

    def show_journal(self):
        """편집 > 전체 변경 이력: 모든 노트의 저장·생성·삭제·이름 바꿈·이동·복원을 시간순으로"""
        top = self.tool_window("전체 변경 이력", "860x540")
        tk.Label(top, text="모든 노트의 변경을 최근 순으로 보여 줍니다(같은 노트의 연속 저장은 1분에 한 번만 기록). 더블클릭하면 그 노트를 엽니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")
        flt = tk.Frame(top, bg=C["bg"])
        flt.pack(fill="x", padx=16)
        names = {"edit": "수정", "create": "새 노트", "delete": "삭제", "restore": "복원", "rename": "이름 바꿈", "move": "이동", "cleanup": "군더더기 정리", "tags": "태그 정리", "external": "앱 밖 수정"}
        var = tk.StringVar(value="전체")
        for label in ["전체"] + list(names.values()):
            tk.Radiobutton(flt, text=label, value=label, variable=var, command=lambda: fill(), indicatoron=False, bd=0, padx=8, pady=2,
                           bg=C["bg"], selectcolor=C["soft"], activebackground=C["soft"], font=(self.ui, 9)).pack(side="left", padx=1)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(8, 12))
        tv = ttk.Treeview(wrap, columns=("when", "ev", "path", "d"), show="headings", selectmode="browse")
        for col, text, w, stretch in (("when", "시각", 130, False), ("ev", "종류", 90, False), ("path", "노트", 420, True), ("d", "내용", 150, False)):
            tv.heading(col, text=text)
            tv.column(col, width=w, stretch=stretch)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        recs = self.store.journal_read()
        rel_of = {}
        rec_of = {}

        def fill():
            tv.delete(*tv.get_children())
            rel_of.clear()
            rec_of.clear()
            want = var.get()
            shown = 0
            for r in recs:
                label = names.get(r["ev"], r["ev"])
                if want != "전체" and label != want:
                    continue
                path = r["path"] + (" → " + r["to"] if r.get("to") else "")
                iid = tv.insert("", "end", values=(time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(r["t"])), label, path, r.get("d", "")))
                rel_of[iid] = r.get("to") or r["path"]
                rec_of[iid] = r
                shown += 1
                if shown >= 3000:
                    break
        fill()

        def open_sel(e=None):
            sel = tv.selection()
            if not sel:
                return
            full = os.path.normcase(os.path.join(self.store.root, rel_of[sel[0]].replace("/", os.sep)))
            n = next((x for x in self.all_notes if os.path.normcase(x["path"]) == full), None)
            if n:
                self.open_note(n)
            else:
                messagebox.showinfo(APP, "이 노트는 지금 없습니다(삭제되었거나 이름이 바뀌었습니다). 휴지통에서 찾아 보세요.", parent=top)
        tv.bind("<Double-1>", open_sel)

        def undo():
            sel = tv.selection()
            if not sel:
                return messagebox.showinfo(APP, "되돌릴 변경을 고르세요.", parent=top)
            r = rec_of.get(sel[0])
            if not r:
                return
            if r["ev"] not in ("edit", "create", "delete", "rename", "move"):
                return messagebox.showinfo(APP, "이 종류의 변경은 이력에서 되돌릴 수 없습니다.", parent=top)
            what = {"edit": "이 수정 직전의 내용으로 되돌릴까요?\n(지금 내용은 새 버전으로 남겨 둡니다)", "create": "이 새 노트를 휴지통으로 보낼까요?",
                    "delete": "휴지통에서 복원할까요?", "rename": "원래 이름으로 되돌릴까요?", "move": "원래 노트북으로 되돌릴까요?"}[r["ev"]]
            if not messagebox.askyesno(APP, r["path"] + "\n\n" + what, parent=top):
                return
            self.flush()
            cur_path = self.cur["path"] if self.cur else None
            try:
                msg = self.store.undo_event(r)
            except (OSError, ValueError) as ex:
                return messagebox.showerror(APP, str(ex), parent=top)
            self.reload_notes()
            if cur_path:   # 열어 둔 노트가 바뀌었으면 다시 연다
                fresh = next((x for x in self.all_notes if os.path.normcase(x["path"]) in (os.path.normcase(cur_path),)
                              or os.path.normcase(x["path"]) == os.path.normcase(os.path.join(self.store.root, r["path"].replace("/", os.sep)))), None)
                if fresh:
                    self.open_note(fresh)
            recs[:] = self.store.journal_read()
            fill()
            messagebox.showinfo(APP, msg, parent=top)
        menu = tk.Menu(top, tearoff=0)
        menu.add_command(label="이 변경 되돌리기", command=undo)

        def on_menu(e):
            iid = tv.identify_row(e.y)
            if iid:
                tv.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)
        tv.bind("<Button-3>", on_menu)
        bar = tk.Frame(top, bg=C["bg"])
        bar.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        Btn(bar, "이 변경 되돌리기", undo, kind="primary", padx=14).pack(side="right")

    def cleanup_dialog(self, found):
        if not found:
            return messagebox.showinfo(APP, "정리할 군더더기(맨위로·공유하기·댓글 쓰기 같은 줄)가 없습니다.", parent=self.root)
        top = self.tool_window(f"스크랩 군더더기 — 노트 {len(found):,}개", native=True)
        tk.Label(top, text="지울 줄이 있는 노트입니다. 노트를 고르면 지워질 줄을 보여 줍니다. 적용하면 이전 내용이 노트 버전으로 남습니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        left = tk.Frame(top, bg=C["panel"], width=320)
        left.pack(side="left", fill="y", padx=(16, 0))
        left.pack_propagate(False)
        lb = tk.Listbox(left, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", selectmode="extended",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        lsb = ttk.Scrollbar(left, orient="vertical", command=lb.yview)
        lb.config(yscrollcommand=autohide(lsb, lb))
        lb.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        pwrap = tk.Frame(top, bg=C["panel"])
        pwrap.pack(side="left", fill="both", expand=True, padx=16)
        pv = tk.Text(pwrap, wrap="word", state="disabled", relief="flat", bd=0, highlightthickness=0, bg=C["panel"], fg=C["text"],
                     font=(self.mono, 10), padx=14, pady=10)
        psb = ttk.Scrollbar(pwrap, orient="vertical", command=pv.yview)
        pv.config(yscrollcommand=autohide(psb, pv))
        pv.pack(side="left", fill="both", expand=True)
        pv.tag_configure("rm", foreground=C["danger"], overstrike=True)
        shown_lines = {}   # 미리 보기의 행 번호 → 지워지는 줄

        def keep_line(row):
            line = shown_lines.get(row)
            if line is None:
                return
            cfg = self.cleanup_cfg()
            k = cleanup.keep_key(line)
            if k not in cfg["keep"]:
                cfg["keep"].append(k)
                st.write_config(cleanup=cfg)
            if messagebox.askyesno(APP, "이 줄은 앞으로 지우지 않도록 했습니다:\n" + k[:80] + "\n\n지금 결과에 반영하려면 다시 찾아야 합니다. 다시 찾을까요?", parent=top):
                top.destroy()
                self.cleanup_scan(self.cleanup_cfg())
        pmenu = tk.Menu(pv, tearoff=0)

        def on_pv_menu(e):
            row = int(pv.index(f"@{e.x},{e.y}").split(".")[0])
            if row in shown_lines:
                pmenu.delete(0, "end")
                pmenu.add_command(label="이 줄은 지우지 않기", command=lambda: keep_line(row))
                pmenu.tk_popup(e.x_root, e.y_root)
        pv.bind("<Button-3>", on_pv_menu)

        def fill():
            lb.delete(0, "end")
            for n, new, removed in found:
                lb.insert("end", f"{n['title']}  ({len(removed)}줄)")

        def show(e=None):
            sel = lb.curselection()
            if not sel:
                return
            n, new, removed = found[sel[-1]]
            if len(sel) == 1:   # 노트 하나를 누르면 그 노트로 연결
                self.open_path_note(n["path"])
            pv.config(state="normal")
            pv.delete("1.0", "end")
            pv.insert("end", f"{n['title']} — {self.nb_label(n['nb'])}\n지워지는 줄 {len(removed)}개 (줄을 오른쪽 클릭하면 \"이 줄은 지우지 않기\"):\n\n")
            shown_lines.clear()
            for no, line, why in removed[:300]:
                shown_lines[int(pv.index("end-1c").split(".")[0])] = line
                pv.insert("end", f"{no:>5}  [{why}] {line}\n", "rm")
            pv.config(state="disabled")
        fill()
        lb.bind("<<ListboxSelect>>", show)

        def apply(items):
            if not items:
                return messagebox.showinfo(APP, "정리할 노트를 먼저 고르세요.", parent=top)
            if st.version_settings()["keep"] <= 0 and not messagebox.askyesno(
                    APP, "노트 버전 기록이 꺼져 있어 적용하면 되돌릴 수 없습니다. 그래도 적용할까요?", parent=top):
                return
            if not messagebox.askyesno(APP, f"노트 {len(items)}개에서 군더더기 줄을 지울까요?", parent=top):
                return
            cur_path = self.cur["path"] if self.cur else None
            self.flush()

            def go():
                done = 0
                for n, new, removed in items:
                    try:   # 수정 시각은 그대로 두고(touch=False), 이전 내용은 버전으로 남긴다(force)
                        self.store.save(n["path"], new, versioned=True, force=True, touch=False, ev="cleanup")
                        done += 1
                    except OSError:
                        pass
                    found[:] = [f for f in found if f[0]["path"] != n["path"]]
                self.reload_notes()
                m = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
                if m:
                    self.open_note(m, record=False)
                messagebox.showinfo(APP, f"{done}개 노트를 정리했습니다.", parent=top)
                if not found:
                    return top.destroy()
                fill()
                pv.config(state="normal")
                pv.delete("1.0", "end")
                pv.config(state="disabled")
            self.checkpoint("군더더기 정리 전", go) if len(items) >= 5 else go()

        def selected():
            return [found[i] for i in lb.curselection()]
        Btn(btns, "모두 정리", lambda: apply(list(found)), kind="primary", padx=12, pady=3).pack(side="right")

        menu = tk.Menu(top, tearoff=0)

        def on_menu(e):   # 우클릭: 누른 줄이 고른 줄 안이 아니면 그 줄만 고르고(미리 보기도 갱신), 열어 보기·정리 메뉴를 띄운다
            i = lb.nearest(e.y)
            if 0 <= i < lb.size() and i not in lb.curselection():
                lb.selection_clear(0, "end")
                lb.selection_set(i)
                show()
            sel = selected()
            menu.delete(0, "end")
            menu.add_command(label="노트 열어 보기", command=lambda: self.open_path_note(sel[0][0]["path"]), state="normal" if sel else "disabled")
            menu.add_command(label=f"선택한 노트 정리 ({len(sel)}개)" if len(sel) > 1 else "이 노트 정리",
                             command=lambda: apply(selected()), state="normal" if sel else "disabled")
            menu.tk_popup(e.x_root, e.y_root)
        lb.bind("<Button-3>", on_menu)

    # ------------------------------------------------------------ 도움말 > 업데이트 확인

    def show_properties(self):
        if not self.cur or self.doc_open:
            return messagebox.showinfo(APP, "먼저 노트를 여세요." if not self.cur else "가져온 파일에는 노트 속성이 없습니다.", parent=self.root)
        self.flush()
        n = self.cur
        meta = st.parse_meta(n["body"])
        top = tk.Toplevel(self.root)
        top.title("노트 속성")
        top.configure(bg=C["bg"])
        top.transient(self.root)
        top.resizable(False, False)
        top.geometry(f"+{self.root.winfo_x() + 160}+{self.root.winfo_y() + 90}")
        f = tk.Frame(top, bg=C["bg"], padx=26, pady=20)
        f.pack()
        tk.Label(f, text="노트 속성", bg=C["bg"], fg=C["text"], font=(self.ui, 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))
        fmt = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))  # noqa: E731
        state = {"r": 1}

        def row(label, value="", btn=None, link=None, copyable=False):
            r = state["r"]
            state["r"] += 1
            tk.Label(f, text=label, bg=C["bg"], fg=C["muted"], font=(self.ui, 10, "bold"), anchor="nw", width=9).grid(row=r, column=0, sticky="nw", pady=5)
            if copyable:
                var = tk.StringVar(value=value)
                tk.Entry(f, textvariable=var, state="readonly", width=46, relief="flat", bd=0, bg=C["panel"], readonlybackground=C["panel"],
                         fg=C["text"], highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 9)).grid(row=r, column=1, sticky="w", pady=4, ipady=3)
            else:
                v = tk.Label(f, text=value or "—", bg=C["bg"], fg=C["accent"] if link else C["text"], anchor="w", justify="left",
                             wraplength=360, font=(self.ui, 10, "underline") if link else (self.ui, 10), cursor="hand2" if link else "")
                v.grid(row=r, column=1, sticky="w", pady=5)
                if link:
                    v.bind("<Button-1>", lambda e: link())
            if btn:
                Btn(f, btn[0], btn[1], padx=8, pady=1).grid(row=r, column=2, sticky="w", padx=(8, 0))

        def edit_time(kind):
            label = "갱신됨" if kind == "updated" else "생성됨"
            cur_t = n["mtime"] if kind == "updated" else n.get("ctime", n["mtime"])
            ans = simpledialog.askstring(f"{label} 변경", "형식: 2023-03-21 20:24:00", initialvalue=fmt(cur_t), parent=top)
            if not ans:
                return
            t = st.parse_time(ans)
            if t is None:
                return messagebox.showerror(APP, "날짜를 읽지 못했습니다. 예: 2023-03-21 20:24:00", parent=top)
            try:
                self.store.set_dates(n["path"], updated=t if kind == "updated" else None, created=t if kind == "created" else None)
            except (OSError, ValueError) as ex:
                return messagebox.showerror(APP, str(ex), parent=top)
            path = n["path"]
            top.destroy()
            self.reload_notes()
            again = next((x for x in self.notes if x["path"] == path), None)
            if again:
                self.open_note(again, record=False)
                self.show_properties()

        def copy(text):
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        url = st.note_source(n["body"], meta)
        nvers = len(self.store.versions(n["path"]))
        row("제목", n["title"])
        row("위치", self.nb_label(n["nb"]))
        row("파일", n["path"], ("복사", lambda: copy(n["path"])), copyable=True)
        row("갱신됨", fmt(n["mtime"]), ("✎", lambda: edit_time("updated")))
        row("생성됨", fmt(n.get("ctime", n["mtime"])), ("✎", lambda: edit_time("created")) if meta["created"] else None)
        if meta["fm"] and (meta["updated"] or meta["created"]):
            row("날짜 출처", "노트 머리말(front matter)의 날짜")
        else:
            row("날짜 출처", "파일의 수정·생성 시각")
        row("URL", url, link=(lambda: webbrowser.open(url)) if url else None)
        if meta["author"]:
            row("작성자", meta["author"])
        tags = sorted(n.get("tags", ()))
        row("태그", "   ".join("# " + t for t in tags))
        text = n["body"]
        row("크기", f"{len(text):,}자 · {text.count(chr(10)) + 1:,}줄")
        row("노트 역사", f"이전 버전 {nvers}개 보기" if nvers else "저장된 이전 버전 없음",
            link=(lambda: (top.destroy(), self.show_versions())) if nvers else None)
        row("마크업", "Markdown")
        bf = tk.Frame(f, bg=C["bg"])
        bf.grid(row=state["r"], column=0, columnspan=3, sticky="e", pady=(16, 0))
        Btn(bf, "닫기", top.destroy, kind="primary", padx=22, pady=5).pack()
        top.bind("<Escape>", lambda e: top.destroy())

    # ------------------------------------------------------------ 노트 버전

    def show_versions(self):
        """편집 > 노트 버전…: 이 노트의 이전 내용을 보고, 골라서 되돌린다."""
        if not self.cur or self.doc_open:
            return messagebox.showinfo(APP, "먼저 노트를 여세요." if not self.cur else "가져온 파일에는 노트 버전이 없습니다.", parent=self.root)
        self.flush()
        n = self.cur
        top = tk.Toplevel(self.root)
        top.title("노트 버전 — " + n["title"])
        top.configure(bg=C["bg"])
        top.transient(self.root)
        top.geometry(f"860x540+{self.root.winfo_x() + 90}+{self.root.winfo_y() + 60}")
        top.minsize(640, 400)
        left = tk.Frame(top, bg=C["panel"], width=250)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="저장된 버전", bg=C["panel"], fg=C["text"], font=(self.ui, 11, "bold"), anchor="w", padx=16, pady=14).pack(fill="x")
        lb = tk.Listbox(left, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        lb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        right = tk.Frame(top, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        info = tk.Label(right, text="", anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=16, pady=10, justify="left")
        info.pack(fill="x")
        btns = tk.Frame(right, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        pv = tk.Text(right, wrap="word", state="disabled", relief="flat", bd=0, highlightthickness=0, bg=C["panel"], fg=C["text"],
                     font=(self.mono, 10), padx=14, pady=10)
        pv.pack(fill="both", expand=True, padx=16)
        vs = []

        def fill():
            nonlocal vs
            vs = self.store.versions(n["path"])
            lb.delete(0, "end")
            for ts, size, _ in vs:
                lb.insert("end", time.strftime("%Y.%m.%d  %H:%M:%S", time.localtime(ts)) + f"   {size:,}B")
            if vs:
                lb.selection_set(0)
                show(None)
            else:
                v = st.version_settings()
                info.config(text="저장된 버전이 없습니다." if v["keep"] else "노트 버전 기록이 꺼져 있습니다. 설정 > 노트 버전 설정에서 켤 수 있습니다.")
                pv.config(state="normal")
                pv.delete("1.0", "end")
                pv.config(state="disabled")

        def show(e):
            sel = lb.curselection()
            if not sel:
                return
            ts, size, fp = vs[sel[0]]
            text = self.store.read_version(fp)
            info.config(text=f"{time.strftime('%Y.%m.%d %H:%M:%S', time.localtime(ts))} 의 내용  ·  지금 {len(n['body']):,}자 / 이 버전 {len(text):,}자")
            pv.config(state="normal", wrap="none" if max((len(x) for x in text.split("\n")), default=0) > 20000 else "word")
            pv.delete("1.0", "end")
            pv.insert("1.0", text[:200000] + ("\n\n… (이하 생략)" if len(text) > 200000 else ""))
            pv.config(state="disabled")

        def restore():
            sel = lb.curselection()
            if not sel:
                return
            ts, _, fp = vs[sel[0]]
            if not messagebox.askyesno(APP, f"{time.strftime('%Y.%m.%d %H:%M:%S', time.localtime(ts))} 버전으로 되돌릴까요?\n"
                                            "(지금 내용은 새 버전으로 남겨 두므로 다시 돌아올 수 있습니다)", parent=top):
                return
            body = self.store.read_version(fp)
            self.store.snapshot(n["path"], body, max(1, st.version_settings()["count"]), 0)
            self.apply_body(body)
            top.destroy()

        def delete():
            sel = lb.curselection()
            if sel and messagebox.askyesno(APP, "이 버전을 삭제할까요?", parent=top):
                self.store.delete_version(vs[sel[0]][2])
                fill()

        lb.bind("<<ListboxSelect>>", show)
        Btn(btns, "닫기", top.destroy, padx=16).pack(side="right")
        Btn(btns, "삭제", delete, kind="danger", padx=14).pack(side="right", padx=6)
        Btn(btns, "이 버전으로 되돌리기", restore, kind="primary", bold=True, padx=16).pack(side="right")
        fill()

    # ------------------------------------------------------------ 테마

    def show_options(self, tab="general"):
        if getattr(self, "opt", None) and self.opt.winfo_exists():
            self.opt.destroy()
        top = self.opt = tk.Toplevel(self.root)
        top.title("옵션")
        top.configure(bg=C["bg"])
        top.transient(self.root)
        h = max(420, min(640, top.winfo_screenheight() - 140))   # 화면이 작거나 글자 배율이 크면 창을 화면에 맞추고, 넘치는 내용은 스크롤한다
        top.geometry(f"900x{h}+{self.root.winfo_x() + 100}+{max(0, min(self.root.winfo_y() + 50, top.winfo_screenheight() - h - 80))}")
        top.minsize(780, 420)
        nav = tk.Frame(top, bg=C["panel"], width=170)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(nav, text="옵션", bg=C["panel"], fg=C["text"], font=(self.ui, 12, "bold"), anchor="w", padx=18, pady=16).pack(fill="x")
        outer = tk.Frame(top, bg=C["bg"])
        outer.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(outer, orient="vertical")
        cv = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, bd=0, yscrollcommand=sb.set)
        sb.config(command=cv.yview)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        content = tk.Frame(cv, bg=C["bg"], padx=28, pady=22)
        cwin = cv.create_window(0, 0, window=content, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfigure(cwin, width=e.width))
        content.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        top.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, "units") if content.winfo_reqheight() > cv.winfo_height() else None)
        foot = tk.Frame(top, bg=C["bg"])
        tabs = {}

        def lab(p, t, **k):
            return tk.Label(p, text=t, bg=C["bg"], fg=k.pop("fg", C["text"]), anchor="w", justify="left",
                            font=k.pop("font", (self.ui, 10)), **k)

        def title(p, t, sub=""):
            lab(p, t, font=(self.ui, 14, "bold")).pack(anchor="w")
            if sub:
                lab(p, sub, fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(2, 14))

        def hr(p):
            tk.Frame(p, height=1, bg=C["line"]).pack(fill="x", pady=14)

        def field(p, label, var, width, button=None):
            row = tk.Frame(p, bg=C["bg"])
            row.pack(fill="x", pady=3)
            lab(row, label, width=8).pack(side="left")
            tk.Entry(row, textvariable=var, width=width, state="readonly", relief="flat", bd=0, bg=C["panel"],
                     readonlybackground=C["panel"], fg=C["text"], highlightthickness=1, highlightbackground=C["line"],
                     font=(self.ui, 10)).pack(side="left", ipady=4, fill="x", expand=button is None)
            if button:
                Btn(row, button[0], button[1], padx=10, pady=3).pack(side="left", padx=6)

        def copy(text):
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

        def general(p):
            title(p, "일반", "노트를 저장하는 곳과 시작할 때의 보기를 정합니다.")
            lab(p, "노트와 그림을 저장하는 폴더는 설정 > 폴더 설정에서 바꿉니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w")
            hr(p)
            lab(p, "위키 링크", font=(self.ui, 10, "bold")).pack(anchor="w")
            wk = tk.BooleanVar(value=st.wiki_enabled())

            def set_wiki():
                st.write_config(wikiEnabled=wk.get())
                if self.cur:
                    self.render()
            tk.Checkbutton(p, text="위키 링크 사용  ([[노트 제목]] 으로 노트 연결)", variable=wk, command=set_wiki,
                           bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            wa = tk.BooleanVar(value=bool(st.read_config().get("wikiAuto", False)))

            def set_auto():
                st.write_config(wikiAuto=wa.get())
                if self.cur:
                    self.render()
            tk.Checkbutton(p, text="괄호 없이 제목과 같은 낱말도 연결  (톰보이 방식)", variable=wa, command=set_auto,
                           bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            lab(p, "켜 두면 같은 제목의 노트는 만들 수 없고, [[제목]] 은 가장 최근에 고친 노트로 연결됩니다. 없는 제목의 링크는 붉게 보이고 누르면 새로 만들 수 있습니다. 끄면 [[ ]] 는 그냥 글자입니다.",
                fg=C["muted"], font=(self.ui, 9), wraplength=620).pack(anchor="w", pady=(2, 0))
            hr(p)
            lab(p, "기능 (쓰지 않으면 끕니다)", font=(self.ui, 10, "bold")).pack(anchor="w")
            for key, label in (("favs", "즐겨찾기"), ("outl", "아웃라이너 폴더"), ("cal", "달력·할일"), ("gongsu", "공수달력 (달력·할일 안에서 공수·일당·일비 계산, 건설·일용직용)")):
                var = tk.BooleanVar(value=self.feat[key])

                def set_feat(k=key, v=var):
                    self.feat[k] = v.get()
                    st.write_config(**({"cal_gongsu": v.get()} if k == "gongsu" else {"use_" + k: v.get()}))
                    if k == "gongsu" and self.planner_view is not None:
                        self.planner_view.refresh()
                    self.reload_notebooks()
                    if self.cur:
                        self.open_note(self.cur, record=False)
                tk.Checkbutton(p, text=label, variable=var, command=set_feat, bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10),
                               selectcolor=C["bg"]).pack(anchor="w")
            hr(p)
            lab(p, "편집기 보기", font=(self.ui, 10, "bold")).pack(anchor="w")
            for key, label in (("edit", "마크다운만"), ("split", "마크다운 + 렌더링 (분할)"), ("view", "렌더링만")):
                tk.Radiobutton(p, text=label, value=key, variable=self.v_mode, command=lambda k=key: self.set_mode(k),
                               bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            hr(p)
            lab(p, "창의 닫기(X) 버튼", font=(self.ui, 10, "bold")).pack(anchor="w")
            ca = tk.StringVar(value=self.close_action())
            for key, label in (("tray", "작업표시줄 알림 영역(트레이)으로 보내기 — 앱은 계속 실행됩니다"), ("quit", "바로 종료")):
                tk.Radiobutton(p, text=label, value=key, variable=ca, command=lambda: st.write_config(closeAction=ca.get()),
                               bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            lab(p, "트레이 아이콘을 누르면 창이 다시 열리고, 우클릭 → 종료로 끕니다. 파일 → 종료(와 트레이의 종료)는 언제나 바로 끕니다.",
                fg=C["muted"], font=(self.ui, 9), wraplength=620).pack(anchor="w", pady=(2, 0))
            hr(p)
            lab(p, "화면 구성", font=(self.ui, 10, "bold")).pack(anchor="w")
            for key, label in (("notebooks", "노트북 보기"), ("tags", "태그 보기"), ("list", "노트 목록 보기"), ("syntax", "문법 해설 보기")):
                tk.Checkbutton(p, text=label, variable=self.v[key], command=self.on_view_toggle, bg=C["bg"],
                               activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")

        def clipper(p):
            title(p, "웹 클리퍼", "조플린 클리퍼 플러스(크롬 확장)로 웹 페이지를 이 앱에 바로 저장합니다.")
            on = tk.BooleanVar(value=bool(st.read_config().get("clipEnabled", True)))
            status = lab(p, "", fg=C["muted"], font=(self.ui, 9))
            port_var, tok_var = tk.StringVar(), tk.StringVar(value=st.clipper_token())

            def refresh_state():
                if self.srv:
                    status.config(text=f"실행 중 — 127.0.0.1:{self.port} (이 컴퓨터에서만 접속됩니다)", fg="#15803d")
                elif on.get():
                    status.config(text="켜져 있지만 서버를 열지 못했습니다(41184~41194 포트가 모두 사용 중).", fg=C["danger"])
                else:
                    status.config(text="꺼져 있음", fg=C["muted"])
                port_var.set(str(self.port or ""))

            def toggle():
                st.write_config(clipEnabled=bool(on.get()))
                if on.get():
                    self.start_clipper()
                else:
                    self.stop_clipper()
                refresh_state()
            tk.Checkbutton(p, text="웹 클리퍼 서비스 사용", variable=on, command=toggle, bg=C["bg"],
                           activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            status.pack(anchor="w", pady=(2, 10))
            field(p, "포트", port_var, 10)

            def regen():
                if messagebox.askyesno("토큰 새로 만들기", "새 토큰을 만들면 크롬 확장 옵션의 토큰도 바꿔야 합니다.\n계속할까요?", parent=top):
                    tok_var.set(secrets.token_hex(24))
                    st.write_config(clipToken=tok_var.get())
            field(p, "토큰", tok_var, 50, ("복사", lambda: copy(tok_var.get())))
            Btn(p, "토큰 새로 만들기", regen, padx=10, pady=3).pack(anchor="w", padx=(64, 0), pady=(2, 0))
            hr(p)
            store_url = "https://chromewebstore.google.com/detail/joplin-clipper-plus/fbieoidncnoalmenkkpbcbomppoenfoa"
            lab(p, "크롬 웹스토어", font=(self.ui, 10, "bold")).pack(anchor="w")
            link = tk.Label(p, text=store_url, bg=C["bg"], fg=C["accent"], cursor="hand2", font=(self.ui, 9, "underline"),
                            anchor="w", justify="left", wraplength=480)
            link.pack(anchor="w", pady=(4, 0))
            link.bind("<Button-1>", lambda e: webbrowser.open(store_url))
            git_url = "https://github.com/iamtalker/joplin-clipper-plus"
            lab(p, "GitHub (소스·설치 방법)", font=(self.ui, 10, "bold")).pack(anchor="w", pady=(12, 0))
            glink = tk.Label(p, text=git_url, bg=C["bg"], fg=C["accent"], cursor="hand2", font=(self.ui, 9, "underline"), anchor="w")
            glink.pack(anchor="w", pady=(4, 0))
            glink.bind("<Button-1>", lambda e: webbrowser.open(git_url))
            refresh_state()

        def imports_tab(p):
            title(p, "가져오기", "노트 폴더 밖의 폴더에 있는 pdf·txt·mp3 등을 읽어 노트처럼 검색합니다. 원본 파일은 건드리지 않고 읽기만 합니다.")
            cfg = self.docs.cfg()
            avail = docidx.available()
            lab(p, "가져올 폴더", font=(self.ui, 10, "bold")).pack(anchor="w")
            box = tk.Frame(p, bg=C["bg"])
            box.pack(fill="x", pady=(4, 0))
            lb = tk.Listbox(box, height=5, relief="flat", bd=0, bg=C["panel"], fg=C["text"], highlightthickness=1, highlightbackground=C["line"],
                            selectbackground=C["soft"], selectforeground=C["text"], activestyle="none", font=(self.ui, 10), exportselection=False)
            lb.pack(fill="x", ipady=2)
            ids = []

            def fill():
                lb.delete(0, "end")
                ids.clear()
                counts = self.docs.counts()
                for f in self.docs.folders():
                    ids.append(f["id"])
                    lb.insert("end", f"{f['path']}    ({counts.get(f['id'], 0):,}개)")
            fill()

            def add():
                path = filedialog.askdirectory(title="가져올 폴더 고르기", parent=top, mustexist=True)
                if not path:
                    return
                path = os.path.normpath(path)
                r = os.path.normcase(self.store.root)
                if os.path.normcase(path) == r or os.path.normcase(path).startswith(r + os.sep) or r.startswith(os.path.normcase(path) + os.sep):
                    return messagebox.showwarning(APP, "노트 폴더와 겹치는 폴더는 가져올 수 없습니다(노트는 이미 읽고 있습니다).", parent=top)
                if not self.docs.add_folder(path):
                    return messagebox.showinfo(APP, "이미 가져온 폴더입니다.", parent=top)
                fill()
                self.after_docs_changed()
                if messagebox.askyesno(APP, "지금 이 폴더의 파일을 읽어 색인할까요?\n(파일이 많으면 처음 한 번은 오래 걸리고, 이후에는 바뀐 파일만 읽습니다)", parent=top):
                    self.scan_docs(self.docs.fid(path))

            def remove():
                sel = lb.curselection()
                if sel:
                    self.remove_doc_folder(ids[sel[0]])
                    fill()
            row = tk.Frame(p, bg=C["bg"])
            row.pack(anchor="w", pady=(8, 0))
            Btn(row, "폴더 추가…", add, padx=12, pady=3).pack(side="left")
            Btn(row, "목록에서 빼기", remove, padx=12, pady=3).pack(side="left", padx=6)
            Btn(row, "지금 다시 읽기", lambda: self.scan_docs(), padx=12, pady=3).pack(side="left")
            lab(p, "빼도 원본 파일은 그대로입니다. 앱을 켜고 잠시 뒤 바뀐 파일은 저절로 다시 읽습니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(6, 0))
            hr(p)

            lab(p, "읽을 파일 종류 (고른 확장자만 읽습니다)", font=(self.ui, 10, "bold")).pack(anchor="w")
            common = ["pdf", "txt", "md", "mp3", "docx", "pptx", "xlsx", "csv", "html", "m4a", "flac", "wav", "ogg", "log", "json"]
            chosen = {e.lower().lstrip(".") for e in cfg["exts"]}
            vars_ = {e: tk.BooleanVar(value=e in chosen) for e in common}
            extra = tk.StringVar(value=" ".join(sorted(chosen - set(common))))

            def save_exts(*_):
                exts = [e for e in common if vars_[e].get()]
                exts += [x.lower().lstrip(".") for x in re.split(r"[\s,;]+", extra.get()) if x.strip(".")]
                c = self.docs.cfg()
                c["exts"] = exts or list(docidx.DEFAULT_EXTS)
                self.docs.save_cfg(c)
            grid = tk.Frame(p, bg=C["bg"])
            grid.pack(anchor="w", pady=(6, 0))
            for i, e in enumerate(common):
                tk.Checkbutton(grid, text="." + e, variable=vars_[e], command=save_exts, bg=C["bg"], activebackground=C["bg"], selectcolor=C["bg"],
                               font=(self.ui, 10), width=7, anchor="w").grid(row=i // 5, column=i % 5, sticky="w")
            erow = tk.Frame(p, bg=C["bg"])
            erow.pack(anchor="w", pady=(6, 0))
            lab(erow, "그 밖의 확장자").pack(side="left")
            ent = tk.Entry(erow, textvariable=extra, width=24, relief="flat", bd=0, bg=C["panel"], fg=C["text"], highlightthickness=1,
                           highlightbackground=C["line"], insertbackground=C["accent"], font=(self.ui, 10))
            ent.pack(side="left", padx=8, ipady=3)
            ent.bind("<FocusOut>", save_exts)
            ent.bind("<Return>", save_exts)
            missing = [n for n, ok in (("pdf", "pypdf"), ("mp3", "tinytag")) if n not in avail]
            lab(p, "글을 읽는 도구가 없는 확장자는 파일 이름만 색인됩니다. 종류를 바꾼 뒤에는 '지금 다시 읽기'를 누르세요."
                + (f"\n(이 컴퓨터에는 {', '.join(missing)} 라이브러리가 없어 해당 형식은 이름만 색인됩니다)" if missing else ""),
                fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(6, 0))
            hr(p)

            content = tk.BooleanVar(value=cfg["content"])

            def save_content():
                c = self.docs.cfg()
                c["content"] = bool(content.get())
                self.docs.save_cfg(c)
            tk.Checkbutton(p, text="문서 안의 글도 색인 (pdf·txt·docx 본문, mp3 태그와 가사)", variable=content, command=save_content, bg=C["bg"],
                           activebackground=C["bg"], selectcolor=C["bg"], font=(self.ui, 10)).pack(anchor="w")
            lab(p, "끄면 파일 이름과 경로로만 찾습니다(빠르고 DB 가 작아집니다). 문서를 열어 둔 상태에서 Ctrl+F 로 그 문서 안에서 찾는 것은 켜든 끄든 쓸 수 있습니다.",
                fg=C["muted"], font=(self.ui, 9), wraplength=620).pack(anchor="w", pady=(2, 0))

        def versions_tab(p):
            title(p, "노트 버전", "노트를 고칠 때마다 이전 내용을 노트별로 보관해 두고, 나중에 골라서 되돌릴 수 있습니다.")
            cfg = st.read_config().get("versions", {})
            enabled = tk.BooleanVar(value=bool(cfg.get("enabled", True)))
            keep = tk.StringVar(value=str(cfg.get("keep", 10)))
            minutes = tk.StringVar(value=str(int(float(cfg.get("minutes", 1)))))

            def apply(*_):
                try:
                    k = max(1, min(200, int(keep.get())))
                except ValueError:
                    k = 10
                try:
                    m = max(0, min(1440, int(minutes.get())))
                except ValueError:
                    m = 5
                keep.set(str(k))
                minutes.set(str(m))
                st.write_config(versions={"enabled": bool(enabled.get()), "keep": k, "minutes": m})
                spin_state()

            def spin_state():
                for w in (sp1, sp2):
                    w.config(state="normal" if enabled.get() else "disabled")
            tk.Checkbutton(p, text="노트 버전 기록 사용", variable=enabled, command=apply, bg=C["bg"], activebackground=C["bg"],
                           font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")

            def spin(label, var, lo, hi, unit):
                row = tk.Frame(p, bg=C["bg"])
                row.pack(fill="x", pady=6)
                lab(row, label, width=18).pack(side="left")
                w = tk.Spinbox(row, from_=lo, to=hi, textvariable=var, width=6, command=apply, relief="flat", bd=0, bg=C["panel"],
                               highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 10), buttonbackground=C["panel"])
                w.pack(side="left", ipady=4)
                w.bind("<Return>", apply)
                w.bind("<FocusOut>", apply)
                lab(row, unit, fg=C["muted"], font=(self.ui, 9)).pack(side="left", padx=8)
                return w
            sp1 = spin("노트당 보관 개수", keep, 1, 200, "개 (넘으면 오래된 것부터 지웁니다)")
            sp2 = spin("새 버전 간격", minutes, 0, 1440, "분 (0 = 자동 저장할 때마다)")
            spin_state()
            hr(p)
            lab(p, "버전을 만드는 때: ① 노트를 연 뒤 처음 고칠 때(그 직전 내용)  ② 그 뒤로는 '새 버전 간격'이 지난 뒤 고칠 때.\n"
                   "예) 간격 1분이면, 한 노트를 계속 고치는 동안 1분에 한 번씩 버전이 남습니다.\n"
                   "버전은 저장 폴더의 .history 폴더에 노트별로 보관됩니다(노트북으로 보이지 않습니다).\n"
                   "노트의 이름을 바꾸거나 다른 노트북으로 옮겨도 버전 기록이 따라갑니다.\n"
                   "보기: 편집 > 노트 버전…  또는 노트 목록에서 우클릭", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w")
            Btn(p, "이 노트의 버전 보기", lambda: (top.destroy(), self.show_versions()), padx=12, pady=4).pack(anchor="w", pady=(14, 0))

        def theme_tab(p):
            title(p, "테마·색상", "노트 전체의 색을 고릅니다. 누르면 바로 적용됩니다.")
            cfg = st.read_config().get("theme", {})
            cur_name = cfg.get("name", DEFAULT_THEME)
            cur_acc = cfg.get("accent")
            grid = tk.Frame(p, bg=C["bg"])
            grid.pack(fill="x")

            def card(i, tname):
                t = compute_theme(tname, cur_acc if tname == cur_name else None)
                chosen = tname == cur_name
                f = tk.Frame(grid, bg=C["accent"] if chosen else C["line"], padx=2, pady=2, cursor="hand2")
                f.grid(row=i // 3, column=i % 3, padx=(0, 10), pady=(0, 10))
                body = tk.Frame(f, bg=t["bg"], width=150, height=84)
                body.pack()
                body.pack_propagate(False)
                tk.Frame(body, bg=t["panel"], width=34).pack(side="left", fill="y")
                right = tk.Frame(body, bg=t["bg"])
                right.pack(side="left", fill="both", expand=True)
                tk.Label(right, text=tname, bg=t["bg"], fg=t["text"], font=(self.ui, 9, "bold")).pack(anchor="w", padx=8, pady=(12, 4))
                chips = tk.Frame(right, bg=t["bg"])
                chips.pack(anchor="w", padx=8)
                for col, w in ((t["accent"], 30), (t["soft"], 22), (t["line"], 14)):
                    tk.Frame(chips, bg=col, width=w, height=9).pack(side="left", padx=(0, 4))
                tk.Label(right, text="✓ 사용 중" if chosen else "", bg=t["bg"], fg=t["accent"], font=(self.ui, 8)).pack(anchor="w", padx=8, pady=(6, 0))
                for w in (f, body, right, *right.winfo_children(), *chips.winfo_children()):
                    w.bind("<Button-1>", lambda e, n=tname: self.root.after(20, lambda: self.set_theme(n)))
            for i, tname in enumerate(THEMES):
                card(i, tname)
            hr(p)
            lab(p, "강조색", font=(self.ui, 10, "bold")).pack(anchor="w")
            row = tk.Frame(p, bg=C["bg"])
            row.pack(fill="x", pady=8)
            tk.Frame(row, bg=C["accent"], width=34, height=22, highlightthickness=1, highlightbackground=C["line"]).pack(side="left")
            lab(row, cur_acc or "테마 기본색", fg=C["muted"], font=(self.ui, 9)).pack(side="left", padx=10)

            def choose():
                rgb, hexa = colorchooser.askcolor(color=C["accent"], title="강조색 고르기", parent=top)
                if hexa:
                    self.root.after(20, lambda: self.set_theme(cur_name, hexa))
            Btn(row, "색 고르기…", choose, padx=12, pady=4).pack(side="left")
            Btn(row, "테마 기본색으로", lambda: self.root.after(20, lambda: self.set_theme(cur_name, None)), padx=12, pady=4).pack(side="left", padx=6)
            lab(p, "강조색은 선택된 글, 버튼, 링크, 태그 등에 쓰이는 포인트 색입니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w")

            hr(p)
            lab(p, "유튜브 영상", font=(self.ui, 10, "bold")).pack(anchor="w")
            lab(p, "노트 안의 유튜브 영상은 썸네일로 보이고, 누르면 재생 창이 열립니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(0, 4))
            vo = tk.StringVar(value=st.read_config().get("video_open", "app"))
            for key, label in (("app", "작은 재생 창 (Edge 앱 창, 주소창 없음)"), ("browser", "기본 브라우저")):
                tk.Radiobutton(p, text=label, value=key, variable=vo, command=lambda: st.write_config(video_open=vo.get()),
                               bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10)).pack(anchor="w")

        def folders_tab(p):
            title(p, "폴더", "노트와 그림(리소스)을 저장하는 폴더를 정합니다.")
            root_var, media_var = tk.StringVar(), tk.StringVar()
            mode_note = lab(p, "", fg=C["muted"], font=(self.ui, 9))

            def refresh():
                root_var.set(self.store.root)
                media_var.set(self.store.media_dir)
                if self.store.media_is_vault:
                    mode_note.config(text="현재: 볼트 안 .resources (숨김)")
                else:
                    mode_note.config(text="현재: 예전 방식의 리소스 폴더입니다. 「볼트 안으로 옮기기」를 누르면 그림을 .resources 로 옮기고 노트의 링크도 고칩니다.")

            def change_root():
                if self.choose_root():
                    refresh()

            def apply_media(mode, path=None):
                new = self.store.media_dir_for(mode, path)
                old = self.store.media_dir
                same = os.path.normcase(os.path.abspath(new)) == os.path.normcase(os.path.abspath(old))
                migrate = False
                count = self.store.count_media()
                if not same and count:
                    ans = messagebox.askyesnocancel(
                        "리소스 폴더 변경", f"기존 리소스 {count}개를 새 폴더로 옮기고 노트의 그림 링크도 고칠까요?\n\n"
                        "예: 옮기고 링크 수정 (권장)\n아니오: 설정만 바꿈 (기존 파일과 링크는 그대로)\n취소: 변경 안 함", parent=top)
                    if ans is None:
                        return
                    migrate = bool(ans)
                self.flush()
                cur_path = self.cur["path"] if self.cur else None

                def go():
                    if not migrate:
                        try:
                            return finish(self.store.set_media(mode, path, False))
                        except (OSError, ValueError) as ex:
                            return messagebox.showerror(APP, f"리소스 폴더를 바꾸지 못했습니다.\n{ex}", parent=top)
                    self.run_task("리소스 폴더 옮기는 중", lambda prog, cancel: self.store.set_media(mode, path, True, prog),
                                  finish, text="리소스를 옮기고 노트의 링크를 고치는 중…", cancellable=False)

                def finish(res):
                    moved, relinked = res
                    self.reload_notes()
                    n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
                    if n:
                        self.open_note(n, record=False)   # 링크가 바뀐 글을 다시 읽어 와서 낡은 내용으로 덮어쓰지 않게
                    refresh()
                    if migrate:
                        messagebox.showinfo(APP, f"리소스 {moved}개를 옮기고 노트 {relinked}개의 링크를 고쳤습니다.", parent=top)
                self.checkpoint("리소스 폴더 이전 전", go) if migrate else go()   # 노트의 링크가 바뀌므로 먼저 복원 지점

            def adopt_folder():
                """마크다운마다 미디어 폴더 이름이 다르니, 고른 폴더를 .resources 로 바꾸고 모든 노트의 링크도 고친다(확인 후)"""
                old = filedialog.askdirectory(title="미디어(그림·첨부)가 들어 있는 폴더 고르기", initialdir=self.store.root, mustexist=True, parent=top)
                if not old:
                    return
                old = os.path.normpath(old)
                why = self.store.check_media_folder(old)
                if why:
                    return messagebox.showwarning(APP, why, parent=top)

                def confirm(res):
                    files, notes = res
                    if not files:
                        return messagebox.showinfo(APP, "이 폴더에는 옮길 파일이 없습니다.", parent=top)
                    if not messagebox.askyesno(
                            "미디어 폴더를 .resources 로 바꾸기",
                            f"「{old}」\n\n안의 {files:,}개 항목을 볼트의 .resources 로 옮기고,\n모든 노트 중 {notes:,}개의 그림·링크 경로를 고칩니다.\n"
                            "(.md 노트는 옮기지 않고, 이름이 겹치는 파일은 번호를 붙입니다. 먼저 복원 지점을 만듭니다.)\n\n바꿀까요?", parent=top):
                        return
                    self.flush()
                    cur_path = self.cur["path"] if self.cur else None

                    def finish(r):
                        moved, relinked = r
                        self.reload_notes()
                        n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
                        if n:
                            self.open_note(n, record=False)
                        refresh()
                        messagebox.showinfo(APP, f"{moved:,}개 항목을 옮기고 노트 {relinked:,}개의 링크를 고쳤습니다.\n이제 새 그림도 .resources 에 저장됩니다.", parent=top)
                    self.checkpoint("미디어 폴더 이전 전", lambda: self.run_task(
                        "미디어 폴더 옮기는 중", lambda prog, cancel: self.store.move_media_folder(old, prog), finish,
                        text="파일을 옮기고 노트의 링크를 고치는 중…", cancellable=False))
                self.run_task("확인하는 중", lambda prog, cancel: self.store.preview_media_folder(old, prog), confirm, text="노트에서 이 폴더를 가리키는 링크를 세는 중…")

            lab(p, "노트 폴더", font=(self.ui, 10, "bold")).pack(anchor="w")
            lab(p, "노트북 = 폴더(하위 폴더는 하위 노트북), 노트 = .md 파일", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(0, 6))
            field(p, "경로", root_var, 52, ("변경…", change_root))
            Btn(p, "노트 폴더 열기", lambda: os.startfile(self.store.root), padx=10, pady=3).pack(anchor="w", padx=(64, 0), pady=(4, 0))
            hr(p)
            lab(p, "그림·첨부 (볼트 안 숨김 폴더)", font=(self.ui, 10, "bold")).pack(anchor="w")
            lab(p, "웹 클리퍼로 저장한 그림 등은 노트 폴더(볼트) 안의 숨김 폴더 .resources 에 저장되고,\n노트에는 노트 위치 기준의 상대 경로로 연결됩니다. 따로 지정할 필요가 없습니다.",
                fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(0, 6))
            field(p, "경로", media_var, 52)
            row = tk.Frame(p, bg=C["bg"])
            row.pack(anchor="w", padx=(64, 0), pady=(6, 0))
            move_btn = Btn(row, "볼트 안으로 옮기기", lambda: apply_media("vault"), padx=10, pady=3)
            move_btn.pack(side="left")
            Btn(row, "열기", lambda: (self.store.ensure_media(), os.startfile(self.store.media_dir)), padx=10, pady=3).pack(side="left", padx=6)
            Btn(row, "다른 폴더를 .resources 로 바꾸기…", adopt_folder, padx=10, pady=3).pack(side="left")
            lab(p, "노트가 쓰던 미디어 폴더 이름이 다르면(attachments, images 등) 그 폴더를 직접 골라 .resources 로 모으고,\n모든 노트의 링크를 한꺼번에 고칩니다. 고른 뒤 몇 곳이 바뀌는지 보여 주고 확인을 받습니다.",
                fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", padx=(64, 0), pady=(6, 0))
            mode_note.pack(anchor="w", padx=(64, 0), pady=(8, 0))
            refresh()
            if self.store.media_is_vault:
                move_btn.pack_forget()

        def fonts_tab(p):
            title(p, "글꼴", "노트 목록과 노트의 글자 크기·굵기를 정합니다. 적용을 누르면 바로 바뀝니다.")
            fc = self.font_cfg()
            ls, lb = tk.StringVar(value=str(fc["list_size"])), tk.BooleanVar(value=fc["list_bold"])
            ns, nb = tk.StringVar(value=str(fc["note_size"])), tk.BooleanVar(value=fc["note_bold"])

            def section(name, size_var, bold_var, lo, hi):
                lab(p, name, font=(self.ui, 10, "bold")).pack(anchor="w", pady=(6, 4))
                row = tk.Frame(p, bg=C["bg"])
                row.pack(fill="x")
                lab(row, "글자 크기", width=9).pack(side="left")
                tk.Spinbox(row, from_=lo, to=hi, textvariable=size_var, width=5, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                           insertbackground=C["accent"], highlightthickness=1, highlightbackground=C["line"],
                           font=(self.ui, 10), buttonbackground=C["panel"]).pack(side="left", ipady=4)
                lab(row, "pt", fg=C["muted"], font=(self.ui, 9)).pack(side="left", padx=6)
                tk.Checkbutton(row, text="굵게", variable=bold_var, bg=C["bg"], fg=C["text"], activebackground=C["bg"],
                               selectcolor=C["bg"], font=(self.ui, 10)).pack(side="left", padx=18)
            section("노트 목록", ls, lb, 8, 20)
            prev1 = lab(p, "노트 목록 제목 미리보기", fg=C["text"])
            prev1.pack(anchor="w", pady=(8, 0))
            hr(p)
            section("노트 (에디터·렌더링)", ns, nb, 8, 28)
            prev2 = lab(p, "노트 본문 미리보기 — 가나다라 ABC abc 123", fg=C["text"])
            prev2.pack(anchor="w", pady=(8, 0))

            def preview(*_):
                try:
                    a, b = int(float(ls.get())), int(float(ns.get()))
                except ValueError:
                    return
                prev1.config(font=(self.ui, max(8, min(20, a)), "bold" if lb.get() else "normal"))
                prev2.config(font=(self.ui, max(8, min(28, b)), "bold" if nb.get() else "normal"))
            for v in (ls, lb, ns, nb):
                v.trace_add("write", preview)
            preview()
            row = tk.Frame(p, bg=C["bg"])
            row.pack(anchor="w", pady=(22, 0))
            Btn(row, "적용", lambda: self.root.after(20, lambda: self.set_fonts(ls.get(), lb.get(), ns.get(), nb.get())),
                kind="primary", bold=True, padx=22, pady=5).pack(side="left")
            Btn(row, "기본값으로", lambda: self.root.after(20, lambda: self.set_fonts(10, False, 11, False)), padx=14, pady=5).pack(side="left", padx=8)

        def sync_tab(p):
            syncui.tab(self, p, dict(lab=lab, title=title, hr=hr, copy=copy, Btn=Btn, C=C, top=top, ui=self.ui))

        def index_tab(p):
            title(p, "색인", "노트와 가져온 폴더를 빨리 찾으려고 만들어 둔 목록의 상태입니다. 노트 파일이 원본이고, 색인은 언제든 다시 만듭니다.")
            rows = {}
            for key, label in (("notes", "노트"), ("state", "상태"), ("docs", "가져온 폴더"), ("kept", "보관 중인 색인")):
                lab(p, label, font=(self.ui, 10, "bold")).pack(anchor="w", pady=(10, 0))
                rows[key] = lab(p, "…", fg=C["text"], wraplength=620)
                rows[key].pack(anchor="w", pady=(2, 0))
            lab(p, "가져온 폴더를 목록에서 빼도 이미 만든 색인은 지우지 않고 보관합니다. 같은 폴더를 다시 넣으면 그 색인을 되살리고 바뀐 파일만 읽습니다.",
                fg=C["muted"], font=(self.ui, 9), wraplength=620).pack(anchor="w", pady=(14, 0))
            Btn(p, "노트 다시 훑기", lambda: self.reload_notes(), padx=12, pady=4).pack(anchor="w", pady=(10, 0))
            alive = {"on": True}
            p.bind("<Destroy>", lambda e: alive.update(on=False) if e.widget is p else None)

            def tick():
                if not alive["on"]:
                    return
                try:
                    files, indexed = len(self.all_notes), self.store.index_count()
                    d, t = self.load_prog
                    rows["notes"].config(text=f"파일 {files:,}개 · 색인 {indexed:,}개" + (f" ({indexed / files:.0%})" if files else ""))
                    rows["state"].config(text=(f"처음 색인을 만드는 중… {d:,} / {t:,} ({d / t:.0%})" if t and d < t else "최신 상태입니다(바뀐 파일은 자동으로 다시 읽습니다)"))
                    counts, folders = self.docs.counts(), self.docs.folders()
                    rows["docs"].config(text="\n".join(f"{f.get('name') or f['path']}  —  색인 {counts.get(f['id'], 0):,}개" for f in folders) or "(없음)")
                    kept = self.docs.kept_counts()
                    rows["kept"].config(text=f"목록에서 뺀 폴더의 색인 {sum(kept.values()):,}개" if kept else "(없음)")
                except (tk.TclError, sqlite3.Error):
                    return
                p.after(1000, tick)
            tick()

        def planner_tab(p):
            title(p, "달력·할일", "달력과 할일, 그리고 일용직·건설직의 공수달력을 정합니다.")
            on = tk.BooleanVar(value=self.feat["cal"])
            gs = tk.BooleanVar(value=bool(st.read_config().get("cal_gongsu", False)))

            def apply_cal():
                self.feat["cal"] = on.get()
                st.write_config(use_cal=on.get(), cal_gongsu=gs.get())
                self.reload_notebooks()
                if self.nb == CAL:
                    self.show_empty(True)
            tk.Checkbutton(p, text="달력·할일 사용 (노트북 목록의 '바로가기'에 나타납니다)", variable=on, command=apply_cal, bg=C["bg"],
                           activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            hr(p)
            tk.Checkbutton(p, text="공수달력 사용 (날을 누르면 공수 0.5·1·1.5·2 를 적고, 달마다 합계를 계산)", variable=gs, command=apply_cal, bg=C["bg"],
                           activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            gg = tk.BooleanVar(value=bool(st.read_config().get("cal_google", True)))

            def set_google():
                st.write_config(cal_google=gg.get())
                if gg.get():
                    self.sync_holidays(force=True)
            tk.Checkbutton(p, text="구글 달력에서 대한민국 공휴일 가져오기 (로그인 없이 공개 달력을 한 달에 한 번 받음)", variable=gg, command=set_google, bg=C["bg"],
                           activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w", pady=(6, 0))
            cfg = st.read_config()
            for key, label in (("cal_wage", "단가 (1공수, 원)"), ("cal_meal", "일비 (하루, 원)")):
                row = tk.Frame(p, bg=C["bg"])
                row.pack(anchor="w", pady=4, padx=(24, 0))
                lab(row, label, width=16).pack(side="left")
                var = tk.StringVar(value=str(cfg.get(key) or ""))
                e = tk.Entry(row, textvariable=var, width=14, relief="flat", bd=0, bg=C["panel"], fg=C["text"], highlightthickness=1,
                             highlightbackground=C["line"], highlightcolor=C["accent"], font=(self.ui, 10))
                e.pack(side="left", ipady=4)

                def save(*_, k=key, v=var):
                    s = v.get().replace(",", "").strip()
                    try:
                        st.write_config(**{k: int(float(s)) if s else 0})
                    except ValueError:
                        return
                    if self.planner_view is not None:
                        self.planner_view.refresh()
                var.trace_add("write", save)
            lab(p, "공수 합계 × 단가 = 일당, 출근한 날 수 × 일비 = 일비. 공휴일은 구글 달력에서 받은 것을 쓰고, 못 받으면 내장 표(2024~2030년)로 표시합니다.", fg=C["muted"], font=(self.ui, 9),
                wraplength=620).pack(anchor="w", pady=(10, 0))

        pages = (("general", "일반", general), ("planner", "달력·할일", planner_tab), ("index", "색인", index_tab), ("folders", "폴더", folders_tab), ("imports", "가져오기", imports_tab), ("fonts", "글꼴", fonts_tab), ("theme", "테마·색상", theme_tab), ("versions", "노트 버전", versions_tab), ("sync", "동기화", sync_tab), ("clipper", "웹 클리퍼", clipper))

        def select(key):
            for k, b in tabs.items():
                b.set_on(k == key)
            for w in content.winfo_children():
                w.destroy()
            dict((k, f) for k, _, f in pages)[key](content)
            cv.yview_moveto(0)

        for key, label, _ in pages:
            b = Btn(nav, label, lambda k=key: select(k), kind="nav", padx=18, pady=8, anchor="w")
            b.pack(fill="x", padx=8, pady=1)
            tabs[key] = b
        foot.pack(side="bottom", fill="x", padx=28, pady=(0, 16), before=outer)
        Btn(foot, "닫기", top.destroy, kind="primary", padx=22, pady=5).pack(side="right")
        select(tab)

    # ------------------------------------------------------------ 단축키·종료
