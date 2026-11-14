"""저장된 검색(스마트 폴더)의 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class SavedSearchMixin:
    # ---- 저장된 검색(스마트 폴더): 검색식·기간·태그·정렬을 이름 붙여 저장해 두고, 고르면 그 조건을 그대로 적용한다
    def smart_list(self):
        return [s for s in st.read_config().get("smart", []) if isinstance(s, dict) and s.get("id")]

    def save_search(self, overwrite=None):
        """지금의 검색(검색어·기간·태그·정렬)을 저장한다. overwrite 는 덮어쓸 저장된 검색의 id"""
        q, f, t, tag = self.q.get().strip(), self.d_from.get().strip(), self.d_to.get().strip(), self.tag
        if not (q or f or t or tag or self.tag_none or self.adv_conditions):
            return messagebox.showinfo(APP, tr("저장할 검색이 없습니다. 검색어나 기간, 태그를 먼저 정하세요."), parent=self.root)
        lst = self.smart_list()
        cond = {"q": q, "d_from": f, "d_to": t, "tag": tag or "", "tag_none": self.tag_none,
                "advanced": [dict(x) for x in self.adv_conditions], "sort": self.sort, "asc": self.asc}
        if overwrite:
            for s in lst:
                if s["id"] == overwrite:
                    s.update(cond)
            sid = overwrite
        else:
            default_name = "태그 없음" if self.tag_none else f"# {tag}" if tag else "고급 검색" if self.adv_conditions else "검색"
            name = simpledialog.askstring(tr("검색 저장"), tr("이 검색의 이름:"), initialvalue=q or tr(default_name), parent=self.root)
            if not name or not name.strip():
                return
            sid = secrets.token_hex(4)
            lst.append({"id": sid, "name": name.strip(), **cond})
        st.write_config(smart=lst)
        self.nb = "@smart:" + sid
        self.reload_notebooks()
        self.status.config(text=tr("검색을 저장했습니다 (왼쪽 '저장된 검색')"))

    def open_smart(self, key):
        s = next((x for x in self.smart_list() if "@smart:" + x["id"] == key), None)
        if not s:
            return
        self.flush()
        self.close_note()
        self.nb = key
        self.tag = s.get("tag") or None
        self.tag_none = bool(s.get("tag_none", False))
        self.adv_conditions = [dict(x) for x in s.get("advanced", []) if isinstance(x, dict)]
        self.sort, self.asc = (s.get("sort") if s.get("sort") in self.sort_names else "relevance"), bool(s.get("asc"))
        self.d_from.set(s.get("d_from", ""))
        self.d_to.set(s.get("d_to", ""))
        if (s.get("d_from") or s.get("d_to")) and not self.date_row.winfo_ismapped():
            self.toggle_date()
        self.q.set(s.get("q", ""))
        self.apply_loaded(self.all_notes)

    def smart_menu(self, key):
        """저장된 검색 우클릭 메뉴용: (이름 바꾸기 · 지금 검색으로 덮어쓰기 · 삭제)"""
        sid = key[7:]
        s = next((x for x in self.smart_list() if x["id"] == sid), None)
        if not s:
            return

        def rename():
            name = simpledialog.askstring(tr("이름 바꾸기"), tr("저장된 검색의 이름:"), initialvalue=s["name"], parent=self.root)
            if name and name.strip():
                lst = self.smart_list()
                for x in lst:
                    if x["id"] == sid:
                        x["name"] = name.strip()
                st.write_config(smart=lst)
                self.reload_notebooks()

        def delete():
            if not messagebox.askyesno(APP, tr('저장된 검색 「{0}」을(를) 지울까요?\n(노트와 파일은 그대로입니다)').format(s['name']), parent=self.root):
                return
            st.write_config(smart=[x for x in self.smart_list() if x["id"] != sid])
            if self.nb == key:
                self.nb = ALL
                self.apply_loaded(self.all_notes)
            else:
                self.reload_notebooks()
        return [(tr("이름 바꾸기…"), rename), (tr("지금의 검색으로 덮어쓰기"), lambda: self.save_search(overwrite=sid)), (tr("삭제"), delete)]

    def in_nb(self, n):
        """지금 고른 노트북에 속한 노트인가 (하위 노트북의 노트 포함)"""
        if self.nb == ALL:
            return True
        if self.nb in (CAL, TRASH):
            return False
        if self.nb == FAVS:
            return self.is_fav(n)
        if self.nb == "":
            return n["nb"] == ""
        return n["nb"] == self.nb or n["nb"].startswith(self.nb + "/")

    def visible_notebooks(self):
        """노트북 목록에 보일 폴더: 달력 마크다운 폴더(달력/)는 '바로가기 > 달력·할일' 로만 들어가므로 뺀다"""
        books, self._books_once = getattr(self, "_books_once", None), None   # 노트 목록을 읽으며 이미 훑었으면 그것을 한 번만 쓴다
        if books is None:
            books = self.store.notebooks()
        return [n for n in books if n != pm.MD_DIR and not n.startswith(pm.MD_DIR + "/")]

    def reload_notebooks(self):
        names = self.visible_notebooks()
        if OUTL not in names:
            try:
                self.store.create_notebook(OUTL)
                names = self.visible_notebooks()
            except OSError:
                pass
        outl_names = [n for n in names if n == OUTL or n.startswith(OUTL + "/")]
        dfolders = self.docs.folders()
        doc_keys = ["@docs"] if dfolders else []
        doc_counts = self.docs.counts() if dfolders else {}
        for folder in dfolders:
            root_key = "@doc:" + folder["id"]
            doc_keys.append(root_key)
            subfolders = self.docs.subfolders(folder["id"])
            for rel, count in sorted(subfolders.items(), key=lambda item: (item[0].count("/"), item[0].lower())):
                doc_key = root_key + "/" + rel
                doc_keys.append(doc_key)
                doc_counts[doc_key] = count
        smarts = self.smart_list()
        smart_keys = (["@smarts"] + ["@smart:" + s["id"] for s in smarts]) if smarts else []
        if self.nb not in (ALL, "", FAVS, QUICK, CAL, TRASH) and self.nb not in names and self.nb not in doc_keys and self.nb not in smart_keys:
            self.nb = ALL
        if not self.feat["outl"] and self.nb in outl_names:
            self.nb = ALL
        outl = outl_names if self.feat["outl"] else []
        quick = ([FAVS] if self.feat["favs"] else []) + outl + ([CAL] if self.feat["cal"] else [])
        if self.nb == CAL and not self.feat["cal"]:
            self.nb = ALL
        if self.nb == FAVS and not self.feat["favs"]:
            self.nb = ALL
        self.nb_keys = [ALL] + ([QUICK] + quick if quick else []) + [""] + [n for n in names if n not in outl_names] + doc_keys + smart_keys + [TRASH]
        self.prune_folder_meta()
        direct = {}
        for n in self.all_notes:
            direct[n["nb"]] = direct.get(n["nb"], 0) + 1
        self.nb_direct = direct
        total = lambda key: sum(c for k, c in direct.items() if k == key or k.startswith(key + "/"))  # noqa: E731
        self.quiet = True
        self.nbtree.delete(*self.nbtree.get_children())
        idx = {key: i for i, key in enumerate(self.nb_keys)}
        for i, key in enumerate(self.nb_keys):
            if key == QUICK:
                label, count, parent = tr("바로가기"), None, ""
            elif key == FAVS:
                label, count, parent = tr("즐겨찾기"), sum(1 for n in self.all_notes if self.is_fav(n)), f"nb{idx[QUICK]}"
            elif key == OUTL:
                label, count, parent = tr("아웃라이너"), total(key), f"nb{idx[QUICK]}"
            elif key == TRASH:
                try:
                    n_trash = len(os.listdir(self.store.trash_dir))
                except OSError:
                    n_trash = 0
                label, count, parent = tr("🗑 휴지통"), n_trash, ""
            elif key == CAL:
                label, count, parent = tr("달력·할일"), sum(1 for t in self.planner.todos if not t["done"]), f"nb{idx[QUICK]}"
            elif key == ALL:
                label, count, parent = tr("모든 파일"), len(self.all_notes) + sum(doc_counts.get(f["id"], 0) for f in dfolders), ""   # 노트 + 가져온 문서
            elif key == "":
                label, count, parent = self.store.root_name, len(self.all_notes) or None, ""   # 저장 폴더 아래 전체 노트 수(바로 있는 노트 + 하위 노트북 노트, 하위 노트북 줄과 같은 방식)
            elif key == "@docs":
                n_docs = sum(doc_counts.get(f["id"], 0) for f in dfolders)
                label, count, parent = tr("가져온 폴더"), n_docs or None, ""
            elif key.startswith("@doc:"):
                fid, rel = self.doc_key_parts(key)
                root_key = "@doc:" + fid
                label = self.nb_label(key)
                # 최상위 가져온 폴더는 하위 폴더까지 포함한 전체 수, 하위 폴더는 그 폴더 아래 수.
                n_docs = doc_counts.get(fid, 0) if not rel else doc_counts.get(key, 0)
                count = n_docs or None
                parent_key = root_key + ("/" + rel.rpartition("/")[0] if "/" in rel else "") if rel else "@docs"
                parent = f"nb{idx[parent_key]}"
            elif key == "@smarts":
                label, count, parent = tr("저장된 검색"), None, ""
            elif key.startswith("@smart:"):
                label, count, parent = self.nb_label(key), None, f"nb{idx['@smarts']}"
            else:
                label, count = self.nb_short(key), total(key)
                # 최상위 노트북은 저장 폴더 항목(scrapbook) 아래에 들여써서 보여 준다
                parent = f"nb{idx[key.rsplit('/', 1)[0]]}" if "/" in key else f"nb{idx['']}"
            self.nbtree.insert(parent, "end", iid=f"nb{i}", text="  " + label + ("" if count is None else f"   {count:,}"), values=("" if count is None else f"{count:,}",),
                               open=self.nb_open.get(key, not key.startswith("@doc:")))   # 가져온 폴더(와 그 하위 폴더)는 기본으로 접어 둔다
        self.nbtree.selection_set(f"nb{idx[self.nb]}")
        self.nbtree.see(f"nb{idx[self.nb]}")   # 고른 항목이 접힌 폴더 안이면 그 위쪽만 펼쳐 보인다
        texts = []

        def collect(parent=""):
            for c in self.nbtree.get_children(parent):
                texts.append(self.nbtree.set(c, "n"))
                collect(c)
        collect()
        self.fit_count(self.nbtree, texts)
        self.quiet = False
        self.root_label.config(text=self.store.root)

    def reload_tags(self):
        if not self.show["tags"]:
            return   # 태그 보기를 켤 때 만든다(태그가 많으면 느리다)
        counts = {}
        if self.tag_global:
            sources = self.all_notes
            doc_counts = self.docs.tag_counts()
            untagged = sum(not n["tags"] for n in sources) + self.docs.untagged_count()
        else:
            sources = self.notes
            doc_counts = {}
            untagged = sum(not n["tags"] for n in sources)
        for n in sources:
            for t in n["tags"]:
                counts[t] = counts.get(t, 0) + 1
        for t, c in doc_counts.items():
            counts[t] = counts.get(t, 0) + c
        self.note_tag_set = set(counts)   # 노트·가져온 파일에 붙은 태그(이 태그는 누르면 노트를 거른다)
        # 폴더 태그: 그 태그가 붙은 폴더 수(폴더 자체에 붙은 것이라 노트·파일 수에는 더하지 않는다)
        self.ftag_map = {}
        for key, tags in self.docs.folder_tags().items():
            if key not in getattr(self, "nb_keys", []):
                continue
            for t in tags:
                self.ftag_map.setdefault(t, []).append(key)
                counts[t] = counts.get(t, 0) + 1
        self.tag_keys = [None] + tagac.ordered_tags(counts, getattr(self, "tag_sort", "frequency"))
        self.quiet = True
        self.tagtree.delete(*self.tagtree.get_children())
        self.tagtree.insert("", "end", iid="tg0", text=f"  {tr('태그 없음')}   {untagged:,}", values=(f"{untagged:,}",))
        for i, t in enumerate(self.tag_keys[1:], 1):
            self.tagtree.insert("", "end", iid=f"tg{i}", text="  # " + t + f"   {counts[t]:,}", values=(f"{counts[t]:,}",))
        selection = self.tagtree.selection()
        if selection:
            self.tagtree.selection_remove(*selection)
        if self.tag_none:
            self.tagtree.selection_set("tg0")
        elif self.tag in self.tag_keys[1:]:
            self.tagtree.selection_set(f"tg{self.tag_keys.index(self.tag)}")
        self.fit_count(self.tagtree, [f"{untagged:,}"] + [f"{c:,}" for c in list(counts.values())[:200]])
        self.quiet = False

    def show_tag_sort(self):
        if getattr(self, "tag_sort_menu", None):
            self.tag_sort_menu.destroy()
        menu = self.tag_sort_menu = tk.Menu(self.root, tearoff=0)
        selected = self.tag_sort_selection = tk.StringVar(master=self.root, value=self.tag_sort)
        for value, label in (("frequency", tr("빈도순")), ("name", tr("이름순 (한글 → 영어)"))):
            menu.add_radiobutton(label=label, variable=selected, value=value,
                                 command=lambda value=value: self.change_tag_sort(value))
        try:
            menu.tk_popup(self.tag_sort_btn.winfo_rootx(), self.tag_sort_btn.winfo_rooty() + self.tag_sort_btn.winfo_height())
        finally:
            menu.grab_release()

    def change_tag_sort(self, mode):
        self.tag_sort = "name" if mode == "name" else "frequency"
        st.write_config(tagSort=self.tag_sort)
        self.tag_sort_btn.config(text=tr("이름순") if self.tag_sort == "name" else tr("빈도순"))
        self.reload_tags()

    def toggle_tag_scope(self):
        self.tag_global = not self.tag_global
        st.write_config(tagGlobal=self.tag_global)
        self.tag_scope_btn.config(text=tr("전체 범위") if self.tag_global else tr("현재 범위"))
        self.reload_tags()

    def clear_tag(self):
        if self.tag or self.tag_none:
            self.tag = None
            self.tag_none = False
            self.tagtree.selection_remove(*self.tagtree.selection())
            self.refresh()

    def on_tag_click(self, e):
        row = self.tagtree.identify_row(e.y)
        if not row or e.state & 0x5:   # Ctrl/Shift+클릭은 여러 개 고르기라서 노트를 거르지 않는다
            return
        tag = self.tag_keys[int(row[2:])]
        if tag is not None and tag in getattr(self, "ftag_map", {}) and tag not in getattr(self, "note_tag_set", ()):
            return self.show_folder_tag_menu(tag, e)   # 폴더에 붙은 태그: 그 폴더들을 고르게 한다(노트 거르기는 하지 않는다)
        if tag is None:
            self.tag_none = not self.tag_none
            self.tag = None
        else:
            self.tag_none = False
            self.tag = None if tag == self.tag else tag   # 선택된 태그를 다시 누르면 해제
        if self.tag is None and not self.tag_none:
            self.tagtree.selection_remove(*self.tagtree.selection())
        self.refresh()

    def show_folder_tag_menu(self, tag, e):
        """폴더 태그를 누르면 그 태그가 붙은 노트북·가져온 폴더를 메뉴로 보여 주고, 고르면 그 폴더로 간다"""
        menu = tk.Menu(self.root, tearoff=0)
        for key in self.ftag_map.get(tag, []):
            menu.add_command(label=self.nb_label(key), command=lambda k=key: self.go_nb(k))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def on_nb_toggle(self, opened):
        """노트북 목록에서 삼각형을 눌러 펼치거나 접은 것을 기억한다(목록을 다시 그려도 그대로 두려고)"""
        if self.quiet:
            return
        iid = self.nbtree.focus()
        if iid and iid.startswith("nb") and iid[2:].isdigit() and int(iid[2:]) < len(self.nb_keys):
            self.nb_open[self.nb_keys[int(iid[2:])]] = opened

    def nb_set_all(self, opened):
        """노트북 목록의 하위가 있는 항목을 모두 펼치거나 모두 접는다"""
        def walk(parent=""):
            for c in self.nbtree.get_children(parent):
                if self.nbtree.get_children(c):
                    self.nbtree.item(c, open=opened)
                    self.nb_open[self.nb_keys[int(c[2:])]] = opened
                walk(c)
        walk()

    def folder_gone(self, key):
        """폴더 태그·메모의 폴더가 디스크에서 없어졌는가(탐색기에서 옮기거나 지운 경우). 저장 폴더·가져온 폴더의 최상위가 안 보이는 때(드라이브 빠짐, 동기화 중 등)는 없어진 것으로 보지 않는다"""
        try:
            if key.startswith("@doc:"):
                fid, rel = self.doc_key_parts(key)
                f = next((f for f in self.docs.folders() if f["id"] == fid), None)
                if not rel or not f or not os.path.isdir(f["path"]):
                    return False
                return not os.path.isdir(os.path.join(f["path"], *rel.split("/")))
            if not key or key.startswith("@") or not os.path.isdir(self.store.root):
                return False
            return not os.path.isdir(os.path.join(self.store.root, *key.split("/")))
        except OSError:
            return False

    def prune_folder_meta(self):
        """없어진 폴더에 붙어 있던 태그·메모 기록을 지운다(탐색기에서 옮기면 옛 경로에 매달려 남던 것)"""
        try:
            keys = set(self.docs.folder_tags()) | set(self.docs.folder_memos())
            gone = [k for k in keys if self.folder_gone(k)]
            if gone:
                self.docs.drop_folder_meta(gone)
        except Exception:  # noqa: BLE001  (정리는 못 해도 화면에는 영향이 없다)
            pass

    def open_folder_in_explorer(self, key):
        """노트북·가져온 폴더의 실제 위치를 탐색기로 연다"""
        path = self.folder_path_of(key)
        if not path or not os.path.isdir(path):
            return messagebox.showinfo(APP, tr("폴더를 찾을 수 없습니다.") + "\n" + (path or ""), parent=self.root)
        try:
            os.startfile(path)
        except OSError as ex:
            messagebox.showerror(APP, str(ex), parent=self.root)

    def on_nb_click(self, e):
        """이미 고른 폴더를 다시 누르면(노트를 열어 둔 상태) 노트를 닫고 폴더 화면으로 돌아온다. 고른 항목이 바뀌면 on_nb_select 가 처리한다"""
        row = self.nbtree.identify_row(e.y)
        if not row or self.nbtree.identify_region(e.x, e.y) == "tree" and self.nbtree.identify_element(e.x, e.y).endswith("indicator"):
            return   # 펼침 삼각형을 누른 것은 건드리지 않는다
        key = self.nb_keys[int(row[2:])]
        if key == self.nb and self.cur and self.folder_tag_ok():
            self.flush()
            self.close_note()

    def on_nb_select(self, e=None):
        if self.quiet:
            return
        sel = self.nbtree.selection()
        if not sel:
            return
        key = self.nb_keys[int(sel[0][2:])]
        if key == self.nb:
            return
        if key in ("@smarts", QUICK):   # 머리글: 고를 수 없다. 원래 선택으로 되돌린다
            self.quiet = True
            self.nbtree.selection_set(f"nb{self.nb_keys.index(self.nb)}")
            self.quiet = False
            return
        if key.startswith("@smart:"):
            return self.open_smart(key)
        self.flush()
        self.nb = key
        self.close_note()
        self.reload_notes()

    def on_nb_menu(self, e):
        row = self.nbtree.identify_row(e.y)
        if not row:
            return
        key = self.nb_keys[int(row[2:])]
        self.nb_menu_target = key
        m = self.nbmenu
        m.delete(0, "end")
        if key in (FAVS, QUICK, CAL, TRASH):
            return
        if key.startswith("@smart"):   # 저장된 검색
            if key == "@smarts":
                m.add_command(label=tr("지금의 검색 저장…"), command=self.save_search)
            else:
                for label, cmd in self.smart_menu(key) or []:
                    m.add_command(label=label, command=cmd)
            return m.tk_popup(e.x_root, e.y_root)
        if key.startswith("@doc"):   # 가져온 폴더: 원본 파일은 건드리지 않는다
            if key.startswith("@doc:"):
                fid, rel = self.doc_key_parts(key)
                m.add_command(label=tr("탐색기에서 폴더 열기"), command=lambda: self.open_folder_in_explorer(key))
                m.add_command(label=tr("다시 읽기"), command=lambda: self.scan_docs(fid))
                if not rel:
                    m.add_command(label=tr("목록에서 빼기 (원본 파일은 그대로)"), command=lambda: self.remove_doc_folder(fid))
            else:
                m.add_command(label=tr("모두 다시 읽기"), command=lambda: self.scan_docs())
            m.add_command(label=tr("가져오기 설정…"), command=lambda: self.show_options("imports"))
            return m.tk_popup(e.x_root, e.y_root)
        if key == ALL:   # '모든 노트'는 노트북이 아니므로 최상위에 새 노트북을 만든다
            m.add_command(label=tr("새 노트북 만들기"), command=self.add_notebook)
        else:            # 저장 폴더(최상위)도 노트북처럼 상위가 될 수 있다
            m.add_command(label=tr("하위 노트북 만들기"), command=lambda: self.add_notebook(parent=key, show_parent=True))
        if key != ALL:
            m.add_command(label=tr("탐색기에서 폴더 열기"), command=lambda: self.open_folder_in_explorer(key))
            m.add_command(label=tr("저장 폴더 전체 삭제(휴지통)") if key == "" else tr("노트북 삭제(휴지통)"), command=self.delete_notebook)
        m.tk_popup(e.x_root, e.y_root)

    def add_subnotebook(self):
        """고른 노트북(저장 폴더 자체 포함) 안에 하위 노트북을 만든다. '모든 노트'를 골랐으면 최상위에 만든다."""
        parent = self.md_nb()
        self.add_notebook(parent=parent, show_parent=not (self.nb == ALL or self.nb.startswith("@")))

    def add_notebook(self, parent="", show_parent=False):
        where = tr('\n상위: {0}').format(self.nb_label(parent)) if (parent or show_parent) else ""
        name = simpledialog.askstring(tr("새 하위 노트북") if (parent or show_parent) else tr("새 노트북"), tr("노트북 이름") + where, parent=self.root)
        if not name or not name.strip():
            return
        try:
            folder = self.store.create_notebook(name, parent)
        except OSError as ex:
            return messagebox.showerror(APP, tr('노트북을 만들지 못했습니다.\n{0}').format(ex))
        self.flush()
        self.close_note()
        self.nb = folder
        self.reload_notes()

    def delete_notebook(self):
        key = self.nb_menu_target
        if key is None:
            sel = self.nbtree.selection()
            key = self.nb_keys[int(sel[0][2:])] if sel else None
        self.nb_menu_target = None
        if key in (None, ALL) or key.startswith("@"):   # 가져온 폴더·저장된 검색은 노트북이 아니라 휴지통으로 보내지 않는다
            return
        if key == "":
            return self.delete_root()
        if not messagebox.askyesno(APP, tr('노트북 "{0}"을(를) 휴지통으로 보낼까요?\n(하위 노트북과 안의 노트도 함께 가며, {1}일 동안 보관합니다)').format(self.nb_label(key), self.store.trash_days), parent=self.root):
            return
        self.flush()
        try:
            self.store.delete_notebook(key)
        except OSError as ex:
            return messagebox.showerror(APP, str(ex))
        if self.nb == key or self.nb.startswith(key + "/"):
            self.nb = ALL
        self.close_note()
        self.reload_notes()

    def delete_root(self):
        """저장 폴더(scrapbook) 자체를 통째로 휴지통으로 보낸다. 빈 폴더는 다시 만들어 앱이 계속 동작하게 한다."""
        root = self.store.root
        books = self.store.notebooks()
        inside = os.path.normcase(os.path.abspath(self.store.media_dir)).startswith(os.path.normcase(os.path.abspath(root)) + os.sep)
        msg = (tr('저장 폴더 "{0}" 전체를 휴지통으로 보낼까요?\n\n{1}\n\n안의 노트 {2}개, 노트북 {3}개').format(self.store.root_name, root, len(self.all_notes), len(books))
               + (tr(", 리소스 폴더(그림)") if inside else "") + tr(", 노트 버전 기록이 모두 함께 갑니다.\n")
               + ("" if inside else tr("(리소스 폴더는 저장 폴더 밖에 있어서 그대로 남습니다.)\n"))
               + tr('\n앱의 휴지통에서 {0}일 동안 보관하며 복원할 수 있습니다.').format(self.store.trash_days))
        if not messagebox.askyesno(APP, msg, icon="warning", parent=self.root):
            return
        self.flush()

        def go():
            try:
                self.store.delete_root()
            except (OSError, ValueError) as ex:
                return messagebox.showerror(APP, str(ex), parent=self.root)
            self.hist, self.hpos = [], -1
            self.nb, self.tag, self.tag_none, self.adv_conditions = ALL, None, False, []
            self.close_note()
            self.reload_notes()
            self.status.config(text=tr("저장 폴더의 내용을 휴지통으로 보냈습니다. (파일 → 휴지통에서 복원)"))
        self.checkpoint(tr("저장 폴더 삭제 전"), go)

    def choose_root(self):
        d = filedialog.askdirectory(parent=self.root, initialdir=self.store.root, title=tr("노트를 저장할 폴더"))
        if not d:
            return False
        self.flush()
        self.store.set_root(d)
        self.nb, self.tag, self.tag_none, self.adv_conditions = ALL, None, False, []
        self.hist, self.hpos = [], -1
        self.close_note()
        self.reload_notes()
        return True
