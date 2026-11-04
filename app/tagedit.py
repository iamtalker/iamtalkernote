"""태그 편집(제목 아래 태그 박스·메모·이름 바꾸기·삭제·합치기): App 에서 그대로 옮겨 온 메서드 묶음.
App 이 TagEditMixin 을 물려받아 self.메서드() 처럼 그대로 부른다."""
from notes_shared import *  # noqa: F401,F403
import autotags


class TagEditMixin:
    def show_auto_tags(self):
        """전체 문서 또는 현재 검색 결과를 분석하고, 미리 본 뒤 일괄 추가한다."""
        top = self.tool_window(tr("자동 태그 추가"), "620x330")
        scope = tk.StringVar(value="all")
        existing_only = tk.BooleanVar(value=st.read_config().get("autoTagsExistingOnly", True))
        tk.Label(top, text=tr("문서마다 키워드 최대 3개와 확장자 태그를 추가합니다.\n기존 태그는 유지합니다. 본문이 없으면 제목을 분석합니다. 가져온 파일은 색인된 본문을 사용합니다."),
                 bg=C["bg"], fg=C["text"], wraplength=520, justify="left").pack(padx=20, pady=18)
        for value, label in (("all", tr("전체 문서 (가져온 폴더 포함)")), ("results", tr("현재 검색 결과 전체"))):
            tk.Radiobutton(top, text=label, variable=scope, value=value, bg=C["bg"], fg=C["text"],
                           selectcolor=C["panel"], anchor="w").pack(fill="x", padx=20)
        tk.Checkbutton(top, text=tr("이미 존재하는 태그로만 추가 (부족해도 새 단어로 채우지 않음)"),
                       variable=existing_only, bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                       anchor="w", wraplength=570).pack(fill="x", padx=20, pady=(12, 0))
        tk.Label(top, text=tr("본문이 없으면 제목을 분석합니다. 확장자 태그는 별도로 추가합니다 (txt·md 제외)."),
                 bg=C["bg"], fg=C["muted"], wraplength=570, justify="left").pack(fill="x", padx=20, pady=(6, 0))

        def start():
            self.flush()
            targets = (list(self.all_notes) + self.docs.list_docs()) if scope.get() == "all" else list(self.results)
            targets = list({(isinstance(n, docidx.Doc), n["path"]): n for n in targets if not n.get("trash")}.values())
            known = self.known_content_tags()
            only = existing_only.get()
            st.write_config(autoTagsExistingOnly=only)
            top.destroy()
            self.run_task(tr("자동 태그 분석"), lambda p, c: autotags.plan(targets, p, c, known, only),
                          lambda result: self.preview_auto_tags(result, len(targets)))
        Btn(top, tr("분석 후 미리보기"), start, kind="primary", padx=18, pady=6).pack(pady=15)

    def preview_auto_tags(self, result, total):
        rows, errors = result
        top = self.tool_window(tr("자동 태그 미리보기"), "900x560")
        summary = tr("분석 {0}개 · 추가할 문서 {1}개 · 읽기 실패 {2}개").format(total, len(rows), len(errors))
        tk.Label(top, text=summary, bg=C["bg"], fg=C["text"], padx=16, pady=12).pack(anchor="w")
        tk.Label(top, text=tr("기존 태그는 유지하고 중복은 추가하지 않습니다. 적용 전에 내용이 바뀐 문서는 건너뜁니다."),
                 bg=C["bg"], fg=C["muted"], wraplength=850).pack(padx=16)
        frame = tk.Frame(top, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=16, pady=12)
        table = ttk.Treeview(frame, columns=("path", "tags"), show="headings")
        table.heading("path", text=tr("문서")); table.heading("tags", text=tr("추가할 태그"))
        table.column("path", width=540); table.column("tags", width=270)
        scroll = ttk.Scrollbar(frame, command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y"); table.pack(fill="both", expand=True)
        page = [0]
        nav = tk.Frame(top, bg=C["bg"]); nav.pack(fill="x", padx=16, pady=8)
        counter = tk.Label(nav, bg=C["bg"], fg=C["text"])
        def draw(delta=0):
            page[0] = max(0, min(max(0, (len(rows) - 1) // 200), page[0] + delta))
            table.delete(*table.get_children())
            for n, _, tags in rows[page[0] * 200:(page[0] + 1) * 200]:
                table.insert("", "end", values=(n["path"], " ".join("#" + t for t in tags)))
            counter.config(text=f"{page[0] + 1} / {max(1, (len(rows) + 199) // 200)}")
        Btn(nav, tr("이전"), lambda: draw(-1)).pack(side="left")
        counter.pack(side="left", padx=12)
        Btn(nav, tr("다음"), lambda: draw(1)).pack(side="left")
        if errors:
            Btn(nav, tr("읽기 실패 보기"), lambda: messagebox.showinfo(APP, "\n".join(p + ": " + e for p, e in errors), parent=top)).pack(side="left", padx=10)
        def apply():
            top.destroy()
            self.flush()
            cur_path = self.cur["path"] if self.cur else None
            def finished(result):
                done, skipped, failures = result
                self.after_tag_change(cur_path)
                messagebox.showinfo(APP, tr("추가 완료 {0}개 · 변경되어 건너뜀 {1}개 · 실패 {2}개").format(done, skipped, len(failures))
                                    + ("\n\n" + "\n".join(p + ": " + e for p, e in failures) if failures else ""), parent=self.root)
            def write():
                self.run_task(tr("자동 태그 추가"), lambda p, c: autotags.apply(rows, self.store, self.docs, p, c), finished, cancellable=False)
            # 앱의 다른 편집 동작은 진행 창이 막고, 노트는 버전과 복원 지점으로 남긴다.
            self.checkpoint(tr("자동 태그 추가 전"), write) if any(not isinstance(n, docidx.Doc) for n, _, _ in rows) else write()
        if rows:
            Btn(nav, tr("이 태그들 추가"), apply, kind="primary", padx=18, pady=5).pack(side="right")
        draw()

    def edit_tags(self, e=None):
        """제목 아래 태그를 누르면 작은 박스가 열린다(조플린의 '태그 추가 및 제거'): 태그를 치고 Enter 하면 칩으로 쌓이고 다음 태그를 받는다.
        [확인] 을 눌러야 한꺼번에 들어가고 [취소](Esc)는 아무것도 바꾸지 않는다. 이미 있는 태그도 칩으로 보이며 × 로 뺀다."""
        if not self.cur or self.tag_edit:
            return
        self.flush()
        self.ac_tagc = (0.0, self.ac_tagc[1])   # 박스를 여는 순간 뒤에서 태그 개수를 세기 시작한다(열린 뒤 키 입력은 기다리지 않는다)
        self.ac_tags()
        box = tagac.TagBox(self.main, sorted(self.cur.get("tags", ())), self.ac_tags, C, (self.ui, 9),
                           lambda tags: self.finish_tags(True, tags), lambda: self.finish_tags(False), Btn, ime.composing, ime.cancel,
                           self.suggest_content_tags, tr("본문에서 태그 추천"))
        box.pack(side="top", fill="x", before=self.body)
        self.tagbtn.pack_forget()
        self.tag_labels.pack_forget()
        self.tag_edit = box
        box.ent.focus_set()

    def known_content_tags(self):
        known = {t for n in self.all_notes for t in n.get("tags", ())}
        known.update(self.docs.tag_counts())
        return known

    def suggest_content_tags(self):
        body = self.cur.get("body", "") if self.doc_open else self.text.get("1.0", "end-1c")
        return autotags.recommendations(body, self.cur["title"], self.cur.get("tags", ()),
                                        self.known_content_tags(), self.cur.get("ext", "md") if self.doc_open else "md")

    def finish_tags(self, save, tags=None):
        box = self.tag_edit
        if not box:
            return
        self.tag_edit = None
        box.close()
        box.destroy()
        self.tagbtn.pack(side="left", padx=(0, 8))
        self.tag_labels.pack(side="left")
        if save and self.cur and tags is not None:
            self.apply_tags(" ".join("#" + t for t in tags))
        self.update_status()
        if self.cur:
            (self.text if self.mode != "view" else self.lst).focus_set()

    def apply_tags(self, value):
        """입력칸의 태그로 노트를 고친다. 글 맨 아래의 '태그: #a #b' 줄에 적는다(없으면 만든다).
        본문 속 #해시태그나 머리말 tags 로 생긴 태그는 여기서 지울 수 없어서(글 자체를 고쳐야 한다) 알려 준다."""
        if self.doc_open:
            return self.apply_doc_tags(value)
        want = []
        for t in re.split(r"[,\s]+", value):
            t = t.strip().lstrip("#").strip()
            if t and len(t) <= 30 and not re.search(r"[\[\]()/<>]", t) and t not in want:
                want.append(t)
        T = self.text
        body = T.get("1.0", "end-1c")
        have = note_tags(body)
        off = len(body) - len(body_after_fm(body))   # 머리말의 'tags:' 줄을 '태그:' 줄로 착각해 건드리지 않게 머리말 뒤부터만 본다
        on_line = line_tags(body[off:])
        removed = have - set(want)
        stuck = sorted(t for t in removed if t not in on_line)       # 줄에 없는 태그는 지울 수 없다
        keep = [t for t in on_line if t not in removed]
        new_line = keep + [t for t in want if t not in have]
        if set(new_line) == set(on_line):
            if stuck:
                self.status.config(text=tr("본문에 직접 쓴 #태그는 여기서 못 지웁니다: ") + " ".join("#" + t for t in stuck))
            return
        line = "태그: " + " ".join("#" + t for t in new_line) if new_line else ""
        T.edit_separator()
        spans = [(m.start() + off, m.end() + off) for m in TAG_LINE.finditer(body[off:])]
        if spans:
            for k, (a, b) in reversed(list(enumerate(spans))):
                if k == 0 and line:
                    T.delete(f"1.0+{a}c", f"1.0+{b}c")
                    T.insert(f"1.0+{a}c", line)
                else:   # 둘째 줄부터(또는 태그가 없어졌으면 첫 줄도) 줄째로 지운다
                    end = b + 1 if b < len(body) else b
                    T.delete(f"1.0+{a}c", f"1.0+{end}c")
        else:
            tail = "" if body.endswith("\n\n") else ("\n" if body.endswith("\n") else "\n\n")
            T.insert("end-1c", f"{tail}{line}\n")
        T.edit_separator()
        self.dirty = True
        self.flush()                                                  # 바로 저장하고 목록·사이드바·상태 줄을 갱신
        if stuck:
            self.status.config(text=tr("태그를 저장했습니다. 본문에 직접 쓴 #태그는 못 지웁니다: ") + " ".join("#" + t for t in stuck))
        else:
            self.update_status(tr("태그 저장됨"))

    # ------------------------------------------------------------ 태그 목록: 우클릭으로 추가·이름 바꾸기·삭제
    def on_tag_menu(self, e):
        """태그 목록 우클릭: 이름 변경 · 삭제(둘 다 그 태그가 든 모든 노트에서). Ctrl/Shift+클릭으로 여러 개를 골랐으면 그 태그들 모두"""
        row = self.tagtree.identify_row(e.y)
        if not row:
            return
        if row not in self.tagtree.selection():   # 고른 태그들 밖을 누르면 그 태그 하나만 고른다
            self.tagtree.selection_set(row)
        tags = [self.tag_keys[int(i[2:])] for i in self.tagtree.selection()]
        m = tk.Menu(self.root, tearoff=0)
        if len(tags) == 1:
            m.add_command(label=tr("태그 이름 변경…"), command=lambda: self.tag_rename(tags))
            m.add_command(label=tr("태그 삭제…"), command=lambda: self.tag_delete(tags))
        else:
            m.add_command(label=tr('태그 {0}개를 하나의 이름으로 바꾸기(합치기)…').format(len(tags)), command=lambda: self.tag_rename(tags))
            m.add_command(label=tr('태그 {0}개 삭제…').format(len(tags)), command=lambda: self.tag_delete(tags))
        m.tk_popup(e.x_root, e.y_root)
        return "break"

    def apply_doc_tags(self, value):
        """가져온 파일의 태그: 원본은 건드리지 않고 앱의 DB 에만 적는다(입력칸의 태그가 곧 전체 태그)"""
        n = self.cur
        want = [t for t in (clean_tag_name(x) for x in re.split(r"[,\s]+", value)) if t]
        want = list(dict.fromkeys(want))
        if set(want) != set(n.get("tags", ())):
            self.docs.set_annot(n["path"], tags=want)
            n["tags"] = set(want)
            self.reload_tags()
            self.refresh(keep_page=True)
            self.status.config(text=tr("태그를 저장했습니다 (원본 파일은 그대로)"))
        self.update_status()

    def edit_memo(self):
        """가져온 파일에 메모를 붙인다: 앱의 DB 에만 저장되고 검색에도 잡힌다(원본 파일은 그대로)"""
        n = self.cur
        if not (self.doc_open and n):
            return
        top = self.tool_window(tr("메모 — ") + n["title"], "520x340")
        tk.Label(top, text=tr("이 파일에 붙이는 메모입니다. 원본 파일은 건드리지 않고 앱의 DB 에만 저장되며, 검색에도 잡힙니다."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", wraplength=480, padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        box = tk.Text(top, wrap="word", font=(self.ui, 10), bg=C["panel"], fg=C["text"], insertbackground=C["accent"], relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"], padx=10, pady=8, undo=True)
        box.pack(fill="both", expand=True, padx=16)
        box.insert("1.0", n.get("memo", ""))
        box.focus_set()

        def save():
            memo = box.get("1.0", "end-1c").strip()
            self.docs.set_annot(n["path"], memo=memo)
            n["memo"] = memo
            top.destroy()
            self.refresh(keep_page=True)
            if self.cur is n:
                self.show_doc(n, native=self.pv_active)
        Btn(btns, tr("저장"), save, kind="primary", bold=True, padx=22, pady=5).pack(side="right")
        Btn(btns, tr("취소"), top.destroy, padx=14, pady=5).pack(side="right", padx=8)

    def tag_new(self, targets):
        """노트 목록에서 고른 노트(들)에 태그를 붙인다(공백·쉼표로 여러 개 가능)"""
        who = tr('노트 {0}개').format(len(targets)) if len(targets) > 1 else tr("이 노트")
        name = simpledialog.askstring(tr("태그 추가"), tr('{0}에 추가할 태그를 적으세요.\n(공백이나 쉼표로 여러 개, 앞의 # 는 없어도 됩니다)').format(who), parent=self.root)
        if name is None:
            return
        tags = [t for t in (clean_tag_name(x) for x in re.split(r"[,\s]+", name)) if t]
        if not tags:
            return messagebox.showinfo(APP, tr("쓸 수 있는 태그가 없습니다. (비었거나 30자를 넘거나 [ ] ( ) / < > 가 들어 있습니다)"), parent=self.root)
        self.tag_add_to(targets, list(dict.fromkeys(tags)))

    def tag_add_to(self, targets, tags):
        """노트(들)에 태그들을 더한다: 글 아래의 '태그:' 줄에 적는다"""
        self.flush()
        cur_path = self.cur["path"] if self.cur else None
        done = 0
        for n in targets:
            try:
                body, changed = n.read(), False
                for t in tags:
                    body, ok = add_tag(body, t)
                    changed = changed or ok
                if changed:
                    self.store.save(n["path"], body, versioned=True, force=True, ev="tags")
                    done += 1
            except OSError as ex:
                return messagebox.showerror(APP, tr('태그를 더하지 못했습니다.\n{0}').format(ex), parent=self.root)
        self.after_tag_change(cur_path)
        self.status.config(text=tr('태그 {0} 를 노트 {1}개에 더했습니다').format(' '.join('#' + t for t in tags), done)
                                + ("" if done == len(targets) else tr(' (나머지 {0}개는 이미 있음)').format(len(targets) - done)))

    def tag_rename(self, tags):
        """tags(하나 이상)를 모두 새 이름 하나로 바꾼다. 여러 개를 골랐으면 그 이름으로 합쳐진다"""
        if len(tags) == 1:
            title, ask, suggest = tr("태그 이름 바꾸기"), tr("'{0}' 의 새 이름 (공백은 _ 로 바뀝니다):").format(tags[0]), re.sub(r"\s+", "_", tags[0])
        else:
            title, suggest = tr("태그 합치기"), re.sub(r"\s+", "_", tags[0])
            ask = tr('선택한 태그 {0}개({1}{2})를\n모두 이 이름 하나로 바꿉니다 (공백은 _ 로 바뀝니다):').format(len(tags), ', '.join(tags[:4]), ' …' if len(tags) > 4 else '')
        name = simpledialog.askstring(title, ask, initialvalue=suggest, parent=self.root)
        if name is None:
            return
        new = clean_tag_name(name)
        if not new:
            return messagebox.showinfo(APP, tr("쓸 수 없는 이름입니다. (비었거나 30자를 넘거나 [ ] ( ) / < > , 가 들어 있습니다)"), parent=self.root)
        if tags == [new]:
            return
        self.tag_apply(tags, new)

    def tag_delete(self, tags):
        self.tag_apply(tags, None)

    def tag_apply(self, tags, new):
        """태그들(tags)을 가진 모든 노트에서 new 로 바꾸거나(None 이면 지우고) 미리 몇 곳이 바뀌는지 보여 준 뒤 적용한다"""
        self.flush()
        want = set(tags)
        targets = [n for n in self.all_notes if want & n["tags"]]
        names = ", ".join(f"'{t}'" for t in tags[:5]) + (tr(' 외 {0}개').format(len(tags) - 5) if len(tags) > 5 else "")

        def scan(prog, cancel):
            out, total = [], {"fm": 0, "line": 0, "inline": 0, "stuck": 0}
            for i, n in enumerate(targets):
                if cancel():
                    return None
                if i % 50 == 0:
                    prog(i, len(targets))
                body = orig = n.read()
                body, c = edit_tags(body, tags, new)
                for k in total:
                    total[k] += c[k]
                if body != orig:
                    out.append((n, autotags.digest(orig), body))
            return out, total, self.docs.tag_use_count(tags)

        def confirm(res):
            if res is None:
                return
            items, c, dcount = res
            if not items and not dcount:
                return messagebox.showinfo(APP, tr("바꿀 곳이 없습니다.") + (tr('\n(본문 속 #태그 {0}곳은 이 이름으로 바꿀 수 없습니다)').format(c['stuck']) if c["stuck"] else ""), parent=self.root)
            parts = [tr('{0} {1}곳').format(label, c[k]) for k, label in (("fm", tr("머리말")), ("line", tr("태그 줄")), ("inline", tr("본문 #태그"))) if c[k]]
            what = (tr("{0} → '{1}' 로 ").format(names, new) + (tr("합칩니다") if len(tags) > 1 else tr("바꿉니다"))) if new else tr('{0} 를 지웁니다').format(names)
            extra = ""
            if new is None and c["inline"]:
                extra += tr("\n본문 속 #태그는 글에서 그 글자가 지워집니다.")
            if c["stuck"]:
                extra += tr("\n본문 속 #태그 {0}곳은 '{1}' 가 본문 태그로 쓸 수 없는 이름이라 그대로 남습니다.").format(c['stuck'], new)
            if dcount:
                parts.append(tr('가져온 파일 {0:,}개').format(dcount))
            if not messagebox.askyesno(APP, tr('{0}.\n\n노트 {1:,}개 ({2}){3}\n\n이전 내용은 노트 버전으로 남고, 수정 시각은 바뀌지 않습니다. 계속할까요?').format(what, len(items), ', '.join(parts), extra), parent=self.root):
                return
            self.checkpoint(tr("태그 정리 전"), lambda: self.tag_write(items, tags, new)) if len(items) >= 5 else self.tag_write(items, tags, new)
        self.run_task(tr("태그 확인"), scan, confirm, text=tr("태그가 든 노트를 확인하는 중…"))

    def tag_write(self, items, tags, new):
        cur_path = self.cur["path"] if self.cur else None

        def work(progress, cancelled):
            done, skipped, errors = 0, 0, []
            for i, (n, before, body) in enumerate(items):
                try:
                    if autotags.digest(n.read()) != before:
                        skipped += 1
                    else:
                        self.store.save(n["path"], body, versioned=True, force=True, touch=False, ev="tags")
                        done += 1
                except Exception as ex:
                    errors.append((n["path"], str(ex)))
                progress(i + 1, len(items), tr("노트 태그 저장 중…"))
            try:
                dn = self.docs.rename_tags(tags, new, progress=lambda d, t: progress(d, t, tr("가져온 문서 태그 저장 중…")))
            except Exception as ex:
                dn = 0
                errors.append((tr("가져온 문서"), str(ex)))
            return done, dn, skipped, errors

        def finished(result):
            done, dn, skipped, errors = result
            if self.tag in tags:
                self.tag = new
            message = tr('노트 {0:,}개').format(done) + (tr(', 가져온 파일 {0:,}개').format(dn) if dn else "") + tr("의 태그를 ") + (tr("바꿨습니다.") if new else tr("지웠습니다."))
            if skipped or errors:
                message += "\n" + tr("변경되어 건너뜀 {0}개 · 실패 {1}개").format(skipped, len(errors))
            if errors:
                message += "\n" + "\n".join(p + ": " + e for p, e in errors[:10])
            # 마지막 목록 재색인도 worker에서 읽고 UI에는 결과만 적용한다.
            def loaded(notes):
                self.apply_loaded(notes, keep_scroll=True)
                n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
                if n:
                    self.open_note(n, record=False)
                messagebox.showinfo(APP, message, parent=self.root)
            self.run_task(tr("태그 목록 갱신"), lambda p, c: self.read_all_notes(), loaded, cancellable=False)
        self.run_task(tr("태그 바꾸는 중"), work, finished, text=tr("노트 태그 저장 중…"), cancellable=False)

    def after_tag_change(self, cur_path):
        """태그를 바꾼 뒤: 노트를 다시 읽고 사이드바·목록·열려 있던 노트를 갱신한다"""
        self.reload_notes()
        self.reload_tags()
        n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
        if n:
            self.open_note(n, record=False)   # 바뀐 글을 다시 읽어 와서 낡은 내용으로 덮어쓰지 않게
