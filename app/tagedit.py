"""태그 편집(맨 아래 태그 박스·메모·이름 바꾸기·삭제·합치기): App 에서 그대로 옮겨 온 메서드 묶음(동작 변경 없음).
App 이 TagEditMixin 을 물려받아 self.메서드() 처럼 그대로 부른다."""
from notes_shared import *  # noqa: F401,F403


class TagEditMixin:
    def edit_tags(self, e=None):
        """맨 아래 줄의 태그를 누르면 하단에 작은 박스가 열린다(조플린의 '태그 추가 및 제거'): 태그를 치고 Enter 하면 칩으로 쌓이고 다음 태그를 받는다.
        [확인] 을 눌러야 한꺼번에 들어가고 [취소](Esc)는 아무것도 바꾸지 않는다. 이미 있는 태그도 칩으로 보이며 × 로 뺀다."""
        if not self.cur or self.tag_edit:
            return
        self.flush()
        self.ac_tagc = (0.0, self.ac_tagc[1])   # 박스를 여는 순간 뒤에서 태그 개수를 세기 시작한다(열린 뒤 키 입력은 기다리지 않는다)
        self.ac_tags()
        box = tagac.TagBox(self.main, sorted(self.cur.get("tags", ())), self.ac_tags, C, (self.ui, 9),
                           lambda tags: self.finish_tags(True, tags), lambda: self.finish_tags(False), Btn, ime.composing, ime.cancel)
        box.pack(side="bottom", fill="x", after=self.status_sep)   # 맨 아래 상태줄 바로 위
        self.tagbtn.pack_forget()
        self.tag_edit = box
        box.ent.focus_set()

    def finish_tags(self, save, tags=None):
        box = self.tag_edit
        if not box:
            return
        self.tag_edit = None
        box.close()
        box.destroy()
        self.tagbtn.pack(side="left")
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
                self.status.config(text="본문에 직접 쓴 #태그는 여기서 못 지웁니다: " + " ".join("#" + t for t in stuck))
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
            self.status.config(text="태그를 저장했습니다. 본문에 직접 쓴 #태그는 못 지웁니다: " + " ".join("#" + t for t in stuck))
        else:
            self.update_status("태그 저장됨")

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
            m.add_command(label="태그 이름 변경…", command=lambda: self.tag_rename(tags))
            m.add_command(label="태그 삭제…", command=lambda: self.tag_delete(tags))
        else:
            m.add_command(label=f"태그 {len(tags)}개를 하나의 이름으로 바꾸기(합치기)…", command=lambda: self.tag_rename(tags))
            m.add_command(label=f"태그 {len(tags)}개 삭제…", command=lambda: self.tag_delete(tags))
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
            self.status.config(text="태그를 저장했습니다 (원본 파일은 그대로)")
        self.update_status()

    def edit_memo(self):
        """가져온 파일에 메모를 붙인다: 앱의 DB 에만 저장되고 검색에도 잡힌다(원본 파일은 그대로)"""
        n = self.cur
        if not (self.doc_open and n):
            return
        top = self.tool_window("메모 — " + n["title"], "520x340")
        tk.Label(top, text="이 파일에 붙이는 메모입니다. 원본 파일은 건드리지 않고 앱의 DB 에만 저장되며, 검색에도 잡힙니다.",
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
        Btn(btns, "저장", save, kind="primary", bold=True, padx=22, pady=5).pack(side="right")
        Btn(btns, "취소", top.destroy, padx=14, pady=5).pack(side="right", padx=8)

    def tag_new(self, targets):
        """노트 목록에서 고른 노트(들)에 태그를 붙인다(공백·쉼표로 여러 개 가능)"""
        who = f"노트 {len(targets)}개" if len(targets) > 1 else "이 노트"
        name = simpledialog.askstring("태그 추가", f"{who}에 추가할 태그를 적으세요.\n(공백이나 쉼표로 여러 개, 앞의 # 는 없어도 됩니다)", parent=self.root)
        if name is None:
            return
        tags = [t for t in (clean_tag_name(x) for x in re.split(r"[,\s]+", name)) if t]
        if not tags:
            return messagebox.showinfo(APP, "쓸 수 있는 태그가 없습니다. (비었거나 30자를 넘거나 [ ] ( ) / < > 가 들어 있습니다)", parent=self.root)
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
                return messagebox.showerror(APP, f"태그를 더하지 못했습니다.\n{ex}", parent=self.root)
        self.after_tag_change(cur_path)
        self.status.config(text=f"태그 {' '.join('#' + t for t in tags)} 를 노트 {done}개에 더했습니다"
                                + ("" if done == len(targets) else f" (나머지 {len(targets) - done}개는 이미 있음)"))

    def tag_rename(self, tags):
        """tags(하나 이상)를 모두 새 이름 하나로 바꾼다. 여러 개를 골랐으면 그 이름으로 합쳐진다"""
        if len(tags) == 1:
            title, ask, suggest = "태그 이름 바꾸기", f"'{tags[0]}' 의 새 이름 (공백은 _ 로 바뀝니다):", re.sub(r"\s+", "_", tags[0])
        else:
            title, suggest = "태그 합치기", re.sub(r"\s+", "_", tags[0])
            ask = f"선택한 태그 {len(tags)}개({', '.join(tags[:4])}{' …' if len(tags) > 4 else ''})를\n모두 이 이름 하나로 바꿉니다 (공백은 _ 로 바뀝니다):"
        name = simpledialog.askstring(title, ask, initialvalue=suggest, parent=self.root)
        if name is None:
            return
        new = clean_tag_name(name)
        if not new:
            return messagebox.showinfo(APP, "쓸 수 없는 이름입니다. (비었거나 30자를 넘거나 [ ] ( ) / < > , 가 들어 있습니다)", parent=self.root)
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
        names = ", ".join(f"'{t}'" for t in tags[:5]) + (f" 외 {len(tags) - 5}개" if len(tags) > 5 else "")

        def scan(prog, cancel):
            out, total = [], {"fm": 0, "line": 0, "inline": 0, "stuck": 0}
            for i, n in enumerate(targets):
                if cancel():
                    return None
                if i % 50 == 0:
                    prog(i, len(targets))
                body = orig = n.read()
                for t in tags:
                    if t == new:
                        continue
                    body, c = edit_tag(body, t, new)
                    for k in total:
                        total[k] += c[k]
                if body != orig:
                    out.append((n, body))
            return out, total

        def confirm(res):
            if res is None:
                return
            items, c = res
            dcount = self.docs.tag_use_count(tags)   # 가져온 파일에 붙인 같은 태그(원본은 그대로, 앱의 DB 만 바뀐다)
            if not items and not dcount:
                return messagebox.showinfo(APP, "바꿀 곳이 없습니다." + (f"\n(본문 속 #태그 {c['stuck']}곳은 이 이름으로 바꿀 수 없습니다)" if c["stuck"] else ""), parent=self.root)
            parts = [f"{label} {c[k]}곳" for k, label in (("fm", "머리말"), ("line", "태그 줄"), ("inline", "본문 #태그")) if c[k]]
            what = (f"{names} → '{new}' 로 " + ("합칩니다" if len(tags) > 1 else "바꿉니다")) if new else f"{names} 를 지웁니다"
            extra = ""
            if new is None and c["inline"]:
                extra += "\n본문 속 #태그는 글에서 그 글자가 지워집니다."
            if c["stuck"]:
                extra += f"\n본문 속 #태그 {c['stuck']}곳은 '{new}' 가 본문 태그로 쓸 수 없는 이름이라 그대로 남습니다."
            if dcount:
                parts.append(f"가져온 파일 {dcount:,}개")
            if not messagebox.askyesno(APP, f"{what}.\n\n노트 {len(items):,}개 ({', '.join(parts)}){extra}\n\n"
                                            "이전 내용은 노트 버전으로 남고, 수정 시각은 바뀌지 않습니다. 계속할까요?", parent=self.root):
                return
            self.checkpoint("태그 정리 전", lambda: self.tag_write(items, tags, new)) if len(items) >= 5 else self.tag_write(items, tags, new)
        self.run_task("태그 확인", scan, confirm, text="태그가 든 노트를 확인하는 중…")

    def tag_write(self, items, tags, new):
        cur_path = self.cur["path"] if self.cur else None
        top = self.tool_window("태그 바꾸는 중", "420x110", native=True)
        msg = tk.Label(top, text="", bg=C["bg"], fg=C["text"], font=(self.ui, 10), pady=24)
        msg.pack()
        top.protocol("WM_DELETE_WINDOW", lambda: None)
        done = 0
        for i, (n, body) in enumerate(items):
            if i % 10 == 0:
                msg.config(text=f"노트의 태그를 바꾸는 중… {i:,} / {len(items):,}")
                top.update()
            try:   # 수정 시각은 그대로 두고(touch=False), 이전 내용은 버전으로 남긴다(force)
                self.store.save(n["path"], body, versioned=True, force=True, touch=False, ev="tags")
                done += 1
            except OSError:
                pass
        top.destroy()
        dn = self.docs.rename_tags(tags, new)   # 가져온 파일의 태그
        if self.tag in tags:
            self.tag = new
        self.after_tag_change(cur_path)
        messagebox.showinfo(APP, f"노트 {done:,}개" + (f", 가져온 파일 {dn:,}개" if dn else "") + "의 태그를 " + ("바꿨습니다." if new else "지웠습니다."), parent=self.root)

    def after_tag_change(self, cur_path):
        """태그를 바꾼 뒤: 노트를 다시 읽고 사이드바·목록·열려 있던 노트를 갱신한다"""
        self.reload_notes()
        self.reload_tags()
        n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
        if n:
            self.open_note(n, record=False)   # 바뀐 글을 다시 읽어 와서 낡은 내용으로 덮어쓰지 않게
